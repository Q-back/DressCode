"""Trusted, bounded shell evidence delivered by list, never rerun by the gate."""

import hashlib
import os
import selectors
import signal
import subprocess
import time
from pathlib import Path

from dresscode.config import Configuration
from dresscode.entries import Entry
from dresscode.run import ContextRecord, RunError, RunState

OUTPUT_LIMIT = 16384
STDERR_LIMIT = 4096


def trust(config: Configuration) -> None:
    path = _trust_path(config)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(config.local_hash, encoding="utf-8")
    except OSError as error:
        raise RunError(f"{path}: {error}") from error


def trusted(config: Configuration, entry: Entry) -> bool:
    if entry.id not in config.local_contexts:
        return True
    path = _trust_path(config)
    try:
        return path.read_text(encoding="utf-8") == config.local_hash
    except FileNotFoundError:
        return False
    except (OSError, UnicodeError) as error:
        raise RunError(f"{path}: {error}") from error


def _trust_path(config: Configuration) -> Path:
    home = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state")
    clone = str(config.repository.root.resolve())
    return home / "dresscode" / "trust" / hashlib.sha256(clone.encode()).hexdigest()


def required_context(
    config: Configuration, entry: Entry, state: RunState, fingerprint: str
) -> ContextRecord:
    if not trusted(config, entry):
        status, error = "context_untrusted", "Run dresscode trust, then dresscode list."
    else:
        previous = state["contexts"].get(entry.id)
        if (
            previous
            and previous["fingerprint"] == fingerprint
            and previous["command"] == entry.context
        ):
            return previous
        status, error = "unanswered", "Run dresscode list for current context evidence."
    return ContextRecord(
        state=status,
        error=error,
        context_output="",
        command=entry.context or "",
        fingerprint=fingerprint,
    )


def execute(config: Configuration, entry: Entry, fingerprint: str) -> ContextRecord:
    record = ContextRecord(
        state="context_untrusted",
        error="Run dresscode trust, then dresscode list.",
        context_output="",
        command=entry.context or "",
        fingerprint=fingerprint,
    )
    if not trusted(config, entry):
        return record
    timeout = config.settings.get("context", {}).get("timeout_seconds", 10)
    output, error = _capture(entry.context or "", config.repository.root, timeout)
    record.update(
        state="context_failed" if error else "ready", context_output=output, error=error
    )
    return record


def _capture(command: str, root: Path, timeout: float) -> tuple[str, str]:
    stdout, stderr = b"", b""
    truncated = False
    deadline = time.monotonic() + timeout
    try:
        with (
            selectors.DefaultSelector() as selector,
            subprocess.Popen(
                command,
                shell=True,
                cwd=root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            ) as process,
        ):
            try:
                assert process.stdout is not None and process.stderr is not None
                selector.register(process.stdout, selectors.EVENT_READ, "stdout")
                selector.register(process.stderr, selectors.EVENT_READ, "stderr")
                while selector.get_map():
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise subprocess.TimeoutExpired(command, timeout)
                    for key, _ in selector.select(min(remaining, 1.0)):
                        chunk = os.read(key.fd, 8192)
                        if not chunk:
                            selector.unregister(key.fileobj)
                        elif key.data == "stdout":
                            truncated |= len(stdout) + len(chunk) > OUTPUT_LIMIT
                            stdout = (stdout + chunk)[:OUTPUT_LIMIT]
                        else:
                            stderr = (stderr + chunk)[-STDERR_LIMIT:]
                process.wait(timeout=max(0, deadline - time.monotonic()))
                error = (
                    f"Context exited {process.returncode}" if process.returncode else ""
                )
            except subprocess.TimeoutExpired:
                error = f"Context timeout after {timeout:g} seconds"
            finally:
                if process.poll() is None or selector.get_map():
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait()
    except (OSError, TypeError, ValueError, OverflowError) as error:
        return "", f"Cannot execute or capture context: {error}"
    output = stdout.decode("utf-8", errors="replace").strip()
    if truncated:
        output += "\n[truncated]"
    if error and stderr:
        error += ": " + stderr.decode("utf-8", errors="replace").strip()
    return output, error
