import subprocess
from pathlib import Path

import pytest

from dresscode.config import Configuration
from dresscode.diff import DiffError, ScopedDiff, collect, resolve_base
from dresscode.repo import discover


def git(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def test_base_resolution_fallbacks(git_repo: Path) -> None:
    initial = git(git_repo, "rev-parse", "HEAD")
    assert resolve_base(git_repo) == ("main", initial)
    git(git_repo, "branch", "--move", "main", "master")
    assert resolve_base(git_repo) == ("master", initial)
    git(git_repo, "branch", "--delete", "master")
    assert resolve_base(git_repo) == (initial, initial)


def test_configured_base_precedes_remote_and_local_defaults(git_repo: Path) -> None:
    git(git_repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(
        git_repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main"
    )
    assert resolve_base(git_repo)[0] == "origin/HEAD"
    git(git_repo, "branch", "develop")
    assert resolve_base(git_repo, "develop")[0] == "develop"


@pytest.mark.parametrize("configured", ["missing", "--help", "", False, []])
def test_invalid_explicit_base_is_an_error(git_repo: Path, configured: object) -> None:
    with pytest.raises(DiffError, match="base_ref"):
        resolve_base(git_repo, configured)


def test_unborn_repository_is_an_environment_error(tmp_path: Path) -> None:
    git(tmp_path, "init", "--initial-branch=main")
    with pytest.raises(DiffError, match="Git"):
        resolve_base(tmp_path)


def scope(root: Path, **settings: object) -> ScopedDiff:
    return collect(Configuration(discover(root), settings, ()))


def test_cumulative_working_tree_and_untracked_scope(git_repo: Path) -> None:
    (git_repo / "README.md").write_text("Committed.\n")
    git(git_repo, "commit", "--all", "--message", "Committed change")
    (git_repo / "staged.py").write_text("staged\n")
    git(git_repo, "add", "staged.py")
    (git_repo / "README.md").write_text("Committed.\nUnstaged.\n")
    (git_repo / "new.py").write_text("new\nwithout final newline")
    (git_repo / ".git" / "info" / "exclude").write_text("ignored.py\n")
    (git_repo / "ignored.py").write_text("ignored\n")

    result = scope(git_repo)

    assert result.base_ref == "main"
    assert [(file.path, file.added, file.removed) for file in result.files] == [
        ("README.md", 2, 1),
        ("new.py", 2, 0),
        ("staged.py", 1, 0),
    ]
    assert (result.added, result.removed) == (5, 1)


def test_base_moving_on_does_not_enter_the_diff(git_repo: Path) -> None:
    initial = git(git_repo, "rev-parse", "HEAD")
    git(git_repo, "switch", "main")
    (git_repo / "base-only.py").write_text("not reviewed\n")
    git(git_repo, "add", ".")
    git(git_repo, "commit", "--message", "Advance base")
    git(git_repo, "switch", "feature/test")
    (git_repo / "feature.py").write_text("reviewed\n")
    git(git_repo, "add", ".")
    git(git_repo, "commit", "--message", "Feature change")
    result = scope(git_repo)
    assert result.merge_base == initial
    assert [file.path for file in result.files] == ["feature.py"]


@pytest.mark.parametrize(
    "path",
    [
        "uv.lock",
        "web/package-lock.json",
        "npm-shrinkwrap.json",
        "go.sum",
        "dotnet/packages.lock.json",
        "vendor/lib.py",
        "nested/vendor/lib.py",
        "tests/snapshots/result.txt",
        "tests/__snapshots__/result.snap",
        "tests/cassettes/request.yaml",
        "tests/fixtures/input.txt",
    ],
)
def test_defaults_exclude_tracked_and_untracked_paths(
    git_repo: Path, path: str
) -> None:
    excluded = git_repo / path
    excluded.parent.mkdir(parents=True, exist_ok=True)
    excluded.write_text("excluded\n")
    assert scope(git_repo).files == ()
    git(git_repo, "add", ".")
    assert scope(git_repo).files == ()


def test_explicit_pathspecs_replace_defaults_for_listing_and_counting(
    git_repo: Path,
) -> None:
    for path in ("uv.lock", "skip.py", "keep.py", "literal[1].py"):
        (git_repo / path).write_text("one\n")
    git(git_repo, "add", "skip.py")
    result = scope(git_repo, diff={"exclude": ["skip.py", ":(literal)literal[1].py"]})
    assert [file.path for file in result.files] == ["keep.py", "uv.lock"]
    assert result.added == 2
    assert len(scope(git_repo, diff={"exclude": []}).files) == 4


@pytest.mark.parametrize(
    "settings",
    [
        {"diff": False},
        {"diff": {"exclude": "*.py"}},
        {"diff": {"exclude": [False]}},
        {"diff": {"exclude": [""]}},
    ],
)
def test_invalid_diff_settings_are_errors(
    git_repo: Path, settings: dict[str, object]
) -> None:
    with pytest.raises(DiffError, match="diff"):
        scope(git_repo, **settings)


def test_fingerprint_tracks_content_not_index_or_commit_boundaries(
    git_repo: Path,
) -> None:
    (git_repo / "new.py").write_text("first\n")
    original = scope(git_repo).fingerprint
    assert original == scope(git_repo).fingerprint
    (git_repo / "uv.lock").write_text("excluded\n")
    assert original == scope(git_repo).fingerprint
    git(git_repo, "add", ".")
    assert original == scope(git_repo).fingerprint
    git(git_repo, "commit", "--message", "Same reviewed content")
    assert original == scope(git_repo).fingerprint
    (git_repo / "new.py").write_text("other\n")
    assert original != scope(git_repo).fingerprint


@pytest.mark.parametrize(
    "content, executable",
    [
        (b"Test repository.\n", False),
        (b"edited\n", False),
        (b"\0binary", False),
        (b"Test repository.\n", True),
    ],
    ids=["unchanged", "edited", "binary", "mode-only"],
)
def test_index_removal_and_readdition_preserve_the_reviewed_result(
    git_repo: Path, content: bytes, executable: bool
) -> None:
    path = git_repo / "README.md"
    path.write_bytes(content)
    if executable:
        path.chmod(0o755)
    before = scope(git_repo)
    git(git_repo, "rm", "--cached", "README.md")
    assert scope(git_repo) == before
    git(git_repo, "add", "README.md")
    assert scope(git_repo) == before


def test_index_removal_preserves_symlink_baseline(git_repo: Path) -> None:
    path = git_repo / "link"
    path.symlink_to("old-target")
    git(git_repo, "add", "link")
    git(git_repo, "commit", "--message", "Link baseline")
    path.unlink()
    path.symlink_to("new-target")
    before = scope(git_repo, base_ref="HEAD")
    git(git_repo, "rm", "--cached", "link")
    assert scope(git_repo, base_ref="HEAD") == before
    git(git_repo, "add", "link")
    assert scope(git_repo, base_ref="HEAD") == before


@pytest.mark.parametrize("edit_content", [False, True], ids=["ignored-chmod", "edited"])
def test_index_removal_preserves_ignored_executable_baseline(
    git_repo: Path, edit_content: bool
) -> None:
    path = git_repo / "script.sh"
    path.write_text("old\n")
    path.chmod(0o755)
    git(git_repo, "add", "script.sh")
    git(git_repo, "commit", "--message", "Executable baseline")
    git(git_repo, "config", "core.filemode", "false")
    if edit_content:
        path.write_text("new\n")
    else:
        path.chmod(0o644)
    before = scope(git_repo, base_ref="HEAD")
    git(git_repo, "rm", "--cached", "script.sh")
    assert scope(git_repo, base_ref="HEAD") == before
    git(git_repo, "add", "script.sh")
    assert git(git_repo, "ls-files", "--stage", "script.sh").startswith("100644 ")
    assert scope(git_repo, base_ref="HEAD").fingerprint != before.fingerprint


def test_binary_and_unusual_paths_survive_staging(git_repo: Path) -> None:
    path = "tab\tand\nnewline.bin"
    (git_repo / path).write_bytes(b"\0binary")
    result = scope(git_repo)
    assert [(file.path, file.added, file.removed) for file in result.files] == [
        (path, None, None)
    ]
    assert (result.added, result.removed) == (0, 0)
    git(git_repo, "add", ".")
    assert result.fingerprint == scope(git_repo).fingerprint
    (git_repo / path).write_bytes(b"\0edited")
    assert result.fingerprint != scope(git_repo).fingerprint


def test_deletion_rename_and_filemode_changes(git_repo: Path) -> None:
    git(git_repo, "mv", "README.md", "renamed.md")
    result = scope(git_repo)
    assert [(file.path, file.added, file.removed) for file in result.files] == [
        ("README.md", 0, 1),
        ("renamed.md", 1, 0),
    ]
    (git_repo / "renamed.md").chmod(0o755)
    assert result.fingerprint != scope(git_repo).fingerprint


@pytest.mark.parametrize("content", [b"", b"text\r\n", b"\x00binary"])
def test_new_content_has_stable_counts_and_fingerprint_when_staged(
    git_repo: Path, content: bytes
) -> None:
    (git_repo / "new.txt").write_bytes(content)
    (git_repo / "new.txt").chmod(0o755)
    git(git_repo, "config", "core.filemode", "false")
    before = scope(git_repo)
    git(git_repo, "add", ".")
    assert scope(git_repo) == before


def test_attributes_apply_to_untracked_and_tracked_counts(git_repo: Path) -> None:
    (git_repo / ".git/info/attributes").write_text("*.dat binary\n")
    (git_repo / "new.dat").write_text("text marked binary\n")
    before = scope(git_repo)
    assert before.files[0].added is None
    git(git_repo, "add", ".")
    assert scope(git_repo) == before


def test_symlinks_hash_the_link_not_its_target(git_repo: Path, tmp_path: Path) -> None:
    target = tmp_path / "outside.txt"
    target.write_text("outside\n")
    (git_repo / "link").symlink_to(target)
    original = scope(git_repo).fingerprint
    target.write_text("changed outside\n")
    assert original == scope(git_repo).fingerprint
    git(git_repo, "add", ".")
    assert original == scope(git_repo).fingerprint
