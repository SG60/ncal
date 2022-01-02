import os
import pickle
from datetime import datetime, timezone

import dateutil.parser
import secret_tokens  # private file containing tokens (don't commit to git!) # TODO: remove this
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from notion_client import Client


def notion_time():
    return datetime.now(timezone.utc).isoformat()
    # return datetime.now().strftime(
    #     "%Y-%m-%dT%H:%M:%S"
    # )  # Change the last 5 characters to be representative of your timezone
    # # ^^ has to be adjusted for when daylight savings is different if your area observes it


def DateTimeIntoNotionFormat(dateTimeValue: datetime):
    return dateTimeValue.isoformat()
    # return dateTimeValue.strftime(
    #     "%Y-%m-%dT%H:%M:%S"
    # )  # Change the last 5 characters to be representative of your timezone
    # # ^^ has to be adjusted for when daylight savings is different if your area observes it


def googleQuery():
    return datetime.now(timezone.utc).isoformat()
    # return datetime.now().strftime(
    #     "%Y-%m-%dT%H:%M:%S"
    # )  # Change the last 5 characters to be representative of your timezone
    # # ^^ has to be adjusted for when daylight savings is different if your area observes it


# SET UP THE GOOGLE CALENDAR API INTERFACE
def setup_google_api(runscriptlocation, calendar_id, credentials_location):

    credentials = pickle.load(open(credentials_location, "rb"))
    service = build("calendar", "v3", credentials=credentials)

    # There could be a hiccup if the Google Calendar API token expires.
    # If the token expires, the other python script GCalToken.py creates a new token for the program to use
    # This is placed here because it can take a few seconds to start working and I want the most heavy tasks to occur first
    try:
        calendar = service.calendars().get(calendarId=calendar_id).execute()
    except:
        # refresh the token

        os.system(runscriptlocation)

        # SET UP THE GOOGLE CALENDAR API INTERFACE

        credentials = pickle.load(open(credentials_location, "rb"))
        service = build("calendar", "v3", credentials=credentials)

        # result = service.calendarList().list().execute()
        # print(result['items'][:])

        calendar = service.calendars().get(calendarId=calendar_id).execute()

    return (service, calendar)


###########################################################################
##### Part 5: Deletion Sync -- If marked Done in Notion, then it will delete the GCal event (and the Notion event once Python API updates)
###########################################################################
def delete_page(
    notion,
    database_id,
    GCalEventId_Notion_Name,
    On_GCal_Notion_Name,
    Delete_Notion_Name,
    DELETE_OPTION,
    calendarDictionary,
    Calendar_Notion_Name,
    service,
):
    my_page = notion.databases.query(
        **{
            "database_id": database_id,
            "filter": {
                "and": [
                    {
                        "property": GCalEventId_Notion_Name,
                        "text": {"is_not_empty": True},
                    },
                    {"property": On_GCal_Notion_Name, "checkbox": {"equals": True}},
                    {"property": Delete_Notion_Name, "checkbox": {"equals": True}},
                ]
            },
        }
    )

    resultList = my_page["results"]

    if (
        DELETE_OPTION == 0 and len(resultList) > 0
    ):  # delete gCal event (and Notion task once the Python API is updated)
        CalendarList = []
        CurrentCalList = []

        for i, el in enumerate(resultList):
            calendarID = calendarDictionary[
                el["properties"][Calendar_Notion_Name]["select"]["name"]
            ]
            eventId = el["properties"][GCalEventId_Notion_Name]["rich_text"][0]["text"][
                "content"
            ]

            pageId = el["id"]

            print(calendarID, eventId)

            try:
                service.events().delete(
                    calendarId=calendarID, eventId=eventId
                ).execute()
            except:
                continue

            my_page = notion.pages.update(  ##### Delete Notion task (diesn't work yet)
                **{"page_id": pageId, "archived": True, "properties": {}},
            )

            print(my_page)
