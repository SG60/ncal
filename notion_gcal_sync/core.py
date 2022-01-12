import datetime as dt
import os
import pickle
from typing import Any

import arrow
import dateutil.parser
import notion_client as nc
from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore
from googleapiclient.discovery import build  # type: ignore

from notion_gcal_sync import config


# SET UP THE GOOGLE CALENDAR API INTERFACE
def setup_google_api(
    runscriptlocation: str, calendar_id: str, credentials_location: str
):

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


def notion_time():
    return dt.datetime.now(dt.timezone.utc).isoformat()
    # return dt.datetime.now().strftime(
    #     "%Y-%m-%dT%H:%M:%S"
    # )  # Change the last 5 characters to be representative of your timezone
    # # ^^ has to be adjusted for when daylight savings is different if your area observes it


def DateTimeIntoNotionFormat(dateTimeValue: dt.datetime):
    return dateTimeValue.isoformat()
    # return dateTimeValue.strftime(
    #     "%Y-%m-%dT%H:%M:%S"
    # )  # Change the last 5 characters to be representative of your timezone
    # # ^^ has to be adjusted for when daylight savings is different if your area observes it


def googleQuery():
    return dt.datetime.now(dt.timezone.utc).isoformat()
    # return datetime.now().strftime(
    #     "%Y-%m-%dT%H:%M:%S"
    # )  # Change the last 5 characters to be representative of your timezone
    # # ^^ has to be adjusted for when daylight savings is different if your area observes it


def setup_api_connections(
    runscript_location, default_calendar_id, credentials_location, notion_api_token
) -> tuple[Any, Any, nc.Client]:
    service, calendar = setup_google_api(
        runscript_location,
        default_calendar_id,
        str(credentials_location),
    )

    # This is where we set up the connection with the Notion API

    notion = nc.Client(auth=notion_api_token)

    return service, calendar, notion


def get_new_notion_pages(
    database_id: str,
    on_gcal_notion_name: str,
    date_notion_name: str,
    delete_notion_name: str,
    notion: nc.Client,
) -> list:
    """Get new pages from notion (with pagination!)."""
    # todayDate = dt.datetime.today().strftime("%Y-%m-%d")
    todayDate = arrow.utcnow().isoformat()

    matching_pages = []

    query = {
        "database_id": database_id,
        "filter": {
            "and": [
                {
                    "property": on_gcal_notion_name,
                    "checkbox": {"equals": False},
                },
                {
                    "property": date_notion_name,
                    "date": {"on_or_after": todayDate},
                },
                {"property": delete_notion_name, "checkbox": {"equals": False}},
            ]
        },
    }

    while True:
        # this query will return a dictionary that we will parse for information that we want
        response = notion.databases.query(**query)
        matching_pages.extend(response["results"])
        if response["next_cursor"]:
            query["start_cursor"] = response["next_cursor"]
        else:
            break
    return matching_pages


def new_events_notion_to_gcal(
    database_id,
    urlRoot,
    DEFAULT_CALENDAR_NAME,
    calendarDictionary,
    Task_Notion_Name,
    Date_Notion_Name,
    Initiative_Notion_Name,
    ExtraInfo_Notion_Name,
    On_GCal_Notion_Name,
    GCalEventId_Notion_Name,
    LastUpdatedTime_Notion_Name,
    Calendar_Notion_Name,
    Current_Calendar_Id_Notion_Name,
    Delete_Notion_Name,
    notion,
    service,
):
    """
    Part 1: Take Notion Events not on GCal and move them over to GCal


    Note that we are only querying for events that are today or in the next week so the code can be efficient.
    If you just want all Notion events to be on GCal, then you'll have to edit the query so it is only checking the 'On GCal?' property
    """

    resultList = get_new_notion_pages(
        database_id, On_GCal_Notion_Name, Date_Notion_Name, Delete_Notion_Name, notion
    )

    # print(len(resultList))

    try:
        print(resultList[0])
    except:
        print("")

    TaskNames = []
    start_Dates = []
    end_Times = []
    Initiatives = []
    ExtraInfo = []
    URL_list = []
    calEventIdList = []
    CalendarList = []

    if len(resultList) > 0:
        for i, el in enumerate(resultList):
            print("\n")
            print(el)
            print("\n")

            TaskNames.append(
                el["properties"][Task_Notion_Name]["title"][0]["text"]["content"]
            )
            start_Dates.append(el["properties"][Date_Notion_Name]["date"]["start"])

            if el["properties"][Date_Notion_Name]["date"]["end"] != None:
                end_Times.append(el["properties"][Date_Notion_Name]["date"]["end"])
            else:
                end_Times.append(el["properties"][Date_Notion_Name]["date"]["start"])

            try:
                # TODO: Make this work with Project relation
                Initiatives.append(
                    el["properties"][Initiative_Notion_Name]["select"]["name"]
                )
            except:
                Initiatives.append("")

            try:
                ExtraInfo.append(
                    el["properties"][ExtraInfo_Notion_Name]["rich_text"][0]["text"][
                        "content"
                    ]
                )
            except:
                ExtraInfo.append("")
            URL_list.append(makeTaskURL(el["id"], urlRoot))

            try:
                CalendarList.append(
                    calendarDictionary[
                        el["properties"][Calendar_Notion_Name]["select"]["name"]
                    ]
                )
            except:  # keyerror occurs when there's nothing put into the calendar in the first place
                CalendarList.append(calendarDictionary[DEFAULT_CALENDAR_NAME])

            pageId = el["id"]
            my_page = notion.pages.update(  ##### This checks off that the event has been put on Google Calendar
                **{
                    "page_id": pageId,
                    "properties": {
                        On_GCal_Notion_Name: {"checkbox": True},
                        LastUpdatedTime_Notion_Name: {
                            "date": {
                                "start": notion_time(),
                                "end": None,
                            }
                        },
                    },
                },
            )
            print(CalendarList)

            # 2 Cases: Start and End are  both either date or date+time #Have restriction that the calendar events don't cross days
            try:
                # start and end are both dates
                calEventId = makeCalEvent(
                    TaskNames[i],
                    makeEventDescription(Initiatives[i], ExtraInfo[i]),
                    dt.datetime.strptime(start_Dates[i], "%Y-%m-%d"),
                    URL_list[i],
                    dt.datetime.strptime(end_Times[i], "%Y-%m-%d"),
                    CalendarList[i],
                    service,
                )
            except:
                try:
                    # start and end are both date+time
                    calEventId = makeCalEvent(
                        TaskNames[i],
                        makeEventDescription(Initiatives[i], ExtraInfo[i]),
                        dateutil.parser.isoparse(start_Dates[i]),
                        URL_list[i],
                        dateutil.parser.isoparse(end_Times[i]),
                        CalendarList[i],
                        service,
                    )
                except:
                    calEventId = makeCalEvent(
                        TaskNames[i],
                        makeEventDescription(Initiatives[i], ExtraInfo[i]),
                        dateutil.parser.isoparse(start_Dates[i]),
                        URL_list[i],
                        dateutil.parser.isoparse(end_Times[i]),
                        CalendarList[i],
                        service,
                    )

            calEventIdList.append(calEventId)

            if (
                CalendarList[i] == calendarDictionary[DEFAULT_CALENDAR_NAME]
            ):  # this means that there is no calendar assigned on Notion
                my_page = notion.pages.update(  ##### This puts the the GCal Id into the Notion Dashboard
                    **{
                        "page_id": pageId,
                        "properties": {
                            GCalEventId_Notion_Name: {
                                "rich_text": [{"text": {"content": calEventIdList[i]}}]
                            },
                            Current_Calendar_Id_Notion_Name: {
                                "rich_text": [{"text": {"content": CalendarList[i]}}]
                            },
                            Calendar_Notion_Name: {
                                "select": {"name": DEFAULT_CALENDAR_NAME},
                            },
                        },
                    },
                )
            else:  # just a regular update
                my_page = notion.pages.update(
                    **{
                        "page_id": pageId,
                        "properties": {
                            GCalEventId_Notion_Name: {
                                "rich_text": [{"text": {"content": calEventIdList[i]}}]
                            },
                            Current_Calendar_Id_Notion_Name: {
                                "rich_text": [{"text": {"content": CalendarList[i]}}]
                            },
                        },
                    },
                )

    else:
        print("Nothing new added to GCal")
    return todayDate


