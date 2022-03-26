"""Core functionality for synchronisation."""
import datetime
import logging
import time
from typing import Any, Final

import arrow
import dateutil.parser
import googleapiclient.discovery  # type: ignore
import notion_client as nc  # type: ignore
from googleapiclient.errors import HttpError  # type: ignore

from ncal import config, notion_utils
from ncal.gcal_setup import setup_google_api
from ncal.notion_utils import get_property_text

DATE_AND_TIME_FORMAT_STRING: Final = "%Y-%m-%dT%H:%M:%S"


def setup_api_connections(
    default_calendar_id: str,
    credentials_location,
    notion_api_token: str,
    client_secret_location,
) -> tuple[googleapiclient.discovery.Resource, Any, nc.Client]:
    """Set up the API connections to Google Calendar and notion.

    Args:
        default_calendar_id: gcal calendar Id
        credentials_location: location of the credentials pickle file
        notion_api_token: token from the notion api
    Returns:
        (google api service, calendar, notion client)
    """
    # setup google api
    service, calendar = setup_google_api(
        calendar_id=default_calendar_id,
        token_file=str(credentials_location),
        client_secret_file=str(client_secret_location),
    )
    # This is where we set up the connection with the Notion API
    notion = nc.Client(auth=notion_api_token)
    return service, calendar, notion


