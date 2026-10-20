import json
import shlex
import sys
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dresscode.cli import app
from dresscode.config import layer_paths
from dresscode.repo import discover
from dresscode.run import RunStore

runner = CliRunner()


def invoke(*arguments: str, code: int = 0):
    result = runner.invoke(app, [*arguments, "--json"])
    assert result.exit_code == code, result.output
    assert result.stderr == ""
    return json.loads(result.stdout)


def configure(root: Path, command: str, layer: str = "repo", timeout: float = 10):
    paths = layer_paths(discover(root))[layer]
    path = paths[0] if paths else root / ".dresscode" / "rules.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"[context]\ntimeout_seconds = {timeout}\n[[entries]]\n"
        'id = "size"\nquestion = "Small?"\nexpects = true\nreveal = "SECRET"\n'
        f"context = {json.dumps(command)}\n"
    )
    return path


@pytest.fixture(autouse=True)
def in_repository(git_repo: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(git_repo)


@pytest.mark.parametrize("directory", [False, True])
def test_trust_delivery_and_recorded_report(git_repo: Path, directory: bool):
    if directory:
        (git_repo / ".dresscode").mkdir()
    rules = configure(git_repo, "printf '  evidence  '")
    blocked = invoke("list")["entries"][0]
    assert blocked["state"] == "context_untrusted"
    assert "dresscode trust" in blocked["error"]
    invoke("answer", "size", "--yes", "--evidence", "Reviewed", code=2)
    invoke("trust")
    listed = invoke("list")["entries"][0]
    assert "evidence" in runner.invoke(app, ["list"]).stdout
    assert listed["context_output"] == "evidence"
    assert not {"expects", "reveal"} & listed.keys()
    invoke("answer", "size", "--yes", "--evidence", "Reviewed")
    assert invoke("check")["status"] == "passed"
    assert invoke("report")["entries"][0]["context_output"] == "evidence"
    assert "evidence" in runner.invoke(app, ["report"]).stdout
    with rules.open("a") as output:
        output.write("\n# changed\n")
    assert invoke("list")["entries"][0]["state"] == "context_untrusted"
    assert invoke("check", code=1)["entries"][0]["state"] == "context_untrusted"


@pytest.mark.parametrize("layer", ["repo", "private", "global"])
def test_only_local_commands_need_trust(git_repo: Path, tmp_path: Path, layer: str):
    marker = tmp_path / "executed"
    configure(git_repo, f"touch {shlex.quote(str(marker))}; pwd", layer)
    listed = invoke("list")["entries"][0]
    assert marker.exists() == (layer != "repo")
    if layer != "repo":
        assert listed["context_output"] == str(git_repo)


def test_context_provenance_survives_field_overrides(git_repo: Path):
    configure(git_repo, "printf global", "global")
    local = layer_paths(discover(git_repo))["repo"][0]
    local.write_text('[[entries]]\nid="size"\nquestion="Local?"\n')
    assert invoke("list")["entries"][0]["context_output"] == "global"
    local.write_text('[[entries]]\nid="size"\ncontext="printf local"\n')
    private = layer_paths(discover(git_repo))["private"][0]
    private.parent.mkdir(parents=True, exist_ok=True)
    private.write_text('[[entries]]\nid="size"\nquestion="Private?"\n')
    assert invoke("list")["entries"][0]["state"] == "context_untrusted"


@pytest.mark.parametrize(
    "command", ["printf tail >&2; exit 3", "printf tail >&2; sleep 30"]
)
def test_failed_context_blocks_gate_and_cannot_be_answered(
    git_repo: Path, command: str
):
    configure(git_repo, command, "private", timeout=0.1)
    listed = invoke("list")["entries"][0]
    assert listed["state"] == "context_failed"
    assert "tail" in listed["error"]
    assert ("timeout" if "sleep" in command else "3") in listed["error"]
    assert invoke("check", code=1)["entries"][0]["state"] == "context_failed"
    plain = runner.invoke(app, ["check"])
    assert plain.exit_code == 1 and "tail" in plain.stdout
    invoke("answer", "size", "--n-a", "--evidence", "Reviewed", code=2)
    assert "SECRET" not in json.dumps(invoke("report"))


def test_answer_preserves_delivered_output_without_rerunning(
    git_repo: Path, tmp_path: Path
):
    evidence = tmp_path / "evidence"
    evidence.write_text("first")
    configure(git_repo, f"cat {shlex.quote(str(evidence))}", "global")
    invoke("answer", "size", "--yes", "--evidence", "Reviewed", code=2)
    invoke("list")
    evidence.write_text("second")
    invoke("answer", "size", "--yes", "--evidence", "Reviewed")
    assert invoke("report")["entries"][0]["context_output"] == "first"
    invoke("reset")
    invoke("answer", "size", "--yes", "--evidence", "Reviewed", code=2)
    evidence.write_text("first")
    invoke("list")
    invoke("answer", "size", "--yes", "--evidence", "Reviewed")
    assert (
        RunStore(discover(git_repo)).read()["verdicts"]["size"]["context_output"]
        == "first"
    )
    (git_repo / "new.py").write_text("changed")
    assert invoke("check", code=1)["entries"][0]["state"] == "stale"
    invoke("answer", "size", "--yes", "--evidence", "Reviewed", code=2)


def test_large_output_is_capped_and_recorded(git_repo: Path):
    command = shlex.join([sys.executable, "-c", "print('x' * 100000)"])
    configure(git_repo, command, "global")
    output = invoke("list")["entries"][0]["context_output"]
    assert len(output) < 20000
    assert output.endswith("[truncated]")
    invoke("answer", "size", "--yes", "--evidence", "Reviewed")
    assert invoke("report")["entries"][0]["context_output"] == output


@pytest.mark.parametrize("value", ["0", "-1", "true", '"slow"', "nan", "inf"])
def test_invalid_timeout_is_a_configuration_error(git_repo: Path, value: str):
    rules = configure(git_repo, "true")
    rules.write_text(
        rules.read_text().replace("timeout_seconds = 10", f"timeout_seconds = {value}")
    )
    assert "timeout_seconds" in invoke("list", code=2)["error"]


def test_real_diff_context_from_subdirectory(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
):
    configure(git_repo, "dresscode diff --numstat")
    (git_repo / "new.py").write_text("new line\n")
    subdirectory = git_repo / "sub"
    subdirectory.mkdir()
    monkeypatch.chdir(subdirectory)
    invoke("trust")
    output = invoke("list")["entries"][0]["context_output"]
    assert "1\t0\tnew.py" in output and "TOTAL" in output
    invoke("answer", "size", "--yes", "--evidence", "Reviewed counts")
    assert invoke("report")["entries"][0]["context_output"] == output


def test_directory_membership_invalidates_trust(git_repo: Path):
    (git_repo / ".dresscode").mkdir()
    configure(git_repo, "printf evidence")
    invoke("trust")
    extra = git_repo / ".dresscode" / "extra.toml"
    extra.write_text("# new file\n")
    assert invoke("list")["entries"][0]["state"] == "context_untrusted"
    invoke("trust")
    extra.unlink()
    assert invoke("list")["entries"][0]["state"] == "context_untrusted"


def test_timeout_kills_shell_descendants(git_repo: Path, tmp_path: Path):
    marker = tmp_path / "survivor"
    configure(
        git_repo,
        f"(sleep 0.5; touch {shlex.quote(str(marker))}) & wait",
        "global",
        timeout=0.1,
    )
    assert invoke("list")["entries"][0]["state"] == "context_failed"
    time.sleep(0.6)
    assert not marker.exists()


def test_changed_global_command_requires_new_delivery(git_repo: Path):
    configure(git_repo, "printf first", "global")
    invoke("list")
    invoke("answer", "size", "--yes", "--evidence", "Reviewed")
    configure(git_repo, "printf second", "global")
    invoke("answer", "size", "--yes", "--evidence", "Reviewed", code=2)
    invoke("check", code=1)
    invoke("list")
    invoke("answer", "size", "--yes", "--evidence", "Reviewed again")
    assert invoke("report")["entries"][0]["context_output"] == "second"
