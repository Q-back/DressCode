"""Review questions and field-wise merging of their sealed expectations."""

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Required, TypedDict, cast


class EntryError(ValueError):
    """An entry cannot be loaded from configuration."""


@dataclass(frozen=True)
class Entry:
    id: str
    question: str
    expects: bool
    reveal: str = ""
    context: str | None = None


class EntryFields(TypedDict, total=False):
    id: Required[str]
    question: str
    expects: bool
    reveal: str
    context: str
    enabled: bool


FIELD_TYPES = {
    "id": str,
    "question": str,
    "expects": bool,
    "reveal": str,
    "context": str,
    "enabled": bool,
}


def merge_entries(layers: Iterable[tuple[Path, object]]) -> tuple[Entry, ...]:
    merged: dict[str, tuple[Path, EntryFields]] = {}
    for source, raw in layers:
        for fields in _parse_fields(raw, source):
            previous = merged.get(fields["id"])
            combined: EntryFields = {**(previous[1] if previous else {}), **fields}
            merged[fields["id"]] = (source, combined)
    return tuple(
        _build_entry(fields, source)
        for source, fields in merged.values()
        if fields.get("enabled", True)
    )


def _parse_fields(raw: object, source: Path) -> list[EntryFields]:
    if not isinstance(raw, list) or any(not isinstance(item, dict) for item in raw):
        raise EntryError(f"{source}: entries must be an array of tables")
    records: list[EntryFields] = []
    for record in raw:
        identifier = record.get("id", "<unknown>")
        label = f"{source}: entry {identifier!r}"
        if not isinstance(record.get("id"), str):
            raise EntryError(f"{label}: missing or invalid required key 'id'")
        for key, value in record.items():
            if key not in FIELD_TYPES:
                raise EntryError(f"{label}: unknown key {key!r}")
            if not isinstance(value, FIELD_TYPES[key]):
                raise EntryError(f"{label}: invalid type for {key!r}")
        records.append(cast(EntryFields, record))
    return records


def _build_entry(fields: EntryFields, source: Path) -> Entry:
    label = f"{source}: entry {fields['id']!r}"
    if "question" not in fields:
        raise EntryError(f"{label}: missing required key 'question'")
    if "expects" not in fields:
        raise EntryError(f"{label}: missing required key 'expects'")
    return Entry(
        fields["id"],
        fields["question"],
        fields["expects"],
        fields.get("reveal", ""),
        fields.get("context"),
    )
