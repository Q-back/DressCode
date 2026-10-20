"""Command-line interface for DressCode."""

import json
from dataclasses import asdict
from typing import Annotated, NoReturn

import typer

from dresscode.authoring import append_entry
from dresscode.config import Configuration, ConfigurationError, load
from dresscode.diff import DiffError, collect
from dresscode.entries import Entry
from dresscode.repo import Repository, RepositoryError, discover
from dresscode.run import RunError, RunStore
from dresscode.store import EntryStore, StoreError

JsonOutput = Annotated[
    bool, typer.Option("--json", help="Emit a single JSON document.")
]

app = typer.Typer(
    help="Review recurring coding mistakes against the current diff.",
    add_completion=False,
    no_args_is_help=True,
)


def fail(message: str, json_output: bool) -> NoReturn:
    if json_output:
        typer.echo(json.dumps({"status": "error", "error": message}))
    else:
        typer.echo(message, err=True)
    raise typer.Exit(code=2)


def repository(json_output: bool) -> Repository:
    try:
        return discover()
    except RepositoryError as error:
        fail(str(error), json_output)


def configuration(json_output: bool) -> Configuration:
    try:
        return load(repository(json_output))
    except ConfigurationError as error:
        fail(str(error), json_output)


def unimplemented(
    ctx: typer.Context,
    json_output: JsonOutput = False,
) -> NoReturn:
    configuration(json_output)
    if json_output:
        typer.echo(json.dumps({"command": ctx.info_name, "status": "unimplemented"}))
    else:
        typer.echo(f"dresscode {ctx.info_name} is not implemented yet.", err=True)
    raise typer.Exit(code=2)


@app.command("add", help="Append a review question to a configuration layer.")
def add(
    identifier: str,
    question: Annotated[str, typer.Option("--question")],
    expects: Annotated[
        str, typer.Option("--expects", help="Expected answer: true or false.")
    ],
    reveal: str = "",
    context: str | None = None,
    layer: Annotated[
        str,
        typer.Option(
            help="Write to: repo (shared repository config), private (personal "
            "overrides for this repository), or global (defaults for all repositories)."
        ),
    ] = "repo",
    json_output: JsonOutput = False,
) -> None:
    config = configuration(json_output)
    if expects not in ("true", "false"):
        fail("expects must be true or false", json_output)
    entry = Entry(identifier, question, expects == "true", reveal, context)
    try:
        path = append_entry(config.repository, entry, layer)
    except ConfigurationError as error:
        fail(str(error), json_output)
    typer.echo(
        json.dumps({"status": "added", "id": identifier, "path": str(path)})
        if json_output
        else f"Added {identifier} to {path}"
    )


@app.command("retire", help="Retire a question, keeping its history.")
def retire(identifier: str, reason: str = "", json_output: JsonOutput = False) -> None:
    config = configuration(json_output)
    entry = next((entry for entry in config.entries if entry.id == identifier), None)
    if entry is None:
        fail(f"Unknown entry: {identifier}", json_output)
    store = EntryStore(config.repository)
    try:
        if identifier in store.retirements():
            fail(f"Entry already retired: {identifier}", json_output)
        store.retire(entry, reason)
    except StoreError as error:
        fail(str(error), json_output)
    typer.echo(
        json.dumps({"status": "retired", "id": identifier, "reason": reason})
        if json_output
        else f"Retired {identifier}"
    )


@app.command(
    "list", help="List questions with expectations sealed. Context is not executed."
)
def list_entries(json_output: JsonOutput = False) -> None:
    config = configuration(json_output)
    try:
        retired = EntryStore(config.repository).retirements()
    except StoreError as error:
        fail(str(error), json_output)
    entries = [
        {"id": entry.id, "question": entry.question}
        for entry in config.entries
        if entry.id not in retired
    ]
    typer.echo(
        json.dumps({"entries": entries})
        if json_output
        else "\n".join(f"{entry['id']}: {entry['question']}" for entry in entries)
    )


