import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


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


def test_git_repo_mutations_do_not_change_template(
    git_repo: Path, git_repo_template: Path
) -> None:
    baseline = {
        path.relative_to(git_repo_template): path.read_bytes()
        for path in git_repo_template.rglob("*")
        if path.is_file()
    }
    for relative in baseline:
        assert (git_repo / relative).stat().st_ino != (
            git_repo_template / relative
        ).stat().st_ino

    (git_repo / "README.md").write_text("Changed in one test.\n")
    for arguments in (
        ("config", "user.name", "Changed author"),
        ("switch", "--create", "isolated"),
        ("add", "README.md"),
        ("commit", "--message", "Isolated change"),
    ):
        subprocess.run(
            ["git", *arguments],
            cwd=git_repo,
            check=True,
            capture_output=True,
            text=True,
        )

    assert {
        path.relative_to(git_repo_template): path.read_bytes()
        for path in git_repo_template.rglob("*")
        if path.is_file()
    } == baseline


@pytest.mark.parametrize(
    ("filename", "content"),
    [
        ("ignore", "README.md\n"),
        ("attributes", "README.md working-tree-encoding=UTF-16\n"),
    ],
)
def test_git_repo_template_ignores_host_xdg_config(
    tmp_path: Path, filename: str, content: str
) -> None:
    host_config = tmp_path / "host-config"
    (host_config / "git").mkdir(parents=True)
    (host_config / "git" / filename).write_text(content)
    suite = tmp_path / "suite"
    suite.mkdir()
    shutil.copyfile(Path(__file__).with_name("conftest.py"), suite / "conftest.py")
    (suite / "test_template.py").write_text(
        "def test_repository(git_repo):\n"
        "    assert (git_repo / 'README.md').read_text() == 'Test repository.\\n'\n"
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--tb=short",
            "--basetemp",
            str(tmp_path / "pytest"),
            "--confcutdir",
            str(suite),
            str(suite),
        ],
        cwd=suite,
        check=False,
        env=os.environ | {"XDG_CONFIG_HOME": str(host_config)},
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stdout + result.stderr
