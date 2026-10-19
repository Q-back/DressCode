"""Optional global, repository-local and private configuration layers."""

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


def load(repository: Repository) -> Configuration:
    settings: dict[str, Any] = {}
    entry_layers: list[tuple[Path, object]] = []
    for paths in layer_paths(repository).values():
        for path in paths:
            if not path.exists():
                continue
            try:
                document = tomllib.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
                raise ConfigurationError(f"{path}: {error}") from error
            settings = _merge_settings(
                settings,
                {key: value for key, value in document.items() if key != "entries"},
            )
            entry_layers.append((path, document.get("entries", [])))
    try:
        entries = merge_entries(entry_layers)
    except EntryError as error:
        raise ConfigurationError(str(error)) from error
    return Configuration(repository, settings, entries)


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
