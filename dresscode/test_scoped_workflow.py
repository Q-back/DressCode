"""Separate baselines through installed commands and nested context subprocesses."""

import hashlib
import json
import shlex
import sys
from pathlib import Path

import pytest

from dresscode.config import layer_paths
from dresscode.repo import discover
from dresscode.test_workflow import cli, document, git


def test_two_equal_fingerprint_reviews_keep_evidence_verdicts_and_reset_isolated(
    workflow_repo: Path, xdg_home: Path
) -> None:
    root = workflow_repo
    rules = root / ".dresscode.toml"
    rules.write_text(
        rules.read_text().replace("dresscode diff --numstat", "dresscode diff --json")
    )
    git(root, "add", ".dresscode.toml")
    git(root, "commit", "-m", "Inspect pinned baseline in context")
    first = git(root, "rev-parse", "HEAD").strip()
    git(root, "branch", "--force", "main", first)
    git(root, "tag", "alias", first)
    git(root, "commit", "--allow-empty", "-m", "Second baseline, same tree")
    second = git(root, "rev-parse", "HEAD").strip()
    (root / "committed.txt").write_text("committed\n")
    git(root, "add", "committed.txt")
    git(root, "commit", "-m", "Committed work")
    (root / "staged.txt").write_text("staged\n")
    git(root, "add", "staged.txt")
    (root / "README.md").write_text("unstaged\n")
    (root / "new.txt").write_text("untracked\n")
    (root / "uv.lock").write_text("excluded\n")
    a = document(root, "diff", "--base", first)
    b = document(root, "diff", "--base", second)
    assert a["fingerprint"] == b["fingerprint"]
    assert a["run_key"] != b["run_key"]
    assert {file["path"] for file in a["files"]} == {
        "committed.txt",
        "staged.txt",
        "README.md",
        "new.txt",
    }
    cli(root, "trust")
    listed = document(root, "list", "--base", first)
    context_a = listed["entries"][0]["context_output"]
    assert json.loads(context_a)["base_commit"] == first
    assert all(not {"expects", "reveal"} & entry.keys() for entry in listed["entries"])
    for identifier, verdict in [
        ("size", "yes"),
        ("side-effects", "no"),
        ("python", "n-a"),
    ]:
        document(
            root,
            "answer",
            identifier,
            f"--{verdict}",
            "--evidence",
            "Review A",
            "--base",
            first,
        )
    assert document(root, "check", "--strict", "--base", "alias")["status"] == "passed"
    assert document(root, "check")["run_key"] == a["run_key"]
    # Equal fingerprints cannot deliver A's context into B's run.
    blocked = document(
        root,
        "answer",
        "size",
        "--yes",
        "--evidence",
        "Review B",
        "--base",
        second,
        code=2,
    )
    assert "list" in blocked["error"]
    pending = document(root, "check", "--base", second, code=1)
    assert pending["entries"][0]["state"] == "unanswered"
    for entry in pending["entries"]:
        for remedy in entry["commands"]:
            if " trust" not in remedy:
                assert f"--base {second}" in remedy
    context_b = document(root, "list", "--base", second)["entries"][0]["context_output"]
    assert json.loads(context_b)["base_commit"] == second
    for identifier, verdict in [
        ("size", "yes"),
        ("side-effects", "yes"),
        ("python", "n-a"),
    ]:
        document(
            root,
            "answer",
            identifier,
            f"--{verdict}",
            "--evidence",
            "Review B",
            "--base",
            second,
        )
    document(
        root, "waive", "side-effects", "--reason", "Accepted for B", "--base", second
    )
    assert document(root, "check", "--base", second)["status"] == "passed-with-waivers"
    assert (
        document(root, "check", "--strict", "--base", second, code=1)["status"]
        == "failed"
    )
    for baseline, context_output, evidence in [
        (first, context_a, "Review A"),
        (second, context_b, "Review B"),
    ]:
        report = document(root, "report", "--base", baseline)
        assert report["base_commit"] == baseline
        assert report["entries"][0]["context_output"] == context_output
        assert report["entries"][0]["evidence"] == evidence
        assert baseline in cli(root, "report", "--base", baseline).stdout.replace(
            "\n", ""
        )
    # Re-answer history remains local too.
    document(
        root, "answer", "size", "--yes", "--evidence", "Review A again", "--base", first
    )
    for scope, count in [(a, 1), (b, 0)]:
        name = hashlib.sha256(scope["run_key"].encode()).hexdigest() + ".json"
        state = json.loads((xdg_home / "state/dresscode/runs" / name).read_text())
        assert len(state["history"]) == count
    # Staging and committing against fixed SHAs preserve fingerprints and answers.
    git(root, "add", ".")
    git(root, "commit", "-m", "Commit reviewed content")
    assert document(root, "diff", "--base", first)["fingerprint"] == a["fingerprint"]
    (root / "uv.lock").write_text("different excluded content\n")
    assert document(root, "check", "--base", first)["status"] == "passed"
    document(root, "reset", "--base", first)
    assert (
        document(root, "check", "--base", first, code=1)["entries"][0]["state"]
        == "unanswered"
    )
    assert document(root, "check", "--base", second)["status"] == "passed-with-waivers"
    assert (
        document(root, "report", "--base", second)["entries"][0]["context_output"]
        == context_b
    )
    (root / "committed.txt").write_text("scoped edit after review\n")
    assert (
        document(root, "check", "--base", second, code=1)["entries"][0]["state"]
        == "stale"
    )


