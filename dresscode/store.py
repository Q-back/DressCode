"""Repository-scoped entry metadata, independent of configuration layers."""

import json
import os
import sqlite3
from collections.abc import Generator
from contextlib import closing, contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dresscode.entries import Entry
from dresscode.repo import Repository


class StoreError(ValueError):
    """Entry metadata could not be read or written."""


@dataclass(frozen=True)
class Counters:
    asked: int = 0
    violated: int = 0
    n_a: int = 0
    last_violated: str | None = None


class EntryStore:
    def __init__(self, repository: Repository) -> None:
        home = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state")
        self.path = home / "dresscode" / "entries.sqlite3"
        self.repo_id = repository.identity

    def counters(self, identifier: str) -> Counters:
        if not self.path.exists():
            return Counters()
        with self._connection() as database:
            row = database.execute(
                "SELECT asked, violated, n_a, last_violated FROM counters WHERE repo=? AND id=?",
                (self.repo_id, identifier),
            ).fetchone()
        return Counters(*row) if row is not None else Counters()

    def record(self, entry: Entry, verdict: bool | None) -> None:
        violated = verdict is not None and verdict != entry.expects
        timestamp = datetime.now(UTC).isoformat() if violated else None
        with self._connection() as database:
            database.execute(
                """INSERT INTO counters VALUES (?, ?, 1, ?, ?, ?)
                ON CONFLICT(repo, id) DO UPDATE SET
                    asked = asked + 1, violated = violated + excluded.violated,
                    n_a = n_a + excluded.n_a,
                    last_violated = COALESCE(excluded.last_violated, last_violated)""",
                (
                    self.repo_id,
                    entry.id,
                    int(violated),
                    int(verdict is None),
                    timestamp,
                ),
            )

    def retire(self, entry: Entry, reason: str) -> None:
        with self._connection() as database:
            database.execute(
                "INSERT INTO retired VALUES (?, ?, ?, ?, ?)",
                (
                    self.repo_id,
                    entry.id,
                    reason,
                    datetime.now(UTC).isoformat(),
                    json.dumps(asdict(entry)),
                ),
            )

    def retirements(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        with self._connection() as database:
            rows = database.execute(
                "SELECT id, reason, timestamp, entry FROM retired WHERE repo=?",
                (self.repo_id,),
            ).fetchall()
        return {
            identifier: {
                "reason": reason,
                "timestamp": timestamp,
                "entry": json.loads(snapshot),
            }
            for identifier, reason, timestamp, snapshot in rows
        }

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection]:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(self.path)) as database, database:
                database.execute(
                    """CREATE TABLE IF NOT EXISTS counters (
                        repo TEXT NOT NULL, id TEXT NOT NULL,
                        asked INTEGER NOT NULL DEFAULT 0,
                        violated INTEGER NOT NULL DEFAULT 0,
                        n_a INTEGER NOT NULL DEFAULT 0, last_violated TEXT,
                        PRIMARY KEY(repo, id))"""
                )
                database.execute(
                    """CREATE TABLE IF NOT EXISTS retired (
                        repo TEXT NOT NULL, id TEXT NOT NULL, reason TEXT NOT NULL,
                        timestamp TEXT NOT NULL, entry TEXT NOT NULL,
                        PRIMARY KEY(repo, id))"""
                )
                yield database
        except (OSError, sqlite3.Error) as error:
            raise StoreError(f"{self.path}: {error}") from error
