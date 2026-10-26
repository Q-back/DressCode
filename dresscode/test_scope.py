"""Baseline identity through real Git and the CLI."""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from dresscode.cli import app
from dresscode.repo import discover
from dresscode.test_diff import git

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
    return git_repo


def test_default_metadata_and_legacy_approvals_are_isolated(
    review_repo: Path, xdg_home: Path
) -> None:
    legacy_key = f"{discover(review_repo).identity}:feature/test"
    legacy = (
        xdg_home
        / "state/dresscode/runs"
        / (hashlib.sha256(legacy_key.encode()).hexdigest() + ".json")
    )
    legacy.parent.mkdir(parents=True)
    baseline = git(review_repo, "rev-parse", "main")
    fingerprint = invoke("diff")["fingerprint"]
    record = {
        "verdict": "yes",
        "evidence": "Old review",
        "fingerprint": fingerprint,
        "timestamp": "2026-01-01T00:00:00Z",
    }
    legacy.write_text(
        json.dumps(
            {
                "run_key": legacy_key,
                "verdicts": {"rule": record},
                "history": [],
                "waivers": {},
                "contexts": {},
            }
        )
    )
    original = legacy.read_bytes()
    diff = invoke("diff")
    assert diff["base_commit"] == baseline
    assert "merge_base" not in diff
    assert json.loads(diff["run_key"]) == [
        "v2",
        discover(review_repo).identity,
        "feature/test",
        baseline,
    ]
    for command in ("list", "check", "report", "reset"):
        response = invoke(command, code=1 if command == "check" else 0)
        assert response["base_commit"] == baseline
        assert response["run_key"] == diff["run_key"]
        if command == "list":
            assert "SEALED" not in json.dumps(response)
    answered = invoke("answer", "rule", "--yes", "--evidence", "Fresh review")
    assert answered["run_key"] == diff["run_key"]
    assert answered["base_commit"] == baseline
    assert invoke("check")["status"] == "passed"
    assert legacy.read_bytes() == original


def test_default_baseline_movement_separates_equal_fingerprints(
    review_repo: Path,
) -> None:
    first = invoke("diff")
    invoke("answer", "rule", "--no", "--evidence", "Known violation")
    waived = invoke("waive", "rule", "--reason", "Accepted")
    assert waived["base_commit"] == first["base_commit"]
    assert invoke("check")["status"] == "passed-with-waivers"
    git(review_repo, "commit", "--allow-empty", "-m", "Advance baseline")
    git(review_repo, "update-ref", "refs/heads/main", "HEAD")
    second = invoke("diff")
    assert second["fingerprint"] == first["fingerprint"]
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
    invoke("trust")
    first = invoke("list")
    assert first["entries"][0]["context_output"] == git(
        review_repo, "rev-parse", "main"
    )
    invoke("answer", "rule", "--yes", "--evidence", "Pinned context")
    # Changing only the target spelling in a global layer does not change content.
    from dresscode.config import layer_paths

    config = layer_paths(discover(review_repo))["global"][0]
    config.parent.mkdir(parents=True)
    config.write_text('merge_base_with = "refs/heads/main"\n')
    assert invoke("check")["run_key"] == first["run_key"]
    config.write_text('merge_base_with = "missing"\n')
    assert "merge_base_with" in invoke("list", code=2)["error"]
