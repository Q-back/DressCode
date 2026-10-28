"""Command-line interface for DressCode."""

import ipaddress
import json
import re
import shlex
import unicodedata
from dataclasses import asdict
from importlib.metadata import PackageNotFoundError, distribution
from importlib.resources import files
from typing import Annotated, NoReturn
from urllib.parse import urlsplit

import typer

from dresscode.authoring import append_entry
from dresscode.config import Configuration, ConfigurationError, load
from dresscode.context import execute, required_context
from dresscode.context import trust as trust_context
from dresscode.diff import DiffError, collect, resolve_scope
from dresscode.entries import Entry
from dresscode.gate import review
from dresscode.repo import Repository, RepositoryError, discover
from dresscode.report import render, summarize
from dresscode.run import RunError, RunStore
from dresscode.store import EntryStore, StoreError

JsonOutput = Annotated[
    bool, typer.Option("--json", help="Emit a single JSON document.")
]

BaseSelection = Annotated[
    str | None,
    typer.Option(
        "--base",
        help="Compare with this exact commit/ref; overrides inherited and default baselines.",
    ),
]

app = typer.Typer(
    help="Review recurring coding mistakes against the current diff.",
    add_completion=False,
    no_args_is_help=True,
)

_OFFICIAL_INSTALL_COMMAND = (
    "uv tool install 'git+https://github.com/Q-back/DressCode.git'"
)
_FULL_GIT_COMMIT = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\Z")
_INVALID_PERCENT_ESCAPE = re.compile(r"%(?![0-9a-fA-F]{2})")
_URI_REG_NAME = re.compile(r"(?:[A-Za-z0-9._~!$&'()*+,;=-]|%[0-9a-fA-F]{2})+\Z")


def supported_repository_host(hostname: str) -> bool:
    if ":" in hostname and "%" in hostname:
        return False
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        try:
            ascii_hostname = hostname.encode("idna").decode("ascii")
        except UnicodeError:
            return False
        return _URI_REG_NAME.fullmatch(ascii_hostname) is not None
    return True


def supported_repository_url(url: str) -> bool:
    if (
        any(
            char.isspace() or unicodedata.category(char) == "Cc" or char == "`"
            for char in url
        )
        or "?" in url
        or "#" in url
        or "\\" in url
        or _INVALID_PERCENT_ESCAPE.search(url) is not None
    ):
        return False
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and parsed.hostname is not None
        and supported_repository_host(parsed.hostname)
        and parsed.username is None
        and parsed.password is None
        and (port is None or 0 <= port <= 65535)
        and bool(parsed.path.strip("/"))
    )


def installed_source_pin() -> str | None:
    try:
        raw_url = distribution("dresscode").read_text("direct_url.json")
        if raw_url is None:
            return None
        direct_url = json.loads(raw_url)
    except PackageNotFoundError, OSError, ValueError:
        return None
    if not isinstance(direct_url, dict):
        return None
    vcs_info = direct_url.get("vcs_info")
    if not isinstance(vcs_info, dict) or vcs_info.get("vcs") != "git":
        return None
    url = direct_url.get("url")
    commit = vcs_info.get("commit_id")
    if (
        not isinstance(url, str)
        or not supported_repository_url(url)
        or not isinstance(commit, str)
        or _FULL_GIT_COMMIT.fullmatch(commit) is None
    ):
        return None
    return f"git+{url}@{commit}"


def render_skill() -> str:
    skill = files("dresscode").joinpath("SKILL.md").read_text(encoding="utf-8")
    source = installed_source_pin()
    if source is None:
        return skill
    install_command = f"uv tool install {shlex.quote(source)}"
    return skill.replace(_OFFICIAL_INSTALL_COMMAND, install_command, 1)


@app.callback(invoke_without_command=True)
def options(
    skill: Annotated[
        bool,
        typer.Option(
            "--skill", help="Print the agent skill as Markdown and exit.", is_eager=True
        ),
    ] = False,
) -> None:
    if skill:
        typer.echo(render_skill(), nl=False)
        raise typer.Exit()


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


