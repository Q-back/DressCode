import json
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from dresscode.cli import app
from dresscode.config import layer_paths, load
from dresscode.repo import discover
from dresscode.store import EntryStore

runner = CliRunner()
QUESTION = 'Did you reuse the "existing" factory?'
ADD = [
    "add",
    "factory",
    "--question",
    QUESTION,
    "--expects",
    "false",
    "--reveal",
    "SECRET",
]


@pytest.fixture(autouse=True)
def in_repository(git_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(git_repo)


def run(*arguments: str) -> Result:
    result = runner.invoke(app, list(arguments))
    assert result.exit_code == 0, result.output
    return result


@pytest.mark.parametrize("layer", [None, "repo", "private", "global"])
def test_add_round_trips_to_sealed_listing(
    git_repo: Path, tmp_path: Path, layer: str | None
) -> None:
    marker = tmp_path / "executed"
    arguments = [*ADD, "--context", f"touch {marker}", "--json"]
    if layer is not None:
        arguments += ["--layer", layer]
    response = json.loads(run(*arguments).stdout)
    repository = discover(git_repo)
    assert response == {
        "status": "added",
        "id": "factory",
        "path": str(layer_paths(repository)[layer or "repo"][0]),
    }
    assert load(repository).entries[0].reveal == "SECRET"
    assert json.loads(run("list", "--json").stdout) == {
        "entries": [{"id": "factory", "question": QUESTION}]
    }
    text = run("list").stdout
    assert QUESTION in text and "SECRET" not in text and "expects" not in text
    assert not marker.exists()
    assert not EntryStore(repository).path.exists()


@pytest.mark.parametrize(
    "original",
    [
        '# Keep this comment\nbase_ref = "main"\n',
        "# Keep this comment\nentries = []\n",
        '# Keep this comment\nentries = [{id="other",question="Other?",expects=true}]\n',
        '# Keep this comment\n[[entries]]\nid="other"\nquestion="Other?"\nexpects=true\n[context]\ntimeout_seconds=3\n',
    ],
)
def test_add_preserves_existing_toml(git_repo: Path, original: str) -> None:
    path = git_repo / ".dresscode.toml"
    path.write_text(original)
    run(*ADD)
    document = tomllib.loads(path.read_text())
    assert "# Keep this comment" in path.read_text()
    assert document["entries"][-1]["id"] == "factory"
    for key, value in tomllib.loads(original).items():
        if key != "entries":
            assert document[key] == value


@pytest.mark.parametrize("existing_file", [False, True])
def test_add_uses_existing_directory_without_creating_fallback(
    git_repo: Path, existing_file: bool
) -> None:
    directory = git_repo / ".dresscode"
    directory.mkdir()
    if existing_file:
        (directory / "z.toml").write_text('base_ref = "main"\n')
    run(*ADD)
    destination = directory / ("z.toml" if existing_file else "rules.toml")
    assert "factory" in destination.read_text()
    assert not (git_repo / ".dresscode.toml").exists()


@pytest.mark.parametrize("reason", [None, "now an ast-grep rule"])
def test_retire_keeps_history_and_counters_without_config_writes(
    git_repo: Path, reason: str | None
) -> None:
    run(*ADD)
    repository = discover(git_repo)
    store = EntryStore(repository)
    entry = load(repository).entries[0]
    store.record(entry, True)
    counters = store.counters(entry.id)
    path = git_repo / ".dresscode.toml"
    original = path.read_bytes()
    path.chmod(0o444)
    try:
        response = json.loads(
            run(
                "retire",
                "factory",
                *(["--reason", reason] if reason is not None else []),
                "--json",
            ).stdout
        )
        assert response["status"] == "retired"
        assert json.loads(run("list", "--json").stdout) == {"entries": []}
        history = EntryStore(repository).retirements()["factory"]
        assert history["reason"] == (reason or "")
        assert history["timestamp"]
        assert history["entry"]["question"] == QUESTION
        assert history["entry"]["reveal"] == "SECRET"
        assert store.counters(entry.id) == counters
        assert path.read_bytes() == original
    finally:
        path.chmod(0o644)


def test_disabled_entries_are_not_listed(git_repo: Path) -> None:
    run(*ADD)
    path = layer_paths(discover(git_repo))["private"][0]
    path.parent.mkdir(parents=True)
    path.write_text('[[entries]]\nid="factory"\nenabled=false\n')
    assert json.loads(run("list", "--json").stdout) == {"entries": []}


@pytest.mark.parametrize(
    "arguments",
    [
        ["retire", "unknown", "--json"],
        ["add", "x", "--question", "Q?", "--expects", "maybe", "--json"],
        [*ADD, "--layer", "unknown", "--json"],
    ],
)
def test_authoring_errors_are_single_json_documents(arguments: list[str]) -> None:
    result = runner.invoke(app, arguments)
    assert result.exit_code == 2
    assert result.stderr == ""
    assert json.loads(result.stdout)["status"] == "error"


def test_empty_listing_does_not_create_state(git_repo: Path) -> None:
    assert json.loads(run("list", "--json").stdout) == {"entries": []}
    assert not EntryStore(discover(git_repo)).path.exists()


def test_corrupt_store_is_a_named_json_error(git_repo: Path) -> None:
    path = EntryStore(discover(git_repo)).path
    path.parent.mkdir(parents=True)
    path.write_bytes(b"not a database")
    result = runner.invoke(app, ["list", "--json"])
    assert result.exit_code == 2
    assert result.stderr == ""
    assert str(path) in json.loads(result.stdout)["error"]


def test_installed_entry_point_can_author_and_list(git_repo: Path) -> None:
    executable = str(Path(sys.executable).with_name("dresscode"))
    for arguments in [ADD, ["list", "--json"]]:
        result = subprocess.run(
            [executable, *arguments],
            cwd=git_repo,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["entries"][0]["id"] == "factory"
