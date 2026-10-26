import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from dresscode.cli import app
from dresscode.config import load
from dresscode.diff import collect, resolve_scope
from dresscode.entries import Entry
from dresscode.repo import discover
from dresscode.run import RunStore
from dresscode.store import Counters, EntryStore, StoreError

runner = CliRunner()
RULES = """\
[[entries]]
id = "factory"
question = "Did you reuse the factory?"
expects = true
reveal = "Keep test setup consistent."

[diff]
exclude = ["*.skip"]
"""


def git(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture(autouse=True)
def in_repository(git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(git_repo)


def configure(repository: Path) -> None:
    (repository / ".dresscode.toml").write_text(RULES)


def answer(*arguments: str):
    return runner.invoke(app, ["answer", *arguments])


def test_answer_records_evidence_fingerprint_and_reveal_after_persisting(
    git_repo: Path,
) -> None:
    configure(git_repo)
    repository = discover(git_repo)
    config = load(repository)
    fingerprint = collect(config).fingerprint
    before = git(git_repo, "status", "--porcelain")

    result = answer(
        "factory", "--yes", "--evidence", "Reused the shared fixture.", "--json"
    )

    assert result.exit_code == 0, result.output
    response = json.loads(result.stdout)
    record = RunStore(resolve_scope(load(repository))).read()["verdicts"]["factory"]
    assert response == {
        **resolve_scope(config).metadata(),
        "status": "recorded",
        "id": "factory",
        "verdict": "yes",
        "expected": "yes",
        "matched": True,
        "evidence": "Reused the shared fixture.",
        "fingerprint": fingerprint,
        "timestamp": record["timestamp"],
        "reveal": "Keep test setup consistent.",
    }
    assert record == {
        "verdict": "yes",
        "evidence": "Reused the shared fixture.",
        "fingerprint": fingerprint,
        "timestamp": record["timestamp"],
    }
    assert record["timestamp"]
    assert EntryStore(repository).counters("factory") == Counters(asked=1)
    assert git(git_repo, "status", "--porcelain") == before
    assert not (git_repo / "dresscode").exists()


def test_answer_replaces_current_verdict_and_keeps_history_and_counters(
    git_repo: Path,
) -> None:
    configure(git_repo)

    for verdict, evidence in (
        ("--yes", "First review"),
        ("--no", "Second review"),
        ("--n-a", "Only documentation changed"),
    ):
        result = answer("factory", verdict, "--evidence", evidence, "--json")
        assert result.exit_code == 0, result.output
        if verdict == "--n-a":
            assert json.loads(result.stdout)["matched"] is True

    repository = discover(git_repo)
    state = RunStore(resolve_scope(load(repository))).read()
    assert state["verdicts"]["factory"]["verdict"] == "n-a"
    assert [item["verdict"] for item in state["history"]] == ["yes", "no"]
    counters = EntryStore(repository).counters("factory")
    assert counters.asked == 3
    assert counters.violated == 1
    assert counters.n_a == 1
    assert counters.last_violated is not None


@pytest.mark.parametrize(
    "arguments",
    [
        ("factory", "--yes", "--evidence", ""),
        ("missing", "--yes", "--evidence", "Evidence"),
        ("factory", "--yes", "--no", "--evidence", "Evidence"),
        ("factory", "--evidence", "Evidence"),
    ],
)
def test_invalid_answers_exit_two_without_recording(
    git_repo: Path, arguments: tuple[str, ...]
) -> None:
    configure(git_repo)
    result = answer(*arguments, "--json")

    assert result.exit_code == 2
    assert result.stderr == ""
    assert json.loads(result.stdout)["status"] == "error"
    assert RunStore(resolve_scope(load(discover(git_repo)))).read()["verdicts"] == {}
    assert EntryStore(discover(git_repo)).counters("factory") == Counters()


def test_counter_failure_rolls_back_the_saved_verdict(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure(git_repo)
    first = answer("factory", "--yes", "--evidence", "Reviewed", "--json")
    assert first.exit_code == 0, first.output
    repository = discover(git_repo)
    run = RunStore(resolve_scope(load(repository)))
    before = run.read()
    counters = EntryStore(repository).counters("factory")

    def fail_record(self: EntryStore, entry: Entry, verdict: bool | None) -> None:
        raise StoreError("counter store unavailable")

    monkeypatch.setattr(EntryStore, "record", fail_record)
    failed = answer("factory", "--no", "--evidence", "Changed answer", "--json")

    assert failed.exit_code == 2
    assert json.loads(failed.stdout)["error"] == "counter store unavailable"
    assert run.read() == before
    assert EntryStore(repository).counters("factory") == counters


def test_staleness_uses_scoped_diff_fingerprint(git_repo: Path) -> None:
    configure(git_repo)
    result = answer("factory", "--yes", "--evidence", "Reviewed", "--json")
    assert result.exit_code == 0, result.output
    run = RunStore(resolve_scope(load(discover(git_repo))))
    config = load(discover(git_repo))
    fingerprint = collect(config).fingerprint
    assert run.stale_verdicts(fingerprint) == ()

    (git_repo / "notes.skip").write_text("excluded\n")
    assert run.stale_verdicts(collect(load(discover(git_repo))).fingerprint) == ()

    (git_repo / "new.py").write_text("scoped change\n")
    assert run.stale_verdicts(collect(load(discover(git_repo))).fingerprint) == (
        "factory",
    )


def test_reset_clears_current_answers_and_waivers_but_preserves_counters(
    git_repo: Path,
) -> None:
    configure(git_repo)
    result = answer("factory", "--yes", "--evidence", "Reviewed", "--json")
    assert result.exit_code == 0, result.output
    repository = discover(git_repo)
    run = RunStore(resolve_scope(load(repository)))
    state: dict[str, Any] = json.loads(run.path.read_text())
    history_before = state["history"]
    state["waivers"]["factory"] = {
        "reason": "Accepted",
        "fingerprint": state["verdicts"]["factory"]["fingerprint"],
        "timestamp": state["verdicts"]["factory"]["timestamp"],
    }
    run.path.write_text(json.dumps(state))

    reset = runner.invoke(app, ["reset", "--json"])

    assert reset.exit_code == 0, reset.output
    assert json.loads(reset.stdout)["status"] == "reset"
    cleared = RunStore(resolve_scope(load(repository))).read()
    assert cleared["verdicts"] == {}
    assert cleared["waivers"] == {}
    assert cleared["history"] == history_before
    assert EntryStore(repository).counters("factory") == Counters(asked=1)
