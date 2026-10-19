import os
import subprocess
from pathlib import Path


def test_xdg_home_is_isolated(xdg_home: Path, tmp_path: Path) -> None:
    assert xdg_home == tmp_path
    assert Path(os.environ["XDG_CONFIG_HOME"]) == xdg_home / "config"
    assert Path(os.environ["XDG_STATE_HOME"]) == xdg_home / "state"
    assert (xdg_home / "config").is_dir()
    assert (xdg_home / "state").is_dir()


def test_git_repo_has_base_and_feature_branches(git_repo: Path) -> None:
    branches = subprocess.run(
        ["git", "branch", "--format=%(refname:short)"],
        cwd=git_repo,
        check=True,
        capture_output=True,
        text=True,
    )
    head = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=git_repo,
        check=True,
        capture_output=True,
        text=True,
    )
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=git_repo,
        check=True,
        capture_output=True,
        text=True,
    )
    base = subprocess.run(
        ["git", "show", "main:README.md"],
        cwd=git_repo,
        check=True,
        capture_output=True,
        text=True,
    )

    assert set(branches.stdout.splitlines()) == {"main", "feature/test"}
    assert head.stdout.strip() == "feature/test"
    assert status.stdout == ""
    assert base.stdout == "Test repository.\n"
