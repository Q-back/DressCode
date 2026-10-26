import json
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import BrokenBarrierError

import pytest

from dresscode.config import load
from dresscode.diff import resolve_scope
from dresscode.entries import Entry
from dresscode.repo import discover
from dresscode.run import RunState, RunStore


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
    run = RunStore(resolve_scope(load(repository)))
    assert json.loads(run.run_key)[1:3] == [repository.identity, "feature/test"]
    run.record(entry, "yes", "Reused the factory", "fingerprint")
    first_path = run.path

    git(git_repo, "switch", "main")
    other_branch = RunStore(resolve_scope(load(discover(git_repo))))
    assert json.loads(other_branch.run_key)[1:3] == [
        discover(git_repo).identity,
        "main",
    ]
    assert other_branch.path != first_path
    assert other_branch.read()["verdicts"] == {}

    git(git_repo, "switch", "feature/test")
    restored = RunStore(resolve_scope(load(discover(git_repo))))
    assert restored.path == first_path
    assert restored.read()["verdicts"]["factory"]["verdict"] == "yes"
    assert first_path.is_relative_to(xdg_home / "state" / "dresscode" / "runs")


def test_detached_head_uses_short_commit_sha(git_repo: Path) -> None:
    identity = discover(git_repo).identity
    sha = git(git_repo, "rev-parse", "--short", "HEAD")
    git(git_repo, "switch", "--detach", "HEAD")

    assert json.loads(RunStore(resolve_scope(load(discover(git_repo)))).run_key)[
        1:3
    ] == [identity, f"detached-{sha}"]


def test_concurrent_answers_do_not_overwrite_each_other(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = RunStore(resolve_scope(load(discover(git_repo))))
    entries = [Entry(f"question-{index}", "Question?", True) for index in range(8)]
    writes = threading.Barrier(len(entries))
    original_write = RunStore._write

    def synchronized_write(instance: RunStore, state: RunState) -> None:
        try:
            writes.wait(timeout=0.1)
        except BrokenBarrierError:
            pass
        original_write(instance, state)

    monkeypatch.setattr(RunStore, "_write", synchronized_write)
    with ThreadPoolExecutor(max_workers=len(entries)) as workers:
        list(
            workers.map(
                lambda entry: store.record(entry, "yes", "Reviewed", "fingerprint"),
                entries,
            )
        )

    assert set(store.read()["verdicts"]) == {entry.id for entry in entries}


def test_run_state_is_written_outside_the_repository(
    git_repo: Path, xdg_home: Path
) -> None:
    repository = discover(git_repo)
    before = git(git_repo, "status", "--porcelain")
    run = RunStore(resolve_scope(load(repository)))
    run.reset()

    assert run.path.is_relative_to(xdg_home / "state" / "dresscode" / "runs")
    assert git(git_repo, "status", "--porcelain") == before
    assert {path.name for path in git_repo.iterdir()} == {".git", "README.md"}
