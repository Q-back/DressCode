"""The bundled skill is readable anywhere and its example uses the real CLI."""

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from importlib.metadata import PackageNotFoundError
from importlib.resources import files
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from dresscode import cli
from dresscode.cli import app
from dresscode.test_cli import normalize_help_text
from dresscode.test_diff import git

runner = CliRunner()


def skill_text() -> str:
    return files("dresscode").joinpath("SKILL.md").read_text(encoding="utf-8")


def set_direct_url(
    monkeypatch: pytest.MonkeyPatch, value: str | Exception | None
) -> None:
    def read_text(name: str) -> str | None:
        assert name == "direct_url.json"
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(
        cli,
        "distribution",
        lambda package: SimpleNamespace(read_text=read_text),
        raising=False,
    )


def direct_url_json(url: str, commit: str, vcs: str = "git") -> str:
    return json.dumps({"url": url, "vcs_info": {"vcs": vcs, "commit_id": commit}})


def uv_source_repository(root: Path) -> tuple[Path, str]:
    repository = root / "uv-source"
    repository.mkdir()
    (repository / "pyproject.toml").write_text(
        '[project]\nname = "uv-source-probe"\nversion = "0.1.0"\n'
        'requires-python = ">=3.8"\n'
        '[project.scripts]\nuv-source-probe = "uv_source_probe:main"\n'
        '[build-system]\nrequires = []\nbuild-backend = "backend"\n'
        'backend-path = ["."]\n',
        encoding="utf-8",
    )
    (repository / "backend.py").write_text(
        """from base64 import urlsafe_b64encode
from hashlib import sha256
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    name = "uv_source_probe-0.1.0-py3-none-any.whl"
    info = "uv_source_probe-0.1.0.dist-info"
    files = {
        "uv_source_probe.py": b"def main():\\n    return 0\\n",
        f"{info}/METADATA": b"Metadata-Version: 2.1\\nName: uv-source-probe\\nVersion: 0.1.0\\nRequires-Python: >=3.8\\n\\n",
        f"{info}/WHEEL": b"Wheel-Version: 1.0\\nGenerator: test\\nRoot-Is-Purelib: true\\nTag: py3-none-any\\n\\n",
        f"{info}/entry_points.txt": b"[console_scripts]\\nuv-source-probe = uv_source_probe:main\\n",
    }
    rows = []
    for path, contents in files.items():
        digest = urlsafe_b64encode(sha256(contents).digest()).rstrip(b"=").decode()
        rows.append(f"{path},sha256={digest},{len(contents)}")
    record = f"{info}/RECORD"
    files[record] = ("\\n".join([*rows, f"{record},,"]) + "\\n").encode()
    wheel = Path(wheel_directory) / name
    with ZipFile(wheel, "w", ZIP_DEFLATED) as archive:
        for path, contents in files.items():
            archive.writestr(path, contents)
    return name
""",
        encoding="utf-8",
    )
    git(repository, "init", "--initial-branch=main")
    git(repository, "config", "user.name", "DressCode tests")
    git(repository, "config", "user.email", "tests@dresscode.invalid")
    git(repository, "config", "commit.gpgsign", "false")
    git(repository, "config", "core.hooksPath", os.devnull)
    git(repository, "add", ".")
    git(repository, "commit", "--message", "Add uv metadata probe")
    commit = git(repository, "rev-parse", "HEAD")
    git(repository, "tag", "v1.0.0")
    return repository, commit


def test_help_advertises_skill() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "--skill" in normalize_help_text(result.stdout)


@pytest.mark.parametrize("arguments", [[], ["--unknown"], ["unknown"]])
def test_root_usage_errors_remain_errors(arguments: list[str]) -> None:
    result = runner.invoke(app, arguments)

    assert result.exit_code == 2


@pytest.mark.parametrize("arguments", [["--skill"], ["--skill", "check"]])
def test_skill_outside_git_ignores_config_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, arguments: list[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", str(tmp_path))
    config = tmp_path / "config" / "dresscode"
    config.mkdir()
    (config / "config.toml").write_text("invalid = [")
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}

    result = runner.invoke(app, arguments)

    assert result.exit_code == 0, result.output
    assert result.stdout == skill_text()
    assert result.stderr == ""
    assert {
        path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()
    } == (before)
    assert not (tmp_path / "state" / "dresscode").exists()