@app.command("list", help="List sealed questions with trusted context evidence.")
def list_entries(json_output: JsonOutput = False, base: BaseSelection = None) -> None:
    config = configuration(json_output)
    try:
        retired = EntryStore(config.repository).retirements()
        active = [entry for entry in config.entries if entry.id not in retired]
        contextual = [entry for entry in active if entry.context is not None]
        scope = resolve_scope(config, base)
        contexts = {}
        if contextual:
            fingerprint = collect(config, scope).fingerprint
            contexts = {
                entry.id: execute(config, entry, fingerprint, scope)
                for entry in contextual
            }
            RunStore(scope).save_contexts(contexts)
    except (StoreError, RunError, DiffError) as error:
        fail(str(error), json_output)
    entries = []
    for entry in active:
        item = {"id": entry.id, "question": entry.question}
        if entry.id in contexts:
            record = contexts[entry.id]
            item.update(
                {key: record[key] for key in ("state", "context_output", "error")}
            )
        entries.append(item)
    typer.echo(
        json.dumps({**scope.metadata(), "entries": entries})
        if json_output
        else f"Base: {scope.base_commit}\n"
        + "\n".join(
            f"{entry['id']}: {entry['question']}"
            + (
                f"\n  Context: {entry['context_output']}"
                if "context_output" in entry
                else ""
            )
            + (
                f"\n  [{entry['state']}] {entry['error']}"
                if bool(entry.get("error"))
                else ""
            )
            for entry in entries
        )
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
    base: BaseSelection = None,
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
        scoped = collect(config, resolve_scope(config, base))
    except DiffError as error:
        fail(str(error), json_output)
    verdict = "n-a" if not_applicable else "yes" if yes else "no"
    answer_value = None if not_applicable else yes
    expected = "yes" if entry.expects else "no"
    matched = verdict == "n-a" or verdict == expected
    try:
        run = RunStore(scoped.scope)
        context_output = None
        if entry.context is not None:
            context = required_context(
                config, entry, run.read(), scoped.fingerprint, scoped.scope
            )
            if context["state"] != "ready":
                fail(context["error"], json_output)
            context_output = context["context_output"]
        record = run.record(
            entry,
            verdict,
            evidence.strip(),
            scoped.fingerprint,
            after_save=lambda: EntryStore(config.repository).record(
                entry, answer_value
            ),
            context_output=context_output,
            context_command=entry.context,
        )
    except (RunError, StoreError) as error:
        fail(str(error), json_output)
    response = {
        **scoped.scope.metadata(),
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
    typer.echo(f"Base: {scoped.base_commit}")
    typer.echo(
        f"Recorded {identifier}: {verdict} (expected {expected}; "
        f"matched: {'yes' if matched else 'no'})."
    )
    if entry.reveal:
        typer.echo(f"Reveal: {entry.reveal}")


@app.command("check", help="Gate hand-over on current verdicts and waivers.")
def check(
    strict: Annotated[bool, typer.Option(help="Reject waivers too.")] = False,
    json_output: JsonOutput = False,
    base: BaseSelection = None,
) -> None:
    config = configuration(json_output)
    try:
        _, state, decision = review(config, strict, resolve_scope(config, base))
    except (DiffError, RunError, StoreError) as error:
        fail(str(error), json_output)
    if json_output:
        typer.echo(json.dumps(decision))
    else:
        typer.echo(f"Base: {decision['base_commit']}")
        typer.echo(decision["status"])
        for entry in decision["entries"]:
            if entry["commands"]:
                typer.echo(f"{entry['id']}: {entry['question']} [{entry['state']}]")
                if bool(entry.get("error")):
                    typer.echo(f"  {entry['error']}")
                if entry["state"] == "waived":
                    typer.echo(f"  Waiver: {state['waivers'][entry['id']]['reason']}")
                for command in entry["commands"]:
                    typer.echo(f"  {command}")
    raise typer.Exit(code=1 if decision["status"] == "failed" else 0)


@app.command("waive", help="Document a current violation that may ship.")
def waive(
    identifier: str,
    reason: Annotated[str, typer.Option("--reason")] = "",
    json_output: JsonOutput = False,
    base: BaseSelection = None,
) -> None:
    config = configuration(json_output)
    try:
        retired = EntryStore(config.repository).retirements()
        entry = next(
            (
                item
                for item in config.entries
                if item.id == identifier and item.id not in retired
            ),
            None,
        )
        if entry is None:
            fail(f"Unknown entry: {identifier}", json_output)
        scoped = collect(config, resolve_scope(config, base))
        waiver = RunStore(scoped.scope).waive(entry, reason, scoped.fingerprint)
    except (DiffError, RunError, StoreError) as error:
        fail(str(error), json_output)
    typer.echo(
        json.dumps(
            {**scoped.scope.metadata(), "status": "waived", "id": identifier, **waiver}
        )
        if json_output
        else f"Base: {scoped.base_commit}\nWaived {identifier}: {waiver['reason']}"
    )


@app.command("report", help="Summarize verdicts, evidence and waivers.")
def report(json_output: JsonOutput = False, base: BaseSelection = None) -> None:
    config = configuration(json_output)
    try:
        scoped, state, decision = review(config, scope=resolve_scope(config, base))
    except (DiffError, RunError, StoreError) as error:
        fail(str(error), json_output)
    summary = summarize(config, scoped, state, decision)
    if json_output:
        typer.echo(json.dumps(summary))
    else:
        render(summary)


@app.command("reset", help="Clear the current review run.")
def reset(json_output: JsonOutput = False, base: BaseSelection = None) -> None:
    config = configuration(json_output)
    try:
        scope = resolve_scope(config, base)
        run = RunStore(scope)
        run.reset()
    except (RunError, DiffError) as error:
        fail(str(error), json_output)
    typer.echo(
        json.dumps({"status": "reset", **scope.metadata()})
        if json_output
        else f"Base: {scope.base_commit}\nReset review run {run.run_key}"
    )


@app.command(
    "diff",
    help=(
        "Show file counts from the merge base of HEAD and the selected base "
        "to the working tree. Includes committed, staged, unstaged and untracked "
        "non-ignored files. Configured diff exclusions apply.\n\n"
        "Base priority: configured merge_base_with, origin/HEAD, local main, local master, "
        "then the root commit. An invalid configured merge_base_with is an error, "
        "not a fallback. REF or --base selects an exact commit, even with unrelated "
        "history, and bypasses the default target. Explicit selection wins over "
        "inherited DRESSCODE_BASE_COMMIT, then defaults. Supplying both selectors "
        "is an error."
    ),
)
def show_diff(
    reference: Annotated[
        str | None, typer.Argument(help="Exact baseline; shorthand for --base.")
    ] = None,
    numstat: Annotated[
        bool, typer.Option(help="Emit tab-separated counts and paths.")
    ] = False,
    json_output: JsonOutput = False,
    base: BaseSelection = None,
) -> None:
    if reference is not None and base is not None:
        fail("Cannot supply both REF and --base", json_output)
    selected = reference if reference is not None else base
    config = configuration(json_output)
    try:
        scoped = collect(config, resolve_scope(config, selected))
    except DiffError as error:
        fail(str(error), json_output)
    if json_output:
        typer.echo(
            json.dumps(
                {
                    **scoped.scope.metadata(),
                    "files": [asdict(file) for file in scoped.files],
                    "fingerprint": scoped.fingerprint,
                    "totals": {"added": scoped.added, "removed": scoped.removed},
                }
            )
        )
        return
    typer.echo(f"Base: {scoped.base_commit}", err=numstat)
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


@app.command("trust", help="Trust the current repository-local context configuration.")
def trust(json_output: JsonOutput = False) -> None:
    config = configuration(json_output)
    try:
        trust_context(config)
    except RunError as error:
        fail(str(error), json_output)
    typer.echo(
        json.dumps({"status": "trusted", "hash": config.local_hash})
        if json_output
        else "Trusted current repository-local context commands."
    )


def main() -> None:
    """Run the DressCode command-line application."""
    app()
