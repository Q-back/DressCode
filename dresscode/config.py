"""Optional global, repository-local and private configuration layers."""

import hashlib
import math
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

from dresscode.entries import Entry, EntryError, merge_entries
from dresscode.repo import Repository


class ConfigurationError(ValueError):
    """A configuration file cannot be read or validated."""


@dataclass(frozen=True)
class Configuration:
    repository: Repository
    settings: dict[str, Any]
    entries: tuple[Entry, ...]
    local_contexts: frozenset[str] = frozenset()
    local_hash: str = ""


def load(repository: Repository) -> Configuration:
    settings: dict[str, Any] = {}
    entry_layers: list[tuple[Path, object]] = []
    context_layers: dict[str, str] = {}
    local_hash = hashlib.sha256()
    for layer, paths in layer_paths(repository).items():
        for path in paths:
            if not path.exists():
                continue
            try:
                content = path.read_bytes()
                document = tomllib.loads(content.decode("utf-8"))
            except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
                raise ConfigurationError(f"{path}: {error}") from error
            settings = _merge_settings(
                settings,
                {key: value for key, value in document.items() if key != "entries"},
            )
            raw_entries = document.get("entries", [])
            entry_layers.append((path, raw_entries))
            if layer == "repo":
                local_hash.update(path.name.encode() + b"\0" + content + b"\0")
            if isinstance(raw_entries, list):
                for fields in raw_entries:
                    if (
                        isinstance(fields, dict)
                        and isinstance(fields.get("id"), str)
                        and "context" in fields
                    ):
                        context_layers[fields["id"]] = layer
            context = document.get("context", {})
            timeout = (
                context.get("timeout_seconds", 10)
                if isinstance(context, dict)
                else None
            )
            if (
                isinstance(timeout, bool)
                or not isinstance(timeout, (int, float))
                or not math.isfinite(timeout)
                or timeout <= 0
            ):
                raise ConfigurationError(
                    f"{path}: context.timeout_seconds must be positive and finite"
                )
    try:
        entries = merge_entries(entry_layers)
    except EntryError as error:
        raise ConfigurationError(str(error)) from error
    return Configuration(
        repository,
        settings,
        entries,
        frozenset(
            identifier
            for identifier, layer in context_layers.items()
            if layer == "repo"
        ),
        local_hash.hexdigest(),
    )


def layer_paths(repository: Repository) -> dict[str, tuple[Path, ...]]:
    home = (
        Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "dresscode"
    )
    local_directory = repository.root / ".dresscode"
    local_files = (
        tuple(sorted(local_directory.glob("*.toml")))
        if local_directory.is_dir()
        else (repository.root / ".dresscode.toml",)
    )
    return {
        "global": (home / "config.toml",),
        "repo": local_files,
        "private": (home / "repos" / f"{quote(repository.identity, safe='')}.toml",),
    }


def _merge_settings(lower: dict[str, Any], higher: dict[str, Any]) -> dict[str, Any]:
    merged = lower.copy()
    for key, value in higher.items():
        previous = merged.get(key)
        merged[key] = (
            _merge_settings(previous, value)
            if isinstance(previous, dict) and isinstance(value, dict)
            else value
        )
    return merged
