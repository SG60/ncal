from notion_gcal_sync import __version__, config
from os import environ


def test_version():
    assert __version__ == "0.1.0"


def generate_test_settings(tmp_path):
    return config.Settings(
        NOTION_API_TOKEN="asdfaa",
        database_id="asdfad",
        urlRoot="asdadf",
        credentialsLocation=f"{tmp_path}/sub/picklefile",
    )


def test_toml_import(tmp_path):
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
    settings = generate_test_settings(tmp_path)
    # test that toml import produces the correct settings
    assert config.load_config_file(tmpfile) == settings


def test_envvar_import(tmp_path):
    # using 3.9 in-place union operator
    global environ
    environ |= {
        "NCAL_NOTION_API_TOKEN": "asdfaa",
        "ncal_database_id": "asdfad",
        "NCAL_urlRoot": "asdadf",
        "NCAL_credentialsLocation": f"{tmp_path}/sub/picklefile",
    }
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "picklefile").touch()
    settings = generate_test_settings(tmp_path)
    assert config.Settings() == settings
