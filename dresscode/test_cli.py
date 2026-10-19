import json
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dresscode.cli import app

COMMANDS = (
    "add",
    "answer",
    "check",
    "diff",
    "list",
    "report",
    "reset",
    "retire",
    "trust",
    "waive",
)
PLACEHOLDERS = tuple(name for name in COMMANDS if name not in {"add", "list", "retire"})
runner = CliRunner()


def test_help_lists_every_v0_command() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in COMMANDS:
        assert command in result.stdout


def test_add_help_explains_layers_outside_a_git_worktree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["add", "--help"], color=False)

    assert result.exit_code == 0
    help_text = " ".join(result.stdout.replace("│", " ").split())
    assert "repo (shared repository config)" in help_text
    assert "private (personal overrides for this repository)" in help_text
    assert "global (defaults for all repositories)" in help_text
    assert "[default: repo]" in help_text
    assert set(tmp_path.iterdir()) == {tmp_path / "config", tmp_path / "state"}


@pytest.mark.parametrize("command", PLACEHOLDERS)
def test_placeholders_are_explicitly_unimplemented(command: str) -> None:
    result = runner.invoke(app, [command])

    assert result.exit_code == 2
    assert result.stdout == ""
    assert f"dresscode {command}" in result.stderr
    assert "not implemented" in result.stderr


@pytest.mark.parametrize("command", PLACEHOLDERS)
def test_placeholder_json_is_a_single_document(command: str) -> None:
    result = runner.invoke(app, [command, "--json"])

    assert result.exit_code == 2
    assert result.stderr == ""
    assert json.loads(result.stdout) == {
        "command": command,
        "status": "unimplemented",
    }


@pytest.mark.parametrize("command", COMMANDS)
def test_command_help_is_available(command: str) -> None:
    result = runner.invoke(app, [command, "--help"])

    assert result.exit_code == 0
    assert "--json" in result.stdout


@pytest.mark.parametrize("json_output", [False, True])
def test_command_outside_a_git_worktree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, json_output: bool
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["list", *(["--json"] if json_output else [])])

    assert result.exit_code == 2
    if json_output:
        response = json.loads(result.stdout)
        assert response["status"] == "error"
        assert "Git work tree" in response["error"]
        assert result.stderr == ""
    else:
        assert result.stdout == ""
        assert "Git work tree" in result.stderr


def test_installed_entry_point_works_outside_the_project(tmp_path: Path) -> None:
    executable = Path(sys.executable).with_name("dresscode")
    result = subprocess.run(
        [str(executable), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    for command in COMMANDS:
        assert command in result.stdout
