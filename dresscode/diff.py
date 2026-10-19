"""Scoped changes and their content fingerprints."""

import hashlib
import json
import os
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from dresscode.config import Configuration

DEFAULT_EXCLUDES = (
    ":(glob)**/*.lock",
    ":(glob)**/*-lock.json",
    ":(glob)**/npm-shrinkwrap.json",
    ":(glob)**/go.sum",
    ":(glob)**/packages.lock.json",
    ":(glob)**/vendor/**",
    ":(glob)**/snapshots/**",
    ":(glob)**/__snapshots__/**",
    ":(glob)**/cassettes/**",
    ":(glob)**/fixtures/**",
)
DIFF_OPTIONS = (
    "--no-ext-diff",
    "--no-textconv",
    "--no-renames",
    "--ignore-submodules=none",
)


@dataclass(frozen=True)
class FileChange:
    path: str
    added: int | None
    removed: int | None


@dataclass(frozen=True)
class ScopedDiff:
    base_ref: str
    merge_base: str
    files: tuple[FileChange, ...]
    fingerprint: str

    @property
    def added(self) -> int:
        return sum(file.added or 0 for file in self.files)

    @property
    def removed(self) -> int:
        return sum(file.removed or 0 for file in self.files)


class DiffError(ValueError):
    """The review scope cannot be resolved or read."""


def collect(config: Configuration) -> ScopedDiff:
    root = config.repository.root
    pathspecs = _pathspecs(config)
    base_ref, base_commit = resolve_base(root, config.settings.get("base_ref"))
    merge_base = _git(root, "merge-base", "HEAD", base_commit).decode().strip()
    arguments = ("diff", "--merge-base", base_commit, *DIFF_OPTIONS)
    counts = _git(root, *arguments, "--numstat", "-z", "--", *pathspecs)
    files = [_parse_numstat(record) for record in counts.split(b"\0") if record]
    raw = _git(root, *arguments, "--raw", "--no-abbrev", "-z", "--", *pathspecs)
    fields = raw.split(b"\0")[:-1]
    metadata = {}
    for header, path in zip(fields[::2], fields[1::2], strict=True):
        old_mode, new_mode, old_oid, _, _ = header[1:].decode().split()
        metadata[os.fsdecode(path)] = (old_mode, old_oid, new_mode)
    try:
        _include_untracked(root, pathspecs, files, metadata)
        fingerprint = _fingerprint(root, metadata, arguments)
    except OSError as error:
        raise DiffError(f"Cannot read scoped content at {root}: {error}") from error
    return ScopedDiff(
        base_ref,
        merge_base,
        tuple(sorted(files, key=lambda file: file.path)),
        fingerprint,
    )


def resolve_base(root: Path, configured: object = None) -> tuple[str, str]:
    if configured is not None and (not isinstance(configured, str) or not configured):
        raise DiffError("base_ref must be a non-empty string")
    candidates = (
        [(configured, configured)]
        if configured is not None
        else [
            ("origin/HEAD", "refs/remotes/origin/HEAD"),
            ("main", "refs/heads/main"),
            ("master", "refs/heads/master"),
        ]
    )
    for name, reference in candidates:
        commit = (
            _git(
                root,
                "rev-parse",
                "--verify",
                "--quiet",
                "--end-of-options",
                f"{reference}^{{commit}}",
                allowed_codes=(0, 1),
            )
            .decode()
            .strip()
        )
        if commit:
            return name, commit
    if configured is not None:
        raise DiffError(f"base_ref does not resolve to a commit: {configured}")
    root_commit = (
        _git(root, "rev-list", "--max-parents=0", "HEAD").decode().splitlines()[0]
    )
    return root_commit, root_commit


