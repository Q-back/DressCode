import json
import shlex
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dresscode.cli import app
from dresscode.config import load
from dresscode.diff import resolve_scope
from dresscode.repo import discover
from dresscode.report import render
from dresscode.run import RunStore

runner = CliRunner()


@pytest.fixture(autouse=True)
def configured_repository(git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(git_repo)
    (git_repo / ".dresscode.toml").write_text(
        '[[entries]]\nid = "factory"\nquestion = "Reuse the factory?"\n'
        'expects = true\nreveal = "Keep setup consistent."\n'
    )


def invoke(*arguments: str):
    return runner.invoke(app, list(arguments))


def record(verdict: str = "--yes") -> None:
    result = invoke("answer", "factory", verdict, "--evidence", "Reviewed setup")
    assert result.exit_code == 0, result.output


@pytest.mark.parametrize(
    "identifier", ["--factory", "-factory", "factory with 'quotes'"]
)
def test_suggested_commands_work_with_option_like_and_quoted_ids(
    git_repo: Path, identifier: str
) -> None:
    rules = git_repo / ".dresscode.toml"
    rules.write_text(
        rules.read_text().replace('id = "factory"', f"id = {json.dumps(identifier)}")
    )

    def run_suggestion(command: str, verdict: str = "--no") -> None:
        filled = command.replace("--yes|--no|--n-a", verdict).replace(
            "<text>", "Reviewed"
        )
        result = invoke(*shlex.split(filled)[1:])
        assert result.exit_code == 0, result.output

    unanswered = json.loads(invoke("check", "--json").stdout)
    run_suggestion(unanswered["entries"][0]["commands"][0])
    violated = json.loads(invoke("check", "--json").stdout)
    assert violated["entries"][0]["state"] == "violated"
    run_suggestion(violated["entries"][0]["commands"][1])
    assert invoke("check").exit_code == 0
    strict = json.loads(invoke("check", "--strict", "--json").stdout)
    run_suggestion(strict["entries"][0]["commands"][0], "--yes")
    assert invoke("check", "--strict").exit_code == 0


def test_redirected_report_strips_embedded_ansi_but_preserves_json(
    capsys: pytest.CaptureFixture[str],
) -> None:
    evidence = "\x1b[31mReviewed setup\x1b[0m"
    reason = "\x1b[32mAccepted tradeoff\x1b[0m"
    assert invoke("answer", "factory", "--no", "--evidence", evidence).exit_code == 0
    assert invoke("waive", "factory", "--reason", reason).exit_code == 0
    summary = json.loads(invoke("report", "--json").stdout)
    assert summary["entries"][0]["evidence"] == evidence
    assert summary["waivers"][0]["reason"] == reason

    render(summary)
    output = capsys.readouterr().out
    assert "\x1b[" not in output
    assert "Reviewed setup" in output
    assert "Accepted tradeoff" in output
    assert summary["entries"][0]["evidence"] == evidence
    assert summary["waivers"][0]["reason"] == reason


@pytest.mark.parametrize("verdict", ["--yes", "--n-a"])
@pytest.mark.parametrize("strict", [False, True])
def test_matching_and_not_applicable_verdicts_pass(verdict: str, strict: bool) -> None:
    record(verdict)
    result = invoke("check", "--json", *(["--strict"] if strict else []))

    assert result.exit_code == 0, result.output
    assert result.stderr == ""
    summary = json.loads(result.stdout)
    assert summary["status"] == "passed"
    assert summary["entries"][0]["state"] == "passed"
    assert "reveal" not in result.stdout
    assert "expects" not in result.stdout


def test_empty_entry_list_passes(git_repo: Path) -> None:
    (git_repo / ".dresscode.toml").unlink()
    result = invoke("check", "--json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        **resolve_scope(load(discover(git_repo))).metadata(),
        "status": "passed",
        "entries": [],
    }


@pytest.mark.parametrize("state", ["unanswered", "violated", "stale", "context_failed"])
def test_blockers_name_question_state_and_fix(git_repo: Path, state: str) -> None:
    if state != "unanswered":
        record("--no" if state == "violated" else "--yes")
    if state == "stale":
        (git_repo / "new.py").write_text("changed\n")
    if state == "context_failed":
        run = RunStore(resolve_scope(load(discover(git_repo))))
        document = json.loads(run.path.read_text())
        document["verdicts"]["factory"]["verdict"] = "context_failed"
        run.path.write_text(json.dumps(document))

    result = invoke("check", "--json")
    assert result.exit_code == 1, result.output
    assert result.stderr == ""
    summary = json.loads(result.stdout)
    assert summary["status"] == "failed"
    entry = summary["entries"][0]
    assert entry["id"] == "factory"
    assert entry["question"] == "Reuse the factory?"
    assert entry["state"] == state
    assert any(
        command.startswith("dresscode answer ") and command.endswith("-- factory")
        for command in entry["commands"]
    )
    if state == "violated":
        assert any(
            command == "dresscode waive --reason <text> -- factory"
            for command in entry["commands"]
        )
    plain = invoke("check")
    assert plain.exit_code == 1
    for value in ("factory", entry["question"], state, *entry["commands"]):
        assert value in plain.stdout


def test_waiver_passes_normal_gate_but_not_strict(git_repo: Path) -> None:
    record("--no")
    result = invoke("waive", "factory", "--reason", "  Accepted tradeoff  ", "--json")
    assert result.exit_code == 0, result.output
    response = json.loads(result.stdout)
    waiver = RunStore(resolve_scope(load(discover(git_repo)))).read()["waivers"][
        "factory"
    ]
    assert waiver == {
        "reason": "Accepted tradeoff",
        "fingerprint": response["fingerprint"],
        "timestamp": response["timestamp"],
    }
    normal = invoke("check", "--json")
    assert normal.exit_code == 0, normal.output
    assert json.loads(normal.stdout)["status"] == "passed-with-waivers"
    strict = invoke("check", "--strict", "--json")
    assert strict.exit_code == 1, strict.output
    assert json.loads(strict.stdout)["entries"][0]["state"] == "waived"
    assert "Accepted tradeoff" in invoke("check", "--strict").stdout


@pytest.mark.parametrize("verdict", [None, "--yes", "--n-a", "stale", "--no"])
def test_invalid_waivers_exit_two(git_repo: Path, verdict: str | None) -> None:
    if verdict is not None:
        record("--no" if verdict == "stale" else verdict)
    if verdict == "stale":
        (git_repo / "new.py").write_text("changed\n")
    reason = "  " if verdict == "--no" else "Accepted"
    result = invoke("waive", "factory", "--reason", reason, "--json")
    assert result.exit_code == 2, result.output
    assert result.stderr == ""
    assert json.loads(result.stdout)["status"] == "error"
    assert RunStore(resolve_scope(load(discover(git_repo)))).read()["waivers"] == {}


def test_unknown_id_and_missing_reason_are_usage_errors() -> None:
    for arguments in [("missing", "--reason", "Accepted"), ("factory",)]:
        result = invoke("waive", *arguments, "--json")
        assert result.exit_code == 2
        assert json.loads(result.stdout)["status"] == "error"


def test_waivers_expire_and_reset_with_verdicts(git_repo: Path) -> None:
    record("--no")
    assert invoke("waive", "factory", "--reason", "Accepted").exit_code == 0
    (git_repo / "new.py").write_text("changed\n")
    result = invoke("check", "--json")
    assert result.exit_code == 1
    assert json.loads(result.stdout)["entries"][0]["state"] == "stale"
    assert invoke("reset").exit_code == 0
    assert RunStore(resolve_scope(load(discover(git_repo)))).read()["waivers"] == {}
    assert (
        json.loads(invoke("check", "--json").stdout)["entries"][0]["state"]
        == "unanswered"
    )


def test_reanswer_discards_waiver() -> None:
    record("--no")
    assert invoke("waive", "factory", "--reason", "Accepted").exit_code == 0
    record("--no")
    assert invoke("check").exit_code == 1


@pytest.mark.parametrize("waived", [False, True])
def test_report_shows_verdict_evidence_reveal_size_and_waivers(waived: bool) -> None:
    record("--no" if waived else "--yes")
    if waived:
        assert (
            invoke("waive", "factory", "--reason", "Accepted tradeoff").exit_code == 0
        )
    result = invoke("report", "--json")
    assert result.exit_code == 0, result.output
    assert result.stderr == ""
    summary = json.loads(result.stdout)
    assert summary["status"] == ("passed-with-waivers" if waived else "passed")
    assert json.loads(summary["run_key"])[2] == "feature/test"
    assert summary["diff"]["added"] > 0
    assert summary["diff"]["removed"] == 0
    entry = summary["entries"][0]
    assert entry["verdict"] == ("no" if waived else "yes")
    assert entry["evidence"] == "Reviewed setup"
    assert entry["reveal"] == "Keep setup consistent."
    assert bool(summary["waivers"]) == waived
    plain = invoke("report")
    assert plain.exit_code == 0, plain.output
    assert "\x1b[" not in plain.stdout
    for value in (
        summary["status"],
        "Reuse the factory?",
        "Reviewed setup",
        "Keep setup consistent.",
    ):
        assert value in plain.stdout
    if waived:
        assert summary["waivers"][0]["reason"] == "Accepted tradeoff"
        assert "Waivers" in plain.stdout
        assert "Accepted tradeoff" in plain.stdout


def test_unanswered_report_does_not_reveal_sealed_fields() -> None:
    result = invoke("report", "--json")
    assert result.exit_code == 0, result.output
    summary = json.loads(result.stdout)
    assert summary["status"] == "failed"
    assert summary["entries"][0]["verdict"] is None
    assert "reveal" not in result.stdout
    assert "expected" not in result.stdout
    assert "Keep setup consistent." not in invoke("report").stdout


def test_report_marks_stale_waivers(git_repo: Path) -> None:
    record("--no")
    assert invoke("waive", "factory", "--reason", "Accepted").exit_code == 0
    (git_repo / "new.py").write_text("changed\n")
    summary = json.loads(invoke("report", "--json").stdout)
    assert summary["status"] == "failed"
    assert summary["waivers"][0]["state"] == "stale"


def test_retired_and_disabled_entries_are_absent(git_repo: Path) -> None:
    record("--no")
    assert invoke("waive", "factory", "--reason", "Accepted").exit_code == 0
    assert invoke("retire", "factory").exit_code == 0
    with (git_repo / ".dresscode.toml").open("a") as output:
        output.write('\n[[entries]]\nid = "disabled"\nenabled = false\n')
    for command in ("check", "report"):
        result = invoke(command, "--json")
        assert result.exit_code == 0, result.output
        summary = json.loads(result.stdout)
        assert summary["status"] == "passed"
        assert summary["entries"] == []
        assert summary.get("waivers", []) == []


@pytest.mark.parametrize("command", ["check", "report"])
def test_malformed_waiver_is_a_state_error(git_repo: Path, command: str) -> None:
    record()
    run = RunStore(resolve_scope(load(discover(git_repo))))
    state = json.loads(run.path.read_text())
    state["waivers"]["factory"] = {"reason": "Missing fingerprint"}
    run.path.write_text(json.dumps(state))
    result = invoke(command, "--json")
    assert result.exit_code == 2, result.output
    assert "invalid run state" in json.loads(result.stdout)["error"]


@pytest.mark.parametrize("command", ["check", "report"])
def test_configuration_errors_exit_two(git_repo: Path, command: str) -> None:
    (git_repo / ".dresscode.toml").write_text("broken = [")
    result = invoke(command, "--json")

    assert result.exit_code == 2
    assert result.stderr == ""
    assert json.loads(result.stdout)["status"] == "error"
