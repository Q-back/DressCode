import subprocess
from pathlib import Path

import pytest

from dresscode.repo import RepositoryError, discover, normalize_origin


@pytest.mark.parametrize(
    "origin",
    [
        "git@example.com:team/repo.git",
        "https://example.com/team/repo",
        "https://user:secret@example.com/team/repo.git/",
        "ssh://git@example.com/team/repo.git",
    ],
)
def test_origin_shapes_resolve_equally(origin: str) -> None:
    assert normalize_origin(origin) == "example.com/team/repo"


def test_discover_from_subdirectory_uses_origin(git_repo: Path) -> None:
    subprocess.run(
        ["git", "remote", "add", "origin", "git@example.com:team/repo.git"],
        cwd=git_repo,
        check=True,
    )
    nested = git_repo / "nested"
    nested.mkdir()

    repository = discover(nested)

    assert repository.root == git_repo
    assert repository.identity == "example.com/team/repo"


@pytest.mark.parametrize("origin", [None, "https://example.com/team/repo.git"])
def test_linked_worktree_shares_identity(
    git_repo: Path, tmp_path: Path, origin: str | None
) -> None:
    if origin is not None:
        subprocess.run(
            ["git", "remote", "add", "origin", origin], cwd=git_repo, check=True
        )
    linked = tmp_path / "linked"
    subprocess.run(
        ["git", "worktree", "add", str(linked), "-b", "linked"],
        cwd=git_repo,
        check=True,
        capture_output=True,
    )

    assert discover(linked).root == linked
    assert discover(linked).identity == discover(git_repo).identity


def test_no_origin_uses_main_worktree_realpath(git_repo: Path, tmp_path: Path) -> None:
    alias = tmp_path / "alias"
    alias.symlink_to(git_repo, target_is_directory=True)

    assert discover(alias).identity == str(git_repo.resolve())


def test_outside_worktree_is_an_environment_error(tmp_path: Path) -> None:
    with pytest.raises(RepositoryError, match="Git work tree"):
        discover(tmp_path)


def test_malformed_origin_is_an_environment_error(git_repo: Path) -> None:
    subprocess.run(
        ["git", "config", "remote.origin.url", "https://[invalid/repo"],
        cwd=git_repo,
        check=True,
    )
    with pytest.raises(RepositoryError, match="Git work tree"):
        discover(git_repo)


def test_bare_repository_is_not_a_worktree(tmp_path: Path) -> None:
    bare = tmp_path / "bare.git"
    subprocess.run(
        ["git", "init", "--bare", str(bare)], check=True, capture_output=True
    )

    with pytest.raises(RepositoryError, match="Git work tree"):
        discover(bare)