def existing_events_notion_to_gcal(
    database_id,
    urlRoot,
    DEFAULT_CALENDAR_ID,
    DEFAULT_CALENDAR_NAME,
    calendarDictionary,
    Task_Notion_Name,
    Date_Notion_Name,
    Initiative_Notion_Name,
    ExtraInfo_Notion_Name,
    On_GCal_Notion_Name,
    NeedGCalUpdate_Notion_Name,
    GCalEventId_Notion_Name,
    LastUpdatedTime_Notion_Name,
    Calendar_Notion_Name,
    Current_Calendar_Id_Notion_Name,
    Delete_Notion_Name,
    notion,
    todayDate,
    service,
):
    ###########################################################################
    ##### Part 2: Updating GCal Events that Need To Be Updated (Changed on Notion but need to be changed on GCal)
    ###########################################################################

    # Just gotta put a fail-safe in here in case people deleted the Calendar Variable
    # this queries items in the next week where the Calendar select thing is empty
    my_page = notion.databases.query(
        **{
            "database_id": database_id,
            "filter": {
                "and": [
                    {"property": Calendar_Notion_Name, "select": {"is_empty": True}},
                    {
                        "or": [
                            {
                                "property": Date_Notion_Name,
                                "date": {"equals": todayDate},
                            },
                            {"property": Date_Notion_Name, "date": {"next_week": {}}},
                        ]
                    },
                    {"property": Delete_Notion_Name, "checkbox": {"equals": False}},
                ]
            },
        }
    )
    resultList = my_page["results"]

    if len(resultList) > 0:
        for i, el in enumerate(resultList):
            pageId = el["id"]
            my_page = notion.pages.update(  ##### This checks off that the event has been put on Google Calendar
                **{
                    "page_id": pageId,
                    "properties": {
                        Calendar_Notion_Name: {
                            "select": {"name": DEFAULT_CALENDAR_NAME},
                        },
                        LastUpdatedTime_Notion_Name: {
                            "date": {
                                "start": notion_time(),
                                "end": None,
                            }
                        },
                    },
                },
            )

    ## Filter events that have been updated since the GCal event has been made

    # this query will return a dictionary that we will parse for information that we want
    # look for events that are today or in the next week
    my_page = notion.databases.query(
        **{
            "database_id": database_id,
            "filter": {
                "and": [
                    {
                        "property": NeedGCalUpdate_Notion_Name,
                        "checkbox": {"equals": True},
                    },
                    {"property": On_GCal_Notion_Name, "checkbox": {"equals": True}},
                    {
                        "or": [
                            {
                                "property": Date_Notion_Name,
                                "date": {"equals": todayDate},
                            },
                            {"property": Date_Notion_Name, "date": {"next_week": {}}},
                        ]
                    },
                    {"property": Delete_Notion_Name, "checkbox": {"equals": False}},
                ]
            },
        }
    )
    resultList = my_page["results"]

    updatingNotionPageIds = []
    updatingCalEventIds = []

    for result in resultList:
        print(result)
        print("\n")
        pageId = result["id"]
        updatingNotionPageIds.append(pageId)
        print("\n")
        print(result)
        print("\n")
        try:
            calId = result["properties"][GCalEventId_Notion_Name]["rich_text"][0][
                "text"
            ]["content"]
        except:
            calId = DEFAULT_CALENDAR_ID
        print(calId)
        updatingCalEventIds.append(calId)

    TaskNames = []
    start_Dates = []
    end_Times = []
    Initiatives = []
    ExtraInfo = []
    URL_list = []
    CalendarList = []
    CurrentCalList = []

    if len(resultList) > 0:
        for i, el in enumerate(resultList):
            print("\n")
            print(el)
            print("\n")

            TaskNames.append(
                el["properties"][Task_Notion_Name]["title"][0]["text"]["content"]
            )
            start_Dates.append(el["properties"][Date_Notion_Name]["date"]["start"])

            if el["properties"][Date_Notion_Name]["date"]["end"] != None:
                end_Times.append(el["properties"][Date_Notion_Name]["date"]["end"])
            else:
                end_Times.append(el["properties"][Date_Notion_Name]["date"]["start"])

            try:
                # TODO: Make this work with Project relation
                Initiatives.append(
                    el["properties"][Initiative_Notion_Name]["select"]["name"]
                )
            except:
                Initiatives.append("")

            try:
                ExtraInfo.append(
                    el["properties"][ExtraInfo_Notion_Name]["rich_text"][0]["text"][
                        "content"
                    ]
                )
            except:
                ExtraInfo.append("")
            URL_list.append(makeTaskURL(el["id"], urlRoot))

            print(el)
            # CalendarList.append(calendarDictionary[el['properties'][Calendar_Notion_Name]['select']['name']])
            try:
                CalendarList.append(
                    calendarDictionary[
                        el["properties"][Calendar_Notion_Name]["select"]["name"]
                    ]
                )
            except:  # keyerror occurs when there's nothing put into the calendar in the first place
                CalendarList.append(calendarDictionary[DEFAULT_CALENDAR_NAME])

            CurrentCalList.append(
                el["properties"][Current_Calendar_Id_Notion_Name]["rich_text"][0][
                    "text"
                ]["content"]
            )

            pageId = el["id"]

            ##depending on the format of the dates, we'll update the gCal event as necessary
            try:
                calEventId = upDateCalEvent(
                    TaskNames[i],
                    makeEventDescription(Initiatives[i], ExtraInfo[i]),
                    dt.datetime.strptime(start_Dates[i], "%Y-%m-%d"),
                    URL_list[i],
                    updatingCalEventIds[i],
                    dt.datetime.strptime(end_Times[i], "%Y-%m-%d"),
                    CurrentCalList[i],
                    CalendarList[i],
                    service,
                )
            except:
                try:
                    calEventId = upDateCalEvent(
                        TaskNames[i],
                        makeEventDescription(Initiatives[i], ExtraInfo[i]),
                        dateutil.parser.isoparse(start_Dates[i]),
                        URL_list[i],
                        updatingCalEventIds[i],
                        dateutil.parser.isoparse(end_Times[i]),
                        CurrentCalList[i],
                        CalendarList[i],
                        service,
                    )
                except:
                    calEventId = upDateCalEvent(
                        TaskNames[i],
                        makeEventDescription(Initiatives[i], ExtraInfo[i]),
                        dateutil.parser.isoparse(start_Dates[i]),
                        URL_list[i],
                        updatingCalEventIds[i],
                        dateutil.parser.isoparse(end_Times[i]),
                        CurrentCalList[i],
                        CalendarList[i],
                        service,
                    )

            my_page = notion.pages.update(  ##### This updates the last time that the page in Notion was updated by the code
                **{
                    "page_id": pageId,
                    "properties": {
                        LastUpdatedTime_Notion_Name: {
                            "date": {
                                "start": notion_time(),  # has to be adjusted for when daylight savings is different
                                "end": None,
                            }
                        },
                        Current_Calendar_Id_Notion_Name: {
                            "rich_text": [{"text": {"content": CalendarList[i]}}]
                        },
                    },
                },
            )

    else:
        print("Nothing new updated to GCal")


