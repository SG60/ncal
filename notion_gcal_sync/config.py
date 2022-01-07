import pathlib
from os import environ

import pydantic
import tomli

# from dotenv import load_dotenv, dotenv_values


###########################################################################
##### The Set-Up Section. Please follow the comments to understand the code.
###########################################################################

#
# CONFIG order of priorities (high to low):
# cli config options
# environment variables
# .env
# toml config file in current directory
#


class Settings(pydantic.BaseSettings):
    """Class for storing settings"""

    NOTION_API_TOKEN: str

    # get the mess of numbers before the "?" on your dashboard URL (no need to split into dashes)
    database_id: str

    # open up a task and then copy the URL root up to the "p="
    urlRoot: str

    runScript: str = "python3 GCalToken.py"  # GCalToken creating program

    credentialsLocation: pydantic.FilePath = (
        "token.pkl"  # Pickle file containing GCal Credentials
    )

    DEFAULT_EVENT_LENGTH: int = 60  # Default event length in minutes
    timezone: str = "Europe/London"  # http://www.timezoneconverter.com/cgi-bin/zonehelp.tzc  TODO: make this unnecessary

    DEFAULT_EVENT_START: int = (
        8  # 8 would be 8 am. 16 would be 4 pm. Only whole numbers
    )

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

    class Config:
        env_prefix = "NCAL_"


def load_config_file(path_to_file: pathlib.Path) -> Settings:
    with open(path_to_file, "rb") as f:
        tomli_dictionary = tomli.load(f)
        settings = Settings(**tomli_dictionary)
        return settings
