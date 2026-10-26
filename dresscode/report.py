"""Human-readable review summaries."""

import sys
from typing import Any

from rich.console import Console
from rich.text import Text

from dresscode.config import Configuration
from dresscode.diff import ScopedDiff
from dresscode.gate import GateDecision
from dresscode.run import RunState


def summarize(
    config: Configuration,
    scoped: ScopedDiff,
    state: RunState,
    decision: GateDecision,
) -> dict[str, Any]:
    entries = []
    waivers = []
    definitions = {entry.id: entry for entry in config.entries}
    for item in decision["entries"]:
        identifier = item["id"]
        record = state["verdicts"].get(identifier)
        detail = {**item, "verdict": None}
        if record is not None:
            entry = definitions[identifier]
            detail.update(
                **record,
                expected="yes" if entry.expects else "no",
                reveal=entry.reveal,
            )
        entries.append(detail)
        waiver = state["waivers"].get(identifier)
        if waiver is not None:
            waivers.append(
                {
                    "id": identifier,
                    **waiver,
                    "state": "current" if item["state"] == "waived" else "stale",
                }
            )
    return {
        "status": decision["status"],
        **scoped.scope.metadata(),
        "diff": {
            "base_commit": scoped.base_commit,
            "fingerprint": scoped.fingerprint,
            "added": scoped.added,
            "removed": scoped.removed,
        },
        "entries": entries,
        "waivers": waivers,
    }


def render(summary: dict[str, Any]) -> None:
    console = Console(color_system="auto" if sys.stdout.isatty() else None)
    style = "red" if summary["status"] == "failed" else "green"
    console.print(summary["status"], style=style, markup=False)
    diff = summary["diff"]
    console.print(
        Text.from_ansi(
            f"Diff: +{diff['added']} / -{diff['removed']} (base {diff['base_commit']})"
        )
    )
    for entry in summary["entries"]:
        console.print(
            Text.from_ansi(f"{entry['id']}: {entry['question']} [{entry['state']}]")
        )
        if entry.get("error"):
            console.print(Text.from_ansi(f"  {entry['error']}"))
        if "context_output" in entry:
            console.print(Text.from_ansi(f"  Context: {entry['context_output']}"))
        if entry["verdict"] is not None:
            console.print(
                Text.from_ansi(
                    f"  Verdict: {entry['verdict']}\n  Evidence: {entry['evidence']}\n"
                    f"  Reveal: {entry['reveal']}"
                )
            )
    if summary["waivers"]:
        console.print("Waivers", style="yellow")
        for waiver in summary["waivers"]:
            console.print(
                Text.from_ansi(
                    f"  {waiver['id']} [{waiver['state']}]: {waiver['reason']}"
                )
            )
