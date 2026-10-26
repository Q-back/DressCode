"""Human-readable review summaries."""

import sys
from typing import Any

from rich.console import Console
from rich.padding import Padding
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
    color = {"failed": "red", "passed": "green", "passed-with-waivers": "yellow"}[
        summary["status"]
    ]
    console.print(Text(summary["status"], style=f"bold {color}"))
    diff = summary["diff"]
    console.print(
        Text.from_ansi(
            f"Diff: +{diff['added']} / -{diff['removed']} (base {diff['base_commit']})"
        )
    )
    for entry in summary["entries"]:
        _render_entry(console, entry)
    if summary["waivers"]:
        console.print()
        console.print(Text("Waivers", style="bold yellow"))
        for waiver in summary["waivers"]:
            console.print()
            console.print(
                Text.from_ansi(
                    f"  {waiver['id']} [{waiver['state']}]: {waiver['reason']}"
                )
            )


def _render_entry(console: Console, entry: dict[str, Any]) -> None:
    color = {
        "passed": "green",
        "violated": "red",
        "context_failed": "red",
        "stale": "yellow",
        "unanswered": "yellow",
        "waived": "yellow",
        "context_untrusted": "yellow",
    }[entry["state"]]
    console.print()
    console.print(Text("-" * console.width))
    heading = Text(f"Rule: {Text.from_ansi(entry['id']).plain}", style="bold cyan")
    heading.append(f" [{entry['state']}]", style=f"bold {color}")
    console.print(heading)
    _render_field(console, "Question", entry["question"], style="dim")
    verdict = entry["verdict"] or "unanswered"
    if verdict in ("yes", "no") and verdict != entry["expected"]:
        verdict += f" (expected {entry['expected']})"
    _render_field(console, "Verdict", verdict, style=f"bold {color}")
    if entry["verdict"] is not None:
        _render_field(console, "Evidence", entry["evidence"], stacked=True)
    if "context_output" in entry:
        _render_field(console, "Context", entry["context_output"], stacked=True)
    if entry.get("error"):
        _render_field(
            console, "Context error", entry["error"], style="red", stacked=True
        )
    if entry["verdict"] is not None:
        _render_field(console, "Reveal", entry["reveal"], style="dim")


def _render_field(
    console: Console, label: str, value: str, *, style: str = "", stacked: bool = False
) -> None:
    console.print()
    field = Text(style=style)
    field.append(f"{label}:", style="bold")
    content = Text.from_ansi(value).plain
    if stacked:
        console.print(field)
        console.print(Padding(Text(content, style=style), (0, 0, 0, 2)))
    else:
        field.append(f" {content}", style=style)
        console.print(field)
