"""Full review cycles through the installed CLI and real Git repositories."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def git(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=root, check=True, capture_output=True, text=True
    ).stdout


def cli(root: Path, *arguments: str, code: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [str(Path(sys.executable).with_name("dresscode")), *arguments],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == code, result.stdout + result.stderr
    assert result.stderr == ""
    return result


def document(root: Path, *arguments: str, code: int = 0) -> dict[str, Any]:
    return json.loads(cli(root, *arguments, "--json", code=code).stdout)


def test_report_groups_multiple_rules_and_preserves_json(workflow_repo: Path):
    root = workflow_repo
    cli(root, "trust")
    (root / "change.txt").write_text("A small catalog change.\n")
    listed = document(root, "list")["entries"]
    evidence = (
        "demo/fruit_catalog.py:12 keeps [Pear] before [Apple]. "
        "Reviewed every catalog entry and its ordering.\n"
        "The [demo] catalog contains no other changes."
    )
    verdicts = {"size": "no", "side-effects": "no", "python": "n-a"}
    for identifier, verdict in verdicts.items():
        document(root, "answer", identifier, f"--{verdict}", "--evidence", evidence)
    reason = "Accepted [demo] catalog size."
    cli(root, "waive", "size", "--reason", reason)

    for stale in (False, True):
        if stale:
            (root / "change.txt").write_text("Changed after the review.\n")
        summary = document(root, "report")
        rendered = cli(root, "report").stdout
        assert "\x1b[" not in rendered
        assert summary == document(root, "report")
        assert summary["status"] == ("failed" if stale else "passed-with-waivers")
        compact = "".join(rendered.split())
        assert summary["diff"]["base_commit"] in compact
        assert "Expected:" not in rendered
        blocks = rendered.split("Rule: ")[1:]
        assert len(blocks) == 3
        for block, entry, question in zip(
            blocks, summary["entries"], listed, strict=True
        ):
            identifier = entry["id"]
            state = (
                "stale" if stale else ("waived" if identifier == "size" else "passed")
            )
            assert block.startswith(f"{identifier} [{state}]")
            assert entry["state"] == state
            normalized = " ".join(block.split())
            assert f"Question: {question['question']}" in normalized
            assert f"Reveal: {entry['reveal']}" in normalized
            assert "\n\nEvidence:\n" in block
            assert "".join(evidence.split()) in "".join(block.split())
            expected = "no" if identifier == "side-effects" else "yes"
            assert entry["expected"] == expected
            assert entry["evidence"] == evidence
            assert entry["verdict"] == verdicts[identifier]
            annotation = " (expected yes)" if identifier == "size" else ""
            assert f"Verdict: {verdicts[identifier]}{annotation}\n" in block
            if identifier == "size":
                assert entry["context_output"] == question["context_output"]
                assert "Context:" in block
                assert "change.txt" in block
        assert "\n\nWaivers\n" in rendered
        waiver = summary["waivers"][0]
        assert waiver["state"] == ("stale" if stale else "current")
        assert f"size [{waiver['state']}]: {reason}" in rendered.split("Waivers\n")[1]


def test_waived_review_covers_intermediate_commits_and_expires(workflow_repo: Path):
    root = workflow_repo
    cli(root, "trust")
    initial = document(root, "check", code=1)
    assert initial["status"] == "failed"
    assert {entry["id"] for entry in initial["entries"]} == {
        "size",
        "side-effects",
        "python",
    }
    hooks_before = {
        path.name: path.read_bytes() for path in (root / ".git/hooks").iterdir()
    }

    for name in ("first.txt", "second.txt"):
        (root / name).write_text(f"{name}\n")
        git(root, "add", name)
        git(root, "commit", "-m", f"Add {name} without review answers")

    assert git(root, "rev-list", "--count", "main..HEAD").strip() == "2"
    pending = document(root, "check", code=1)
    assert pending["status"] == "failed"
    assert any(entry["state"] == "unanswered" for entry in pending["entries"])
    scoped = document(root, "diff")
    assert {item["path"] for item in scoped["files"]} == {"first.txt", "second.txt"}
    assert scoped["totals"] == {"added": 2, "removed": 0}
    status_before = git(root, "status", "--porcelain=v1", "--untracked-files=all")

    listed = document(root, "list")
    assert len(listed["entries"]) == 3
    assert all(not {"expects", "reveal"} & entry.keys() for entry in listed["entries"])
    context_output = listed["entries"][0]["context_output"]
    assert "first.txt" in context_output and "second.txt" in context_output
    for entry in listed["entries"]:
        answer = document(
            root,
            "answer",
            entry["id"],
            "--yes",
            "--evidence",
            f"Reviewed {entry['id']}",
        )
        assert answer["reveal"]

    violated = document(root, "check", code=1)
    assert {
        entry["id"] for entry in violated["entries"] if entry["state"] == "violated"
    } == {"side-effects"}
    reason = "The explicit output write is required for this command."
    cli(root, "waive", "side-effects", "--reason", reason)
    assert document(root, "check")["status"] == "passed-with-waivers"
    strict = document(root, "check", "--strict", code=1)
    assert strict["status"] == "failed"
    assert any(entry["state"] == "waived" for entry in strict["entries"])
    report = cli(root, "report").stdout
    assert "passed-with-waivers" in report and "Waivers" in report
    assert reason in " ".join(report.split())
    assert "\x1b[" not in report
    summary = document(root, "report")
    assert summary["entries"][0]["context_output"] == context_output
    assert summary["waivers"][0]["state"] == "current"
    assert (
        git(root, "status", "--porcelain=v1", "--untracked-files=all") == status_before
    )
    assert {
        path.name: path.read_bytes() for path in (root / ".git/hooks").iterdir()
    } == hooks_before

    (root / "first.txt").write_text("changed after review\n")
    stale = document(root, "check", code=1)
    assert {entry["state"] for entry in stale["entries"]} == {"stale"}
    expired = document(root, "report")
    assert expired["status"] == "failed"
    assert expired["waivers"][0]["state"] == "stale"
    assert expired["diff"]["fingerprint"] != scoped["fingerprint"]


def test_review_reports_violations_without_fixes_or_waivers(workflow_repo: Path):
    root = workflow_repo
    cli(root, "trust")
    (root / "change.txt").write_text("A change to review without fixing it.\n")
    status_before = git(root, "status", "--porcelain=v1", "--untracked-files=all")
    fingerprint = document(root, "diff")["fingerprint"]
    listed = document(root, "list")["entries"]
    verdicts = {
        "size": ("yes", "The diff adds one line."),
        "side-effects": ("yes", "The change adds an output file."),
        "python": ("n-a", "The change contains no Python."),
    }
    assert {entry["id"] for entry in listed} == set(verdicts)
    for identifier, (verdict, evidence) in verdicts.items():
        document(root, "answer", identifier, f"--{verdict}", "--evidence", evidence)

    summary = document(root, "report")
    assert summary["status"] == "failed"
    assert summary["waivers"] == []
    assert {entry["id"]: entry["state"] for entry in summary["entries"]} == {
        "size": "passed",
        "side-effects": "violated",
        "python": "passed",
    }
    for entry in summary["entries"]:
        verdict, evidence = verdicts[entry["id"]]
        assert entry["verdict"] == verdict
        assert entry["evidence"] == evidence
    assert summary["diff"]["fingerprint"] == fingerprint
    assert document(root, "check", code=1)["status"] == "failed"
    assert document(root, "check", "--strict", code=1)["status"] == "failed"
    assert (
        git(root, "status", "--porcelain=v1", "--untracked-files=all") == status_before
    )


def test_unwaived_review_passes_both_gates_and_reports_evidence(workflow_repo: Path):
    root = workflow_repo
    cli(root, "trust")
    (root / "change.txt").write_text("A small text-only change.\n")
    assert document(root, "check", code=1)["status"] == "failed"
    status_before = git(root, "status", "--porcelain=v1", "--untracked-files=all")
    scoped = document(root, "diff")
    listed = document(root, "list")["entries"]
    assert {entry["id"] for entry in listed} == {"size", "side-effects", "python"}
    verdicts = {
        "size": ("yes", "The cumulative diff adds one line."),
        "side-effects": ("no", "Only a text file was added."),
        "python": ("n-a", "The change contains no Python."),
    }
    for identifier, (verdict, evidence) in verdicts.items():
        answer = document(
            root, "answer", identifier, f"--{verdict}", "--evidence", evidence
        )
        assert answer["reveal"]

    assert document(root, "check")["status"] == "passed"
    assert document(root, "check", "--strict")["status"] == "passed"
    summary = document(root, "report")
    assert summary["status"] == "passed"
    assert summary["diff"]["added"] == 1
    assert summary["diff"]["removed"] == 0
    assert summary["diff"]["fingerprint"] == scoped["fingerprint"]
    assert summary["waivers"] == []
    reveals = {
        "size": "Keep reviews manageable.",
        "side-effects": "Keep transformations pure.",
        "python": "Check Python types when applicable.",
    }
    assert len(summary["entries"]) == 3
    for entry in summary["entries"]:
        verdict, evidence = verdicts[entry["id"]]
        assert entry["verdict"] == verdict
        assert entry["evidence"] == evidence
        assert entry["reveal"] == reveals[entry["id"]]
        assert entry["state"] == "passed"
    assert summary["entries"][0]["context_output"] == listed[0]["context_output"]
    assert (
        git(root, "status", "--porcelain=v1", "--untracked-files=all") == status_before
    )
