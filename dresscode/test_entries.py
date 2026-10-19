from pathlib import Path

import pytest

from dresscode.entries import Entry, EntryError, merge_entries


def test_minimal_entry_and_optional_defaults() -> None:
    entries = merge_entries(
        [
            (
                Path("rules.toml"),
                [{"id": "factory", "question": "Reuse?", "expects": True}],
            )
        ]
    )
    assert entries == (Entry("factory", "Reuse?", True),)


def test_entries_merge_fields_and_disable_by_id() -> None:
    global_entries = [
        {
            "id": "factory",
            "question": "Reuse?",
            "expects": True,
            "reveal": "Use a factory.",
        },
        {"id": "size", "question": "Small?", "expects": True},
    ]
    result = merge_entries(
        [
            (Path("global.toml"), global_entries),
            (Path("repo.toml"), [{"id": "factory", "question": "Existing factory?"}]),
            (Path("private.toml"), [{"id": "size", "enabled": False}]),
        ]
    )
    assert result == (Entry("factory", "Existing factory?", True, "Use a factory."),)


@pytest.mark.parametrize(
    ("fields", "key"),
    [
        ({}, "id"),
        ({"id": "factory"}, "question"),
        ({"id": "factory", "question": "Reuse?"}, "expects"),
        ({"id": "factory", "question": "Reuse?", "expects": "yes"}, "expects"),
        ({"id": "factory", "question": 42, "expects": True}, "question"),
        (
            {
                "id": "factory",
                "question": "Reuse?",
                "expects": True,
                "severity": "high",
            },
            "severity",
        ),
        (
            {"id": "factory", "question": "Reuse?", "expects": True, "reveal": False},
            "reveal",
        ),
        (
            {"id": "factory", "question": "Reuse?", "expects": True, "context": []},
            "context",
        ),
        ({"id": "factory", "enabled": "false"}, "enabled"),
    ],
)
def test_entry_errors_name_file_entry_and_key(
    fields: dict[str, object], key: str
) -> None:
    with pytest.raises(EntryError) as failure:
        merge_entries([(Path("rules.toml"), [fields])])
    message = str(failure.value)
    assert "rules.toml" in message
    assert key in message
    if "id" in fields:
        assert "factory" in message


@pytest.mark.parametrize("entries", [True, {}, ["not a table"]])
def test_entries_must_be_an_array_of_tables(entries: object) -> None:
    with pytest.raises(EntryError, match="array of tables"):
        merge_entries([(Path("rules.toml"), entries)])


def test_context_is_only_loaded_not_executed(tmp_path: Path) -> None:
    marker = tmp_path / "executed"
    command = f"touch {marker}"
    entries = merge_entries(
        [
            (
                Path("rules.toml"),
                [
                    {
                        "id": "context",
                        "question": "Q?",
                        "expects": False,
                        "context": command,
                    }
                ],
            )
        ]
    )
    assert entries[0].context == command
    assert not marker.exists()
