"""Exact revision selection, including Git's ref and object ambiguity rules."""

import hashlib
import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dresscode.cli import app
from dresscode.test_cli import normalize_help_text
from dresscode.test_diff import git

runner = CliRunner()
REVIEW_COMMANDS = ("diff", "list", "answer", "waive", "check", "report", "reset")


@pytest.fixture
def revisions(git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str]:
    monkeypatch.chdir(git_repo)
    (git_repo / "first.txt").write_text("first\n")
    git(git_repo, "add", ".")
    git(git_repo, "commit", "-m", "First")
    first = git(git_repo, "rev-parse", "HEAD")
    git(git_repo, "branch", "selected")
    git(git_repo, "update-ref", "refs/remotes/origin/selected", first)
    git(git_repo, "tag", "light")
    git(git_repo, "tag", "-a", "annotated", "-m", "Annotated")
    (git_repo / "second.txt").write_text("second\n")
    git(git_repo, "add", ".")
    git(git_repo, "commit", "-m", "Second")
    return git_repo, first


@pytest.mark.parametrize(
    "selector",
    [
        "selected",
        "origin/selected",
        "light",
        "annotated",
        "sha",
        "abbreviation",
        "HEAD~1",
    ],
)
@pytest.mark.parametrize("positional", [False, True])
def test_exact_single_commit_revisions(
    revisions: tuple[Path, str], selector: str, positional: bool
) -> None:
    _, first = revisions
    reference = (
        first
        if selector == "sha"
        else first[:12]
        if selector == "abbreviation"
        else selector
    )
    arguments = [reference] if positional else ["--base", reference]
    result = runner.invoke(app, ["diff", *arguments, "--json", "--numstat"])
    assert result.exit_code == 0, result.output
    assert result.stderr == ""
    response = json.loads(result.stdout)
    assert response["base_commit"] == first
    assert "merge_base" not in response
    assert response["files"] == [{"path": "second.txt", "added": 1, "removed": 0}]
    assert json.loads(response["run_key"])[-1] == first
    plain = runner.invoke(app, ["diff", *arguments])
    assert first in plain.stdout


@pytest.mark.parametrize("json_output", [False, True])
@pytest.mark.parametrize(
    "reference",
    [
        "",
        "missing",
        "HEAD..main",
        "HEAD...main",
        "HEAD^{tree}",
        "HEAD:first.txt",
        "--help",
        "--output=oops",
    ],
)
def test_invalid_revisions_are_single_errors(
    revisions: tuple[Path, str], reference: str, json_output: bool
) -> None:
    options = ["--json"] if json_output else []
    result = runner.invoke(app, ["diff", *options, "--", reference])
    assert result.exit_code == 2, result.output
    if json_output:
        assert result.stderr == ""
        error = json.loads(result.stdout)
        assert error["status"] == "error"
        message = error["error"]
    else:
        assert result.stdout == ""
        message = result.stderr
    assert "revision" in message.lower()


@pytest.mark.parametrize(
    "positional,option", [("HEAD", "main"), ("", "main"), ("HEAD", "")]
)
def test_diff_rejects_two_selectors(
    revisions: tuple[Path, str], positional: str, option: str
) -> None:
    result = runner.invoke(app, ["diff", positional, "--base", option, "--json"])
    assert result.exit_code == 2
    assert result.stderr == ""
    assert "both" in json.loads(result.stdout)["error"].lower()


@pytest.mark.parametrize("command", REVIEW_COMMANDS)
def test_all_review_commands_accept_base_and_reject_empty(
    revisions: tuple[Path, str], command: str
) -> None:
    help_result = runner.invoke(app, [command, "--help"])
    assert "--base" in normalize_help_text(help_result.stdout)
    extras = (
        ["rule", "--yes", "--evidence", "Reviewed"]
        if command == "answer"
        else ["rule", "--reason", "Accepted"]
        if command == "waive"
        else []
    )
    # A real entry allows validation to reach the selector in answer and waive.
    (revisions[0] / ".dresscode.toml").write_text(
        '[[entries]]\nid="rule"\nquestion="Review?"\nexpects=true\n'
    )
    result = runner.invoke(app, [command, *extras, "--base", "", "--json"])
    assert result.exit_code == 2
    assert result.stderr == ""
    assert "revision" in json.loads(result.stdout)["error"].lower()


def test_refname_precedence_and_qualified_disambiguation(
    revisions: tuple[Path, str],
) -> None:
    root, first = revisions
    head = git(root, "rev-parse", "HEAD")
    git(root, "branch", "collision", head)
    git(root, "tag", "collision", first)
    for reference, expected in [
        ("collision", first),
        ("refs/tags/collision", first),
        ("refs/heads/collision", head),
    ]:
        result = runner.invoke(app, ["diff", reference, "--json"])
        assert result.exit_code == 0, result.output
        assert result.stderr == ""
        assert json.loads(result.stdout)["base_commit"] == expected


def test_ambiguous_abbreviated_commit_ids_fail(revisions: tuple[Path, str]) -> None:
    root, _ = revisions
    tree = git(root, "rev-parse", "HEAD^{tree}")
    seen: dict[str, bytes] = {}
    # Find a four-hex collision without filling the object database with fixtures.
    for index in range(10000):
        body = (
            f"tree {tree}\nauthor Test <test@example.test> 1 +0000\n"
            f"committer Test <test@example.test> 1 +0000\n\n{index}\n"
        ).encode()
        oid = hashlib.sha1(f"commit {len(body)}\0".encode() + body).hexdigest()
        prefix = oid[:4]
        if prefix in seen:
            for content in (seen[prefix], body):
                subprocess.run(
                    ["git", "hash-object", "-w", "-t", "commit", "--stdin"],
                    cwd=root,
                    input=content,
                    check=True,
                    capture_output=True,
                )
            break
        seen[prefix] = body
    else:
        pytest.fail("No collision found")
    result = runner.invoke(app, ["diff", prefix, "--json"])
    assert result.exit_code == 2
    assert result.stderr == ""
    assert "revision" in json.loads(result.stdout)["error"].lower()


def test_explicit_refs_ignore_defaults_and_handle_unrelated_history(
    revisions: tuple[Path, str],
) -> None:
    root, first = revisions
    (root / ".dresscode.toml").write_text('merge_base_with="missing"\n')
    for reference in (first, "HEAD"):
        result = runner.invoke(app, ["diff", "--base", reference, "--json"])
        assert result.exit_code == 0, result.output
    # A diverged branch contains a file absent from this checkout.
    git(root, "switch", "-c", "diverged", "main")
    (root / "other.txt").write_text("other\n")
    git(root, "add", "other.txt")
    git(root, "commit", "-m", "Diverged")
    git(root, "switch", "feature/test")
    result = runner.invoke(app, ["diff", "diverged", "--json"])
    assert result.exit_code == 0, result.output
    assert {"path": "other.txt", "added": 0, "removed": 1} in json.loads(result.stdout)[
        "files"
    ]
    tree = git(root, "rev-parse", "diverged^{tree}")
    unrelated = subprocess.run(
        ["git", "commit-tree", tree, "-m", "Unrelated"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    result = runner.invoke(app, ["diff", unrelated, "--json"])
    assert result.exit_code == 0, result.output
    response = json.loads(result.stdout)
    assert response["base_commit"] == unrelated
    assert {"path": "other.txt", "added": 0, "removed": 1} in response["files"]
