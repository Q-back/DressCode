import json
import subprocess
import sys
from pathlib import Path

import pytest
from rich.text import Text
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
runner = CliRunner()


def normalize_help_text(output: str) -> str:
    plain_text = Text.from_ansi(output).plain
    without_panel_borders = plain_text.replace("│", " ")
    return " ".join(without_panel_borders.split())


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        ("  --json\tEmit JSON.\n", "--json Emit JSON."),
        ("\x1b[36m-\x1b[0m\x1b[36m-json\x1b[0m", "--json"),
        (
            "│ private (personal overrides for this │\n│ repository) │",
            "private (personal overrides for this repository)",
        ),
    ],
    ids=["plain-whitespace", "ansi-styled-option", "wrapped-panel-text"],
)
def test_normalize_help_text(output: str, expected: str) -> None:
    assert normalize_help_text(output) == expected


def test_help_lists_every_v0_command() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    help_text = normalize_help_text(result.stdout)
    for command in COMMANDS:
        assert command in help_text


def test_add_help_explains_layers_outside_a_git_worktree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["add", "--help"], color=False)

    assert result.exit_code == 0
    help_text = normalize_help_text(result.stdout)
    assert "repo (shared repository config)" in help_text
    assert "private (personal overrides for this repository)" in help_text
    assert "global (defaults for all repositories)" in help_text
    assert "[default: repo]" in help_text
    assert set(tmp_path.iterdir()) == {tmp_path / "config", tmp_path / "state"}


def test_diff_help_explains_scope_and_base_priority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["diff", "--help"], color=False)

    assert result.exit_code == 0
    help_text = normalize_help_text(result.stdout)
    assert "merge base of HEAD and the selected base" in help_text
    assert "working tree" in help_text
    assert "committed, staged, unstaged and untracked non-ignored files" in help_text
    assert (
        "configured base_ref, origin/HEAD, local main, local master, then the root commit"
        in help_text
    )
    assert "Configured diff exclusions apply" in help_text


@pytest.mark.parametrize("command", COMMANDS)
def test_command_help_is_available(command: str) -> None:
    result = runner.invoke(app, [command, "--help"])

    assert result.exit_code == 0
    help_text = normalize_help_text(result.stdout)
    assert "--json" in help_text


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
    help_text = normalize_help_text(result.stdout)
    for command in COMMANDS:
        assert command in help_text
