import subprocess
from pathlib import Path

import pytest

from dresscode.config import Configuration
from dresscode.diff import DiffError, ScopedDiff, collect, resolve_base, resolve_scope
from dresscode.repo import discover


def git(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def commit_all(root: Path, message: str = "Commit review inputs") -> None:
    git(root, "add", "--all")
    git(root, "commit", "--message", message)


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
    with pytest.raises(DiffError, match="merge_base_with"):
        resolve_base(git_repo, configured)


def test_unborn_repository_is_an_environment_error(tmp_path: Path) -> None:
    git(tmp_path, "init", "--initial-branch=main")
    with pytest.raises(DiffError, match="Git"):
        resolve_base(tmp_path)


def scope(root: Path, **settings: object) -> ScopedDiff:
    return collect(Configuration(discover(root), settings, ()))


def test_cumulative_diff_only_reads_committed_paths(git_repo: Path) -> None:
    (git_repo / "README.md").write_text("Committed.\n")
    git(git_repo, "commit", "--all", "--message", "Committed change")
    (git_repo / "staged.py").write_text("staged\n")
    git(git_repo, "add", "staged.py")
    (git_repo / "README.md").write_text("Committed.\nUnstaged.\n")
    (git_repo / "new.py").write_text("new\nwithout final newline")
    (git_repo / ".git" / "info" / "exclude").write_text("ignored.py\n")
    (git_repo / "ignored.py").write_text("ignored\n")

    result = scope(git_repo)

    assert result.scope.base_commit == git(git_repo, "rev-parse", "main")
    assert [(file.path, file.added, file.removed) for file in result.files] == [
        ("README.md", 1, 1),
    ]
    assert (result.added, result.removed) == (1, 1)
    assert result.scope.head_commit == git(git_repo, "rev-parse", "HEAD")


def test_collect_uses_the_resolved_head_even_after_it_moves(git_repo: Path) -> None:
    config = Configuration(discover(git_repo), {}, ())
    resolved = resolve_scope(config)
    (git_repo / "README.md").write_text("Another commit.\n")
    git(git_repo, "commit", "--all", "--message", "Advance HEAD")

    assert collect(config, resolved).files == ()
    assert collect(config).scope.head_commit != resolved.head_commit


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
    assert result.scope.base_commit == initial
    assert [file.path for file in result.files] == ["feature.py"]


def test_explicit_baseline_includes_removals_from_diverged_history(
    git_repo: Path,
) -> None:
    git(git_repo, "switch", "main")
    (git_repo / "base-only.py").write_text("not in feature\n")
    git(git_repo, "add", "base-only.py")
    git(git_repo, "commit", "-m", "Advance main")
    git(git_repo, "switch", "feature/test")
    config = Configuration(discover(git_repo), {}, ())

    resolved = resolve_scope(config, "main")
    assert resolved.base_commit == git(git_repo, "rev-parse", "main")
    assert resolved.head_commit == git(git_repo, "rev-parse", "HEAD")
    assert [
        (file.path, file.added, file.removed)
        for file in collect(config, resolved).files
    ] == [("base-only.py", 0, 1)]


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
def test_defaults_exclude_committed_paths(git_repo: Path, path: str) -> None:
    excluded = git_repo / path
    excluded.parent.mkdir(parents=True, exist_ok=True)
    excluded.write_text("excluded\n")
    git(git_repo, "add", ".")
    git(git_repo, "commit", "-m", "Add excluded path")
    assert scope(git_repo).files == ()


def test_explicit_pathspecs_replace_defaults_for_listing_and_counting(
    git_repo: Path,
) -> None:
    for path in ("uv.lock", "skip.py", "keep.py", "literal[1].py"):
        (git_repo / path).write_text("one\n")
    git(git_repo, "add", ".")
    git(git_repo, "commit", "-m", "Add scoped files")
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


def test_binary_and_unusual_committed_paths(git_repo: Path) -> None:
    path = "tab\tand\nnewline.bin"
    (git_repo / path).write_bytes(b"\0binary")
    git(git_repo, "add", path)
    git(git_repo, "commit", "-m", "Add binary")

    result = scope(git_repo)
    assert [(file.path, file.added, file.removed) for file in result.files] == [
        (path, None, None)
    ]
    assert (result.added, result.removed) == (0, 0)


def test_committed_rename_and_mode_change(git_repo: Path) -> None:
    (git_repo / "script.sh").write_text("echo test\n")
    git(git_repo, "add", "script.sh")
    git(git_repo, "commit", "-m", "Add script")
    git(git_repo, "branch", "--force", "main", "HEAD")
    git(git_repo, "mv", "README.md", "renamed.md")
    git(git_repo, "update-index", "--chmod=+x", "script.sh")
    git(git_repo, "commit", "-m", "Rename and make executable")

    assert [
        (file.path, file.added, file.removed) for file in scope(git_repo).files
    ] == [
        ("README.md", 0, 1),
        ("renamed.md", 1, 0),
        ("script.sh", 0, 0),
    ]


def test_attributes_apply_to_committed_counts(git_repo: Path) -> None:
    (git_repo / ".gitattributes").write_text("*.dat binary\n")
    (git_repo / "new.dat").write_text("text marked binary\n")
    git(git_repo, "add", ".")
    git(git_repo, "commit", "-m", "Add attributed file")
    result = scope(git_repo)
    assert [(file.path, file.added, file.removed) for file in result.files] == [
        (".gitattributes", 1, 0),
        ("new.dat", None, None),
    ]
    (git_repo / ".gitattributes").write_text("*.dat diff\n")
    assert scope(git_repo) == result


def test_committed_symlink_diff_counts_the_link_not_its_target(
    git_repo: Path, tmp_path: Path
) -> None:
    target = tmp_path / "outside.txt"
    target.write_text("outside\n")
    (git_repo / "link").symlink_to(target)
    git(git_repo, "add", "link")
    git(git_repo, "commit", "-m", "Add symlink")

    result = scope(git_repo)
    assert [(file.path, file.added, file.removed) for file in result.files] == [
        ("link", 1, 0),
    ]
    target.write_text("changed outside\nwith more lines\n")
    assert scope(git_repo) == result