def test_skill_inside_git_ignores_invalid_local_config(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(git_repo)
    config = git_repo / ".dresscode.toml"
    config.write_text("invalid = [")

    result = runner.invoke(app, ["--skill"])

    assert result.exit_code == 0, result.output
    assert result.stdout == skill_text()
    assert result.stderr == ""
    assert config.read_text() == "invalid = ["


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/Q-back/DressCode.git",
        "https://git.example.invalid/fork/DressCode.git",
    ],
)
def test_skill_pins_official_and_fork_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, url: str
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", str(tmp_path))
    commit = "a" * 40
    set_direct_url(monkeypatch, direct_url_json(url, commit))

    result = runner.invoke(app, ["--skill"])

    assert result.exit_code == 0, result.output
    command = f"uv tool install {shlex.quote(f'git+{url}@{commit}')}"
    assert command in result.stdout
    assert "git+https://github.com/Q-back/DressCode.git'" not in result.stdout


def test_skill_pin_ignores_unrelated_caller_head(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    caller_head = git(git_repo, "rev-parse", "HEAD")
    monkeypatch.chdir(git_repo)
    monkeypatch.setenv("PATH", str(git_repo / "no-git"))
    source_commit = "b" * 40
    set_direct_url(
        monkeypatch,
        direct_url_json("https://github.com/Q-back/DressCode.git", source_commit),
    )

    result = runner.invoke(app, ["--skill"])

    assert result.exit_code == 0, result.output
    expected = shlex.quote(
        f"git+https://github.com/Q-back/DressCode.git@{source_commit}"
    )
    assert f"uv tool install {expected}" in result.stdout
    assert caller_head not in result.stdout


@pytest.mark.parametrize(
    "url",
    [
        "http://example.invalid/team/repo.git",
        "https://user:secret@example.invalid/team/repo.git",
        "https:///team/repo.git",
        "https://example.invalid",
        "https://example.invalid/team/repo.git?branch=main",
        "https://example.invalid/team/repo.git#main",
        "https://example.invalid/team/repo name.git",
        "https://example.invalid/team/repo\n.git",
        "https://example.invalid/team/repo`.git",
        "https://example.invalid\\bad/repo.git",
        "https://bad|host/repo.git",
        "https://[invalid]/team/repo.git",
    ],
)
def test_skill_falls_back_for_unsupported_source_urls(
    monkeypatch: pytest.MonkeyPatch, url: str
) -> None:
    set_direct_url(monkeypatch, direct_url_json(url, "c" * 40))

    result = runner.invoke(app, ["--skill"])

    assert result.exit_code == 0, result.output
    assert result.stdout == skill_text()


@pytest.mark.parametrize(
    "metadata",
    [
        None,
        OSError("metadata unreadable"),
        PackageNotFoundError("dresscode"),
        "not JSON",
        "{}",
        direct_url_json("https://example.invalid/team/repo.git", "d" * 40, "hg"),
        direct_url_json("https://example.invalid/team/repo.git", ""),
        direct_url_json("https://example.invalid/team/repo.git", "abc123"),
        direct_url_json("https://example.invalid/team/repo.git", "z" * 40),
    ],
)
def test_skill_falls_back_without_a_supported_git_revision(
    monkeypatch: pytest.MonkeyPatch, metadata: str | Exception | None
) -> None:
    set_direct_url(monkeypatch, metadata)

    result = runner.invoke(app, ["--skill"])

    assert result.exit_code == 0, result.output
    assert result.stdout == skill_text()


@pytest.mark.parametrize("dirty", [False, True])
def test_skill_does_not_infer_a_pin_from_the_caller_checkout(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch, dirty: bool
) -> None:
    monkeypatch.chdir(git_repo)
    if dirty:
        (git_repo / "uncommitted.txt").write_text("dirty checkout")
    set_direct_url(monkeypatch, None)

    result = runner.invoke(app, ["--skill"])

    assert result.exit_code == 0, result.output
    assert result.stdout == skill_text()


def test_skill_quotes_the_complete_git_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = tmp_path / "executed"
    url = f"https://example.invalid/team/repo$(touch${{IFS}}{marker}).git"
    commit = "e" * 40
    set_direct_url(monkeypatch, direct_url_json(url, commit))

    result = runner.invoke(app, ["--skill"])
    command = re.search(r"`uv tool install (.+?)`", result.stdout)
    assert result.exit_code == 0, result.output
    assert command is not None
    executed = subprocess.run(
        ["sh", "-c", f"set -- {command[1]}; printf '%s' \"$1\""],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )

    assert executed.returncode == 0, executed.stderr
    assert executed.stdout == f"git+{url}@{commit}"
    assert not marker.exists()


def test_uv_records_resolved_git_revisions_offline(
    tmp_path: Path,
) -> None:
    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv is required for the direct_url.json regression test")
    repository, commit = uv_source_repository(tmp_path)
    source = repository.as_uri()
    installs = [
        (source, None),
        (f"{source}@main", "main"),
        (f"{source}@v1.0.0", "v1.0.0"),
        (f"{source}@{commit}", commit),
    ]

    for index, (requirement, requested_revision) in enumerate(installs):
        isolated = tmp_path / f"install-{index}"
        environment = os.environ | {
            "UV_TOOL_DIR": str(isolated / "tools"),
            "UV_TOOL_BIN_DIR": str(isolated / "bin"),
            "UV_CACHE_DIR": str(isolated / "cache"),
            "UV_OFFLINE": "1",
            "UV_NO_PROGRESS": "1",
            "UV_NO_PYTHON_DOWNLOADS": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
        }
        result = subprocess.run(
            [
                uv,
                "tool",
                "install",
                "--offline",
                "--no-python-downloads",
                "--no-build-isolation",
                "--python",
                sys.executable,
                f"git+{requirement}",
            ],
            cwd=tmp_path,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        direct_url_paths = list((isolated / "tools").rglob("direct_url.json"))
        assert len(direct_url_paths) == 1
        direct_url = json.loads(direct_url_paths[0].read_text(encoding="utf-8"))
        assert direct_url["url"] == source
        assert direct_url["vcs_info"]["vcs"] == "git"
        assert direct_url["vcs_info"]["commit_id"] == commit
        assert direct_url["vcs_info"].get("requested_revision") == requested_revision


def test_installed_skill_is_plain_markdown_outside_the_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FORCE_COLOR", "1")
    executable = Path(sys.executable).with_name("dresscode")
    result = subprocess.run(
        [str(executable), "--skill"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == skill_text()
    assert result.stderr == ""
    assert result.stdout.startswith("---\nname: dresscode\n")
    assert "\x1b[" not in result.stdout


def test_skill_rule_example_can_be_created_and_reviewed(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(git_repo)
    rules = skill_text().split("## Rules", 1)[1]
    example = re.search(r"```sh\n(.*?)\n```", rules, re.DOTALL)
    assert example is not None
    arguments = shlex.split(example[1].replace("\\\n", ""))
    assert arguments[0] == "dresscode"
    added = runner.invoke(app, arguments[1:])
    assert added.exit_code == 0, added.output
    listed = runner.invoke(app, ["list", "--json"])
    assert listed.exit_code == 0, listed.output
    assert "shared-builder" in listed.stdout
    assert "expects" not in listed.stdout
    assert runner.invoke(app, ["check"]).exit_code == 1
    answered = runner.invoke(
        app,
        [
            "answer",
            "shared-builder",
            "--yes",
            "--evidence",
            "Reused the shared builder.",
        ],
    )
    assert answered.exit_code == 0, answered.output
    assert runner.invoke(app, ["check", "--strict"]).exit_code == 0
    (git_repo / "change.txt").write_text("Changed after review.\n")
    assert runner.invoke(app, ["check"]).exit_code == 1


@pytest.mark.parametrize("source", ["docs/manual.md", "skill"])
def test_documented_scoped_workflow_runs_with_pinned_metadata(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch, source: str
) -> None:
    from dresscode.test_diff import git

    monkeypatch.chdir(git_repo)
    for index in range(2):
        git(git_repo, "commit", "--allow-empty", "-m", f"Commit {index}")
    identifier = "shared-builder" if source == "skill" else "test-factory"
    added = runner.invoke(
        app, ["add", identifier, "--question", "Reuse?", "--expects", "true"]
    )
    assert added.exit_code == 0, added.output
    text = (
        skill_text()
        if source == "skill"
        else (Path(__file__).resolve().parents[1] / source).read_text()
    )
    section = text.split("## Review an exact commit", 1)[1]
    example = re.search(r"```sh\n(.*?)\n```", section, re.DOTALL)
    assert example is not None
    result = subprocess.run(
        ["sh", "-eu", "-c", example[1]],
        cwd=git_repo,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    baseline = git(git_repo, "rev-parse", "HEAD~2")
    assert baseline in result.stdout
    reset = runner.invoke(app, ["check", "--base", baseline, "--json"])
    assert reset.exit_code == 1
    assert "unanswered" in reset.stdout
