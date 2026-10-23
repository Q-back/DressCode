import os
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def xdg_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config = tmp_path / "config"
    state = tmp_path / "state"
    config.mkdir()
    state.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    monkeypatch.setenv("XDG_STATE_HOME", str(state))
    return tmp_path


@pytest.fixture(scope="session")
def git_repo_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build once; tests receive independent copies, including Git metadata."""
    repository = tmp_path_factory.mktemp("git-repo-template")
    (repository / "README.md").write_text("Test repository.\n")
    environment = os.environ | {
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
    }

    for arguments in (
        ("init", "--initial-branch=main"),
        ("config", "user.name", "DressCode tests"),
        ("config", "user.email", "tests@dresscode.invalid"),
        ("config", "commit.gpgsign", "false"),
        ("config", "core.hooksPath", os.devnull),
        ("add", "README.md"),
        ("commit", "--message", "Initial commit"),
        ("switch", "--create", "feature/test"),
    ):
        subprocess.run(
            ["git", *arguments],
            cwd=repository,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
    return repository


@pytest.fixture
def git_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_repo_template: Path
) -> Path:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    return shutil.copytree(git_repo_template, tmp_path / "repo", symlinks=True)
