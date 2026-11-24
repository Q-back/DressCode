import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dresscode.cli import app
from dresscode.test_diff import git

runner = CliRunner()


@pytest.mark.parametrize(
    "command",
    [
        ["diff"],
        ["list"],
        ["answer", "rule", "--yes", "--evidence", "Reviewed"],
        ["waive", "rule", "--reason", "Accepted"],
        ["check"],
    ],
)
@pytest.mark.parametrize("change", ["staged", "unstaged", "untracked"])
def test_guarded_commands_reject_local_edits_without_writing(
    git_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    xdg_home: Path,
    command: list[str],
    change: str,
) -> None:
    config = git_repo / ".dresscode.toml"
    config.write_text('[diff]\nexclude = ["README.md", "*.lock"]\n')
    if command[0] != "check":
        with config.open("a") as file:
            file.write(
                '[[entries]]\nid = "rule"\nquestion = "Reviewed?"\nexpects = true\n'
            )
    git(git_repo, "add", ".dresscode.toml")
    git(git_repo, "commit", "-m", "Configure review")
    git(git_repo, "config", "status.showUntrackedFiles", "no")
    subdir = git_repo / "subdir"
    subdir.mkdir()
    monkeypatch.chdir(subdir)
    path = git_repo / ("edit\tname\n.lock" if change == "untracked" else "README.md")
    path.write_text("local change\n")
    if change == "staged":
        git(git_repo, "add", "README.md")
    index = git_repo / ".git/index"
    original_index = index.read_bytes()

    result = runner.invoke(app, [*command, "--json"])

    assert result.exit_code == 2, result.output
    assert result.stderr == ""
    response = json.loads(result.stdout)
    assert response["status"] == "error"
    assert repr(path.name) in response["error"]
    assert "commit" in response["error"].lower()
    assert path.read_text() == "local change\n"
    assert index.read_bytes() == original_index
    assert not list((xdg_home / "state").iterdir())


def test_ignored_files_do_not_block_review(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(git_repo)
    (git_repo / ".git/info/exclude").write_text("*.cache\n")
    (git_repo / "scratch.cache").write_text("ignored\n")

    result = runner.invoke(app, ["list", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["entries"] == []


def test_rule_management_trust_and_reset_are_available_while_dirty(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(git_repo)
    (git_repo / "README.md").write_text("dirty\n")
    for args in (
        ["add", "rule", "--question", "Reviewed?", "--expects", "true"],
        ["trust"],
        ["retire", "rule"],
        ["reset"],
    ):
        result = runner.invoke(app, args)
        assert result.exit_code == 0, result.output
    assert (git_repo / "README.md").read_text() == "dirty\n"
