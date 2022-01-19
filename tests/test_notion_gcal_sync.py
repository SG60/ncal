from os import environ

import pytest

from ncal import __version__, config

environ.clear()


@pytest.fixture
def settings_dict(tmp_path):
    return {
        "notion_api_token": "asdfaa",
        "database_id": "asdfad",
        "url_root": "asdadf",
        "credentials_location": f"{tmp_path}/sub/picklefile",
    }


def test_toml_import(tmp_path, settings_dict):
    toml_str = f"""
        notion_api_token = "asdfaa"
        database_id = "asdfad"
        url_root = "asdadf"
        credentials_location= "{tmp_path}/sub/picklefile"
    """
    tmpfile = tmp_path / "test_file.toml"
    tmpfile.write_text(toml_str)
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "picklefile").touch()
    # test that toml import produces the correct settings
    assert config.load_settings(tmpfile, use_env_vars=False) == config.Settings(
        **settings_dict
    )


def test_envvar_import(tmp_path, settings_dict):
    global environ
    environ |= {
        "NCAL_NOTION_API_TOKEN": "asdfaa",
        "ncal_database_id": "asdfad",
        "ncal_url_root": "asdadf",
        "ncal_credentials_location": f"{tmp_path}/sub/picklefile",
    }
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "picklefile").touch()
    assert config.load_settings() == config.Settings(**settings_dict)


def test_get_env_vars():
    prefix = "ncal_"
    key, value = ("notion_api_token", "asdfadf")
    environ_key = prefix + key
    environ[environ_key] = value
    env_var_names = {i: prefix + i for i in config.Settings.__fields__.keys()}
    assert (
        environ[environ_key] == config.get_env_vars_case_insensitive(env_var_names)[key]
    )