def existing_events_gcal_to_notion(
    database_id,
    DEFAULT_CALENDAR_NAME,
    calendarDictionary,
    Date_Notion_Name,
    On_GCal_Notion_Name,
    NeedGCalUpdate_Notion_Name,
    GCalEventId_Notion_Name,
    LastUpdatedTime_Notion_Name,
    Calendar_Notion_Name,
    Current_Calendar_Id_Notion_Name,
    Delete_Notion_Name,
    service,
    notion,
    todayDate,
):
    ###########################################################################
    ##### Part 3: Sync GCal event updates for events already in Notion back to Notion!
    ###########################################################################

    ##Query notion tasks already in Gcal, don't have to be updated, and are today or in the next week
    my_page = notion.databases.query(
        **{
            "database_id": database_id,
            "filter": {
                "and": [
                    {
                        "property": NeedGCalUpdate_Notion_Name,
                        "formula": {"checkbox": {"equals": False}},
                    },
                    {"property": On_GCal_Notion_Name, "checkbox": {"equals": True}},
                    {
                        "or": [
                            {
                                "property": Date_Notion_Name,
                                "date": {"equals": todayDate},
                            },
                            {"property": Date_Notion_Name, "date": {"next_week": {}}},
                        ]
                    },
                    {"property": Delete_Notion_Name, "checkbox": {"equals": False}},
                ]
            },
        }
    )

    resultList = my_page["results"]

    # Comparison section:
    # We need to see what times between GCal and Notion are not the same, so we are going to convert all of the notion date/times into
    ## datetime values and then compare that against the datetime value of the GCal event. If they are not the same, then we change the Notion
    ### event as appropriate
    notion_IDs_List = []
    notion_start_datetimes = []
    notion_end_datetimes = []
    notion_gCal_IDs = []  # we will be comparing this against the gCal_datetimes
    gCal_start_datetimes = []
    gCal_end_datetimes = []

    notion_gCal_CalIds = (
        []
    )  # going to fill this in from the select option, not the text option.
    notion_gCal_CalNames = []
    gCal_CalIds = []

    for result in resultList:
        notion_IDs_List.append(result["id"])
        notion_start_datetimes.append(
            result["properties"][Date_Notion_Name]["date"]["start"]
        )
        notion_end_datetimes.append(
            result["properties"][Date_Notion_Name]["date"]["end"]
        )
        notion_gCal_IDs.append(
            result["properties"][GCalEventId_Notion_Name]["rich_text"][0]["text"][
                "content"
            ]
        )
        try:
            notion_gCal_CalIds.append(
                calendarDictionary[
                    result["properties"][Calendar_Notion_Name]["select"]["name"]
                ]
            )
            notion_gCal_CalNames.append(
                result["properties"][Calendar_Notion_Name]["select"]["name"]
            )
        except:  # keyerror occurs when there's nothing put into the calendar in the first place
            notion_gCal_CalIds.append(calendarDictionary[DEFAULT_CALENDAR_NAME])
            notion_gCal_CalNames.append(
                result["properties"][Calendar_Notion_Name]["select"]["name"]
            )

    # the reason we take off the last 6 characters is so we can focus in on just the date and time instead of any extra info
    for i in range(len(notion_start_datetimes)):
        try:
            notion_start_datetimes[i] = dt.datetime.strptime(
                notion_start_datetimes[i], "%Y-%m-%d"
            )
        except:
            try:
                notion_start_datetimes[i] = dt.datetime.strptime(
                    notion_start_datetimes[i][:-6], "%Y-%m-%dT%H:%M:%S.000"
                )
            except:
                notion_start_datetimes[i] = dt.datetime.strptime(
                    notion_start_datetimes[i][:-6], "%Y-%m-%dT%H:%M:%S.%f"
                )

    for i in range(len(notion_end_datetimes)):
        if notion_end_datetimes[i] != None:
            try:
                notion_end_datetimes[i] = dt.datetime.strptime(
                    notion_end_datetimes[i], "%Y-%m-%d"
                )
            except:
                try:
                    notion_end_datetimes[i] = dt.datetime.strptime(
                        notion_end_datetimes[i][:-6], "%Y-%m-%dT%H:%M:%S.000"
                    )
                except:
                    notion_end_datetimes[i] = dt.datetime.strptime(
                        notion_end_datetimes[i][:-6], "%Y-%m-%dT%H:%M:%S.%f"
                    )
        else:
            notion_end_datetimes[i] = notion_start_datetimes[
                i
            ]  # the reason we're doing this weird ass thing is because when we put the end time into the update or make GCal event, it'll be representative of the date

    ##We use the gCalId from the Notion dashboard to get retrieve the start Time from the gCal event
    value = ""
    exitVar = ""
    for gCalId in notion_gCal_IDs:
        # just check all of the calendars of interest for info about the event
        for calendarID in calendarDictionary.keys():
            print("Trying " + calendarID + " for " + gCalId)
            try:
                x = (
                    service.events()
                    .get(calendarId=calendarDictionary[calendarID], eventId=gCalId)
                    .execute()
                )
            except:
                print("Event not found")
                x = {"status": "unconfirmed"}
            if x["status"] == "confirmed":
                gCal_CalIds.append(calendarID)
                value = x
            else:
                continue

        print(value)
        print("\n")
        try:
            gCal_start_datetimes.append(
                dateutil.parser.isoparse(value["start"]["dateTime"])
            )
        except:
            date = dt.datetime.strptime(value["start"]["date"], "%Y-%m-%d")
            # x = datetime(date.year, date.month, date.day, 0, 0, 0) redundant I think
            # gCal_start_datetimes.append(datetime.strptime(x, "%Y-%m-%dT%H:%M:%S"))
            gCal_start_datetimes.append(date)
        try:
            gCal_end_datetimes.append(
                dateutil.parser.isoparse(value["end"]["dateTime"])
            )
        except:
            date = dt.datetime.strptime(value["end"]["date"], "%Y-%m-%d")
            x = dt.datetime(date.year, date.month, date.day, 0, 0, 0) - dt.timedelta(
                days=1
            )
            gCal_end_datetimes.append(x)

    # Now we iterate and compare the time on the Notion Dashboard and the start time of the GCal event
    # If the datetimes don't match up,  then the Notion  Dashboard must be updated

    new_notion_start_datetimes: list[str | dt.datetime] = [""] * len(
        notion_start_datetimes
    )
    new_notion_end_datetimes: list[str | dt.datetime] = [""] * len(notion_end_datetimes)

    for i in range(len(new_notion_start_datetimes)):
        if notion_start_datetimes[i] != gCal_start_datetimes[i]:
            new_notion_start_datetimes[i] = gCal_start_datetimes[i]

        if notion_end_datetimes[i] != gCal_end_datetimes[i]:
            # this means that there is no end time in notion
            new_notion_end_datetimes[i] = gCal_end_datetimes[i]

    print("test")
    print(new_notion_start_datetimes)
    print(new_notion_end_datetimes)
    print("\n")
    for i in range(len(notion_gCal_IDs)):
        print(notion_start_datetimes[i], gCal_start_datetimes[i], notion_gCal_IDs[i])

    for i in range(len(new_notion_start_datetimes)):
        if (
            new_notion_start_datetimes[i] != "" and new_notion_end_datetimes[i] != ""
        ):  # both start and end time need to be updated
            start: dt.datetime = new_notion_start_datetimes[i]
            end: dt.datetime = new_notion_end_datetimes[i]

            if (
                start.hour == 0 and start.minute == 0 and start == end
            ):  # you're given 12 am dateTimes so you want to enter them as dates (not datetimes) into Notion
                my_page = notion.pages.update(  # update the notion dashboard with the new datetime and update the last updated time
                    **{
                        "page_id": notion_IDs_List[i],
                        "properties": {
                            Date_Notion_Name: {
                                "date": {
                                    "start": start.strftime("%Y-%m-%d"),
                                    "end": None,
                                }
                            },
                            LastUpdatedTime_Notion_Name: {
                                "date": {
                                    "start": notion_time(),  # has to be adjsuted for when daylight savings is different
                                    "end": None,
                                }
                            },
                        },
                    },
                )
            elif (
                start.hour == 0
                and start.minute == 0
                and end.hour == 0
                and end.minute == 0
            ):  # you're given 12 am dateTimes so you want to enter them as dates (not datetimes) into Notion
                my_page = notion.pages.update(  # update the notion dashboard with the new datetime and update the last updated time
                    **{
                        "page_id": notion_IDs_List[i],
                        "properties": {
                            Date_Notion_Name: {
                                "date": {
                                    "start": start.strftime("%Y-%m-%d"),
                                    "end": end.strftime("%Y-%m-%d"),
                                }
                            },
                            LastUpdatedTime_Notion_Name: {
                                "date": {
                                    "start": notion_time(),  # has to be adjsuted for when daylight savings is different
                                    "end": None,
                                }
                            },
                        },
                    },
                )
            else:  # update Notin using datetime format
                my_page = notion.pages.update(  # update the notion dashboard with the new datetime and update the last updated time
                    **{
                        "page_id": notion_IDs_List[i],
                        "properties": {
                            Date_Notion_Name: {
                                "date": {
                                    "start": DateTimeIntoNotionFormat(start),
                                    "end": DateTimeIntoNotionFormat(end),
                                }
                            },
                            LastUpdatedTime_Notion_Name: {
                                "date": {
                                    "start": notion_time(),  # has to be adjsuted for when daylight savings is different
                                    "end": None,
                                }
                            },
                        },
                    },
                )
        elif new_notion_start_datetimes[i] != "":  # only start time need to be updated
            start = new_notion_start_datetimes[i]
            end = notion_end_datetimes[i]

            if (
                start.hour == 0 and start.minute == 0 and start == end
            ):  # you're given 12 am dateTimes so you want to enter them as dates (not datetimes) into Notion
                my_page = notion.pages.update(  # update the notion dashboard with the new datetime and update the last updated time
                    **{
                        "page_id": notion_IDs_List[i],
                        "properties": {
                            Date_Notion_Name: {
                                "date": {
                                    "start": start.strftime("%Y-%m-%d"),
                                    "end": None,
                                }
                            },
                            LastUpdatedTime_Notion_Name: {
                                "date": {
                                    "start": notion_time(),  # has to be adjsuted for when daylight savings is different
                                    "end": None,
                                }
                            },
                        },
                    },
                )
            elif (
                start.hour == 0
                and start.minute == 0
                and end.hour == 0
                and end.minute == 0
            ):  # you're given 12 am dateTimes so you want to enter them as dates (not datetimes) into Notion
                my_page = notion.pages.update(  # update the notion dashboard with the new datetime and update the last updated time
                    **{
                        "page_id": notion_IDs_List[i],
                        "properties": {
                            Date_Notion_Name: {
                                "date": {
                                    "start": start.strftime("%Y-%m-%d"),
                                    "end": end.strftime("%Y-%m-%d"),
                                }
                            },
                            LastUpdatedTime_Notion_Name: {
                                "date": {
                                    "start": notion_time(),  # has to be adjsuted for when daylight savings is different
                                    "end": None,
                                }
                            },
                        },
                    },
                )
            else:  # update Notin using datetime format
                my_page = notion.pages.update(  # update the notion dashboard with the new datetime and update the last updated time
                    **{
                        "page_id": notion_IDs_List[i],
                        "properties": {
                            Date_Notion_Name: {
                                "date": {
                                    "start": DateTimeIntoNotionFormat(start),
                                    "end": DateTimeIntoNotionFormat(end),
                                }
                            },
                            LastUpdatedTime_Notion_Name: {
                                "date": {
                                    "start": notion_time(),  # has to be adjsuted for when daylight savings is different
                                    "end": None,
                                }
                            },
                        },
                    },
                )
        elif new_notion_end_datetimes[i] != "":  # only end time needs to be updated
            start = notion_start_datetimes[i]
            end = new_notion_end_datetimes[i]

            if (
                start.hour == 0 and start.minute == 0 and start == end
            ):  # you're given 12 am dateTimes so you want to enter them as dates (not datetimes) into Notion
                my_page = notion.pages.update(  # update the notion dashboard with the new datetime and update the last updated time
                    **{
                        "page_id": notion_IDs_List[i],
                        "properties": {
                            Date_Notion_Name: {
                                "date": {
                                    "start": start.strftime("%Y-%m-%d"),
                                    "end": None,
                                }
                            },
                            LastUpdatedTime_Notion_Name: {
                                "date": {
                                    "start": notion_time(),  # has to be adjsuted for when daylight savings is different
                                    "end": None,
                                }
                            },
                        },
                    },
                )
            elif (
                start.hour == 0
                and start.minute == 0
                and end.hour == 0
                and end.minute == 0
            ):  # you're given 12 am dateTimes so you want to enter them as dates (not datetimes) into Notion
                my_page = notion.pages.update(  # update the notion dashboard with the new datetime and update the last updated time
                    **{
                        "page_id": notion_IDs_List[i],
                        "properties": {
                            Date_Notion_Name: {
                                "date": {
                                    "start": start.strftime("%Y-%m-%d"),
                                    "end": end.strftime("%Y-%m-%d"),
                                }
                            },
                            LastUpdatedTime_Notion_Name: {
                                "date": {
                                    "start": notion_time(),  # has to be adjsuted for when daylight savings is different
                                    "end": None,
                                }
                            },
                        },
                    },
                )
            else:  # update Notin using datetime format
                my_page = notion.pages.update(  # update the notion dashboard with the new datetime and update the last updated time
                    **{
                        "page_id": notion_IDs_List[i],
                        "properties": {
                            Date_Notion_Name: {
                                "date": {
                                    "start": DateTimeIntoNotionFormat(start),
                                    "end": DateTimeIntoNotionFormat(end),
                                }
                            },
                            LastUpdatedTime_Notion_Name: {
                                "date": {
                                    "start": notion_time(),  # has to be adjsuted for when daylight savings is different
                                    "end": None,
                                }
                            },
                        },
                    },
                )
        else:  # nothing needs to be updated here
            continue

    print(notion_IDs_List)
    print("\n")
    print(gCal_CalIds)

    CalNames = list(calendarDictionary.keys())
    CalIds = list(calendarDictionary.values())

    for i, gCalId in enumerate(
        gCal_CalIds
    ):  # instead of checking, just update the notion datebase with whatever calendar the event is on
        print("GcalId: " + gCalId)
        my_page = notion.pages.update(  ##### This puts the the GCal Id into the Notion Dashboard
            **{
                "page_id": notion_IDs_List[i],
                "properties": {
                    Current_Calendar_Id_Notion_Name: {  # this is the text
                        "rich_text": [
                            {"text": {"content": CalIds[CalNames.index(gCalId)]}}
                        ]
                    },
                    Calendar_Notion_Name: {  # this is the select
                        "select": {"name": gCalId},
                    },
                    LastUpdatedTime_Notion_Name: {
                        "date": {
                            "start": notion_time(),  # has to be adjsuted for when daylight savings is different
                            "end": None,
                        }
                    },
                },
            },
        )


