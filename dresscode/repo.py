"""Git work-tree discovery and clone-independent repository identity."""

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


class RepositoryError(ValueError):
    """The current environment cannot identify a Git work tree."""


@dataclass(frozen=True)
class Repository:
    root: Path
    identity: str


def discover(directory: Path | None = None) -> Repository:
    directory = directory or Path.cwd()
    try:
        root = Path(_git(directory, "rev-parse", "--show-toplevel")).resolve()
        try:
            origin = _git(root, "config", "--local", "--get", "remote.origin.url")
        except subprocess.CalledProcessError as error:
            if error.returncode != 1:
                raise
            origin = ""
        if origin:
            identity = normalize_origin(origin)
        else:
            first_record = _git(root, "worktree", "list", "--porcelain", "-z")
            main_worktree = first_record.split("\0", 1)[0].removeprefix("worktree ")
            identity = str(Path(main_worktree).resolve())
        return Repository(root, identity)
    except (subprocess.CalledProcessError, OSError, ValueError) as error:
        detail = (
            error.stderr.strip()
            if isinstance(error, subprocess.CalledProcessError)
            else str(error)
        )
        raise RepositoryError(
            f"Cannot resolve Git work tree at {directory}: {detail}"
        ) from error


def normalize_origin(origin: str) -> str:
    if "://" in origin:
        parsed = urlsplit(origin)
        address = parsed.netloc.rsplit("@", 1)[-1] + parsed.path
    elif match := re.fullmatch(r"(?:[^@/]+@)?(\[[^\]]+\]|[^/:]+):(.+)", origin):
        address = f"{match[1]}/{match[2].lstrip('/')}"
    else:
        address = origin
    return address.rstrip("/").removesuffix(".git")


def _git(directory: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=directory, check=True, capture_output=True, text=True
    ).stdout.rstrip("\n")
