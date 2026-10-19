import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dresscode.cli import app
from dresscode.config import ConfigurationError, layer_paths, load
from dresscode.repo import discover


def write_config(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_missing_layers_are_empty_and_do_not_write(
    git_repo: Path, xdg_home: Path
) -> None:
    before = set(xdg_home.rglob("*"))
    config = load(discover(git_repo))

    assert config.settings == {}
    assert config.entries == ()
    assert set(xdg_home.rglob("*")) == before


@pytest.mark.parametrize("winner", ["global", "repo", "private"])
def test_each_layer_wins_in_priority_order(git_repo: Path, winner: str) -> None:
    repository = discover(git_repo)
    for name, paths in layer_paths(repository).items():
        write_config(paths[0], f'base_ref = "{name}"\n')
        if name == winner:
            break

    assert load(repository).settings["base_ref"] == winner


def test_directory_precedes_fallback_and_files_merge_in_name_order(
    git_repo: Path,
) -> None:
    write_config(git_repo / ".dresscode.toml", 'base_ref = "ignored"\n')
    write_config(git_repo / ".dresscode" / "a.toml", 'base_ref = "first"\n')
    write_config(git_repo / ".dresscode" / "z.toml", 'base_ref = "last"\n')
    write_config(git_repo / ".dresscode" / "ignored.txt", "invalid TOML [")
    assert load(discover(git_repo)).settings["base_ref"] == "last"


def test_settings_tables_merge_and_lists_replace(git_repo: Path) -> None:
    repository = discover(git_repo)
    paths = layer_paths(repository)
    write_config(
        paths["global"][0],
        'base_ref = "main"\n[context]\ntimeout_seconds = 10\n[diff]\nexclude = ["uv.lock"]\n',
    )
    write_config(
        paths["repo"][0],
        '[context]\ntimeout_seconds = 3\n[diff]\nexclude = ["vendor/"]\n',
    )
    assert load(repository).settings == {
        "base_ref": "main",
        "context": {"timeout_seconds": 3},
        "diff": {"exclude": ["vendor/"]},
    }


def test_file_entries_merge_across_all_layers(git_repo: Path) -> None:
    repository = discover(git_repo)
    paths = layer_paths(repository)
    write_config(
        paths["global"][0],
        '[[entries]]\nid = "factory"\nquestion = "Reuse?"\nexpects = true\nreveal = "Hidden"\n',
    )
    write_config(
        paths["repo"][0], '[[entries]]\nid = "factory"\nquestion = "Existing?"\n'
    )
    assert load(repository).entries[0].question == "Existing?"
    assert load(repository).entries[0].reveal == "Hidden"
    write_config(paths["private"][0], '[[entries]]\nid = "factory"\nenabled = false\n')
    assert load(repository).entries == ()


def test_private_filename_cannot_escape_config_home(
    git_repo: Path, xdg_home: Path
) -> None:
    private = layer_paths(discover(git_repo))["private"][0]
    assert private.parent == xdg_home / "config" / "dresscode" / "repos"
    assert "%2F" in private.name


@pytest.mark.parametrize("json_output", [False, True])
def test_invalid_toml_is_a_named_exit_2_error(
    git_repo: Path, monkeypatch: pytest.MonkeyPatch, json_output: bool
) -> None:
    invalid = git_repo / ".dresscode" / "rules.toml"
    write_config(invalid, "invalid = [")
    with pytest.raises(ConfigurationError, match="rules.toml"):
        load(discover(git_repo))
    monkeypatch.chdir(git_repo)
    result = CliRunner().invoke(app, ["list", *(["--json"] if json_output else [])])
    assert result.exit_code == 2
    if json_output:
        response = json.loads(result.stdout)
        assert response["status"] == "error"
        assert str(invalid) in response["error"]
        assert result.stderr == ""
    else:
        assert result.stdout == ""
        assert str(invalid) in result.stderr


def test_entry_error_in_config_names_file(git_repo: Path) -> None:
    path = git_repo / ".dresscode.toml"
    write_config(path, '[[entries]]\nid = "factory"\nquestion = "Reuse?"\n')
    with pytest.raises(ConfigurationError, match="factory.*expects"):
        load(discover(git_repo))