def test_moving_ref_inspection_and_inherited_baseline_precedence(
    workflow_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = workflow_repo
    first = git(root, "rev-parse", "HEAD").strip()
    git(root, "branch", "moving", first)
    git(root, "commit", "--allow-empty", "-m", "Moveable baseline")
    second = git(root, "rev-parse", "HEAD").strip()
    cli(root, "trust")
    document(root, "list", "--base", "moving")
    for identifier, verdict in [
        ("size", "yes"),
        ("side-effects", "no"),
        ("python", "n-a"),
    ]:
        document(
            root,
            "answer",
            identifier,
            f"--{verdict}",
            "--evidence",
            "Pinned review",
            "--base",
            "moving",
        )
    git(root, "update-ref", "refs/heads/moving", second)
    assert document(root, "check", "--base", "moving", code=1)["base_commit"] == second
    assert document(root, "check", "--base", first)["status"] == "passed"
    # Inspection has no side effect on subsequent default selection or files.
    before = git(root, "status", "--porcelain")
    document(root, "diff", "--base", second)
    assert document(root, "diff")["base_commit"] == first
    assert git(root, "status", "--porcelain") == before
    monkeypatch.setenv("DRESSCODE_BASE_COMMIT", second)
    assert document(root, "diff")["base_commit"] == second
    assert document(root, "diff", "--base", first)["base_commit"] == first
    monkeypatch.setenv("DRESSCODE_BASE_COMMIT", "missing")
    assert document(root, "diff", code=2)["status"] == "error"
    assert document(root, "diff", "--base", first)["base_commit"] == first


def test_context_pins_ref_before_movement_and_allows_explicit_auxiliary_scope(
    workflow_repo: Path,
) -> None:
    root = workflow_repo
    first = git(root, "rev-parse", "HEAD").strip()
    git(root, "branch", "moving", first)
    git(root, "commit", "--allow-empty", "-m", "New target")
    second = git(root, "rev-parse", "HEAD").strip()
    # The command moves the symbolic selector, then starts a nested unqualified CLI.

    path = layer_paths(discover(root))["private"][0]
    path.parent.mkdir(parents=True)
    executable = shlex.quote(str(Path(sys.executable).with_name("dresscode")))
    command = f"git update-ref refs/heads/moving {second}; {executable} diff --json"
    path.write_text(f'[[entries]]\nid="size"\ncontext={json.dumps(command)}\n')
    first_list = document(root, "list", "--base", "moving")
    assert first_list["base_commit"] == first
    assert (
        json.loads(first_list["entries"][0]["context_output"])["base_commit"] == first
    )
    assert git(root, "rev-parse", "moving").strip() == second
    command = f"{executable} diff --base {second} --json"
    path.write_text(f'[[entries]]\nid="size"\ncontext={json.dumps(command)}\n')
    auxiliary = document(root, "list", "--base", first)
    assert auxiliary["base_commit"] == first
    assert (
        json.loads(auxiliary["entries"][0]["context_output"])["base_commit"] == second
    )
    assert document(root, "diff")["base_commit"] == first


def test_exact_submodule_baseline_is_stable_and_dirty_content_blocks(
    submodule_repo: tuple[Path, Path],
) -> None:
    root, submodule = submodule_repo
    baseline = git(root, "rev-parse", "HEAD").strip()
    (submodule / "file.txt").write_text("new\n")
    git(submodule, "commit", "-am", "Update submodule")
    first = document(root, "diff", "--base", baseline)
    assert first["files"] == [{"path": "lib", "added": 1, "removed": 1}]
    git(root, "add", "lib")
    git(root, "commit", "-m", "Stage pointer")
    assert document(root, "diff", "--base", baseline) == first
    (submodule / "file.txt").write_text("dirty\n")
    assert (
        "dirty submodule" in document(root, "diff", "--base", baseline, code=2)["error"]
    )
