"""Review verdicts and hand-over gate decisions."""

from shlex import quote
from typing import TypedDict

from dresscode.config import Configuration
from dresscode.diff import ScopedDiff, collect
from dresscode.entries import Entry
from dresscode.run import RunState, RunStore
from dresscode.store import EntryStore


class EntryDecision(TypedDict):
    id: str
    question: str
    state: str
    commands: list[str]


class GateDecision(TypedDict):
    status: str
    entries: list[EntryDecision]


def review(
    config: Configuration, strict: bool = False
) -> tuple[ScopedDiff, RunState, GateDecision]:
    retired = EntryStore(config.repository).retirements()
    scoped = collect(config)
    state = RunStore(config.repository).read()
    decisions = []
    for entry in config.entries:
        if entry.id in retired:
            continue
        status = entry_state(entry, state, scoped.fingerprint)
        decisions.append(
            EntryDecision(
                id=entry.id,
                question=entry.question,
                state=status,
                commands=fixing_commands(entry.id, status, strict),
            )
        )
    blocked = any(item["commands"] for item in decisions)
    waived = any(item["state"] == "waived" for item in decisions)
    status = "failed" if blocked else "passed-with-waivers" if waived else "passed"
    return scoped, state, GateDecision(status=status, entries=decisions)


def entry_state(entry: Entry, state: RunState, fingerprint: str) -> str:
    record = state["verdicts"].get(entry.id)
    if record is None:
        return "unanswered"
    if record["fingerprint"] != fingerprint:
        return "stale"
    if record["verdict"] == "context_failed":
        return "context_failed"
    expected = "yes" if entry.expects else "no"
    if record["verdict"] in (expected, "n-a"):
        return "passed"
    waiver = state["waivers"].get(entry.id)
    if waiver is not None:
        return "waived" if waiver["fingerprint"] == fingerprint else "stale"
    return "violated"


def fixing_commands(identifier: str, state: str, strict: bool) -> list[str]:
    if state == "passed" or (state == "waived" and not strict):
        return []
    identifier = quote(identifier)
    commands = [f"dresscode answer {identifier} --yes|--no|--n-a --evidence <text>"]
    if state == "violated":
        commands.append(f"dresscode waive {identifier} --reason <text>")
    if state == "context_failed":
        commands.insert(0, "dresscode list")
    return commands
