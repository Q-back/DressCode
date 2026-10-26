import os
import shutil
import subprocess
from pathlib import Path

import pytest

from dresscode.test_diff import git


@pytest.fixture(autouse=True)
def xdg_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config = tmp_path / "config"
    state = tmp_path / "state"
    config.mkdir()
    state.mkdir()
    monkeypatch.delenv("DRESSCODE_BASE_COMMIT", raising=False)
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
        "XDG_CONFIG_HOME": str(tmp_path_factory.mktemp("git-template-config")),
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


@pytest.fixture
def workflow_repo(git_repo: Path) -> Path:
    (git_repo / ".dresscode.toml").write_text(
        '[[entries]]\nid = "size"\nquestion = "Is this a small change?"\n'
        'expects = true\nreveal = "Keep reviews manageable."\n'
        'context = "dresscode diff --numstat"\n'
        '[[entries]]\nid = "side-effects"\nquestion = "Were side effects added?"\n'
        'expects = false\nreveal = "Keep transformations pure."\n'
        '[[entries]]\nid = "python"\nquestion = "Are Python types checked?"\n'
        'expects = true\nreveal = "Check Python types when applicable."\n'
    )
    git(git_repo, "add", ".dresscode.toml")
    git(git_repo, "commit", "-m", "Configure review questions")
    git(git_repo, "branch", "--force", "main", "HEAD")
    git(git_repo, "config", "--unset", "core.hooksPath")
    return git_repo


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
