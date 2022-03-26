"""Test the config management module."""
from os import environ

import pytest

from ncal import config

environ.clear()


@pytest.fixture
def settings_dict(tmp_path):
    """Generate a sample dictionary of settings."""
    return {
        "notion_api_token": "asdf",
        "database_id": "asdf",
        "url_root": "asdf",
        "credentials_location": f"{tmp_path}/sub/picklefile",
    }


def test_toml_import(tmp_path, settings_dict):
    """Test that .toml import is working."""
    toml_str = f"""
        notion_api_token = "asdf"
        database_id = "asdf"
        url_root = "asdf"
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
    assert (
        config.load_settings(
            tmp_path / "fake_path.toml",
            use_env_vars=False,
            notion_api_token="1234",
            database_id="asdf",
            url_root="1234",
        )
        == config.Settings(notion_api_token="1234", database_id="asdf", url_root="1234")
    )


def test_env_var_import(tmp_path, settings_dict):
    """Test ncal.config.load_settings for env vars."""
    global environ
    environ |= {
        "NCAL_NOTION_API_TOKEN": "asdf",
        "ncal_database_id": "asdf",
        "ncal_url_root": "asdf",
        "ncal_credentials_location": f"{tmp_path}/sub/picklefile",
    }
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "picklefile").touch()
    assert config.load_settings() == config.Settings(**settings_dict)


def test_get_env_vars():
    """Test case insensitive env var import."""
    prefix = "ncal_"
    key, value = ("notion_api_token", "asdf")
    environ_key = prefix + key
    environ[environ_key] = value
    env_var_names = {i: prefix + i for i in config.Settings.__fields__.keys()}
    assert (
        environ[environ_key] == config.get_env_vars_case_insensitive(env_var_names)[key]
    )
