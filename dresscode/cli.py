"""Command-line interface for DressCode."""

import json
from typing import Annotated, NoReturn

import typer

app = typer.Typer(
    help="Review recurring coding mistakes against the current diff.",
    add_completion=False,
    no_args_is_help=True,
)


def unimplemented(
    ctx: typer.Context,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit a single JSON document.")
    ] = False,
) -> NoReturn:
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