def _include_untracked(
    root: Path,
    pathspecs: tuple[str, ...],
    files: list[FileChange],
    metadata: dict[str, tuple[str, str, str]],
) -> None:
    names = _git(
        root, "ls-files", "--others", "--exclude-standard", "-z", "--", *pathspecs
    )
    executable_bits = (
        _git(
            root, "config", "--bool", "--get", "core.filemode", allowed_codes=(0, 1)
        ).strip()
        != b"false"
    )
    for name in filter(None, names.split(b"\0")):
        path = os.fsdecode(name)
        mode = (root / path).lstat().st_mode
        if stat.S_ISDIR(mode):
            raise DiffError(
                f"Untracked nested Git repository {path!r}: add it as a submodule "
                "or exclude it with diff.exclude"
            )
        git_mode = (
            "120000"
            if stat.S_ISLNK(mode)
            else "100755"
            if executable_bits and mode & 0o111
            else "100644"
        )
        old_mode, old_oid, _ = metadata.get(path, ("000000", "", "000000"))
        counts = _untracked_numstat(root, path, old_mode, old_oid)
        if path in metadata:
            files[:] = [file for file in files if file.path != path]
        if counts:
            metadata[path] = (old_mode, old_oid, git_mode)
            added, removed, _ = counts.split(b"\t", 2)
            files.append(FileChange(path, _count(added), _count(removed)))
        else:
            metadata.pop(path, None)


def _untracked_numstat(root: Path, path: str, old_mode: str, old_oid: str) -> bytes:
    with tempfile.TemporaryDirectory(prefix="dresscode-baseline-") as temporary:
        before = os.devnull
        if old_mode != "000000":
            baseline = Path(temporary) / Path(path).name
            content = _git(root, "cat-file", "blob", old_oid)
            if old_mode == "120000":
                baseline.symlink_to(os.fsdecode(content))
            else:
                baseline.write_bytes(content)
                baseline.chmod(int(old_mode, 8) & 0o777)
            before = str(baseline)
        return _git(
            root,
            "diff",
            "--no-index",
            *DIFF_OPTIONS,
            "--numstat",
            "-z",
            "--",
            before,
            path,
            allowed_codes=(0, 1),
        )


def _pathspecs(config: Configuration) -> tuple[str, ...]:
    diff = config.settings.get("diff", {})
    if not isinstance(diff, dict):
        raise DiffError("diff must be a table")
    excludes = diff.get("exclude", list(DEFAULT_EXCLUDES))
    if not isinstance(excludes, list) or any(
        not isinstance(pattern, str) or not pattern for pattern in excludes
    ):
        raise DiffError("diff.exclude must be a list of non-empty pathspec strings")
    return (".", *(_exclude(pattern) for pattern in excludes))


def _exclude(pattern: str) -> str:
    if pattern.startswith(":("):
        magic, separator, path = pattern[2:].partition(")")
        return f":(exclude,{magic}){path}" if separator else pattern
    if pattern.startswith((":!", ":^")):
        return pattern
    if pattern.startswith(":/"):
        return f":(exclude,top){pattern[2:]}"
    return f":(exclude){pattern}"


def _parse_numstat(record: bytes) -> FileChange:
    added, removed, path = record.split(b"\t", 2)
    return FileChange(os.fsdecode(path), _count(added), _count(removed))


def _count(value: bytes) -> int | None:
    return None if value == b"-" else int(value)


def _fingerprint(
    root: Path, metadata: dict[str, tuple[str, str, str]], arguments: tuple[str, ...]
) -> str:
    records = []
    for path, (old_mode, old_oid, new_mode) in sorted(metadata.items()):
        if new_mode == "000000":
            content = b""
        elif new_mode == "120000":
            content = os.fsencode(os.readlink(root / path))
        elif new_mode == "160000":
            content = _git(root, *arguments, "--binary", "--", f":(literal){path}")
        else:
            content = (root / path).read_bytes()
        records.append(
            (
                path,
                old_mode,
                old_oid if old_mode != "000000" else "",
                new_mode,
                hashlib.sha256(content).hexdigest(),
            )
        )
    return hashlib.sha256(json.dumps(records, ensure_ascii=True).encode()).hexdigest()


def _git(root: Path, *arguments: str, allowed_codes: tuple[int, ...] = (0,)) -> bytes:
    try:
        result = subprocess.run(
            ["git", *arguments], cwd=root, capture_output=True, check=False
        )
    except OSError as error:
        raise DiffError(f"Cannot run Git at {root}: {error}") from error
    if result.returncode not in allowed_codes:
        raise DiffError(
            f"Git at {root}: {result.stderr.decode(errors='replace').strip()}"
        )
    return result.stdout