def new_events_gcal_to_notion(
    database_id,
    calendarDictionary,
    Task_Notion_Name,
    Date_Notion_Name,
    ExtraInfo_Notion_Name,
    On_GCal_Notion_Name,
    GCalEventId_Notion_Name,
    LastUpdatedTime_Notion_Name,
    Calendar_Notion_Name,
    Current_Calendar_Id_Notion_Name,
    Delete_Notion_Name,
    service,
    notion,
):
    ###########################################################################
    ##### Part 4: Bring events (not in Notion already) from GCal to Notion
    ###########################################################################

    ##First, we get a list of all of the GCal Event Ids from the Notion Dashboard.

    my_page = notion.databases.query(
        **{
            "database_id": database_id,
            "filter": {
                "and": [
                    {
                        "property": GCalEventId_Notion_Name,
                        "text": {"is_not_empty": True},
                    },
                    {"property": Delete_Notion_Name, "checkbox": {"equals": False}},
                ]
            },
        }
    )

    my_page = notion.databases.query(
        **{
            "database_id": database_id,
            "filter": {
                "property": GCalEventId_Notion_Name,
                "text": {"is_not_empty": True},
            },
        }
    )

    resultList = my_page["results"]

    ALL_notion_gCal_Ids = []

    for result in resultList:
        ALL_notion_gCal_Ids.append(
            result["properties"][GCalEventId_Notion_Name]["rich_text"][0]["text"][
                "content"
            ]
        )

    ##Get the GCal Ids and other Event Info from Google Calendar

    events = []
    # get all the events from all calendars of interest
    for key, value in calendarDictionary.items():
        x = (
            service.events()
            .list(calendarId=value, maxResults=2000, timeMin=googleQuery())
            .execute()
        )
        events.extend(x["items"])

    print(events)

    # calItems = events['items']
    calItems = events

    calName = [item["summary"] for item in calItems]

    gCal_calendarId = [
        item["organizer"]["email"] for item in calItems
    ]  # this is to get all of the calendarIds for each event

    CalNames = list(calendarDictionary.keys())
    CalIds = list(calendarDictionary.values())
    gCal_calendarName = [CalNames[CalIds.index(x)] for x in gCal_calendarId]

    calStartDates = []
    calEndDates = []
    for el in calItems:
        try:
            calStartDates.append(dateutil.parser.isoparse(el["start"]["dateTime"]))
        except:
            date = dt.datetime.strptime(el["start"]["date"], "%Y-%m-%d")
            x = dt.datetime(date.year, date.month, date.day, 0, 0, 0)
            # gCal_start_datetimes.append(datetime.strptime(x, "%Y-%m-%dT%H:%M:%S"))
            calStartDates.append(x)
        try:
            calEndDates.append(dateutil.parser.isoparse(el["end"]["dateTime"]))
        except:
            date = dt.datetime.strptime(el["end"]["date"], "%Y-%m-%d")
            x = dt.datetime(date.year, date.month, date.day, 0, 0, 0)
            calEndDates.append(x)

    calIds = [item["id"] for item in calItems]
    # calDescriptions = [item['description'] for item in calItems]
    calDescriptions = []
    for item in calItems:
        try:
            calDescriptions.append(item["description"])
        except:
            calDescriptions.append(" ")

    # Now, we compare the Ids from Notion and Ids from GCal. If the Id from GCal is not in the list from Notion, then
    ## we know that the event does not exist in Notion yet, so we should bring that over.

    for i in range(len(calIds)):
        if calIds[i] not in ALL_notion_gCal_Ids:
            if calStartDates[i] == calEndDates[i] - dt.timedelta(
                days=1
            ):  # only add in the start DATE
                # Here, we create a new page for every new GCal event
                end = calEndDates[i] - dt.timedelta(days=1)
                my_page = notion.pages.create(
                    **{
                        "parent": {
                            "database_id": database_id,
                        },
                        "properties": {
                            Task_Notion_Name: {
                                "type": "title",
                                "title": [
                                    {
                                        "type": "text",
                                        "text": {
                                            "content": calName[i],
                                        },
                                    },
                                ],
                            },
                            Date_Notion_Name: {
                                "type": "date",
                                "date": {
                                    "start": calStartDates[i].strftime("%Y-%m-%d"),
                                    "end": None,
                                },
                            },
                            LastUpdatedTime_Notion_Name: {
                                "type": "date",
                                "date": {
                                    "start": notion_time(),
                                    "end": None,
                                },
                            },
                            ExtraInfo_Notion_Name: {
                                "type": "rich_text",
                                "rich_text": [
                                    {"text": {"content": calDescriptions[i]}}
                                ],
                            },
                            GCalEventId_Notion_Name: {
                                "type": "rich_text",
                                "rich_text": [{"text": {"content": calIds[i]}}],
                            },
                            On_GCal_Notion_Name: {"type": "checkbox", "checkbox": True},
                            Current_Calendar_Id_Notion_Name: {
                                "rich_text": [{"text": {"content": gCal_calendarId[i]}}]
                            },
                            Calendar_Notion_Name: {
                                "select": {"name": gCal_calendarName[i]},
                            },
                        },
                    },
                )

            elif (
                calStartDates[i].hour == 0
                and calStartDates[i].minute == 0
                and calEndDates[i].hour == 0
                and calEndDates[i].minute == 0
            ):  # add start and end in DATE format
                # Here, we create a new page for every new GCal event
                end = calEndDates[i] - dt.timedelta(days=1)

                my_page = notion.pages.create(
                    **{
                        "parent": {
                            "database_id": database_id,
                        },
                        "properties": {
                            Task_Notion_Name: {
                                "type": "title",
                                "title": [
                                    {
                                        "type": "text",
                                        "text": {
                                            "content": calName[i],
                                        },
                                    },
                                ],
                            },
                            Date_Notion_Name: {
                                "type": "date",
                                "date": {
                                    "start": calStartDates[i].strftime("%Y-%m-%d"),
                                    "end": end.strftime("%Y-%m-%d"),
                                },
                            },
                            LastUpdatedTime_Notion_Name: {
                                "type": "date",
                                "date": {
                                    "start": notion_time(),
                                    "end": None,
                                },
                            },
                            ExtraInfo_Notion_Name: {
                                "type": "rich_text",
                                "rich_text": [
                                    {"text": {"content": calDescriptions[i]}}
                                ],
                            },
                            GCalEventId_Notion_Name: {
                                "type": "rich_text",
                                "rich_text": [{"text": {"content": calIds[i]}}],
                            },
                            On_GCal_Notion_Name: {"type": "checkbox", "checkbox": True},
                            Current_Calendar_Id_Notion_Name: {
                                "rich_text": [{"text": {"content": gCal_calendarId[i]}}]
                            },
                            Calendar_Notion_Name: {
                                "select": {"name": gCal_calendarName[i]},
                            },
                        },
                    },
                )

            else:  # regular datetime stuff
                # Here, we create a new page for every new GCal event
                my_page = notion.pages.create(
                    **{
                        "parent": {
                            "database_id": database_id,
                        },
                        "properties": {
                            Task_Notion_Name: {
                                "type": "title",
                                "title": [
                                    {
                                        "type": "text",
                                        "text": {
                                            "content": calName[i],
                                        },
                                    },
                                ],
                            },
                            Date_Notion_Name: {
                                "type": "date",
                                "date": {
                                    "start": DateTimeIntoNotionFormat(calStartDates[i]),
                                    "end": DateTimeIntoNotionFormat(calEndDates[i]),
                                },
                            },
                            LastUpdatedTime_Notion_Name: {
                                "type": "date",
                                "date": {
                                    "start": notion_time(),
                                    "end": None,
                                },
                            },
                            ExtraInfo_Notion_Name: {
                                "type": "rich_text",
                                "rich_text": [
                                    {"text": {"content": calDescriptions[i]}}
                                ],
                            },
                            GCalEventId_Notion_Name: {
                                "type": "rich_text",
                                "rich_text": [{"text": {"content": calIds[i]}}],
                            },
                            On_GCal_Notion_Name: {"type": "checkbox", "checkbox": True},
                            Current_Calendar_Id_Notion_Name: {
                                "rich_text": [{"text": {"content": gCal_calendarId[i]}}]
                            },
                            Calendar_Notion_Name: {
                                "select": {"name": gCal_calendarName[i]},
                            },
                        },
                    },
                )

            print(f"Added this event to Notion: {calName[i]}")


