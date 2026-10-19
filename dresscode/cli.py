"""Command-line interface for DressCode."""

import json
from typing import Annotated, NoReturn

import typer

from dresscode.config import Configuration, ConfigurationError, load
from dresscode.repo import Repository, RepositoryError, discover

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
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit a single JSON document.")
    ] = False,
) -> NoReturn:
    configuration(json_output)
    if json_output:
        typer.echo(json.dumps({"command": ctx.info_name, "status": "unimplemented"}))
    else:
        typer.echo(f"dresscode {ctx.info_name} is not implemented yet.", err=True)
    raise typer.Exit(code=2)


for name, description in {
    "add": "Add a review question.",
    "answer": "Record a verdict with evidence.",
    "check": "Check whether the review passes.",
    "diff": "Show the scoped change under review.",
    "list": "List questions with expectations sealed.",
    "report": "Summarize the review.",
    "reset": "Clear the current review.",
    "retire": "Retire a question.",
    "trust": "Trust repository-local context commands.",
    "waive": "Document a violation that may ship.",
}.items():
    app.command(name, help=f"{description} Unavailable: not implemented.")(
        unimplemented
    )


def main() -> None:
    """Run the DressCode command-line application."""
    app()
