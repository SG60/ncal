from os import environ

import pytest

from notion_gcal_sync import __version__, config

environ.clear()


def test_version():
    assert __version__ == "0.1.0"


@pytest.fixture
def settings_dict(tmp_path):
    return {
        "NOTION_API_TOKEN": "asdfaa",
        "database_id": "asdfad",
        "urlRoot": "asdadf",
        "credentialsLocation": f"{tmp_path}/sub/picklefile",
    }


def test_toml_import(tmp_path, settings_dict):
    toml_str = f"""
        NOTION_API_TOKEN = "asdfaa"
        database_id = "asdfad"
        urlRoot = "asdadf"
        credentialsLocation= "{tmp_path}/sub/picklefile"
    """
    tmpfile = tmp_path / "test_file.toml"
    tmpfile.write_text(toml_str)
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "picklefile").touch()
    # test that toml import produces the correct settings
    assert config.load_config_file(tmpfile) == config.Settings(**settings_dict)


def test_envvar_import(tmp_path, settings_dict):
    global environ
    environ |= {
        "NCAL_NOTION_API_TOKEN": "asdfaa",
        "ncal_database_id": "asdfad",
        "NCAL_urlRoot": "asdadf",
        "NCAL_credentialsLocation": f"{tmp_path}/sub/picklefile",
    }
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "picklefile").touch()
    assert config.Settings() == config.Settings(**settings_dict)


def test_get_env_vars():
    prefix = "ncal_"
    key, value = ("notion_api_token", "asdfadf")
    environ_key = prefix+key
    environ[environ_key] = value
    env_var_names = {i: prefix + i for i in config.Settings.__fields__.keys()}
    assert (
        environ[environ_key]
        == config.get_env_vars_case_insensitive(env_var_names)[key]
    )