@app.command("answer", help="Record a verdict with evidence.")
def answer(
    identifier: str,
    yes: Annotated[bool, typer.Option("--yes", help="Answer yes.")] = False,
    no: Annotated[bool, typer.Option("--no", help="Answer no.")] = False,
    not_applicable: Annotated[
        bool, typer.Option("--n-a", help="Mark the question not applicable.")
    ] = False,
    evidence: Annotated[str, typer.Option("--evidence")] = "",
    json_output: JsonOutput = False,
) -> None:
    config = configuration(json_output)
    selected = sum((yes, no, not_applicable))
    if selected != 1:
        fail("Choose exactly one of --yes, --no or --n-a", json_output)
    if not evidence.strip():
        fail("--evidence must not be empty", json_output)
    try:
        retired = EntryStore(config.repository).retirements()
    except StoreError as error:
        fail(str(error), json_output)
    entry = next(
        (
            item
            for item in config.entries
            if item.id == identifier and identifier not in retired
        ),
        None,
    )
    if entry is None:
        fail(f"Unknown entry: {identifier}", json_output)
    try:
        scoped = collect(config)
    except DiffError as error:
        fail(str(error), json_output)
    verdict = "n-a" if not_applicable else "yes" if yes else "no"
    answer_value = None if not_applicable else yes
    expected = "yes" if entry.expects else "no"
    matched = verdict == "n-a" or verdict == expected
    try:
        record = RunStore(config.repository).record(
            entry, verdict, evidence.strip(), scoped.fingerprint
        )
        EntryStore(config.repository).record(entry, answer_value)
    except (RunError, StoreError) as error:
        fail(str(error), json_output)
    response = {
        "status": "recorded",
        "id": identifier,
        "verdict": verdict,
        "expected": expected,
        "matched": matched,
        "evidence": evidence.strip(),
        "fingerprint": scoped.fingerprint,
        "timestamp": record["timestamp"],
        "reveal": entry.reveal,
    }
    if json_output:
        typer.echo(json.dumps(response))
        return
    typer.echo(
        f"Recorded {identifier}: {verdict} (expected {expected}; "
        f"matched: {'yes' if matched else 'no'})."
    )
    if entry.reveal:
        typer.echo(f"Reveal: {entry.reveal}")


@app.command("reset", help="Clear the current review run.")
def reset(json_output: JsonOutput = False) -> None:
    config = configuration(json_output)
    try:
        run = RunStore(config.repository)
        run.reset()
    except RunError as error:
        fail(str(error), json_output)
    typer.echo(
        json.dumps({"status": "reset", "run_key": run.run_key})
        if json_output
        else f"Reset review run {run.run_key}"
    )


@app.command("diff", help="Show the scoped change under review.")
def show_diff(
    numstat: Annotated[
        bool, typer.Option(help="Emit tab-separated counts and paths.")
    ] = False,
    json_output: JsonOutput = False,
) -> None:
    config = configuration(json_output)
    try:
        scoped = collect(config)
    except DiffError as error:
        fail(str(error), json_output)
    if json_output:
        typer.echo(
            json.dumps(
                {
                    **asdict(scoped),
                    "totals": {"added": scoped.added, "removed": scoped.removed},
                }
            )
        )
        return
    typer.echo(f"Base: {scoped.base_ref} (merge base {scoped.merge_base})", err=numstat)
    if not numstat:
        typer.echo("Added\tRemoved\tPath")
    for file in scoped.files:
        path = (
            json.dumps(file.path)
            if any(character in file.path for character in '\t\n\r"\\')
            else file.path
        )
        counts = "-\t-" if file.added is None else f"{file.added}\t{file.removed}"
        typer.echo(f"{counts}\t{path}")
    typer.echo(f"{scoped.added}\t{scoped.removed}\tTOTAL")


for name, description in {
    "check": "Check whether the review passes.",
    "report": "Summarize the review.",
    "trust": "Trust repository-local context commands.",
    "waive": "Document a violation that may ship.",
}.items():
    app.command(name, help=f"{description} Unavailable: not implemented.")(
        unimplemented
    )


def main() -> None:
    """Run the DressCode command-line application."""
    app()
