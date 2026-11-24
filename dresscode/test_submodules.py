import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dresscode.cli import app
from dresscode.test_diff import git, scope


@pytest.mark.parametrize(
    "change", ["unstaged", "staged", "untracked", "excluded", "pointer"]
)
def test_dirty_submodule_is_rejected_even_when_git_config_hides_it(
    submodule_repo: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    root, submodule = submodule_repo
    monkeypatch.chdir(root)
    git(root, "config", "diff.ignoreSubmodules", "all")
    git(root, "config", "submodule.lib.ignore", "all")
    git(submodule, "config", "status.showUntrackedFiles", "no")
    if change == "excluded":
        (root / ".dresscode.toml").write_text('[diff]\nexclude = ["lib"]\n')
        git(root, "add", ".dresscode.toml")
        git(root, "commit", "-m", "Exclude lib from review scope")
    path = submodule / ("new.txt" if change == "untracked" else "file.txt")
    path.write_text("new\n")
    if change == "staged":
        git(submodule, "add", "file.txt")
    if change == "pointer":
        git(submodule, "commit", "--all", "-m", "Move submodule pointer")

    result = CliRunner().invoke(app, ["check", "--json"])
    assert result.exit_code == 2, result.output
    assert "Working tree is dirty: 'lib'" in json.loads(result.stdout)["error"]


def test_ignored_submodule_file_does_not_block_review(
    submodule_repo: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, submodule = submodule_repo
    monkeypatch.chdir(root)
    (submodule / "ignored.cache").write_text("ignored\n")
    result = CliRunner().invoke(app, ["check", "--json"])
    assert result.exit_code == 0, result.output


def test_committed_submodule_diff_covers_only_parent_pointer(
    submodule_repo: tuple[Path, Path],
) -> None:
    root, submodule = submodule_repo
    initial = scope(root)
    (submodule / "file.txt").write_text("first\n")
    git(submodule, "commit", "--all", "--message", "First change")
    assert scope(root) == initial
    git(root, "add", "lib")
    assert scope(root) == initial
    git(root, "commit", "--message", "Update pointer")

    changed = scope(root)
    assert [(file.path, file.added, file.removed) for file in changed.files] == [
        ("lib", 1, 1)
    ]
    assert changed.scope.head_commit != initial.scope.head_commit
    for display in ("short", "log", "diff"):
        git(root, "config", "diff.submodule", display)
        assert scope(root) == changed
    (submodule / "file.txt").write_text("other\n")
    git(submodule, "commit", "--all", "--message", "Other change")
    assert scope(root) == changed


def test_uninitialized_submodule_still_reports_committed_pointer(
    submodule_repo: tuple[Path, Path],
) -> None:
    root, submodule = submodule_repo
    (submodule / "file.txt").write_text("committed\n")
    git(submodule, "commit", "--all", "--message", "Submodule update")
    git(root, "add", "lib")
    git(root, "commit", "--message", "Update parent pointer")
    before = scope(root)
    git(root, "submodule", "deinit", "--", "lib")
    assert [file.path for file in before.files] == ["lib"]
    assert scope(root) == before


@pytest.mark.parametrize("dirty", ["tracked", "untracked-hidden", "deep-hidden"])
def test_dirty_nested_submodule_is_rejected(
    submodule_repo: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    dirty: str,
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
    nested = submodule / "nested"
    if dirty == "deep-hidden":
        git(
            nested,
            "-c",
            "protocol.file.allow=always",
            "submodule",
            "add",
            str(tmp_path / "submodule-source"),
            "deep",
        )
        git(
            nested,
            "-c",
            "user.name=Tests",
            "-c",
            "user.email=tests@dresscode.invalid",
            "commit",
            "--all",
            "--message",
            "Deep baseline",
        )
        git(submodule, "commit", "--all", "--message", "Nested pointer update")
        git(nested, "config", "submodule.deep.ignore", "all")
        (nested / "deep/file.txt").write_text("dirty deep content\n")
    elif dirty == "untracked-hidden":
        git(nested, "config", "status.showUntrackedFiles", "no")
        (nested / "untracked.txt").write_text("untracked\n")
    else:
        (nested / "file.txt").write_text("dirty nested content\n")
    if dirty.endswith("hidden"):
        assert (
            git(
                submodule,
                "--no-optional-locks",
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
                "--ignore-submodules=none",
            )
            == ""
        )
    monkeypatch.chdir(root)
    result = CliRunner().invoke(app, ["diff", "--json"])
    assert result.exit_code == 2, result.output
    assert "Working tree is dirty: 'lib'" in json.loads(result.stdout)["error"]
    report = CliRunner().invoke(app, ["report", "--json"])
    assert report.exit_code == 0, report.output
    assert json.loads(report.stdout)["working_tree_dirty"] is True


def test_submodule_replaced_by_symlink_does_not_inspect_its_target(
    submodule_repo: tuple[Path, Path], tmp_path: Path
) -> None:
    root, submodule = submodule_repo
    git(root, "submodule", "deinit", "--", "lib")
    submodule.rmdir()
    target = tmp_path / "submodule-source"
    (target / "file.txt").write_text("dirty outside scope\n")
    submodule.symlink_to(target, target_is_directory=True)
    before = scope(root)
    (target / "file.txt").write_text("different outside scope\n")
    assert scope(root) == before


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
    baseline = git(root, "rev-parse", "HEAD")
    git(root, "branch", "--force", "main", "HEAD~1")
    diff = ["diff", "--base", baseline]
    before = git(root, "status", "--porcelain=v1", "--ignore-submodules=none")
    index = submodule / git(submodule, "rev-parse", "--git-path", "index")
    index_before = index.read_bytes()
    result = CliRunner().invoke(app, [*diff, *options])
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
    assert "Working tree is dirty: 'lib'" in message
    assert "commit" in message.lower()
    assert "diff.exclude" in message
    assert git(root, "status", "--porcelain=v1", "--ignore-submodules=none") == before
    assert (submodule / "file.txt").read_text() == "dirty\n"
    assert index.read_bytes() == index_before
    assert list((xdg_home / "state").iterdir()) == []
    git(submodule, "commit", "--all", "--message", "Commit reviewed content")
    git(root, "add", "lib")
    staged = CliRunner().invoke(app, [*diff, "--json"])
    assert staged.exit_code == 2, staged.output
    git(root, "commit", "-m", "Update parent pointer")
    clean = CliRunner().invoke(app, [*diff, "--json"])
    assert clean.exit_code == 0, clean.output
    response = json.loads(clean.stdout)
    assert response["base_commit"] == baseline
    assert response["head_commit"] == git(root, "rev-parse", "HEAD")
    assert response["files"] == [{"path": "lib", "added": 1, "removed": 1}]