def paginated_database_query(
    notion_client: nc.Client, database_id: str, **query: Any
) -> list:
    """Similar to notion_client.database.query(**query).

    Args:
        notion_client:
        database_id:
        **query: A query such as would be used for the normal notion_client query
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


def new_events_notion_to_gcal(
    database_id,
    url_root,
    default_calendar_name,
    calendar_dictionary,
    task_notion_name,
    date_notion_name,
    initiative_notion_name,
    extra_info_notion_name,
    on_gcal_notion_name,
    gcal_event_id_notion_name,
    last_updated_time_notion_name,
    calendar_notion_name,
    current_calendar_id_notion_name,
    delete_notion_name,
    notion,
    service,
    settings: config.Settings,
):
    """
    Take Notion Events not on GCal and move them over to GCal.

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
        matching_pages = []

        query = {
            # "database_id": database_id,
            "filter": {
                "and": [
                    {
                        "property": on_gcal_notion_name,
                        "checkbox": {"equals": False},
                    },
                    {"property": delete_notion_name, "checkbox": {"equals": False}},
                ]
            },
        }

        matching_pages = paginated_database_query(notion, database_id, **query)
        return matching_pages

    result_list = get_new_notion_pages(
        database_id, on_gcal_notion_name, date_notion_name, delete_notion_name, notion
    )

    # logging.info(len(result_list))

    try:
        logging.info(result_list[0])
    except IndexError:
        logging.info("index error")

    task_names = []
    start_dates = []
    end_times = []
    initiatives = []
    extra_info = []
    url_list = []
    cal_event_id_list = []
    calendar_list = []

    if len(result_list) > 0:
        for i, el in enumerate(result_list):
            logging.info(el)

            task_names.append(
                notion_utils.collapse_rich_text_property(
                    el["properties"][task_notion_name]["title"]
                )
            )
            start_dates.append(el["properties"][date_notion_name]["date"]["start"])

            if el["properties"][date_notion_name]["date"]["end"] is not None:
                end_times.append(el["properties"][date_notion_name]["date"]["end"])
            else:
                end_times.append(el["properties"][date_notion_name]["date"]["start"])

            try:
                initiatives.append(
                    get_property_text(
                        notion=notion,
                        notion_page=el,
                        property_name=initiative_notion_name,
                        property_type=settings.initiative_notion_type,
                    )
                )
            except ValueError:
                initiatives.append("")

            try:
                extra_info.append(
                    el["properties"][extra_info_notion_name]["rich_text"][0]["text"][
                        "content"
                    ]
                )
            except IndexError:
                extra_info.append("")
            url_list.append(make_task_url(el["id"], url_root))

            try:
                calendar_list.append(
                    calendar_dictionary[
                        el["properties"][calendar_notion_name]["select"]["name"]
                    ]
                )
            # keyerror occurs when there's nothing put into the calendar in the first
            # place
            except (KeyError, TypeError):
                calendar_list.append(calendar_dictionary[default_calendar_name])

            page_id = el["id"]
            # This checks off that the event has been put on Google Calendar
            notion.pages.update(
                **{
                    "page_id": page_id,
                    "properties": {
                        on_gcal_notion_name: {"checkbox": True},
                        last_updated_time_notion_name: {
                            "date": {
                                "start": arrow.utcnow().isoformat(),
                                "end": None,
                            }
                        },
                    },
                },
            )
            logging.info(calendar_list)

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
                    cal_event_id = make_cal_event(
                        task_name,
                        make_event_description(initiative, extra_info),
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
                        cal_event_id = make_cal_event(
                            task_name,
                            make_event_description(initiative, extra_info),
                            dateutil.parser.isoparse(start),
                            url,
                            dateutil.parser.isoparse(end),
                            calendar,
                            service,
                            settings,
                        )
                    except ValueError:
                        cal_event_id = make_cal_event(
                            task_name,
                            make_event_description(initiative, extra_info),
                            dateutil.parser.isoparse(start),
                            url,
                            dateutil.parser.isoparse(end),
                            calendar,
                            service,
                            settings,
                        )
                return cal_event_id

            cal_event_id = create_gcal_event(
                task_names[i],
                initiatives[i],
                extra_info[i],
                start_dates[i],
                end_times[i],
                url_list[i],
                calendar_list[i],
                service,
                settings,
            )
            cal_event_id_list.append(cal_event_id)

            if (
                calendar_list[i] == calendar_dictionary[default_calendar_name]
            ):  # this means that there is no calendar assigned on Notion
                # This puts the the GCal Id into the Notion Dashboard
                notion.pages.update(
                    **{
                        "page_id": page_id,
                        "properties": {
                            gcal_event_id_notion_name: {
                                "rich_text": [
                                    {"text": {"content": cal_event_id_list[i]}}
                                ]
                            },
                            current_calendar_id_notion_name: {
                                "rich_text": [{"text": {"content": calendar_list[i]}}]
                            },
                            calendar_notion_name: {
                                "select": {"name": default_calendar_name},
                            },
                        },
                    },
                )
            else:  # just a regular update
                notion.pages.update(
                    **{
                        "page_id": page_id,
                        "properties": {
                            gcal_event_id_notion_name: {
                                "rich_text": [
                                    {"text": {"content": cal_event_id_list[i]}}
                                ]
                            },
                            current_calendar_id_notion_name: {
                                "rich_text": [{"text": {"content": calendar_list[i]}}]
                            },
                        },
                    },
                )

    else:
        logging.info("Nothing new added to GCal")
    return


def existing_events_notion_to_gcal(
    database_id,
    url_root,
    default_calendar_id,
    default_calendar_name,
    calendar_dictionary,
    task_notion_name,
    date_notion_name,
    initiative_notion_name,
    extra_info_notion_name,
    on_gcal_notion_name,
    need_gcal_update_notion_name,
    gcal_event_id_notion_name,
    last_updated_time_notion_name,
    calendar_notion_name,
    current_calendar_id_notion_name,
    delete_notion_name,
    notion,
    today_date,
    service,
    settings: config.Settings,
):
    """
    Update GCal Events that Need To Be Updated.

    (Changed on Notion but need to be changed on GCal)
    """
    # In case people deleted the Calendar Variable, this queries items where
    # the Calendar select thing is empty
    query = {
        "filter": {
            "and": [
                {"property": calendar_notion_name, "select": {"is_empty": True}},
                {"property": delete_notion_name, "checkbox": {"equals": False}},
            ]
        },
    }
    result_list = paginated_database_query(
        notion_client=notion, database_id=database_id, **query
    )

    if len(result_list) > 0:
        for i, el in enumerate(result_list):
            page_id = el["id"]

            # This checks off that the event has been put on Google Calendar
            notion.pages.update(
                **{
                    "page_id": page_id,
                    "properties": {
                        calendar_notion_name: {
                            "select": {"name": default_calendar_name},
                        },
                        last_updated_time_notion_name: {
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
                    "property": need_gcal_update_notion_name,
                    "checkbox": {"equals": True},
                },
                {"property": on_gcal_notion_name, "checkbox": {"equals": True}},
                {"property": delete_notion_name, "checkbox": {"equals": False}},
            ]
        },
    }
    result_list = paginated_database_query(notion, database_id, **query)

    updating_notion_page_ids = []
    updating_cal_event_ids = []

    for result in result_list:
        logging.info(result)
        logging.info("\n")
        page_id = result["id"]
        updating_notion_page_ids.append(page_id)
        logging.info("\n")
        logging.info(result)
        logging.info("\n")
        try:
            cal_id = result["properties"][gcal_event_id_notion_name]["rich_text"][0][
                "text"
            ]["content"]
        except IndexError:
            cal_id = default_calendar_id
        logging.info(cal_id)
        updating_cal_event_ids.append(cal_id)

    task_names = []
    start_dates = []
    end_times = []
    initiatives = []
    extra_info = []
    url_list = []
    calendar_list = []
    current_cal_list = []

    if len(result_list) > 0:
        for i, el in enumerate(result_list):
            logging.info("\n")
            logging.info(el)
            logging.info("\n")

            task_names.append(
                notion_utils.collapse_rich_text_property(
                    el["properties"][task_notion_name]["title"]
                )
            )
            start_dates.append(el["properties"][date_notion_name]["date"]["start"])

            if el["properties"][date_notion_name]["date"]["end"] is not None:
                end_times.append(el["properties"][date_notion_name]["date"]["end"])
            else:
                end_times.append(el["properties"][date_notion_name]["date"]["start"])

            try:
                initiatives.append(
                    get_property_text(
                        notion=notion,
                        notion_page=el,
                        property_name=initiative_notion_name,
                        property_type=settings.initiative_notion_type,
                    )
                )
            except ValueError:
                initiatives.append("")

            try:
                extra_info.append(
                    el["properties"][extra_info_notion_name]["rich_text"][0]["text"][
                        "content"
                    ]
                )
            except IndexError:
                extra_info.append("")
            url_list.append(make_task_url(el["id"], url_root))

            logging.info(el)
            # CalendarList.append(calendar_dictionary[el['properties'][Calendar_Notion_Name]['select']['name']])
            try:
                calendar_list.append(
                    calendar_dictionary[
                        el["properties"][calendar_notion_name]["select"]["name"]
                    ]
                )
            # keyerror occurs when there's nothing put into the calendar in the first
            # place
            except KeyError:
                calendar_list.append(calendar_dictionary[default_calendar_name])

            current_cal_list.append(
                el["properties"][current_calendar_id_notion_name]["rich_text"][0][
                    "text"
                ]["content"]
            )

            page_id = el["id"]

            # depending on the format of the dates, we'll update the gcal event as
            # necessary
            try:
                update_calendar_event(
                    task_names[i],
                    make_event_description(initiatives[i], extra_info[i]),
                    datetime.datetime.strptime(start_dates[i], "%Y-%m-%d"),
                    url_list[i],
                    updating_cal_event_ids[i],
                    datetime.datetime.strptime(end_times[i], "%Y-%m-%d"),
                    current_cal_list[i],
                    calendar_list[i],
                    service,
                    settings,
                )
            except ValueError:
                try:
                    update_calendar_event(
                        task_names[i],
                        make_event_description(initiatives[i], extra_info[i]),
                        dateutil.parser.isoparse(start_dates[i]),
                        url_list[i],
                        updating_cal_event_ids[i],
                        dateutil.parser.isoparse(end_times[i]),
                        current_cal_list[i],
                        calendar_list[i],
                        service,
                        settings,
                    )
                except ValueError:
                    update_calendar_event(
                        task_names[i],
                        make_event_description(initiatives[i], extra_info[i]),
                        dateutil.parser.isoparse(start_dates[i]),
                        url_list[i],
                        updating_cal_event_ids[i],
                        dateutil.parser.isoparse(end_times[i]),
                        current_cal_list[i],
                        calendar_list[i],
                        service,
                        settings,
                    )

            # This updates the last time that the page in Notion was updated by the code
            notion.pages.update(
                **{
                    "page_id": page_id,
                    "properties": {
                        last_updated_time_notion_name: {
                            "date": {
                                "start": arrow.utcnow().isoformat(),
                                "end": None,
                            }
                        },
                        current_calendar_id_notion_name: {
                            "rich_text": [{"text": {"content": calendar_list[i]}}]
                        },
                    },
                },
            )

    else:
        logging.info("Nothing new updated to GCal")


def existing_events_gcal_to_notion(
    database_id,
    default_calendar_name,
    calendar_dictionary,
    date_notion_name,
    on_gcal_notion_name,
    need_gcal_update_notion_name,
    gcal_event_id_notion_name,
    last_updated_time_notion_name,
    calendar_notion_name,
    current_calendar_id_notion_name,
    delete_notion_name,
    service,
    notion,
    today_date,
    settings: config.Settings,
):
    """Sync GCal event updates for events already in Notion back to Notion.

    Query notion tasks already in Gcal, don't have to be updated, and are today or
    in the future.
    """
    query = {
        "filter": {
            "and": [
                {
                    "property": need_gcal_update_notion_name,
                    "formula": {"checkbox": {"equals": False}},
                },
                {"property": on_gcal_notion_name, "checkbox": {"equals": True}},
                # {
                #     "or": [
                #         {
                #             "property": date_notion_name,
                #             "date": {"equals": todayDate},
                #         },
                #         {"property": date_notion_name, "date": {"next_week": {}}},
                #     ]
                # },
                {"property": delete_notion_name, "checkbox": {"equals": False}},
            ]
        },
    }

    result_list = paginated_database_query(notion, database_id, **query)

    # Comparison section:
    # We need to see what times between GCal and Notion are not the same, so we are
    # going to convert all of the notion date/times into datetime values and then
    # compare that against the datetime value of the GCal event.
    # If they are not the same, then we change the Notion event as appropriate.
    notion_ids_list = []
    notion_start_datetimes = []
    notion_end_datetimes = []
    notion_gcal_ids = []  # we will be comparing this against the gcal_datetimes
    gcal_start_datetimes = []
    gcal_end_datetimes = []

    notion_gcal_cal_ids = (
        []
    )  # going to fill this in from the select option, not the text option.
    notion_gcal_cal_names = []
    gcal_cal_ids = []

    for result in result_list:
        notion_ids_list.append(result["id"])
        notion_start_datetimes.append(
            result["properties"][date_notion_name]["date"]["start"]
        )
        notion_end_datetimes.append(
            result["properties"][date_notion_name]["date"]["end"]
        )
        notion_gcal_ids.append(
            result["properties"][gcal_event_id_notion_name]["rich_text"][0]["text"][
                "content"
            ]
        )
        try:
            notion_gcal_cal_ids.append(
                calendar_dictionary[
                    result["properties"][calendar_notion_name]["select"]["name"]
                ]
            )
            notion_gcal_cal_names.append(
                result["properties"][calendar_notion_name]["select"]["name"]
            )
        # keyerror occurs when there's nothing put into the calendar in the first place
        except KeyError:
            notion_gcal_cal_ids.append(calendar_dictionary[default_calendar_name])
            notion_gcal_cal_names.append(
                result["properties"][calendar_notion_name]["select"]["name"]
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

    # We use the gcalId from the Notion dashboard to get retrieve the start Time from
    # the gcal event
    value = ""
    for gcal_id in notion_gcal_ids:
        # just check all of the calendars of interest for info about the event
        for calendar_id in calendar_dictionary.keys():
            logging.info("Trying " + calendar_id + " for " + gcal_id)
            try:
                x = (
                    service.events()
                    .get(calendarId=calendar_dictionary[calendar_id], eventId=gcal_id)
                    .execute()
                )
            except HttpError:
                logging.info("Event not found")
                x = {"status": "unconfirmed"}
            if x["status"] == "confirmed":
                gcal_cal_ids.append(calendar_id)
                value = x
            else:
                continue

        logging.info(value)
        logging.info("\n")
        try:
            gcal_start_datetimes.append(
                dateutil.parser.isoparse(value["start"]["dateTime"])  # type: ignore
            )
        except KeyError:
            date = datetime.datetime.strptime(value["start"]["date"], "%Y-%m-%d")  # type: ignore # noqa
            gcal_start_datetimes.append(date)
        try:
            gcal_end_datetimes.append(
                dateutil.parser.isoparse(value["end"]["dateTime"])  # type: ignore
            )
        except KeyError:
            date = datetime.datetime.strptime(value["end"]["date"], "%Y-%m-%d")  # type: ignore # noqa
            x = datetime.datetime(
                date.year, date.month, date.day, 0, 0, 0
            ) - datetime.timedelta(days=1)
            gcal_end_datetimes.append(x)

    # Now we iterate and compare the time on the Notion Dashboard and the start time of
    # the GCal event
    # If the datetimes don't match up,  then the Notion  Dashboard must be updated

    new_notion_start_datetimes: list[None | datetime.datetime] = []
    new_notion_end_datetimes: list[None | datetime.datetime] = []

    for i in range(len(notion_start_datetimes)):
        if notion_start_datetimes[i] != gcal_start_datetimes[i]:
            new_notion_start_datetimes.append(gcal_start_datetimes[i])
        else:
            new_notion_start_datetimes.append(None)

        if notion_end_datetimes[i] != gcal_end_datetimes[i]:
            # this means that there is no end time in notion
            new_notion_end_datetimes.append(gcal_end_datetimes[i])
        else:
            new_notion_end_datetimes.append(None)

    logging.info("test")
    logging.info(new_notion_start_datetimes)
    logging.info(new_notion_end_datetimes)
    logging.info("\n")
    for i in range(len(notion_gcal_ids)):
        logging.info(
            notion_start_datetimes[i], gcal_start_datetimes[i], notion_gcal_ids[i]
        )

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
                        "page_id": notion_ids_list[i],
                        "properties": {
                            date_notion_name: {
                                "date": {
                                    "start": start.strftime("%Y-%m-%d"),
                                    "end": None,
                                }
                            },
                            last_updated_time_notion_name: {
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
                        "page_id": notion_ids_list[i],
                        "properties": {
                            date_notion_name: {
                                "date": {
                                    "start": start.strftime("%Y-%m-%d"),
                                    "end": end.strftime("%Y-%m-%d"),
                                }
                            },
                            last_updated_time_notion_name: {
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
                        "page_id": notion_ids_list[i],
                        "properties": {
                            date_notion_name: {
                                "date": {
                                    "start": start.isoformat(),
                                    "end": end.isoformat(),
                                }
                            },
                            last_updated_time_notion_name: {
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
                        "page_id": notion_ids_list[i],
                        "properties": {
                            date_notion_name: {
                                "date": {
                                    "start": start.strftime("%Y-%m-%d"),
                                    "end": None,
                                }
                            },
                            last_updated_time_notion_name: {
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
                        "page_id": notion_ids_list[i],
                        "properties": {
                            date_notion_name: {
                                "date": {
                                    "start": start.strftime("%Y-%m-%d"),
                                    "end": end.strftime("%Y-%m-%d"),
                                }
                            },
                            last_updated_time_notion_name: {
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
                        "page_id": notion_ids_list[i],
                        "properties": {
                            date_notion_name: {
                                "date": {
                                    "start": start.isoformat(),
                                    "end": end.isoformat(),
                                }
                            },
                            last_updated_time_notion_name: {
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
                        "page_id": notion_ids_list[i],
                        "properties": {
                            date_notion_name: {
                                "date": {
                                    "start": start.strftime("%Y-%m-%d"),
                                    "end": None,
                                }
                            },
                            last_updated_time_notion_name: {
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
                        "page_id": notion_ids_list[i],
                        "properties": {
                            date_notion_name: {
                                "date": {
                                    "start": start.strftime("%Y-%m-%d"),
                                    "end": end.strftime("%Y-%m-%d"),
                                }
                            },
                            last_updated_time_notion_name: {
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
                        "page_id": notion_ids_list[i],
                        "properties": {
                            date_notion_name: {
                                "date": {
                                    "start": start.isoformat(),
                                    "end": end.isoformat(),
                                }
                            },
                            last_updated_time_notion_name: {
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

    logging.info(notion_ids_list)
    logging.info("\n")
    logging.info(gcal_cal_ids)

    cal_names = list(calendar_dictionary.keys())
    cal_ids = list(calendar_dictionary.values())

    for i, gcal_id in enumerate(gcal_cal_ids):
        # instead of checking, just update the notion datebase with whatever calendar
        # the event is on
        logging.info("GcalId: " + gcal_id)
        notion.pages.update(
            # This puts the the GCal Id into the Notion Dashboard
            **{
                "page_id": notion_ids_list[i],
                "properties": {
                    current_calendar_id_notion_name: {  # this is the text
                        "rich_text": [
                            {"text": {"content": cal_ids[cal_names.index(gcal_id)]}}
                        ]
                    },
                    calendar_notion_name: {  # this is the select
                        "select": {"name": gcal_id},
                    },
                    last_updated_time_notion_name: {
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
    calendar_dictionary,
    task_notion_name,
    date_notion_name,
    extra_info_notion_name,
    on_gcal_notion_name,
    gcal_event_id_notion_name,
    last_updated_time_notion_name,
    calendar_notion_name,
    current_calendar_id_notion_name,
    delete_notion_name,
    service,
    notion,
    settings: config.Settings,
):
    """
    Bring events (not in Notion already) from GCal to Notion.

    First, we get a list of all of the GCal Event Ids from the Notion Dashboard.
    """
    my_page = paginated_database_query(
        notion,
        database_id,
        **{
            "filter": {
                "and": [
                    {
                        "property": gcal_event_id_notion_name,
                        "text": {"is_not_empty": True},
                    },
                    {"property": delete_notion_name, "checkbox": {"equals": False}},
                ]
            },
        },
    )

    my_page = paginated_database_query(
        notion,
        database_id,
        **{
            "filter": {
                "property": gcal_event_id_notion_name,
                "text": {"is_not_empty": True},
            },
        },
    )

    result_list = my_page

    all_notion_gcal_ids = []

    for result in result_list:
        all_notion_gcal_ids.append(
            result["properties"][gcal_event_id_notion_name]["rich_text"][0]["text"][
                "content"
            ]
        )

    # Get the GCal Ids and other Event Info from Google Calendar

    events = []
    # get all the events from all calendars of interest
    for key, value in calendar_dictionary.items():
        x = (
            service.events()
            .list(calendarId=value, maxResults=2000, timeMin=arrow.utcnow().isoformat())
            .execute()
        )
        events.extend(x["items"])
        time.sleep(0.1)

    logging.info(events)

    cal_items = events

    cal_name = [item["summary"] for item in cal_items]

    gcal_calendar_id = [
        item["organizer"]["email"] for item in cal_items
    ]  # this is to get all of the calendarIds for each event

    cal_names = list(calendar_dictionary.keys())
    cal_ids = list(calendar_dictionary.values())
    gcal_calendar_name = [cal_names[cal_ids.index(x)] for x in gcal_calendar_id]

    cal_start_dates = []
    cal_end_dates = []
    for el in cal_items:
        try:
            cal_start_dates.append(dateutil.parser.isoparse(el["start"]["dateTime"]))
        except KeyError:
            date = datetime.datetime.strptime(el["start"]["date"], "%Y-%m-%d")
            x = datetime.datetime(date.year, date.month, date.day, 0, 0, 0)
            cal_start_dates.append(x)
        try:
            cal_end_dates.append(dateutil.parser.isoparse(el["end"]["dateTime"]))
        except KeyError:
            date = datetime.datetime.strptime(el["end"]["date"], "%Y-%m-%d")
            x = datetime.datetime(date.year, date.month, date.day, 0, 0, 0)
            cal_end_dates.append(x)

    cal_ids = [item["id"] for item in cal_items]
    cal_descriptions = []
    for item in cal_items:
        try:
            cal_descriptions.append(item["description"])
        except KeyError:
            cal_descriptions.append(" ")

    # Now, we compare the Ids from Notion and Ids from GCal. If the Id from GCal is
    # not in the list from Notion, then we know that the event does not exist in
    # Notion yet, so we should bring that over.

    for i in range(len(cal_ids)):
        if cal_ids[i] not in all_notion_gcal_ids:
            if cal_start_dates[i] == cal_end_dates[i] - datetime.timedelta(
                days=1
            ):  # only add in the start DATE
                # Here, we create a new page for every new GCal event
                end = cal_end_dates[i] - datetime.timedelta(days=1)
                my_page = notion.pages.create(
                    **{
                        "parent": {
                            "database_id": database_id,
                        },
                        "properties": {
                            task_notion_name: {
                                "type": "title",
                                "title": [
                                    {
                                        "type": "text",
                                        "text": {
                                            "content": cal_name[i],
                                        },
                                    },
                                ],
                            },
                            date_notion_name: {
                                "type": "date",
                                "date": {
                                    "start": cal_start_dates[i].strftime("%Y-%m-%d"),
                                    "end": None,
                                },
                            },
                            last_updated_time_notion_name: {
                                "type": "date",
                                "date": {
                                    "start": arrow.utcnow().isoformat(),
                                    "end": None,
                                },
                            },
                            extra_info_notion_name: {
                                "type": "rich_text",
                                "rich_text": [
                                    {"text": {"content": cal_descriptions[i]}}
                                ],
                            },
                            gcal_event_id_notion_name: {
                                "type": "rich_text",
                                "rich_text": [{"text": {"content": cal_ids[i]}}],
                            },
                            on_gcal_notion_name: {"type": "checkbox", "checkbox": True},
                            current_calendar_id_notion_name: {
                                "rich_text": [
                                    {"text": {"content": gcal_calendar_id[i]}}
                                ]
                            },
                            calendar_notion_name: {
                                "select": {"name": gcal_calendar_name[i]},
                            },
                        },
                    },
                )

            elif (
                cal_start_dates[i].hour == 0
                and cal_start_dates[i].minute == 0
                and cal_end_dates[i].hour == 0
                and cal_end_dates[i].minute == 0
            ):  # add start and end in DATE format
                # Here, we create a new page for every new GCal event
                end = cal_end_dates[i] - datetime.timedelta(days=1)

                my_page = notion.pages.create(
                    **{
                        "parent": {
                            "database_id": database_id,
                        },
                        "properties": {
                            task_notion_name: {
                                "type": "title",
                                "title": [
                                    {
                                        "type": "text",
                                        "text": {
                                            "content": cal_name[i],
                                        },
                                    },
                                ],
                            },
                            date_notion_name: {
                                "type": "date",
                                "date": {
                                    "start": cal_start_dates[i].strftime("%Y-%m-%d"),
                                    "end": end.strftime("%Y-%m-%d"),
                                },
                            },
                            last_updated_time_notion_name: {
                                "type": "date",
                                "date": {
                                    "start": arrow.utcnow().isoformat(),
                                    "end": None,
                                },
                            },
                            extra_info_notion_name: {
                                "type": "rich_text",
                                "rich_text": [
                                    {"text": {"content": cal_descriptions[i]}}
                                ],
                            },
                            gcal_event_id_notion_name: {
                                "type": "rich_text",
                                "rich_text": [{"text": {"content": cal_ids[i]}}],
                            },
                            on_gcal_notion_name: {"type": "checkbox", "checkbox": True},
                            current_calendar_id_notion_name: {
                                "rich_text": [
                                    {"text": {"content": gcal_calendar_id[i]}}
                                ]
                            },
                            calendar_notion_name: {
                                "select": {"name": gcal_calendar_name[i]},
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
                            task_notion_name: {
                                "type": "title",
                                "title": [
                                    {
                                        "type": "text",
                                        "text": {
                                            "content": cal_name[i],
                                        },
                                    },
                                ],
                            },
                            date_notion_name: {
                                "type": "date",
                                "date": {
                                    "start": cal_start_dates[i].isoformat(),
                                    "end": cal_end_dates[i].isoformat(),
                                },
                            },
                            last_updated_time_notion_name: {
                                "type": "date",
                                "date": {
                                    "start": arrow.utcnow().isoformat(),
                                    "end": None,
                                },
                            },
                            extra_info_notion_name: {
                                "type": "rich_text",
                                "rich_text": [
                                    {"text": {"content": cal_descriptions[i]}}
                                ],
                            },
                            gcal_event_id_notion_name: {
                                "type": "rich_text",
                                "rich_text": [{"text": {"content": cal_ids[i]}}],
                            },
                            on_gcal_notion_name: {"type": "checkbox", "checkbox": True},
                            current_calendar_id_notion_name: {
                                "rich_text": [
                                    {"text": {"content": gcal_calendar_id[i]}}
                                ]
                            },
                            calendar_notion_name: {
                                "select": {"name": gcal_calendar_name[i]},
                            },
                        },
                    },
                )

            logging.info(f"Added this event to Notion: {cal_name[i]}")


def delete_done_pages(
    notion: nc.Client,
    database_id: str,
    gcal_event_id_notion_name,
    on_gcal_notion_name,
    delete_notion_name,
    delete_option: bool,
    calendar_dictionary,
    calendar_notion_name,
    service,
):
    """Sync/delete Done pages.

    - If marked *Done* in Notion, then it will delete the GCal event
    (and the Notion event once Python API updates)
    """
    result_list = paginated_database_query(
        notion,
        database_id,
        **{
            "filter": {
                "and": [
                    {
                        "property": gcal_event_id_notion_name,
                        "text": {"is_not_empty": True},
                    },
                    {"property": on_gcal_notion_name, "checkbox": {"equals": True}},
                    {"property": delete_notion_name, "checkbox": {"equals": True}},
                ]
            },
        },
    )

    # delete gcal event (and Notion task once the Python API is updated)
    if delete_option and len(result_list) > 0:
        for i, el in enumerate(result_list):
            calendar_id = calendar_dictionary[
                el["properties"][calendar_notion_name]["select"]["name"]
            ]
            event_id = el["properties"][gcal_event_id_notion_name]["rich_text"][0][
                "text"
            ]["content"]

            try:
                service.events().delete(
                    calendarId=calendar_id, eventId=event_id
                ).execute()
                logging.info(f"deleted: {calendar_id} {event_id}")
            except HttpError:
                continue
            time.sleep(0.1)


def make_event_description(initiative, info):
    """Make a calendar event description.

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


def make_task_url(ending: str, url_root: str):
    """Create a task's url."""
    # To make a url for the notion task, we have to take the id of the task and take
    # away the hyphens from the string
    url_id = ending.replace("-", "")
    return url_root + url_id


def make_cal_event(
    event_name,
    event_description,
    event_start_time,
    source_url,
    event_end_time,
    cal_id,
    service,
    config: config.Settings,
):
    """Make a calendar event."""
    if (
        event_start_time.hour == 0
        and event_start_time.minute == 0
        and event_end_time == event_start_time
    ):  # only startTime is given from the Notion Dashboard
        if config.all_day_event_option == 1:
            event_start_time = datetime.datetime.combine(
                event_start_time, datetime.datetime.min.time()
            ) + datetime.timedelta(
                hours=config.default_event_start
            )  # make the events pop up at 8 am instead of 12 am
            event_end_time = event_start_time + datetime.timedelta(
                minutes=config.default_event_length
            )
            event = {
                "summary": event_name,
                "description": event_description,
                "start": {
                    "dateTime": event_start_time.strftime(DATE_AND_TIME_FORMAT_STRING),
                    "timeZone": config.timezone,
                },
                "end": {
                    "dateTime": event_end_time.strftime(DATE_AND_TIME_FORMAT_STRING),
                    "timeZone": config.timezone,
                },
                "source": {
                    "title": "Notion Link",
                    "url": source_url,
                },
            }
        else:
            event_end_time = event_end_time + datetime.timedelta(
                days=1
            )  # gotta make it to 12AM the day after
            event = {
                "summary": event_name,
                "description": event_description,
                "start": {
                    "date": event_start_time.strftime("%Y-%m-%d"),
                    "timeZone": config.timezone,
                },
                "end": {
                    "date": event_end_time.strftime("%Y-%m-%d"),
                    "timeZone": config.timezone,
                },
                "source": {
                    "title": "Notion Link",
                    "url": source_url,
                },
            }
    elif (
        event_start_time.hour == 0
        and event_start_time.minute == 0
        and event_end_time.hour == 0
        and event_end_time.minute == 0
        and event_start_time != event_end_time
    ):

        event_end_time = event_end_time + datetime.timedelta(
            days=1
        )  # gotta make it to 12AM the day after

        event = {
            "summary": event_name,
            "description": event_description,
            "start": {
                "date": event_start_time.strftime("%Y-%m-%d"),
                "timeZone": config.timezone,
            },
            "end": {
                "date": event_end_time.strftime("%Y-%m-%d"),
                "timeZone": config.timezone,
            },
            "source": {
                "title": "Notion Link",
                "url": source_url,
            },
        }

    else:
        if event_start_time.hour == 0 and event_start_time.minute == 0:
            if event_end_time == event_start_time:
                # if the datetime fed into this is only a date or is at 12 AM,
                # then the event will fall under here
                event_start_time = datetime.datetime.combine(
                    event_start_time, datetime.datetime.min.time()
                ) + datetime.timedelta(
                    hours=config.default_event_start
                )  # make the events pop up at 8 am instead of 12 am
                event_end_time = event_start_time + datetime.timedelta(
                    minutes=config.default_event_length
                )
        elif event_end_time == event_start_time:
            # this would meant that only 1 datetime was actually on the notion dashboard
            event_end_time = event_start_time + datetime.timedelta(
                minutes=config.default_event_length
            )

        event = {
            "summary": event_name,
            "description": event_description,
            "start": {
                "dateTime": event_start_time.strftime(DATE_AND_TIME_FORMAT_STRING),
                "timeZone": config.timezone,
            },
            "end": {
                "dateTime": event_end_time.strftime(DATE_AND_TIME_FORMAT_STRING),
                "timeZone": config.timezone,
            },
            "source": {
                "title": "Notion Link",
                "url": source_url,
            },
        }
    logging.info(f"Adding this event to calendar: {event_name}")

    logging.info(event)
    x = service.events().insert(calendarId=cal_id, body=event).execute()
    return x["id"]


def update_calendar_event(
    event_name,
    event_description,
    event_start_time,
    source_url,
    event_id,
    event_end_time,
    current_cal_id,
    cal_id,
    service,
    config: config.Settings,
):
    """Update a Google Calendar event.

    Args:
        event_name:
        event_description:
        event_start_time:
        source_url:
        event_id:
        event_end_time:
        current_cal_id:
        cal_id:
        service:
        config (config.Settings):

    Returns:
        _type_: _description_
    """
    if (
        event_start_time.hour == 0
        and event_start_time.minute == 0
        and event_end_time == event_start_time
    ):  # you're given a single date
        if config.all_day_event_option == 1:
            event_start_time = datetime.datetime.combine(
                event_start_time, datetime.datetime.min.time()
            ) + datetime.timedelta(
                hours=config.default_event_start
            )  # make the events pop up at 8 am instead of 12 am
            event_end_time = event_start_time + datetime.timedelta(
                minutes=config.default_event_length
            )
            event = {
                "summary": event_name,
                "description": event_description,
                "start": {
                    "dateTime": event_start_time.strftime(DATE_AND_TIME_FORMAT_STRING),
                    "timeZone": config.timezone,
                },
                "end": {
                    "dateTime": event_end_time.strftime(DATE_AND_TIME_FORMAT_STRING),
                    "timeZone": config.timezone,
                },
                "source": {
                    "title": "Notion Link",
                    "url": source_url,
                },
            }
        else:
            event_end_time = event_end_time + datetime.timedelta(
                days=1
            )  # gotta make it to 12AM the day after
            event = {
                "summary": event_name,
                "description": event_description,
                "start": {
                    "date": event_start_time.strftime("%Y-%m-%d"),
                    "timeZone": config.timezone,
                },
                "end": {
                    "date": event_end_time.strftime("%Y-%m-%d"),
                    "timeZone": config.timezone,
                },
                "source": {
                    "title": "Notion Link",
                    "url": source_url,
                },
            }
    elif (
        event_start_time.hour == 0
        and event_start_time.minute == 0
        and event_end_time.hour == 0
        and event_end_time.minute == 0
        and event_start_time != event_end_time
    ):  # it's a multiple day event

        event_end_time = event_end_time + datetime.timedelta(
            days=1
        )  # gotta make it to 12AM the day after

        event = {
            "summary": event_name,
            "description": event_description,
            "start": {
                "date": event_start_time.strftime("%Y-%m-%d"),
                "timeZone": config.timezone,
            },
            "end": {
                "date": event_end_time.strftime("%Y-%m-%d"),
                "timeZone": config.timezone,
            },
            "source": {
                "title": "Notion Link",
                "url": source_url,
            },
        }

    else:  # just 2 datetimes passed in
        if event_start_time.hour == 0 and event_start_time.minute == 0:
            if event_end_time != event_start_time:
                # Start on Notion is 12 am and end is also given on Notion
                pass
            else:
                # if the datetime fed into this is only a date or is at 12 AM,
                # then the event will fall under here
                event_start_time = datetime.datetime.combine(
                    event_start_time, datetime.datetime.min.time()
                ) + datetime.timedelta(
                    hours=config.default_event_start
                )  # make the events pop up at 8 am instead of 12 am
                event_end_time = event_start_time + datetime.timedelta(
                    minutes=config.default_event_length
                )
        elif event_end_time == event_start_time:
            # this would meant that only 1 datetime was actually on the notion dashboard
            event_end_time = event_start_time + datetime.timedelta(
                minutes=config.default_event_length
            )

        event = {
            "summary": event_name,
            "description": event_description,
            "start": {
                "dateTime": event_start_time.strftime(DATE_AND_TIME_FORMAT_STRING),
                "timeZone": config.timezone,
            },
            "end": {
                "dateTime": event_end_time.strftime(DATE_AND_TIME_FORMAT_STRING),
                "timeZone": config.timezone,
            },
            "source": {
                "title": "Notion Link",
                "url": source_url,
            },
        }
    logging.info(f"Updating this event to calendar: {event_name}")

    if current_cal_id == cal_id:
        x = (
            service.events()
            .update(calendarId=cal_id, eventId=event_id, body=event)
            .execute()
        )

    else:
        # When we have to move the event to a new calendar.
        # We must move the event over to the new calendar and
        # then update the information on the event
        logging.info("Event " + event_id)
        logging.info("CurrentCal " + current_cal_id)
        logging.info("NewCal " + cal_id)
        x = (
            service.events()
            .move(calendarId=current_cal_id, eventId=event_id, destination=cal_id)
            .execute()
        )
        logging.info("New event id: " + x["id"])
        x = (
            service.events()
            .update(calendarId=cal_id, eventId=event_id, body=event)
            .execute()
        )

    return x["id"]
