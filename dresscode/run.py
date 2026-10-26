"""Baseline-keyed review state."""

import fcntl
import hashlib
import json
import os
import tempfile
from collections.abc import Callable, Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, NotRequired, TypedDict, cast

from dresscode.diff import ResolvedScope
from dresscode.entries import Entry


class RunError(ValueError):
    """A run key or its state cannot be read or written."""


class ContextRecord(TypedDict):
    state: str
    context_output: str
    error: str
    command: str
    fingerprint: str


class VerdictRecord(TypedDict):
    verdict: str
    evidence: str
    fingerprint: str
    timestamp: str
    context_output: NotRequired[str]
    context_command: NotRequired[str]


class HistoryRecord(VerdictRecord):
    id: str


class WaiverRecord(TypedDict):
    reason: str
    fingerprint: str
    timestamp: str


class RunState(TypedDict):
    run_key: str
    verdicts: dict[str, VerdictRecord]
    history: list[HistoryRecord]
    waivers: dict[str, WaiverRecord]
    contexts: dict[str, ContextRecord]


class RunStore:
    """Read and atomically update one resolved review run."""

    def __init__(self, scope: ResolvedScope) -> None:
        self.run_key = scope.run_key
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
        document.setdefault("contexts", {})
        return cast(RunState, document)

    def save_contexts(self, contexts: dict[str, ContextRecord]) -> None:
        with self._lock():
            state = self._read()
            state["contexts"].update(contexts)
            self._write(state)

    def record(
        self,
        entry: Entry,
        verdict: Literal["yes", "no", "n-a"],
        evidence: str,
        fingerprint: str,
        after_save: Callable[[], None] | None = None,
        context_output: str | None = None,
        context_command: str | None = None,
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
            if context_output is not None:
                record["context_output"] = context_output
            if context_command is not None:
                record["context_command"] = context_command
            state["verdicts"][entry.id] = record
            state["waivers"].pop(entry.id, None)
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

    def waive(self, entry: Entry, reason: str, fingerprint: str) -> WaiverRecord:
        if not reason.strip():
            raise RunError("--reason must not be empty")
        with self._lock():
            state = self._read()
            verdict = state["verdicts"].get(entry.id)
            violating = "no" if entry.expects else "yes"
            if (
                verdict is None
                or verdict["fingerprint"] != fingerprint
                or verdict["verdict"] != violating
                or verdict.get("context_command") != entry.context
            ):
                raise RunError(
                    f"{entry.id}: waiver requires a current violating verdict"
                )
            waiver: WaiverRecord = {
                "reason": reason.strip(),
                "fingerprint": fingerprint,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            state["waivers"][entry.id] = waiver
            self._write(state)
            return waiver

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
            state["contexts"] = {}
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
        "contexts": state["contexts"].copy(),
    }


def _empty_state(run_key: str) -> RunState:
    return {
        "run_key": run_key,
        "verdicts": {},
        "history": [],
        "waivers": {},
        "contexts": {},
    }


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
        if any(
            key in record and not isinstance(record[key], str)
            for key in ("context_output", "context_command")
        ):
            return False
    for identifier, waiver in waivers.items():
        if (
            not isinstance(identifier, str)
            or not isinstance(waiver, dict)
            or not all(
                isinstance(waiver.get(field), str)
                for field in ("reason", "fingerprint", "timestamp")
            )
            or not waiver["reason"].strip()
        ):
            return False
    contexts = document.get("contexts", {})
    if not isinstance(contexts, dict) or any(
        not isinstance(identifier, str)
        or not isinstance(record, dict)
        or not all(
            isinstance(record.get(key), str) for key in ContextRecord.__annotations__
        )
        for identifier, record in contexts.items()
    ):
        return False
    return all(isinstance(identifier, str) for identifier in verdicts)
