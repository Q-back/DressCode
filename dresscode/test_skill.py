"""The bundled skill is readable anywhere and its example uses the real CLI."""

import re
import shlex
import subprocess
import sys
from importlib.resources import files
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dresscode.cli import app
from dresscode.test_cli import normalize_help_text

runner = CliRunner()


def skill_text() -> str:
    return files("dresscode").joinpath("SKILL.md").read_text(encoding="utf-8")


def test_help_advertises_skill() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "--skill" in normalize_help_text(result.stdout)


@pytest.mark.parametrize("arguments", [[], ["--unknown"], ["unknown"]])
def test_root_usage_errors_remain_errors(arguments: list[str]) -> None:
    result = runner.invoke(app, arguments)

    assert result.exit_code == 2


@pytest.mark.parametrize("arguments", [["--skill"], ["--skill", "check"]])
def test_skill_outside_git_ignores_config_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, arguments: list[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", str(tmp_path))
    config = tmp_path / "config" / "dresscode"
    config.mkdir()
    (config / "config.toml").write_text("invalid = [")
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}

    result = runner.invoke(app, arguments)

    assert result.exit_code == 0, result.output
    assert result.stdout == skill_text()
    assert result.stderr == ""
    assert {
        path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()
    } == (before)
    assert not (tmp_path / "state" / "dresscode").exists()


def test_skill_inside_git_ignores_invalid_local_config(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(git_repo)
    config = git_repo / ".dresscode.toml"
    config.write_text("invalid = [")

    result = runner.invoke(app, ["--skill"])

    assert result.exit_code == 0, result.output
    assert result.stdout == skill_text()
    assert result.stderr == ""
    assert config.read_text() == "invalid = ["


def test_installed_skill_is_plain_markdown_outside_the_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FORCE_COLOR", "1")
    executable = Path(sys.executable).with_name("dresscode")
    result = subprocess.run(
        [str(executable), "--skill"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == skill_text()
    assert result.stderr == ""
    assert result.stdout.startswith("---\nname: dresscode\n")
    assert "\x1b[" not in result.stdout


def test_skill_rule_example_can_be_created_and_reviewed(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(git_repo)
    example = re.search(r"```sh\n(.*?)\n```", skill_text(), re.DOTALL)
    assert example is not None
    arguments = shlex.split(example[1].replace("\\\n", ""))
    assert arguments[0] == "dresscode"
    added = runner.invoke(app, arguments[1:])
    assert added.exit_code == 0, added.output
    listed = runner.invoke(app, ["list", "--json"])
    assert listed.exit_code == 0, listed.output
    assert "shared-builder" in listed.stdout
    assert "expects" not in listed.stdout
    assert runner.invoke(app, ["check"]).exit_code == 1
    answered = runner.invoke(
        app,
        [
            "answer",
            "shared-builder",
            "--yes",
            "--evidence",
            "Reused the shared builder.",
        ],
    )
    assert answered.exit_code == 0, answered.output
    assert runner.invoke(app, ["check", "--strict"]).exit_code == 0
    (git_repo / "change.txt").write_text("Changed after review.\n")
    assert runner.invoke(app, ["check"]).exit_code == 1


@pytest.mark.parametrize("source", ["docs/manual.md", "skill"])
def test_documented_scoped_workflow_runs_with_pinned_metadata(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch, source: str
) -> None:
    from dresscode.test_diff import git

    monkeypatch.chdir(git_repo)
    for index in range(2):
        git(git_repo, "commit", "--allow-empty", "-m", f"Commit {index}")
    identifier = "shared-builder" if source == "skill" else "test-factory"
    added = runner.invoke(
        app, ["add", identifier, "--question", "Reuse?", "--expects", "true"]
    )
    assert added.exit_code == 0, added.output
    text = (
        skill_text()
        if source == "skill"
        else (Path(__file__).resolve().parents[1] / source).read_text()
    )
    section = text.split("## Review an exact commit", 1)[1]
    example = re.search(r"```sh\n(.*?)\n```", section, re.DOTALL)
    assert example is not None
    result = subprocess.run(
        ["sh", "-eu", "-c", example[1]],
        cwd=git_repo,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    baseline = git(git_repo, "rev-parse", "HEAD~2")
    assert baseline in result.stdout
    reset = runner.invoke(app, ["check", "--base", baseline, "--json"])
    assert reset.exit_code == 1
    assert "unanswered" in reset.stdout