def delete_page(
    notion: nc.Client,
    database_id,
    GCalEventId_Notion_Name,
    On_GCal_Notion_Name,
    Delete_Notion_Name,
    DELETE_OPTION,
    calendarDictionary,
    Calendar_Notion_Name,
    service,
):
    ###########################################################################
    ##### Part 5: Deletion Sync -- If marked Done in Notion, then it will delete the GCal event (and the Notion event once Python API updates)
    ###########################################################################
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


######################################################################
# METHOD TO MAKE A CALENDAR EVENT DESCRIPTION

# This method can be edited as wanted. Whatever is returned from this method will be in the GCal event description
# Whatever you change up, be sure to return a string


def makeEventDescription(initiative, info):
    if initiative == "" and info == "":
        return ""
    elif info == "":
        return initiative
    elif initiative == "":
        return info
    else:
        return f"Initiative: {initiative} \n{info}"


######################################################################
# METHOD TO MAKE A TASK'S URL
# To make a url for the notion task, we have to take the id of the task and take away the hyphens from the string


def makeTaskURL(ending, urlRoot):
    # urlId = ending[0:8] + ending[9:13] + ending[14:18] + ending[19:23] + ending[24:]  #<--- super inefficient way to do things lol
    urlId = ending.replace("-", "")
    return urlRoot + urlId


