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
    "answer": "Record a verdict with evidence.",
    "check": "Check whether the review passes.",
    "report": "Summarize the review.",
    "reset": "Clear the current review.",
    "trust": "Trust repository-local context commands.",
    "waive": "Document a violation that may ship.",
}.items():
    app.command(name, help=f"{description} Unavailable: not implemented.")(
        unimplemented
    )


def main() -> None:
    """Run the DressCode command-line application."""
    app()
