import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dresscode.cli import app
from dresscode.diff import DiffError
from dresscode.test_diff import git, scope


@pytest.fixture
def submodule_repo(git_repo: Path, tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "submodule-source"
    source.mkdir()
    git(source, "init", "--initial-branch=main")
    (source / "file.txt").write_text("old\n")
    (source / ".gitignore").write_text("*.cache\n")
    git(source, "add", ".")
    git(
        source,
        "-c",
        "user.name=Tests",
        "-c",
        "user.email=tests@dresscode.invalid",
        "commit",
        "-m",
        "Source baseline",
    )
    git(
        git_repo,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        str(source),
        "lib",
    )
    submodule = git_repo / "lib"
    git(submodule, "config", "user.name", "DressCode tests")
    git(submodule, "config", "user.email", "tests@dresscode.invalid")
    git(git_repo, "commit", "--all", "--message", "Submodule baseline")
    git(git_repo, "branch", "--force", "main", "HEAD")
    return git_repo, submodule


@pytest.mark.parametrize("change", ["unstaged", "staged", "untracked"])
def test_dirty_submodule_is_rejected_even_when_git_config_hides_it(
    submodule_repo: tuple[Path, Path], change: str
) -> None:
    root, submodule = submodule_repo
    git(root, "config", "diff.ignoreSubmodules", "all")
    git(root, "config", "submodule.lib.ignore", "all")
    git(submodule, "config", "status.showUntrackedFiles", "no")
    path = submodule / ("new.txt" if change == "untracked" else "file.txt")
    path.write_text("new\n")
    if change == "staged":
        git(submodule, "add", "file.txt")
    with pytest.raises(DiffError, match="dirty submodule 'lib'"):
        scope(root)


def test_excluded_dirty_submodule_does_not_affect_scope(
    submodule_repo: tuple[Path, Path],
) -> None:
    root, submodule = submodule_repo
    before = scope(root, diff={"exclude": ["lib"]})
    (submodule / "file.txt").write_text("dirty\n")
    (submodule / "untracked.txt").write_text("untracked\n")
    assert scope(root, diff={"exclude": ["lib"]}) == before


def test_ignored_submodule_file_does_not_block_diff(
    submodule_repo: tuple[Path, Path],
) -> None:
    root, submodule = submodule_repo
    before = scope(root)
    (submodule / "ignored.cache").write_text("ignored\n")
    assert scope(root) == before


def test_clean_submodule_covers_only_commit_pointer_and_is_staging_invariant(
    submodule_repo: tuple[Path, Path],
) -> None:
    root, submodule = submodule_repo
    before = scope(root)
    (submodule / "file.txt").write_text("first\n")
    git(submodule, "commit", "--all", "--message", "First change")
    changed = scope(root)
    assert [(file.path, file.added, file.removed) for file in changed.files] == [
        ("lib", 1, 1)
    ]
    assert changed.fingerprint != before.fingerprint
    for display in ("short", "log", "diff"):
        git(root, "config", "diff.submodule", display)
        assert scope(root) == changed
    git(root, "add", "lib")
    assert scope(root) == changed
    git(root, "commit", "--message", "Update pointer")
    assert scope(root) == changed
    (submodule / "file.txt").write_text("other\n")
    git(submodule, "commit", "--all", "--message", "Other change")
    assert scope(root).fingerprint != changed.fingerprint


def test_uninitialized_clean_submodule_does_not_inspect_parent_status(
    submodule_repo: tuple[Path, Path],
) -> None:
    root, submodule = submodule_repo
    (submodule / "file.txt").write_text("committed\n")
    git(submodule, "commit", "--all", "--message", "Submodule update")
    git(root, "add", "lib")
    git(root, "commit", "--message", "Update parent pointer")
    before = scope(root)
    git(root, "submodule", "deinit", "--", "lib")
    assert scope(root) == before
    (root / "README.md").write_text("parent edit\n")
    assert [file.path for file in scope(root).files] == ["README.md", "lib"]


def test_dirty_nested_submodule_is_rejected(
    submodule_repo: tuple[Path, Path], tmp_path: Path
) -> None:
    root, submodule = submodule_repo
    git(
        submodule,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        str(tmp_path / "submodule-source"),
        "nested",
    )
    git(submodule, "commit", "--all", "--message", "Nested submodule")
    (submodule / "nested/file.txt").write_text("dirty nested content\n")
    with pytest.raises(DiffError, match="dirty submodule 'lib'"):
        scope(root)


@pytest.mark.parametrize("options", [[], ["--numstat"], ["--json"]])
def test_cli_dirty_submodule_error_is_actionable_and_read_only(
    submodule_repo: tuple[Path, Path],
    xdg_home: Path,
    monkeypatch: pytest.MonkeyPatch,
    options: list[str],
) -> None:
    root, submodule = submodule_repo
    (submodule / "file.txt").write_text("dirty\n")
    monkeypatch.chdir(root)
    before = git(root, "status", "--porcelain=v1", "--ignore-submodules=none")
    index = submodule / git(submodule, "rev-parse", "--git-path", "index")
    index_before = index.read_bytes()
    result = CliRunner().invoke(app, ["diff", *options])
    assert result.exit_code == 2, result.output
    if "--json" in options:
        response = json.loads(result.stdout)
        assert set(response) == {"status", "error"}
        assert response["status"] == "error"
        message = response["error"]
        assert result.stderr == ""
    else:
        message = result.stderr
        assert result.stdout == ""
    assert "dirty submodule 'lib'" in message
    assert "commit" in message.lower()
    assert "diff.exclude" in message
    assert git(root, "status", "--porcelain=v1", "--ignore-submodules=none") == before
    assert (submodule / "file.txt").read_text() == "dirty\n"
    assert index.read_bytes() == index_before
    assert list((xdg_home / "state").iterdir()) == []
    git(submodule, "commit", "--all", "--message", "Commit reviewed content")
    git(root, "add", "lib")
    clean = CliRunner().invoke(app, ["diff", "--json"])
    assert clean.exit_code == 0, clean.output
    assert json.loads(clean.stdout)["files"] == [
        {"path": "lib", "added": 1, "removed": 1}
    ]