######################################################################
# METHOD TO MAKE A CALENDAR EVENT


def makeCalEvent(
    eventName, eventDescription, eventStartTime, sourceURL, eventEndTime, calId, service
):

    if (
        eventStartTime.hour == 0
        and eventStartTime.minute == 0
        and eventEndTime == eventStartTime
    ):  # only startTime is given from the Notion Dashboard
        if config.AllDayEventOption == 1:
            eventStartTime = dt.datetime.combine(
                eventStartTime, dt.datetime.min.time()
            ) + dt.timedelta(
                hours=config.DEFAULT_EVENT_START
            )  ##make the events pop up at 8 am instead of 12 am
            eventEndTime = eventStartTime + dt.timedelta(
                minutes=config.DEFAULT_EVENT_LENGTH
            )
            event = {
                "summary": eventName,
                "description": eventDescription,
                "start": {
                    "dateTime": eventStartTime.strftime("%Y-%m-%dT%H:%M:%S"),
                    "timeZone": config.timezone,
                },
                "end": {
                    "dateTime": eventEndTime.strftime("%Y-%m-%dT%H:%M:%S"),
                    "timeZone": config.timezone,
                },
                "source": {
                    "title": "Notion Link",
                    "url": sourceURL,
                },
            }
        else:
            eventEndTime = eventEndTime + dt.timedelta(
                days=1
            )  # gotta make it to 12AM the day after
            event = {
                "summary": eventName,
                "description": eventDescription,
                "start": {
                    "date": eventStartTime.strftime("%Y-%m-%d"),
                    "timeZone": config.timezone,
                },
                "end": {
                    "date": eventEndTime.strftime("%Y-%m-%d"),
                    "timeZone": config.timezone,
                },
                "source": {
                    "title": "Notion Link",
                    "url": sourceURL,
                },
            }
    elif (
        eventStartTime.hour == 0
        and eventStartTime.minute == 0
        and eventEndTime.hour == 0
        and eventEndTime.minute == 0
        and eventStartTime != eventEndTime
    ):

        eventEndTime = eventEndTime + dt.timedelta(
            days=1
        )  # gotta make it to 12AM the day after

        event = {
            "summary": eventName,
            "description": eventDescription,
            "start": {
                "date": eventStartTime.strftime("%Y-%m-%d"),
                "timeZone": config.timezone,
            },
            "end": {
                "date": eventEndTime.strftime("%Y-%m-%d"),
                "timeZone": config.timezone,
            },
            "source": {
                "title": "Notion Link",
                "url": sourceURL,
            },
        }

    else:  # just 2 datetimes passed in from the method call that are not at 12 AM
        if (
            eventStartTime.hour == 0
            and eventStartTime.minute == 0
            and eventEndTime != eventStartTime
        ):  # Start on Notion is 12 am and end is also given on Notion
            eventStartTime = eventStartTime  # start will be 12 am
            eventEndTime = eventEndTime  # end will be whenever specified
        elif (
            eventStartTime.hour == 0 and eventStartTime.minute == 0
        ):  # if the datetime fed into this is only a date or is at 12 AM, then the event will fall under here
            eventStartTime = dt.datetime.combine(
                eventStartTime, dt.datetime.min.time()
            ) + dt.timedelta(
                hours=config.DEFAULT_EVENT_START
            )  ##make the events pop up at 8 am instead of 12 am
            eventEndTime = eventStartTime + dt.timedelta(
                minutes=config.DEFAULT_EVENT_LENGTH
            )
        elif (
            eventEndTime == eventStartTime
        ):  # this would meant that only 1 datetime was actually on the notion dashboard
            eventStartTime = eventStartTime
            eventEndTime = eventStartTime + dt.timedelta(
                minutes=config.DEFAULT_EVENT_LENGTH
            )
        else:  # if you give a specific start time to the event
            eventStartTime = eventStartTime
            eventEndTime = eventEndTime

        event = {
            "summary": eventName,
            "description": eventDescription,
            "start": {
                "dateTime": eventStartTime.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": config.timezone,
            },
            "end": {
                "dateTime": eventEndTime.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": config.timezone,
            },
            "source": {
                "title": "Notion Link",
                "url": sourceURL,
            },
        }
    print("Adding this event to calendar: ", eventName)

    print(event)
    x = service.events().insert(calendarId=calId, body=event).execute()
    return x["id"]


