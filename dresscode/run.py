"""Repository- and branch-keyed review state."""

import fcntl
import hashlib
import json
import os
import subprocess
import tempfile
from collections.abc import Callable, Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, TypedDict, cast

from dresscode.entries import Entry
from dresscode.repo import Repository


class RunError(ValueError):
    """A run key or its state cannot be read or written."""


class VerdictRecord(TypedDict):
    verdict: str
    evidence: str
    fingerprint: str
    timestamp: str


class HistoryRecord(VerdictRecord):
    id: str


class RunState(TypedDict):
    run_key: str
    verdicts: dict[str, VerdictRecord]
    history: list[HistoryRecord]
    waivers: dict[str, dict[str, Any]]


class RunStore:
    """Read and atomically update one repository-and-branch review run."""

    def __init__(self, repository: Repository) -> None:
        self.run_key = _run_key(repository)
        home = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state")
        filename = hashlib.sha256(self.run_key.encode()).hexdigest() + ".json"
        self.path = home / "dresscode" / "runs" / filename

    def read(self) -> RunState:
        with self._lock():
            return self._read()

    def _read(self) -> RunState:
        if not self.path.exists():
            return _empty_state(self.run_key)
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise RunError(f"{self.path}: {error}") from error
        if not _valid_state(document, self.run_key):
            raise RunError(f"{self.path}: invalid run state")
        return cast(RunState, document)

    def record(
        self,
        entry: Entry,
        verdict: Literal["yes", "no", "n-a"],
        evidence: str,
        fingerprint: str,
        after_save: Callable[[], None] | None = None,
    ) -> VerdictRecord:
        with self._lock():
            previous_state = self._read()
            state = _copy_state(previous_state)
            previous = state["verdicts"].get(entry.id)
            if previous is not None:
                state["history"].append({"id": entry.id, **previous})
            record: VerdictRecord = {
                "verdict": verdict,
                "evidence": evidence,
                "fingerprint": fingerprint,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            state["verdicts"][entry.id] = record
            self._write(state)
            if after_save is not None:
                try:
                    after_save()
                except Exception as error:
                    try:
                        self._write(previous_state)
                    except RunError as rollback_error:
                        raise RunError(
                            f"{self.path}: cannot restore state after failed answer: "
                            f"{rollback_error}"
                        ) from error
                    raise
            return record

    def stale_verdicts(self, fingerprint: str) -> tuple[str, ...]:
        state = self.read()
        return tuple(
            sorted(
                identifier
                for identifier, record in state["verdicts"].items()
                if record["fingerprint"] != fingerprint
            )
        )

    def reset(self) -> None:
        with self._lock():
            state = self._read()
            state["verdicts"] = {}
            state["waivers"] = {}
            self._write(state)

    @contextmanager
    def _lock(self) -> Generator[None]:
        lock_path = self.path.with_suffix(f"{self.path.suffix}.lock")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with lock_path.open("a", encoding="utf-8") as lockfile:
                fcntl.flock(lockfile.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lockfile.fileno(), fcntl.LOCK_UN)
        except OSError as error:
            raise RunError(f"{lock_path}: {error}") from error

    def _write(self, state: RunState) -> None:
        temporary: Path | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                delete=False,
            ) as output:
                temporary = Path(output.name)
                json.dump(state, output, indent=2, sort_keys=True)
                output.write("\n")
            os.replace(temporary, self.path)
        except (OSError, TypeError, ValueError) as error:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            raise RunError(f"{self.path}: {error}") from error


def _copy_state(state: RunState) -> RunState:
    return {
        "run_key": state["run_key"],
        "verdicts": state["verdicts"].copy(),
        "history": state["history"].copy(),
        "waivers": state["waivers"].copy(),
    }


def _empty_state(run_key: str) -> RunState:
    return {"run_key": run_key, "verdicts": {}, "history": [], "waivers": {}}


def _valid_state(document: object, run_key: str) -> bool:
    if not isinstance(document, dict) or document.get("run_key") != run_key:
        return False
    verdicts = document.get("verdicts")
    history = document.get("history")
    waivers = document.get("waivers")
    if not isinstance(verdicts, dict) or not isinstance(history, list):
        return False
    if not isinstance(waivers, dict):
        return False
    for record in (*verdicts.values(), *history):
        if not isinstance(record, dict) or not all(
            isinstance(record.get(field), str)
            for field in ("verdict", "evidence", "fingerprint", "timestamp")
        ):
            return False
    return all(isinstance(identifier, str) for identifier in verdicts)


def _run_key(repository: Repository) -> str:
    branch = _git(
        repository.root,
        "symbolic-ref",
        "--quiet",
        "--short",
        "HEAD",
        allowed_codes=(0, 1),
    )
    if branch:
        return f"{repository.identity}:{branch}"
    short_sha = _git(repository.root, "rev-parse", "--short", "HEAD")
    return f"{repository.identity}:detached-{short_sha}"


def _git(root: Path, *arguments: str, allowed_codes: tuple[int, ...] = (0,)) -> str:
    try:
        result = subprocess.run(
            ["git", *arguments], cwd=root, capture_output=True, text=True, check=False
        )
    except OSError as error:
        raise RunError(f"Cannot run Git at {root}: {error}") from error
    if result.returncode not in allowed_codes:
        message = result.stderr.strip() or result.stdout.strip()
        raise RunError(f"Git at {root}: {message}")
    return result.stdout.strip()
