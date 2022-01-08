from os import environ
from pathlib import Path
from typing import Any, Dict

import pydantic
import tomli
from dotenv import dotenv_values, load_dotenv

# Pydantic default priority order (high to low):
#     Arguments passed to the Settings class initialiser.
#     Environment variables, e.g. my_prefix_special_function as described above.
#     Variables loaded from a dotenv (.env) file.
#     Variables loaded from the secrets directory.
#     The default field values for the Settings model.


class Settings(pydantic.BaseModel):
    """Class for storing settings"""

    # secret api token
    notion_api_token: str
    # get the mess of numbers before the "?" on your dashboard URL (no need to split into dashes)
    database_id: str
    # open up a task and then copy the URL root up to the "p="
    urlRoot: str
    # GCalToken creating program
    runScript: str = "python3 GCalToken.py"
    # Pickle file containing GCal Credentials
    credentialsLocation: pydantic.FilePath = Path("token.pkl")

    DEFAULT_EVENT_LENGTH: int = 60  # Default event length in minutes
    timezone: str = "Europe/London"  # http://www.timezoneconverter.com/cgi-bin/zonehelp.tzc  TODO: make this unnecessary

    # 8 would be 8 am. 16 would be 4 pm. Only whole numbers
    DEFAULT_EVENT_START: int = 8

    AllDayEventOption: int = 0  # 0 if you want dates on your Notion dashboard to be treated as an all-day event
    # ^^ 1 if you want dates on your Notion dashboard to be created at whatever hour you defined in the DEFAULT_EVENT_START variable

    ### MULTIPLE CALENDAR PART:
    #  - VERY IMPORTANT: For each 'key' of the dictionary, make sure that you make that EXACT thing in the Notion database first before running the code. You WILL have an error and your dashboard/calendar will be messed up

    DEFAULT_CALENDAR_ID: str = "cv9aoe96819t4bt5f5jars9b10@group.calendar.google.com"  # The GCal calendar id. The format is something like "sldkjfliksedjgodsfhgshglsj@group.calendar.google.com"

    DEFAULT_CALENDAR_NAME: str = "Notion Events"

    # leave the first entry as is
    # the structure should be as follows:
    # WHAT_THE_OPTION_IN_NOTION_IS_CALLED: GCAL_CALENDAR_ID
    calendarDictionary = {
        DEFAULT_CALENDAR_NAME: DEFAULT_CALENDAR_ID,
        # "Cal Name": "asdfadsf234asef21134@group.calendar.google.com",
    }

    ## doesn't delete the Notion task (yet), I'm waiting for the Python API to be updated to allow deleting tasks
    DELETE_OPTION = 1
    # set at 0 if you want the delete column being checked off to mean that the gCal event and the Notion Event will be checked off.
    # set at 1 if you want nothing deleted

    ##### DATABASE SPECIFIC EDITS
    # There needs to be a few properties on the Notion Database for this to work. Replace the values of each variable with the string of what the variable is called on your Notion dashboard
    # The Last Edited Time column is a property of the notion pages themselves, you just have to make it a column
    # The NeedGCalUpdate column is a formula column that works as such "if(prop("Last Edited Time") > prop("Last Updated Time"), true, false)"
    # Please refer to the Template if you are confused: https://www.notion.so/akarri/2583098dfd32472ab6ca1ff2a8b2866d?v=3a1adf60f15748f08ed925a2eca88421

    Task_Notion_Name: str = "Name"
    Date_Notion_Name: str = "Do Date"
    Initiative_Notion_Name: str = "Priority"
    ExtraInfo_Notion_Name: str = "Description"
    On_GCal_Notion_Name: str = "On GCal?"
    NeedGCalUpdate_Notion_Name: str = "NeedGCalUpdate"
    GCalEventId_Notion_Name: str = "GCal Event Id"
    LastUpdatedTime_Notion_Name: str = "Last Updated Time"
    Calendar_Notion_Name: str = "Calendar"
    Current_Calendar_Id_Notion_Name: str = "Current Calendar Id"
    Delete_Notion_Name: str = "Done"


def load_config_file(path_to_file: Path) -> Dict:
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
    load_dotenv()  # uses .env file if available
    ncal_env_vars: dict[str, str] = {}
    # populate env_vars with values which match the dictionary
    for key, value in env_var_names.items():
        if (x := value.upper()) in environ:
            ncal_env_vars[key] = environ[x]
        if (x := value.lower()) in environ:
            ncal_env_vars[key] = environ[x]
    return ncal_env_vars


# priority (high-low): cli, env, config_file
def load_settings(
    config_file_path: Path = Path("config.toml"),
    **kwargs,
):
    default_settings = Settings.construct().dict()

    prefix = "NCAL_"
    env_var_names = {i: prefix + i for i in Settings.__fields__.keys()}
    env_settings = get_env_vars_case_insensitive(env_var_names)

    try:
        toml_settings = load_config_file(config_file_path)
    except FileNotFoundError:
        print(f"no config file found at {config_file_path}")
        toml_settings = {}

    settings = {**default_settings, **toml_settings, **env_settings, **kwargs}
    return Settings(**settings)
