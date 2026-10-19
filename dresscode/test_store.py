from dataclasses import replace
from pathlib import Path

from dresscode.config import load
from dresscode.repo import discover
from dresscode.store import Counters, EntryStore


def test_counters_are_global_and_survive_read_only_configuration(
    git_repo: Path, xdg_home: Path
) -> None:
    rules = git_repo / ".dresscode.toml"
    original = '[[entries]]\nid = "factory"\nquestion = "Reuse?"\nexpects = true\n'
    rules.write_text(original)
    rules.chmod(0o444)
    try:
        repository = discover(git_repo)
        entry = load(repository).entries[0]
        store = EntryStore(repository)
        assert store.counters(entry.id) == Counters()
        assert not store.path.exists()
        store.record(entry, False)
        first = store.counters(entry.id)
        assert first.asked == 1 and first.violated == 1
        assert first.last_violated is not None
        store.record(entry, True)
        store.record(entry, None)
        assert EntryStore(repository).counters(entry.id) == Counters(
            asked=3, violated=1, n_a=1, last_violated=first.last_violated
        )
        assert store.path.is_relative_to(xdg_home / "state" / "dresscode")
        assert rules.read_text() == original
        assert (
            EntryStore(replace(repository, identity="another/repo")).counters(entry.id)
            == Counters()
        )
    finally:
        rules.chmod(0o644)
