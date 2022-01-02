import secret_tokens  # private file containing tokens (don't commit to git!) # TODO: remove this

###########################################################################
##### The Set-Up Section. Please follow the comments to understand the code.
###########################################################################

# the secret_something from Notion Integration
NOTION_TOKEN = secret_tokens.NOTION_TOKEN

# get the mess of numbers before the "?" on your dashboard URL (no need to split into dashes)
database_id = secret_tokens.database_id

# open up a task and then copy the URL root up to the "p="
urlRoot = secret_tokens.urlRoot

runScript = "python3 GCalToken.py"  # This is the command you will be feeding into the command prompt to run the GCalToken program

# GCal Set Up Part

credentialsLocation = "token.pkl"  # This is where you keep the pickle file that has the Google Calendar Credentials


DEFAULT_EVENT_LENGTH = 60  # This is how many minutes the default event length is. Feel free to change it as you please
timezone = "Europe/London"  # Choose your respective time zone: http://www.timezoneconverter.com/cgi-bin/zonehelp.tzc


DEFAULT_EVENT_START = 8  # 8 would be 8 am. 16 would be 4 pm. Only whole numbers

AllDayEventOption = (
    0  # 0 if you want dates on your Notion dashboard to be treated as an all-day event
)
# ^^ 1 if you want dates on your Notion dashboard to be created at whatever hour you defined in the DEFAULT_EVENT_START variable


### MULTIPLE CALENDAR PART:
#  - VERY IMPORTANT: For each 'key' of the dictionary, make sure that you make that EXACT thing in the Notion database first before running the code. You WILL have an error and your dashboard/calendar will be messed up


DEFAULT_CALENDAR_ID = "cv9aoe96819t4bt5f5jars9b10@group.calendar.google.com"  # The GCal calendar id. The format is something like "sldkjfliksedjgodsfhgshglsj@group.calendar.google.com"

DEFAULT_CALENDAR_NAME = "Notion Events"


# leave the first entry as is
# the structure should be as follows:              WHAT_THE_OPTION_IN_NOTION_IS_CALLED : GCAL_CALENDAR_ID
calendarDictionary = {
    DEFAULT_CALENDAR_NAME: DEFAULT_CALENDAR_ID,
    # "Cal Name": "asdfadsf234asef21134@group.calendar.google.com",  # just typed some random ids but put the one for your calendars here
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


Task_Notion_Name = "Name"
Date_Notion_Name = "Do Date"
Initiative_Notion_Name = "Type"
ExtraInfo_Notion_Name = "Description"
On_GCal_Notion_Name = "On GCal?"
NeedGCalUpdate_Notion_Name = "NeedGCalUpdate"
GCalEventId_Notion_Name = "GCal Event Id"
LastUpdatedTime_Notion_Name = "Last Updated Time"
Calendar_Notion_Name = "Calendar"
Current_Calendar_Id_Notion_Name = "Current Calendar Id"
Delete_Notion_Name = "Done"

#######################################################################################
###               No additional user editing beyond this point is needed            ###
#######################################################################################
