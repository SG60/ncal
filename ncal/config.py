"""
Functions and classes to manage configuration are in this file. Configuration can
operate through toml, .env, environment variables, or the command line.
"""
from os import environ
from pathlib import Path
from typing import Any, Dict, Literal

import pydantic
import tomli
from dotenv import load_dotenv

# Pydantic default priority order (high to low):
#     Arguments passed to the Settings class initialiser.
#     Environment variables, e.g. my_prefix_special_function as described above.
#     Variables loaded from a dotenv (.env) file.
#     Variables loaded from the secrets directory.
#     The default field values for the Settings model.


class Settings(pydantic.BaseModel):
    """Class for storing settings

    Attributes:
        notion_api_token: API token for Notion integration
        credentials_location: file containing GCal Credentials
    """

    notion_api_token: str

    # get the mess of numbers before the "?" on your dashboard URL (no need to split
    # into dashes)
    database_id: str
    # open up a task and then copy the URL root up to the "p="
    url_root: str
    # GCalToken creating program TODO:this might not be necessary anymore?!
    run_script: str = "python3 GCalToken.py"
    # Pickle file containing GCal Credentials
    credentials_location: pydantic.FilePath = Path("token.pkl")

    default_event_length: int = 60  # Default event length in minutes
    # http://www.timezoneconverter.com/cgi-bin/zonehelp.tzc  TODO: make this unnecessary
    timezone: str = "Europe/London"

    # 8 would be 8 am. 16 would be 4 pm. Only whole numbers
    default_event_start: int = 8

    # 0 if you want dates on your Notion dashboard to be treated as an all-day event
    all_day_event_option: int = 0

    # ^^ 1 if you want dates on your Notion dashboard to be created at whatever hour you
    # defined in the DEFAULT_EVENT_START variable

    # MULTIPLE CALENDAR PART:
    #  - VERY IMPORTANT: For each 'key' of the dictionary, make sure that you make that
    # EXACT thing in the Notion database first before running the code. You WILL have
    # an error and your dashboard/calendar will be messed up

    # The GCal calendar id. The format is something like
    # "sldkjfliksedjgodsfhgshglsj@group.calendar.google.com"
    default_calendar_id: str = "cv9aoe96819t4bt5f5jars9b10@group.calendar.google.com"

    default_calendar_name: str = "Notion Events"

    # leave the first entry as is
    # the structure should be as follows:
    # WHAT_THE_OPTION_IN_NOTION_IS_CALLED: GCAL_CALENDAR_ID
    calendar_dictionary = {
        default_calendar_name: default_calendar_id,
        # "Cal Name": "asdfadsf234asef21134@group.calendar.google.com",
    }

    # doesn't delete the Notion task (yet), I'm waiting for the Python API to be
    # updated to allow deleting tasks
    delete_option: bool = False
    # set at True if you want the delete column being checked off to mean that the
    # gCal event and the Notion Event will be checked off.
    # set at False if you want nothing deleted

    # DATABASE SPECIFIC EDITS
    # There needs to be a few properties on the Notion Database for this to work.
    # Replace the values of each variable with the string of what the variable is
    # called on your Notion dashboard
    # The Last Edited Time column is a property of the notion pages themselves,
    # you just have to make it a column
    # The NeedGCalUpdate column is a formula column that works as such
    # "if(prop("Last Edited Time") > prop("Last Updated Time"), true, false)"
    # Please refer to the Template if you are confused:
    # https://www.notion.so/akarri/2583098dfd32472ab6ca1ff2a8b2866d?v=3a1adf60f15748f08ed925a2eca88421

    task_notion_name: str = "Name"
    date_notion_name: str = "Do Date"
    initiative_notion_name: str = "Project"
    initiative_notion_type: Literal["relation", "select"] = "relation"
    extrainfo_notion_name: str = "Description"
    on_gcal_notion_name: str = "On GCal?"
    need_gcal_update_notion_name: str = "NeedGCalUpdate"
    gcal_event_id_notion_name: str = "GCal Event Id"
    lastupdatedtime_notion_name: str = "Last Updated Time"
    calendar_notion_name: str = "Calendar"
    current_calendar_id_notion_name: str = "Current Calendar Id"
    delete_notion_name: str = "Done"


def load_config_file(path_to_file: Path) -> Dict[str, Any]:
    """Load a toml config file into a dictionary
    Args:
        path_to_file:
    Returns:
        Settings (unfiltered)"""
    with open(path_to_file, "rb") as f:
        tomli_dictionary = tomli.load(f)
        # settings = Settings(**tomli_dictionary)
        return tomli_dictionary


def env_var_names_dict(prefix: str) -> Dict[str, str]:
    """
    produces a dictionary: {setting_str: prefixed_str}
    """
    return {i: prefix.lower() + i.lower() for i in Settings.__fields__.keys()}


def get_env_vars_case_insensitive(env_var_names: Dict[str, str]) -> Dict[str, str]:
    """Gets environment variables matching the values in the given dictionary,
    using the keys as the keys for the returned dictionary.
    Args:
        env_var_names: {desired label: environment variable label}
    Returns:
        Dictionary of environment variables
    """
    load_dotenv()  # uses .env file if available
    ncal_env_vars: dict[str, str] = {}
    # populate env_vars with values which match the dictionary
    for key, value in env_var_names.items():
        if (x := value.upper()) in environ:
            ncal_env_vars[key] = environ[x]
        if (x := value.lower()) in environ:
            ncal_env_vars[key] = environ[x]
    return ncal_env_vars


def load_settings(
    config_file_path: Path = Path("config.toml"),
    *,
    use_env_vars: bool = True,
    use_toml_file: bool = True,
    **kwargs,
) -> Settings:
    """Function to load settings from multiple sources.

    This function falls back to defaults, so only a few settings are required.
    Priority (high-low): cli, env, config_file.

    Args:
        config_file_path: Path to a .toml config file
        use_env_vars:
        use_toml_file:
        kwargs: Other settings to provide to the Settings object

    Returns:
        A ncal.config.Settings object
    """
    default_settings = Settings.construct().dict()  # type: ignore

    if use_env_vars:
        prefix = "NCAL_"
        env_var_names = {i: prefix + i for i in Settings.__fields__.keys()}
        env_settings = get_env_vars_case_insensitive(env_var_names)
    else:
        env_settings = {}

    if use_toml_file:
        try:
            toml_settings = load_config_file(config_file_path)
        except FileNotFoundError:
            print(f"no config file found at {config_file_path}")
            toml_settings = {}
    else:
        toml_settings = {}

    passed_settings = {key: value for key, value in kwargs.items() if value is not None}

    settings = {**default_settings, **toml_settings, **env_settings, **passed_settings}
    return Settings(**settings)
