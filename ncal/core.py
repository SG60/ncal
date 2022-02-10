import datetime
import logging
import pickle
import time
from typing import Any, Literal

import arrow
import dateutil.parser
import google.auth.exceptions  # type: ignore
import googleapiclient.discovery  # type: ignore
import notion_client as nc  # type: ignore
from googleapiclient.errors import HttpError  # type: ignore

from ncal import config
from ncal.gcal_token import gcal_token


def setup_google_api(
    calendar_id: str, credentials_location: str
) -> tuple[googleapiclient.discovery.Resource, Any]:
    """Set up the Google Calendar API interface"""

    credentials = pickle.load(open(credentials_location, "rb"))
    service = googleapiclient.discovery.build("calendar", "v3", credentials=credentials)

    # There could be a hiccup if the Google Calendar API token expires.
    # If the token expires, we create a new token for the program to use
    try:
        calendar = service.calendars().get(calendarId=calendar_id).execute()
    except google.auth.exceptions.RefreshError:
        # refresh the token

        # os.system(runscriptlocation)
        gcal_token(credentials_location, "client_secret.json")

        # SET UP THE GOOGLE CALENDAR API INTERFACE

        credentials = pickle.load(open(credentials_location, "rb"))
        service = googleapiclient.discovery.build(
            "calendar", "v3", credentials=credentials
        )

        # result = service.calendarList().list().execute()
        # logging.info(result['items'][:])

        calendar = service.calendars().get(calendarId=calendar_id).execute()

    return (service, calendar)


def setup_api_connections(
    runscript_location, default_calendar_id, credentials_location, notion_api_token
) -> tuple[googleapiclient.discovery.Resource, Any, nc.Client]:
    """Setup the API connections to Google Calendar and notion
    Args:
        default_calendar_id: gcal calendar Id
        credentials_location: location of the credentials pickle file
        notion_api_token: token from the notion api
    Returns:
        (google api service, calendar, notion client)
    """
    # setup google api
    service, calendar = setup_google_api(
        default_calendar_id,
        str(credentials_location),
    )
    # This is where we set up the connection with the Notion API
    notion = nc.Client(auth=notion_api_token)
    return service, calendar, notion


def paginated_database_query(
    notion_client: nc.Client, database_id: str, **query: dict
) -> list:
    """similar to notion_client.database.query(**query)
    Args:
        notion_client:
        database_id:
        query: A query such as would be used for the normal notion_client query
    Returns:
        List of notion pages matching the query
    """
    matching_pages = []

    while True:
        # this query will return a dictionary that we will parse
        # for information that we want
        response = notion_client.databases.query(database_id, **query)
        matching_pages.extend(response["results"])  # type: ignore
        if response["next_cursor"]:  # type: ignore
            query["start_cursor"] = response["next_cursor"]  # type: ignore
        else:
            break
    return matching_pages


def get_property_text(
    notion: nc.Client,
    notion_page: dict[str, Any],
    property_name: str,
    property_type: Literal["relation", "select"],
) -> str:
    """Get the text contained within several different types of property.

    Note: Currently only relation and select are implemented."""
    text: str
    if property_type == "select":
        text = notion_page["properties"][property_name]["select"]["name"]
    elif property_type == "relation":
        text = get_relation_title(
            notion=notion, notion_page=notion_page, relation_name=property_name
        )
    else:
        raise ValueError
    return text