######################################################################
# METHOD TO UPDATE A CALENDAR EVENT


def upDateCalEvent(
    eventName,
    eventDescription,
    eventStartTime,
    sourceURL,
    eventId,
    eventEndTime,
    currentCalId,
    CalId,
    service,
):

    if (
        eventStartTime.hour == 0
        and eventStartTime.minute == 0
        and eventEndTime == eventStartTime
    ):  # you're given a single date
        if config.AllDayEventOption == 1:
            eventStartTime = dt.datetime.combine(
                eventStartTime, dt.datetime.min.time()
            ) + dt.timedelta(
                hours=config.DEFAULT_EVENT_START
            )  ##make the events pop up at 8 am instead of 12 am
            eventEndTime = eventStartTime + dt.timedelta(
                minutes=config.DEFAULT_EVENT_LENGTH
            )
            event = {
                "summary": eventName,
                "description": eventDescription,
                "start": {
                    "dateTime": eventStartTime.strftime("%Y-%m-%dT%H:%M:%S"),
                    "timeZone": config.timezone,
                },
                "end": {
                    "dateTime": eventEndTime.strftime("%Y-%m-%dT%H:%M:%S"),
                    "timeZone": config.timezone,
                },
                "source": {
                    "title": "Notion Link",
                    "url": sourceURL,
                },
            }
        else:
            eventEndTime = eventEndTime + dt.timedelta(
                days=1
            )  # gotta make it to 12AM the day after
            event = {
                "summary": eventName,
                "description": eventDescription,
                "start": {
                    "date": eventStartTime.strftime("%Y-%m-%d"),
                    "timeZone": config.timezone,
                },
                "end": {
                    "date": eventEndTime.strftime("%Y-%m-%d"),
                    "timeZone": config.timezone,
                },
                "source": {
                    "title": "Notion Link",
                    "url": sourceURL,
                },
            }
    elif (
        eventStartTime.hour == 0
        and eventStartTime.minute == 0
        and eventEndTime.hour == 0
        and eventEndTime.minute == 0
        and eventStartTime != eventEndTime
    ):  # it's a multiple day event

        eventEndTime = eventEndTime + dt.timedelta(
            days=1
        )  # gotta make it to 12AM the day after

        event = {
            "summary": eventName,
            "description": eventDescription,
            "start": {
                "date": eventStartTime.strftime("%Y-%m-%d"),
                "timeZone": config.timezone,
            },
            "end": {
                "date": eventEndTime.strftime("%Y-%m-%d"),
                "timeZone": config.timezone,
            },
            "source": {
                "title": "Notion Link",
                "url": sourceURL,
            },
        }

    else:  # just 2 datetimes passed in
        if (
            eventStartTime.hour == 0
            and eventStartTime.minute == 0
            and eventEndTime != eventStartTime
        ):  # Start on Notion is 12 am and end is also given on Notion
            eventStartTime = eventStartTime  # start will be 12 am
            eventEndTime = eventEndTime  # end will be whenever specified
        elif (
            eventStartTime.hour == 0 and eventStartTime.minute == 0
        ):  # if the datetime fed into this is only a date or is at 12 AM, then the event will fall under here
            eventStartTime = dt.datetime.combine(
                eventStartTime, dt.datetime.min.time()
            ) + dt.timedelta(
                hours=config.DEFAULT_EVENT_START
            )  ##make the events pop up at 8 am instead of 12 am
            eventEndTime = eventStartTime + dt.timedelta(
                minutes=config.DEFAULT_EVENT_LENGTH
            )
        elif (
            eventEndTime == eventStartTime
        ):  # this would meant that only 1 datetime was actually on the notion dashboard
            eventStartTime = eventStartTime
            eventEndTime = eventStartTime + dt.timedelta(
                minutes=config.DEFAULT_EVENT_LENGTH
            )
        else:  # if you give a specific start time to the event
            eventStartTime = eventStartTime
            eventEndTime = eventEndTime
        event = {
            "summary": eventName,
            "description": eventDescription,
            "start": {
                "dateTime": eventStartTime.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": config.timezone,
            },
            "end": {
                "dateTime": eventEndTime.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": config.timezone,
            },
            "source": {
                "title": "Notion Link",
                "url": sourceURL,
            },
        }
    print("Updating this event to calendar: ", eventName)

    if currentCalId == CalId:
        x = (
            service.events()
            .update(calendarId=CalId, eventId=eventId, body=event)
            .execute()
        )

    else:  # When we have to move the event to a new calendar. We must move the event over to the new calendar and then update the information on the event
        print("Event " + eventId)
        print("CurrentCal " + currentCalId)
        print("NewCal " + CalId)
        x = (
            service.events()
            .move(calendarId=currentCalId, eventId=eventId, destination=CalId)
            .execute()
        )
        print("New event id: " + x["id"])
        x = (
            service.events()
            .update(calendarId=CalId, eventId=eventId, body=event)
            .execute()
        )

    return x["id"]
