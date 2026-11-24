import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dresscode.cli import app
from dresscode.test_diff import commit_all, git

runner = CliRunner()


def test_diff_json_loads_config_and_updates_head_after_empty_commit(
    git_repo: Path, xdg_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (xdg_home / "config/dresscode").mkdir()
    (xdg_home / "config/dresscode/config.toml").write_text(
        'merge_base_with = "main"\n[diff]\nexclude = ["*.skip"]\n'
    )
    (git_repo / "new.py").write_text("new\n")
    (git_repo / "uv.lock").write_text("included with explicit exclusions\n")
    (git_repo / "ignored.skip").write_text("excluded\n")
    commit_all(git_repo)
    (git_repo / "subdir").mkdir()
    monkeypatch.chdir(git_repo / "subdir")
    before = git(git_repo, "status", "--porcelain")
    result = runner.invoke(app, ["diff", "--json"])

    assert result.exit_code == 0, result.output
    assert result.stderr == ""
    response = json.loads(result.stdout)
    assert response == {
        "run_key": response["run_key"],
        "base_commit": git(git_repo, "rev-parse", "main"),
        "head_commit": git(git_repo, "rev-parse", "HEAD"),
        "files": [
            {"path": "new.py", "added": 1, "removed": 0},
            {"path": "uv.lock", "added": 1, "removed": 0},
        ],
        "totals": {"added": 2, "removed": 0},
    }
    assert git(git_repo, "status", "--porcelain") == before
    assert list((xdg_home / "state").iterdir()) == []
    git(git_repo, "commit", "--allow-empty", "-m", "Same content, different commit")
    committed = runner.invoke(app, ["diff", "--json", "--numstat"])
    assert committed.exit_code == 0, committed.output
    assert committed.stderr == ""
    assert json.loads(committed.stdout) == {
        **response,
        "head_commit": git(git_repo, "rev-parse", "HEAD"),
    }
    assert json.loads(committed.stdout)["head_commit"] != response["head_commit"]


@pytest.mark.parametrize("numstat", [False, True])
def test_diff_text_reports_base_counts_and_totals(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch, numstat: bool
) -> None:
    monkeypatch.chdir(git_repo)
    (git_repo / "new.py").write_text("one\ntwo\n")
    commit_all(git_repo)
    result = runner.invoke(app, ["diff", *(["--numstat"] if numstat else [])])
    assert result.exit_code == 0, result.output
    assert "2\t0\tnew.py" in result.stdout
    assert result.stdout.splitlines()[-1] == "2\t0\tTOTAL"
    metadata = result.stderr if numstat else result.stdout
    assert f"Base: {git(git_repo, 'rev-parse', 'main')}" in metadata
    assert f"HEAD: {git(git_repo, 'rev-parse', 'HEAD')}" in metadata
    assert "\x1b" not in result.output
    if numstat:
        assert result.stdout.splitlines() == ["2\t0\tnew.py", "2\t0\tTOTAL"]


def test_binary_numstat_escapes_unusual_paths(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(git_repo)
    path = "tab\tline\n.bin"
    (git_repo / path).write_bytes(b"\0binary")
    commit_all(git_repo)
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


def test_untracked_nested_repository_blocks_diff(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    git(git_repo, "init", "--initial-branch=main", "nested")
    (git_repo / "nested/file.txt").write_text("nested content\n")
    monkeypatch.chdir(git_repo)
    result = runner.invoke(app, ["diff", "--json"])
    assert result.exit_code == 2, result.output
    assert "'nested/'" in json.loads(result.stdout)["error"]


@pytest.mark.parametrize(
    ("config", "error"),
    [
        ('merge_base_with = "missing"', "merge_base_with"),
        ("[diff]\nexclude = false", "diff.exclude"),
        ('[diff]\nexclude = [":(unknown)README.md"]', "Invalid pathspec magic"),
    ],
)
def test_invalid_diff_configuration_returns_json_error(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch, config: str, error: str
) -> None:
    monkeypatch.chdir(git_repo)
    (git_repo / ".dresscode.toml").write_text(
        config + '\n[[entries]]\nid = "rule"\nquestion = "Reviewed?"\n'
        'expects = true\ncontext = "printf evidence"\n'
    )
    commit_all(git_repo)
    for args in (
        ["list"],
        ["answer", "rule", "--yes", "--evidence", "Reviewed"],
        ["waive", "rule", "--reason", "Accepted"],
        ["check"],
        ["diff"],
        ["report"],
    ):
        result = runner.invoke(app, [*args, "--json"])
        assert result.exit_code == 2, result.output
        response = json.loads(result.stdout)
        assert response["status"] == "error"
        assert error in response["error"]
        assert result.stderr == ""
