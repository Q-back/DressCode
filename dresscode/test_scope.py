"""Baseline identity through real Git and the CLI."""

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from dresscode.cli import app
from dresscode.config import layer_paths, load
from dresscode.repo import discover
from dresscode.store import Counters, EntryStore
from dresscode.test_diff import commit_all, git

runner = CliRunner()


def invoke(*arguments: str, code: int = 0) -> dict[str, Any]:
    result = runner.invoke(app, [*arguments, "--json"])
    assert result.exit_code == code, result.output
    assert result.stderr == ""
    return json.loads(result.stdout)


@pytest.fixture
def review_repo(git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(git_repo)
    (git_repo / ".dresscode.toml").write_text(
        '[[entries]]\nid = "rule"\nquestion = "Reviewed?"\n'
        'expects = true\nreveal = "SEALED"\n'
    )
    commit_all(git_repo)
    return git_repo


def test_legacy_state_is_untouched_and_only_shared_state_is_retained(
    review_repo: Path, xdg_home: Path
) -> None:
    rules = review_repo / ".dresscode.toml"
    with rules.open("a") as file:
        file.write(
            'context = "printf fresh"\n'
            '[[entries]]\nid = "retired"\nquestion = "Retired?"\nexpects = false\n'
        )
    commit_all(review_repo)
    invoke("trust")
    invoke("retire", "retired")
    repository = discover(review_repo)
    store = EntryStore(repository)
    store.record(load(repository).entries[0], True)
    baseline = git(review_repo, "rev-parse", "main")
    head_commit = git(review_repo, "rev-parse", "HEAD")
    legacy_keys = (
        f"{repository.identity}:feature/test",
        json.dumps(
            ["v2", repository.identity, "feature/test", baseline], separators=(",", ":")
        ),
    )
    runs = xdg_home / "state/dresscode/runs"
    runs.mkdir(parents=True)
    old_files = {}
    for key in legacy_keys:
        path = runs / (hashlib.sha256(key.encode()).hexdigest() + ".json")
        stamp = {"timestamp": "2026-01-01T00:00:00Z", "fingerprint": "0" * 64}
        path.write_text(
            json.dumps(
                {
                    "run_key": key,
                    "verdicts": {
                        "rule": {**stamp, "verdict": "no", "evidence": "Old review"}
                    },
                    "history": [],
                    "waivers": {"rule": {**stamp, "reason": "Old waiver"}},
                    "contexts": {
                        "rule": {
                            "state": "ready",
                            "error": "",
                            "context_output": "old",
                            "command": "printf fresh",
                            "fingerprint": stamp["fingerprint"],
                        }
                    },
                }
            )
        )
        old_files[path] = path.read_bytes()

    diff = invoke("diff")
    assert json.loads(diff["run_key"]) == [
        "v3",
        repository.identity,
        "feature/test",
        baseline,
    ]
    assert invoke("check", code=1)["entries"][0]["state"] == "unanswered"
    invoke("answer", "rule", "--yes", "--evidence", "Missing context", code=2)
    assert invoke("report")["waivers"] == []
    for command in ("list", "check", "report", "reset"):
        response = invoke(command, code=1 if command == "check" else 0)
        assert response["base_commit"] == baseline
        assert response["head_commit"] == head_commit
        assert response["run_key"] == diff["run_key"]
        assert "fingerprint" not in json.dumps(response)
        if command == "list":
            assert [entry["id"] for entry in response["entries"]] == ["rule"]
            assert response["entries"][0]["context_output"] == "fresh"
            assert "SEALED" not in json.dumps(response)
    invoke("list")
    answered = invoke("answer", "rule", "--yes", "--evidence", "Fresh review")
    assert answered["run_key"] == diff["run_key"]
    assert answered["base_commit"] == baseline
    assert answered["head_commit"] == head_commit
    assert invoke("check")["status"] == "passed"
    assert store.counters("rule") == Counters(asked=2)
    assert {path: path.read_bytes() for path in old_files} == old_files


def test_default_baseline_movement_separates_runs_at_the_same_head(
    review_repo: Path,
) -> None:
    git(review_repo, "commit", "--allow-empty", "-m", "Create equivalent baseline")
    git(review_repo, "branch", "--force", "main", "HEAD")
    first = invoke("diff")
    invoke("answer", "rule", "--no", "--evidence", "Known violation")
    waived = invoke("waive", "rule", "--reason", "Accepted")
    assert waived["base_commit"] == first["base_commit"]
    assert invoke("check")["status"] == "passed-with-waivers"
    git(review_repo, "branch", "--force", "main", "HEAD~1")
    second = invoke("diff")
    assert second["head_commit"] == first["head_commit"]
    assert second["files"] == first["files"] == []
    assert second["run_key"] != first["run_key"]
    assert invoke("check", code=1)["entries"][0]["state"] == "unanswered"
    invoke("reset")
    git(review_repo, "update-ref", "refs/heads/main", first["base_commit"])
    assert invoke("check")["status"] == "passed-with-waivers"
    assert invoke("report")["entries"][0]["evidence"] == "Known violation"


def test_equivalent_default_targets_share_state_and_context_is_pinned(
    review_repo: Path,
) -> None:
    rules = review_repo / ".dresscode.toml"
    rules.write_text(rules.read_text() + 'context = "printenv DRESSCODE_BASE_COMMIT"\n')
    commit_all(review_repo)
    invoke("trust")
    first = invoke("list")
    assert "DRESSCODE_BASE_COMMIT" not in os.environ
    assert first["entries"][0]["context_output"] == git(
        review_repo, "rev-parse", "main"
    )
    invoke("answer", "rule", "--yes", "--evidence", "Pinned context")
    # Changing only the target spelling in a global layer does not change content.
    config = layer_paths(discover(review_repo))["global"][0]
    config.parent.mkdir(parents=True)
    config.write_text('merge_base_with = "refs/heads/main"\n')
    assert invoke("check")["run_key"] == first["run_key"]
    config.write_text('merge_base_with = "missing"\n')
    assert "merge_base_with" in invoke("list", code=2)["error"]
