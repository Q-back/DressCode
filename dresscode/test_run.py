import subprocess
from pathlib import Path

from dresscode.config import load
from dresscode.repo import discover
from dresscode.run import RunStore


def git(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def test_runs_are_isolated_by_branch_and_restored_on_return(
    git_repo: Path, xdg_home: Path
) -> None:
    (git_repo / ".dresscode.toml").write_text(
        '[[entries]]\nid = "factory"\nquestion = "Reuse?"\nexpects = true\n'
    )
    repository = discover(git_repo)
    entry = load(repository).entries[0]
    run = RunStore(repository)
    assert run.run_key == f"{repository.identity}:feature/test"
    run.record(entry, "yes", "Reused the factory", "fingerprint")
    first_path = run.path

    git(git_repo, "switch", "main")
    other_branch = RunStore(discover(git_repo))
    assert other_branch.run_key == f"{discover(git_repo).identity}:main"
    assert other_branch.path != first_path
    assert other_branch.read()["verdicts"] == {}

    git(git_repo, "switch", "feature/test")
    restored = RunStore(discover(git_repo))
    assert restored.path == first_path
    assert restored.read()["verdicts"]["factory"]["verdict"] == "yes"
    assert first_path.is_relative_to(xdg_home / "state" / "dresscode" / "runs")


def test_detached_head_uses_short_commit_sha(git_repo: Path) -> None:
    identity = discover(git_repo).identity
    sha = git(git_repo, "rev-parse", "--short", "HEAD")
    git(git_repo, "switch", "--detach", "HEAD")

    assert RunStore(discover(git_repo)).run_key == f"{identity}:detached-{sha}"


def test_run_state_is_written_outside_the_repository(
    git_repo: Path, xdg_home: Path
) -> None:
    repository = discover(git_repo)
    before = git(git_repo, "status", "--porcelain")
    run = RunStore(repository)
    run.reset()

    assert run.path.is_relative_to(xdg_home / "state" / "dresscode" / "runs")
    assert git(git_repo, "status", "--porcelain") == before
    assert {path.name for path in git_repo.iterdir()} == {".git", "README.md"}
