"""Append entry definitions without rewriting unrelated TOML content."""

from dataclasses import asdict
from pathlib import Path

import tomlkit
from tomlkit.exceptions import ParseError
from tomlkit.items import AoT, Array

from dresscode.config import ConfigurationError, layer_paths
from dresscode.entries import Entry
from dresscode.repo import Repository


def append_entry(repository: Repository, entry: Entry, layer: str) -> Path:
    paths = layer_paths(repository)
    if layer not in paths:
        raise ConfigurationError("layer must be repo, private or global")
    candidates = paths[layer]
    destination = (
        candidates[-1] if candidates else repository.root / ".dresscode" / "rules.toml"
    )
    try:
        document = (
            tomlkit.parse(destination.read_text(encoding="utf-8"))
            if destination.exists()
            else tomlkit.document()
        )
        if "entries" not in document:
            document["entries"] = tomlkit.aot()
        entries = document["entries"]
        if not isinstance(entries, (AoT, Array)):
            raise ConfigurationError(
                f"{destination}: entries must be an array of tables"
            )
        entries.append(
            {key: value for key, value in asdict(entry).items() if value is not None}
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(tomlkit.dumps(document), encoding="utf-8")
    except (OSError, UnicodeError, ParseError) as error:
        raise ConfigurationError(f"{destination}: {error}") from error
    return destination
