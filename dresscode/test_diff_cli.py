import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dresscode.cli import app
from dresscode.test_diff import git

runner = CliRunner()


def test_diff_json_loads_config_and_preserves_fingerprint_across_commit(
    git_repo: Path, xdg_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (xdg_home / "config/dresscode").mkdir()
    (xdg_home / "config/dresscode/config.toml").write_text(
        'base_ref = "main"\n[diff]\nexclude = ["*.skip"]\n'
    )
    (git_repo / "new.py").write_text("new\n")
    (git_repo / "uv.lock").write_text("included with explicit exclusions\n")
    (git_repo / "ignored.skip").write_text("excluded\n")
    (git_repo / "subdir").mkdir()
    monkeypatch.chdir(git_repo / "subdir")
    before = git(git_repo, "status", "--porcelain")
    result = runner.invoke(app, ["diff", "--json"])

    assert result.exit_code == 0, result.output
    assert result.stderr == ""
    response = json.loads(result.stdout)
    assert response == {
        "base_ref": "main",
        "merge_base": git(git_repo, "rev-parse", "main"),
        "fingerprint": response["fingerprint"],
        "files": [
            {"path": "new.py", "added": 1, "removed": 0},
            {"path": "uv.lock", "added": 1, "removed": 0},
        ],
        "totals": {"added": 2, "removed": 0},
    }
    assert len(response["fingerprint"]) == 64
    assert git(git_repo, "status", "--porcelain") == before
    assert list((xdg_home / "state").iterdir()) == []
    git(git_repo, "add", ".")
    git(git_repo, "commit", "--message", "Reviewed change")
    committed = runner.invoke(app, ["diff", "--json", "--numstat"])
    assert committed.exit_code == 0
    assert json.loads(committed.stdout) == response


@pytest.mark.parametrize("numstat", [False, True])
def test_diff_text_reports_base_counts_and_totals(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch, numstat: bool
) -> None:
    monkeypatch.chdir(git_repo)
    (git_repo / "new.py").write_text("one\ntwo\n")
    result = runner.invoke(app, ["diff", *(["--numstat"] if numstat else [])])
    assert result.exit_code == 0, result.output
    assert "2\t0\tnew.py" in result.stdout
    assert result.stdout.splitlines()[-1] == "2\t0\tTOTAL"
    assert "Base: main" in (result.stderr if numstat else result.stdout)
    assert "\x1b" not in result.output
    if numstat:
        assert result.stdout.splitlines() == ["2\t0\tnew.py", "2\t0\tTOTAL"]


def test_binary_numstat_escapes_unusual_paths(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(git_repo)
    path = "tab\tline\n.bin"
    (git_repo / path).write_bytes(b"\0binary")
    result = runner.invoke(app, ["diff", "--numstat"])
    assert result.exit_code == 0, result.output
    assert result.stdout.splitlines() == [f"-\t-\t{json.dumps(path)}", "0\t0\tTOTAL"]


@pytest.mark.parametrize("json_output", [False, True])
def test_diff_outside_repository_is_a_usage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, json_output: bool
) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["diff", *(["--json"] if json_output else [])])
    assert result.exit_code == 2
    if json_output:
        assert json.loads(result.stdout)["status"] == "error"
        assert result.stderr == ""
    else:
        assert "Git work tree" in result.stderr
        assert result.stdout == ""


@pytest.mark.parametrize("json_output", [False, True])
def test_untracked_nested_repository_has_an_actionable_error(
    git_repo: Path, xdg_home: Path, monkeypatch: pytest.MonkeyPatch, json_output: bool
) -> None:
    nested = git_repo / "nested"
    nested.mkdir()
    git(nested, "init", "--initial-branch=main")
    (nested / "file.txt").write_text("nested content\n")
    git(nested, "add", ".")
    git(
        nested,
        "-c",
        "user.name=Tests",
        "-c",
        "user.email=tests@dresscode.invalid",
        "commit",
        "-m",
        "Nested baseline",
    )
    monkeypatch.chdir(git_repo)
    result = runner.invoke(app, ["diff", *(["--json"] if json_output else [])])
    assert result.exit_code == 2, repr(result.exception)
    if json_output:
        response = json.loads(result.stdout)
        assert response["status"] == "error"
        message = response["error"]
        assert result.stderr == ""
    else:
        message = result.stderr
        assert result.stdout == ""
    assert "nested/" in message
    assert "diff.exclude" in message
    config = xdg_home / "config/dresscode"
    config.mkdir()
    (config / "config.toml").write_text('[diff]\nexclude = ["nested"]\n')
    excluded = runner.invoke(app, ["diff", "--json"])
    assert excluded.exit_code == 0, excluded.output
    assert json.loads(excluded.stdout)["files"] == []


@pytest.mark.parametrize("config", ['base_ref = "missing"', "[diff]\nexclude = false"])
def test_invalid_diff_configuration_returns_json_error(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch, config: str
) -> None:
    monkeypatch.chdir(git_repo)
    (git_repo / ".dresscode.toml").write_text(config)
    result = runner.invoke(app, ["diff", "--json"])
    assert result.exit_code == 2
    assert json.loads(result.stdout)["status"] == "error"
    assert result.stderr == ""
