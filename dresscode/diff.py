"""Baseline selection and committed diff inspection."""

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from dresscode.config import Configuration
from dresscode.repo import Repository

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
    "--submodule=short",
)


@dataclass(frozen=True)
class FileChange:
    path: str
    added: int | None
    removed: int | None


@dataclass(frozen=True)
class ResolvedScope:
    repository: Repository
    base_commit: str
    head_commit: str
    run_key: str

    def metadata(self) -> dict[str, str]:
        return {
            "base_commit": self.base_commit,
            "head_commit": self.head_commit,
            "run_key": self.run_key,
        }

    def description(self) -> str:
        return f"Base: {self.base_commit}\nHEAD: {self.head_commit}"


@dataclass(frozen=True)
class ScopedDiff:
    scope: ResolvedScope
    files: tuple[FileChange, ...]

    @property
    def base_commit(self) -> str:
        return self.scope.base_commit

    @property
    def added(self) -> int:
        return sum(file.added or 0 for file in self.files)

    @property
    def removed(self) -> int:
        return sum(file.removed or 0 for file in self.files)


class DiffError(ValueError):
    """The review scope cannot be resolved or read."""


def collect(config: Configuration, scope: ResolvedScope | None = None) -> ScopedDiff:
    scope = scope if scope is not None else resolve_scope(config)
    counts = _git(
        config.repository.root,
        "diff",
        scope.base_commit,
        scope.head_commit,
        *DIFF_OPTIONS,
        "--numstat",
        "-z",
        "--",
        *_pathspecs(config),
        env=os.environ | {"GIT_ATTR_SOURCE": scope.head_commit},
    )
    files = [_parse_numstat(record) for record in counts.split(b"\0") if record]
    return ScopedDiff(scope, tuple(sorted(files, key=lambda file: file.path)))


def resolve_scope(config: Configuration, reference: str | None = None) -> ResolvedScope:
    root = config.repository.root
    selected = (
        reference if reference is not None else os.environ.get("DRESSCODE_BASE_COMMIT")
    )
    head_commit = _resolve_commit(root, "HEAD")
    if selected is not None:
        baseline = _resolve_commit(root, selected)
    else:
        _, target = resolve_base(
            root, config.settings.get("merge_base_with"), head_commit=head_commit
        )
        baseline = _git(root, "merge-base", head_commit, target).decode().strip()
    branch = (
        _git(root, "symbolic-ref", "--quiet", "--short", "HEAD", allowed_codes=(0, 1))
        .decode()
        .strip()
    )
    if not branch:
        branch = (
            "detached-"
            + _git(root, "rev-parse", "--short", head_commit).decode().strip()
        )
    key = json.dumps(
        ["v3", config.repository.identity, branch, baseline],
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return ResolvedScope(config.repository, baseline, head_commit, key)


def _resolve_commit(root: Path, reference: str) -> str:
    if not reference:
        raise DiffError("Revision must not be empty")
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
    if not commit:
        raise DiffError(f"Revision does not resolve to one commit: {reference}")
    return commit


def resolve_base(
    root: Path, configured: object = None, *, head_commit: str = "HEAD"
) -> tuple[str, str]:
    if configured is not None and (not isinstance(configured, str) or not configured):
        raise DiffError("merge_base_with must be a non-empty string")
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
        raise DiffError(f"merge_base_with does not resolve to a commit: {configured}")
    root_commit = (
        _git(root, "rev-list", "--max-parents=0", head_commit).decode().splitlines()[0]
    )
    return root_commit, root_commit


def dirty_paths(root: Path) -> set[str]:
    status = _git(
        root,
        "--no-optional-locks",
        "status",
        "--porcelain=v1",
        "-z",
        "--no-renames",
        "--untracked-files=all",
        "--ignore-submodules=none",
    )
    paths = {os.fsdecode(record[3:]) for record in status.split(b"\0") if record}
    # Parent status can miss dirtiness hidden by settings deeper in submodules.
    entries = _git(root, "ls-files", "--stage", "-z")
    for record in entries.split(b"\0"):
        if not record.startswith(b"160000 "):
            continue
        path = os.fsdecode(record.split(b"\t", 1)[1])
        submodule = root / path
        if (
            path not in paths
            and not submodule.is_symlink()
            and (submodule / ".git").exists()
            and dirty_paths(submodule)
        ):
            paths.add(path)
    return paths


def require_clean(root: Path) -> None:
    paths = dirty_paths(root)
    if paths:
        names = ", ".join(repr(path) for path in sorted(paths))
        raise DiffError(
            f"Working tree is dirty: {names}. Commit intended changes or remove local "
            "edits before review. For submodules, clean their working trees and commit "
            "any parent pointer updates. diff.exclude does not bypass this check."
        )


def require_current_snapshot(scope: ResolvedScope) -> None:
    root = scope.repository.root
    if _resolve_commit(root, "HEAD") != scope.head_commit:
        raise DiffError(f"HEAD no longer matches reviewed commit {scope.head_commit}.")
    require_clean(root)


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


def _git(
    root: Path,
    *arguments: str,
    allowed_codes: tuple[int, ...] = (0,),
    env: dict[str, str] | None = None,
) -> bytes:
    try:
        result = subprocess.run(
            ["git", *arguments], cwd=root, env=env, capture_output=True, check=False
        )
    except OSError as error:
        raise DiffError(f"Cannot run Git at {root}: {error}") from error
    if result.returncode not in allowed_codes:
        raise DiffError(
            f"Git at {root}: {result.stderr.decode(errors='replace').strip()}"
        )
    return result.stdout