def get_relation_title(
    notion: nc.Client, notion_page: dict[str, Any], relation_name: str
) -> str:
    """Get the title of the first page in a relation property."""
    relation_property: list = notion_page["properties"][relation_name]["relation"]
    if relation_property:
        relation_id: str = relation_property[0]["id"]
        relation_title: dict = notion.pages.properties.retrieve(
            relation_id, "title"
        )  # type:ignore
        return relation_title["results"][0]["title"]["plain_text"]
    else:
        return ""


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
    settings: config.Settings,
):
    """
    Take Notion Events not on GCal and move them over to GCal

    If you just want all Notion events to be on GCal, then you'll have to edit the
    query so it is only checking the 'On GCal?' property
    """

    def get_new_notion_pages(
        database_id: str,
        on_gcal_notion_name: str,
        date_notion_name: str,
        delete_notion_name: str,
        notion: nc.Client,
    ) -> list:
        """Get new pages from notion (with pagination!)."""
        # todayDate = datetime.datetime.today().strftime("%Y-%m-%d")
        # todayDate = arrow.utcnow().isoformat()

        matching_pages = []

        query = {
            # "database_id": database_id,
            "filter": {
                "and": [
                    {
                        "property": on_gcal_notion_name,
                        "checkbox": {"equals": False},
                    },
                    # {
                    #     "property": date_notion_name,
                    #     "date": {"on_or_after": todayDate},
                    # },
                    {"property": delete_notion_name, "checkbox": {"equals": False}},
                ]
            },
        }

        matching_pages = paginated_database_query(notion, database_id, **query)
        return matching_pages

    resultList = get_new_notion_pages(
        database_id, On_GCal_Notion_Name, Date_Notion_Name, Delete_Notion_Name, notion
    )

    # logging.info(len(resultList))

    try:
        logging.info(resultList[0])
    except IndexError:
        logging.info("")

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
            logging.info("\n")
            logging.info(el)
            logging.info("\n")

            TaskNames.append(
                el["properties"][Task_Notion_Name]["title"][0]["text"]["content"]
            )
            start_Dates.append(el["properties"][Date_Notion_Name]["date"]["start"])

            if el["properties"][Date_Notion_Name]["date"]["end"] is not None:
                end_Times.append(el["properties"][Date_Notion_Name]["date"]["end"])
            else:
                end_Times.append(el["properties"][Date_Notion_Name]["date"]["start"])

            try:
                Initiatives.append(
                    get_property_text(
                        notion=notion,
                        notion_page=el,
                        property_name=Initiative_Notion_Name,
                        property_type=settings.initiative_notion_type,
                    )
                )
            except ValueError:
                Initiatives.append("")

            try:
                ExtraInfo.append(
                    el["properties"][ExtraInfo_Notion_Name]["rich_text"][0]["text"][
                        "content"
                    ]
                )
            except IndexError:
                ExtraInfo.append("")
            URL_list.append(makeTaskURL(el["id"], urlRoot))

            try:
                CalendarList.append(
                    calendarDictionary[
                        el["properties"][Calendar_Notion_Name]["select"]["name"]
                    ]
                )
            # keyerror occurs when there's nothing put into the calendar in the first
            # place
            except (KeyError, TypeError):
                CalendarList.append(calendarDictionary[DEFAULT_CALENDAR_NAME])

            pageId = el["id"]
            # This checks off that the event has been put on Google Calendar
            notion.pages.update(
                **{
                    "page_id": pageId,
                    "properties": {
                        On_GCal_Notion_Name: {"checkbox": True},
                        LastUpdatedTime_Notion_Name: {
                            "date": {
                                "start": arrow.utcnow().isoformat(),
                                "end": None,
                            }
                        },
                    },
                },
            )
            logging.info(CalendarList)

            def create_gcal_event(
                task_name,
                initiative,
                extra_info,
                start,
                end,
                url,
                calendar,
                service,
                settings: config.Settings,
            ):
                # 2 Cases: Start and End are  both either date or date+time
                # Have restriction that the calendar events don't cross days
                try:
                    # start and end are both dates
                    calEventId = makeCalEvent(
                        task_name,
                        makeEventDescription(initiative, extra_info),
                        datetime.datetime.strptime(start, "%Y-%m-%d"),
                        url,
                        datetime.datetime.strptime(end, "%Y-%m-%d"),
                        calendar,
                        service,
                        settings,
                    )
                except ValueError:
                    try:
                        # start and end are both date+time
                        calEventId = makeCalEvent(
                            task_name,
                            makeEventDescription(initiative, extra_info),
                            dateutil.parser.isoparse(start),
                            url,
                            dateutil.parser.isoparse(end),
                            calendar,
                            service,
                            settings,
                        )
                    except ValueError:
                        calEventId = makeCalEvent(
                            task_name,
                            makeEventDescription(initiative, extra_info),
                            dateutil.parser.isoparse(start),
                            url,
                            dateutil.parser.isoparse(end),
                            calendar,
                            service,
                            settings,
                        )
                return calEventId

            calEventId = create_gcal_event(
                TaskNames[i],
                Initiatives[i],
                ExtraInfo[i],
                start_Dates[i],
                end_Times[i],
                URL_list[i],
                CalendarList[i],
                service,
                settings,
            )
            calEventIdList.append(calEventId)

            if (
                CalendarList[i] == calendarDictionary[DEFAULT_CALENDAR_NAME]
            ):  # this means that there is no calendar assigned on Notion
                # This puts the the GCal Id into the Notion Dashboard
                notion.pages.update(
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
                notion.pages.update(
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
        logging.info("Nothing new added to GCal")
    return


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
    settings: config.Settings,
):
    """
    Updating GCal Events that Need To Be Updated
    (Changed on Notion but need to be changed on GCal)
    """
    # In case people deleted the Calendar Variable, this queries items where
    # the Calendar select thing is empty
    query = {
        "filter": {
            "and": [
                {"property": Calendar_Notion_Name, "select": {"is_empty": True}},
                # {
                #     "or": [
                #         {
                #             "property": Date_Notion_Name,
                #             "date": {"equals": todayDate},
                #         },
                #         {"property": Date_Notion_Name, "date": {"next_week": {}}},
                #     ]
                # },
                {"property": Delete_Notion_Name, "checkbox": {"equals": False}},
            ]
        },
    }
    resultList = paginated_database_query(
        notion_client=notion, database_id=database_id, **query
    )
    # resultList = my_page["results"]

    if len(resultList) > 0:
        for i, el in enumerate(resultList):
            pageId = el["id"]

            # This checks off that the event has been put on Google Calendar
            notion.pages.update(
                **{
                    "page_id": pageId,
                    "properties": {
                        Calendar_Notion_Name: {
                            "select": {"name": DEFAULT_CALENDAR_NAME},
                        },
                        LastUpdatedTime_Notion_Name: {
                            "date": {
                                "start": arrow.utcnow().isoformat(),
                                "end": None,
                            }
                        },
                    },
                },
            )

    # Filter events that have been updated since the GCal event has been made

    # this query will return a dictionary that we will parse for information that
    # we want
    # look for events that are today or in the next week
    query = {
        "filter": {
            "and": [
                {
                    "property": NeedGCalUpdate_Notion_Name,
                    "checkbox": {"equals": True},
                },
                {"property": On_GCal_Notion_Name, "checkbox": {"equals": True}},
                # {
                #     "or": [
                #         {
                #             "property": Date_Notion_Name,
                #             "date": {"equals": todayDate},
                #         },
                #         {"property": Date_Notion_Name, "date": {"next_week": {}}},
                #     ]
                # },
                {"property": Delete_Notion_Name, "checkbox": {"equals": False}},
            ]
        },
    }
    resultList = paginated_database_query(notion, database_id, **query)

    updatingNotionPageIds = []
    updatingCalEventIds = []

    for result in resultList:
        logging.info(result)
        logging.info("\n")
        pageId = result["id"]
        updatingNotionPageIds.append(pageId)
        logging.info("\n")
        logging.info(result)
        logging.info("\n")
        try:
            calId = result["properties"][GCalEventId_Notion_Name]["rich_text"][0][
                "text"
            ]["content"]
        except IndexError:
            calId = DEFAULT_CALENDAR_ID
        logging.info(calId)
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
            logging.info("\n")
            logging.info(el)
            logging.info("\n")

            TaskNames.append(
                el["properties"][Task_Notion_Name]["title"][0]["text"]["content"]
            )
            start_Dates.append(el["properties"][Date_Notion_Name]["date"]["start"])

            if el["properties"][Date_Notion_Name]["date"]["end"] is not None:
                end_Times.append(el["properties"][Date_Notion_Name]["date"]["end"])
            else:
                end_Times.append(el["properties"][Date_Notion_Name]["date"]["start"])

            try:
                Initiatives.append(
                    get_property_text(
                        notion=notion,
                        notion_page=el,
                        property_name=Initiative_Notion_Name,
                        property_type=settings.initiative_notion_type,
                    )
                )
            except ValueError:
                Initiatives.append("")

            try:
                ExtraInfo.append(
                    el["properties"][ExtraInfo_Notion_Name]["rich_text"][0]["text"][
                        "content"
                    ]
                )
            except IndexError:
                ExtraInfo.append("")
            URL_list.append(makeTaskURL(el["id"], urlRoot))

            logging.info(el)
            # CalendarList.append(calendarDictionary[el['properties'][Calendar_Notion_Name]['select']['name']])
            try:
                CalendarList.append(
                    calendarDictionary[
                        el["properties"][Calendar_Notion_Name]["select"]["name"]
                    ]
                )
            # keyerror occurs when there's nothing put into the calendar in the first
            # place
            except KeyError:
                CalendarList.append(calendarDictionary[DEFAULT_CALENDAR_NAME])

            CurrentCalList.append(
                el["properties"][Current_Calendar_Id_Notion_Name]["rich_text"][0][
                    "text"
                ]["content"]
            )

            pageId = el["id"]

            # depending on the format of the dates, we'll update the gCal event as
            # necessary
            try:
                upDateCalEvent(
                    TaskNames[i],
                    makeEventDescription(Initiatives[i], ExtraInfo[i]),
                    datetime.datetime.strptime(start_Dates[i], "%Y-%m-%d"),
                    URL_list[i],
                    updatingCalEventIds[i],
                    datetime.datetime.strptime(end_Times[i], "%Y-%m-%d"),
                    CurrentCalList[i],
                    CalendarList[i],
                    service,
                    settings,
                )
            except ValueError:
                try:
                    upDateCalEvent(
                        TaskNames[i],
                        makeEventDescription(Initiatives[i], ExtraInfo[i]),
                        dateutil.parser.isoparse(start_Dates[i]),
                        URL_list[i],
                        updatingCalEventIds[i],
                        dateutil.parser.isoparse(end_Times[i]),
                        CurrentCalList[i],
                        CalendarList[i],
                        service,
                        settings,
                    )
                except ValueError:
                    upDateCalEvent(
                        TaskNames[i],
                        makeEventDescription(Initiatives[i], ExtraInfo[i]),
                        dateutil.parser.isoparse(start_Dates[i]),
                        URL_list[i],
                        updatingCalEventIds[i],
                        dateutil.parser.isoparse(end_Times[i]),
                        CurrentCalList[i],
                        CalendarList[i],
                        service,
                        settings,
                    )

            # This updates the last time that the page in Notion was updated by the code
            notion.pages.update(
                **{
                    "page_id": pageId,
                    "properties": {
                        LastUpdatedTime_Notion_Name: {
                            "date": {
                                "start": arrow.utcnow().isoformat(),
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
        logging.info("Nothing new updated to GCal")


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
    settings: config.Settings,
):
    """
    Sync GCal event updates for events already in Notion back to Notion!

    Query notion tasks already in Gcal, don't have to be updated, and are today or
    in the future.
    """
    query = {
        "filter": {
            "and": [
                {
                    "property": NeedGCalUpdate_Notion_Name,
                    "formula": {"checkbox": {"equals": False}},
                },
                {"property": On_GCal_Notion_Name, "checkbox": {"equals": True}},
                # {
                #     "or": [
                #         {
                #             "property": Date_Notion_Name,
                #             "date": {"equals": todayDate},
                #         },
                #         {"property": Date_Notion_Name, "date": {"next_week": {}}},
                #     ]
                # },
                {"property": Delete_Notion_Name, "checkbox": {"equals": False}},
            ]
        },
    }

    resultList = paginated_database_query(notion, database_id, **query)

    # Comparison section:
    # We need to see what times between GCal and Notion are not the same, so we are
    # going to convert all of the notion date/times into datetime values and then
    # compare that against the datetime value of the GCal event.
    # If they are not the same, then we change the Notion event as appropriate.
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
        # keyerror occurs when there's nothing put into the calendar in the first place
        except KeyError:
            notion_gCal_CalIds.append(calendarDictionary[DEFAULT_CALENDAR_NAME])
            notion_gCal_CalNames.append(
                result["properties"][Calendar_Notion_Name]["select"]["name"]
            )

    # the reason we take off the last 6 characters is so we can focus in on just the
    # date and time instead of any extra info
    for i in range(len(notion_start_datetimes)):
        try:
            notion_start_datetimes[i] = datetime.datetime.strptime(
                notion_start_datetimes[i], "%Y-%m-%d"
            )
        except ValueError:
            try:
                notion_start_datetimes[i] = datetime.datetime.strptime(
                    notion_start_datetimes[i][:-6], "%Y-%m-%dT%H:%M:%S.000"
                )
            except ValueError:
                notion_start_datetimes[i] = datetime.datetime.strptime(
                    notion_start_datetimes[i][:-6], "%Y-%m-%dT%H:%M:%S.%f"
                )

    for i in range(len(notion_end_datetimes)):
        if notion_end_datetimes[i] is not None:
            try:
                notion_end_datetimes[i] = datetime.datetime.strptime(
                    notion_end_datetimes[i], "%Y-%m-%d"
                )
            except ValueError:
                try:
                    notion_end_datetimes[i] = datetime.datetime.strptime(
                        notion_end_datetimes[i][:-6], "%Y-%m-%dT%H:%M:%S.000"
                    )
                except ValueError:
                    notion_end_datetimes[i] = datetime.datetime.strptime(
                        notion_end_datetimes[i][:-6], "%Y-%m-%dT%H:%M:%S.%f"
                    )
        else:
            # the reason we're doing this weird ass thing is because when we put the
            # end time into the update or make GCal event, it'll be representative of
            # the date
            notion_end_datetimes[i] = notion_start_datetimes[i]

    # We use the gCalId from the Notion dashboard to get retrieve the start Time from
    # the gCal event
    value = ""
    # exitVar = ""
    for gCalId in notion_gCal_IDs:
        # just check all of the calendars of interest for info about the event
        for calendarID in calendarDictionary.keys():
            logging.info("Trying " + calendarID + " for " + gCalId)
            try:
                x = (
                    service.events()
                    .get(calendarId=calendarDictionary[calendarID], eventId=gCalId)
                    .execute()
                )
            except HttpError:
                logging.info("Event not found")
                x = {"status": "unconfirmed"}
            if x["status"] == "confirmed":
                gCal_CalIds.append(calendarID)
                value = x
            else:
                continue

        logging.info(value)
        logging.info("\n")
        try:
            gCal_start_datetimes.append(
                dateutil.parser.isoparse(value["start"]["dateTime"])  # type: ignore
            )
        except KeyError:
            date = datetime.datetime.strptime(value["start"]["date"], "%Y-%m-%d")  # type: ignore # noqa
            # x = datetime(date.year, date.month, date.day, 0, 0, 0) redundant I think
            # gCal_start_datetimes.append(datetime.strptime(x, "%Y-%m-%dT%H:%M:%S"))
            gCal_start_datetimes.append(date)
        try:
            gCal_end_datetimes.append(
                dateutil.parser.isoparse(value["end"]["dateTime"])  # type: ignore
            )
        except KeyError:
            date = datetime.datetime.strptime(value["end"]["date"], "%Y-%m-%d")  # type: ignore # noqa
            x = datetime.datetime(
                date.year, date.month, date.day, 0, 0, 0
            ) - datetime.timedelta(days=1)
            gCal_end_datetimes.append(x)

    # Now we iterate and compare the time on the Notion Dashboard and the start time of
    # the GCal event
    # If the datetimes don't match up,  then the Notion  Dashboard must be updated

    new_notion_start_datetimes: list[None | datetime.datetime] = []
    new_notion_end_datetimes: list[None | datetime.datetime] = []

    for i in range(len(notion_start_datetimes)):
        if notion_start_datetimes[i] != gCal_start_datetimes[i]:
            new_notion_start_datetimes.append(gCal_start_datetimes[i])
        else:
            new_notion_start_datetimes.append(None)

        if notion_end_datetimes[i] != gCal_end_datetimes[i]:
            # this means that there is no end time in notion
            new_notion_end_datetimes.append(gCal_end_datetimes[i])
        else:
            new_notion_end_datetimes.append(None)

    # for i in range(len(notion_start_datetimes)):
    #     if notion_start_datetimes[i] != gCal_start_datetimes[i]:
    #         new_notion_start_datetimes[i] = gCal_start_datetimes[i]

    #     if notion_end_datetimes[i] != gCal_end_datetimes[i]:
    #         # this means that there is no end time in notion
    #         new_notion_end_datetimes[i] = gCal_end_datetimes[i]

    logging.info("test")
    logging.info(new_notion_start_datetimes)
    logging.info(new_notion_end_datetimes)
    logging.info("\n")
    for i in range(len(notion_gCal_IDs)):
        logging.info(
            notion_start_datetimes[i], gCal_start_datetimes[i], notion_gCal_IDs[i]
        )

    # for i, new_start, new_end in range(len(new_notion_start_datetimes)):
    for i, (new_start, new_end) in enumerate(
        zip(new_notion_start_datetimes, new_notion_end_datetimes)
    ):
        if (
            new_start is not None and new_end is not None
        ):  # both start and end time need to be updated
            start: datetime.datetime = new_start
            end: datetime.datetime = new_end

            # you're given 12 am dateTimes so you want to enter them as dates (not
            # datetimes) into Notion
            if start.hour == 0 and start.minute == 0 and start == end:
                # update the notion dashboard with the new datetime and update the last
                # updated time
                notion.pages.update(
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
                                    "start": arrow.utcnow().isoformat(),
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
            ):
                # you're given 12 am dateTimes so you want to enter them as dates (not
                # datetimes) into Notion
                # update the notion dashboard with the new datetime and update the last
                # updated time
                notion.pages.update(
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
                                    "start": arrow.utcnow().isoformat(),
                                    "end": None,
                                }
                            },
                        },
                    },
                )
            else:  # update Notion using datetime format
                notion.pages.update(
                    # update the notion dashboard with the new datetime and update the
                    # last updated time
                    **{
                        "page_id": notion_IDs_List[i],
                        "properties": {
                            Date_Notion_Name: {
                                "date": {
                                    "start": start.isoformat(),
                                    "end": end.isoformat(),
                                }
                            },
                            LastUpdatedTime_Notion_Name: {
                                "date": {
                                    "start": arrow.utcnow().isoformat(),
                                    "end": None,
                                }
                            },
                        },
                    },
                )
        elif new_start is not None:  # only start time need to be updated
            start = new_start
            end = notion_end_datetimes[i]

            if start.hour == 0 and start.minute == 0 and start == end:
                # you're given 12 am dateTimes so you want to enter them as dates (not
                # datetimes) into Notion
                # update the notion dashboard with the new datetime and update the last
                # updated time
                notion.pages.update(
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
                                    "start": arrow.utcnow().isoformat(),
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
            ):
                # you're given 12 am dateTimes so you want to enter them as dates
                # (not datetimes) into Notion
                notion.pages.update(
                    # update the notion dashboard with the new datetime and update the
                    # last updated time
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
                                    "start": arrow.utcnow().isoformat(),
                                    "end": None,
                                }
                            },
                        },
                    },
                )
            else:
                # update Notion using datetime format
                notion.pages.update(
                    # update the notion dashboard with the new datetime and update the
                    # last updated time
                    **{
                        "page_id": notion_IDs_List[i],
                        "properties": {
                            Date_Notion_Name: {
                                "date": {
                                    "start": start.isoformat(),
                                    "end": end.isoformat(),
                                }
                            },
                            LastUpdatedTime_Notion_Name: {
                                "date": {
                                    "start": arrow.utcnow().isoformat(),
                                    "end": None,
                                }
                            },
                        },
                    },
                )
        elif new_end is not None:  # only end time needs to be updated
            start = notion_start_datetimes[i]
            end = new_end

            if start.hour == 0 and start.minute == 0 and start == end:
                # you're given 12 am dateTimes so you want to enter them as dates (not
                # datetimes) into Notion
                notion.pages.update(
                    # update the notion dashboard with the new datetime and update the
                    # last updated time
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
                                    "start": arrow.utcnow().isoformat(),
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
            ):
                # update the notion dashboard with the new datetime and update the last
                # updated time
                notion.pages.update(
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
                                    "start": arrow.utcnow().isoformat(),
                                    "end": None,
                                }
                            },
                        },
                    },
                )
            else:
                # update Notion using datetime format
                notion.pages.update(
                    # update the notion dashboard with the new datetime and update the
                    # last updated time
                    **{
                        "page_id": notion_IDs_List[i],
                        "properties": {
                            Date_Notion_Name: {
                                "date": {
                                    "start": start.isoformat(),
                                    "end": end.isoformat(),
                                }
                            },
                            LastUpdatedTime_Notion_Name: {
                                "date": {
                                    "start": arrow.utcnow().isoformat(),
                                    "end": None,
                                }
                            },
                        },
                    },
                )
        else:  # nothing needs to be updated here
            continue

    logging.info(notion_IDs_List)
    logging.info("\n")
    logging.info(gCal_CalIds)

    CalNames = list(calendarDictionary.keys())
    CalIds = list(calendarDictionary.values())

    for i, gCalId in enumerate(gCal_CalIds):
        # instead of checking, just update the notion datebase with whatever calendar
        # the event is on
        logging.info("GcalId: " + gCalId)
        notion.pages.update(
            # This puts the the GCal Id into the Notion Dashboard
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
                            "start": arrow.utcnow().isoformat(),
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
    settings: config.Settings,
):
    """
    Bring events (not in Notion already) from GCal to Notion

    First, we get a list of all of the GCal Event Ids from the Notion Dashboard.
    """

    my_page = paginated_database_query(
        notion,
        database_id,
        **{
            "filter": {
                "and": [
                    {
                        "property": GCalEventId_Notion_Name,
                        "text": {"is_not_empty": True},
                    },
                    {"property": Delete_Notion_Name, "checkbox": {"equals": False}},
                ]
            },
        },
    )

    my_page = paginated_database_query(
        notion,
        database_id,
        **{
            "filter": {
                "property": GCalEventId_Notion_Name,
                "text": {"is_not_empty": True},
            },
        },
    )

    resultList = my_page

    ALL_notion_gCal_Ids = []

    for result in resultList:
        ALL_notion_gCal_Ids.append(
            result["properties"][GCalEventId_Notion_Name]["rich_text"][0]["text"][
                "content"
            ]
        )

    # Get the GCal Ids and other Event Info from Google Calendar

    events = []
    # get all the events from all calendars of interest
    for key, value in calendarDictionary.items():
        x = (
            service.events()
            .list(calendarId=value, maxResults=2000, timeMin=arrow.utcnow().isoformat())
            .execute()
        )
        events.extend(x["items"])
        time.sleep(0.1)

    logging.info(events)

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
        except KeyError:
            date = datetime.datetime.strptime(el["start"]["date"], "%Y-%m-%d")
            x = datetime.datetime(date.year, date.month, date.day, 0, 0, 0)
            # gCal_start_datetimes.append(datetime.strptime(x, "%Y-%m-%dT%H:%M:%S"))
            calStartDates.append(x)
        try:
            calEndDates.append(dateutil.parser.isoparse(el["end"]["dateTime"]))
        except KeyError:
            date = datetime.datetime.strptime(el["end"]["date"], "%Y-%m-%d")
            x = datetime.datetime(date.year, date.month, date.day, 0, 0, 0)
            calEndDates.append(x)

    calIds = [item["id"] for item in calItems]
    # calDescriptions = [item['description'] for item in calItems]
    calDescriptions = []
    for item in calItems:
        try:
            calDescriptions.append(item["description"])
        except KeyError:
            calDescriptions.append(" ")

    # Now, we compare the Ids from Notion and Ids from GCal. If the Id from GCal is
    # not in the list from Notion, then we know that the event does not exist in
    # Notion yet, so we should bring that over.

    for i in range(len(calIds)):
        if calIds[i] not in ALL_notion_gCal_Ids:
            if calStartDates[i] == calEndDates[i] - datetime.timedelta(
                days=1
            ):  # only add in the start DATE
                # Here, we create a new page for every new GCal event
                end = calEndDates[i] - datetime.timedelta(days=1)
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
                                    "start": arrow.utcnow().isoformat(),
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
                end = calEndDates[i] - datetime.timedelta(days=1)

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
                                    "start": arrow.utcnow().isoformat(),
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
                                    "start": calStartDates[i].isoformat(),
                                    "end": calEndDates[i].isoformat(),
                                },
                            },
                            LastUpdatedTime_Notion_Name: {
                                "type": "date",
                                "date": {
                                    "start": arrow.utcnow().isoformat(),
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

            logging.info(f"Added this event to Notion: {calName[i]}")


def delete_done_pages(
    notion: nc.Client,
    database_id: str,
    GCalEventId_Notion_Name,
    On_GCal_Notion_Name,
    Delete_Notion_Name,
    DELETE_OPTION: bool,
    calendarDictionary,
    Calendar_Notion_Name,
    service,
):
    """Deletion Sync

    - If marked *Done* in Notion, then it will delete the GCal event
    (and the Notion event once Python API updates)
    """
    resultList = paginated_database_query(
        notion,
        database_id,
        **{
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
        },
    )

    if (
        DELETE_OPTION and len(resultList) > 0
    ):  # delete gCal event (and Notion task once the Python API is updated)
        # CalendarList = []
        # CurrentCalList = []

        for i, el in enumerate(resultList):
            calendarID = calendarDictionary[
                el["properties"][Calendar_Notion_Name]["select"]["name"]
            ]
            eventId = el["properties"][GCalEventId_Notion_Name]["rich_text"][0]["text"][
                "content"
            ]

            # pageId = el["id"]

            try:
                service.events().delete(
                    calendarId=calendarID, eventId=eventId
                ).execute()
                logging.info("deleted:", calendarID, eventId)
            except HttpError:
                continue
            time.sleep(0.1)

            # my_page = notion.pages.update(  # Delete Notion task
            #     **{"page_id": pageId, "archived": True, "properties": {}},
            # )

            # logging.info(my_page)


def makeEventDescription(initiative, info):
    """Method to make a calendar event description

    This method can be edited as wanted. Whatever is returned from this method will
    be in the GCal event description
    Whatever you change up, be sure to return a string
    """
    if initiative == "" and info == "":
        return ""
    elif info == "":
        return initiative
    elif initiative == "":
        return info
    else:
        return f"Initiative: {initiative} \n{info}"


def makeTaskURL(ending, urlRoot):
    """
    Method to make a task's url
    """
    # To make a url for the notion task, we have to take the id of the task and take
    # away the hyphens from the string
    urlId = ending.replace("-", "")
    return urlRoot + urlId


def makeCalEvent(
    eventName,
    eventDescription,
    eventStartTime,
    sourceURL,
    eventEndTime,
    calId,
    service,
    config: config.Settings,
):
    """
    Method to make a calendar event
    """
    if (
        eventStartTime.hour == 0
        and eventStartTime.minute == 0
        and eventEndTime == eventStartTime
    ):  # only startTime is given from the Notion Dashboard
        if config.all_day_event_option == 1:
            eventStartTime = datetime.datetime.combine(
                eventStartTime, datetime.datetime.min.time()
            ) + datetime.timedelta(
                hours=config.default_event_start
            )  # make the events pop up at 8 am instead of 12 am
            eventEndTime = eventStartTime + datetime.timedelta(
                minutes=config.default_event_length
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
            eventEndTime = eventEndTime + datetime.timedelta(
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

        eventEndTime = eventEndTime + datetime.timedelta(
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
        elif eventStartTime.hour == 0 and eventStartTime.minute == 0:
            # if the datetime fed into this is only a date or is at 12 AM,
            # then the event will fall under here
            eventStartTime = datetime.datetime.combine(
                eventStartTime, datetime.datetime.min.time()
            ) + datetime.timedelta(
                hours=config.default_event_start
            )  # make the events pop up at 8 am instead of 12 am
            eventEndTime = eventStartTime + datetime.timedelta(
                minutes=config.default_event_length
            )
        elif eventEndTime == eventStartTime:
            # this would meant that only 1 datetime was actually on the notion dashboard
            eventStartTime = eventStartTime
            eventEndTime = eventStartTime + datetime.timedelta(
                minutes=config.default_event_length
            )
        else:
            # if you give a specific start time to the event
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
    logging.info("Adding this event to calendar: ", eventName)

    logging.info(event)
    x = service.events().insert(calendarId=calId, body=event).execute()
    return x["id"]


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
    config: config.Settings,
):
    """
    Method to update a calendar event
    """
    if (
        eventStartTime.hour == 0
        and eventStartTime.minute == 0
        and eventEndTime == eventStartTime
    ):  # you're given a single date
        if config.all_day_event_option == 1:
            eventStartTime = datetime.datetime.combine(
                eventStartTime, datetime.datetime.min.time()
            ) + datetime.timedelta(
                hours=config.default_event_start
            )  # make the events pop up at 8 am instead of 12 am
            eventEndTime = eventStartTime + datetime.timedelta(
                minutes=config.default_event_length
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
            eventEndTime = eventEndTime + datetime.timedelta(
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

        eventEndTime = eventEndTime + datetime.timedelta(
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
        elif eventStartTime.hour == 0 and eventStartTime.minute == 0:
            # if the datetime fed into this is only a date or is at 12 AM,
            # then the event will fall under here
            eventStartTime = datetime.datetime.combine(
                eventStartTime, datetime.datetime.min.time()
            ) + datetime.timedelta(
                hours=config.default_event_start
            )  # make the events pop up at 8 am instead of 12 am
            eventEndTime = eventStartTime + datetime.timedelta(
                minutes=config.default_event_length
            )
        elif eventEndTime == eventStartTime:
            # this would meant that only 1 datetime was actually on the notion dashboard
            eventStartTime = eventStartTime
            eventEndTime = eventStartTime + datetime.timedelta(
                minutes=config.default_event_length
            )
        else:
            # if you give a specific start time to the event
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
    logging.info("Updating this event to calendar: ", eventName)

    if currentCalId == CalId:
        x = (
            service.events()
            .update(calendarId=CalId, eventId=eventId, body=event)
            .execute()
        )

    else:
        # When we have to move the event to a new calendar.
        # We must move the event over to the new calendar and
        # then update the information on the event
        logging.info("Event " + eventId)
        logging.info("CurrentCal " + currentCalId)
        logging.info("NewCal " + CalId)
        x = (
            service.events()
            .move(calendarId=currentCalId, eventId=eventId, destination=CalId)
            .execute()
        )
        logging.info("New event id: " + x["id"])
        x = (
            service.events()
            .update(calendarId=CalId, eventId=eventId, body=event)
            .execute()
        )

    return x["id"]
