import datetime as dt
import os

# from notion_client import Client
import notion_client as nc
import typer

from notion_gcal_sync import config, core


def typer_test():
    typer.echo(
        f"\nhello world, this is the cli main() function :)\ncalendar = {config.DEFAULT_CALENDAR_NAME}"
    )


def main():

    service, calendar = core.setup_google_api(
        config.runScript, config.DEFAULT_CALENDAR_ID, config.credentialsLocation
    )

    ##This is where we set up the connection with the Notion API
    os.environ["NOTION_TOKEN"] = config.NOTION_TOKEN
    notion = nc.Client(auth=os.environ["NOTION_TOKEN"])

    todayDate = dt.datetime.today().strftime("%Y-%m-%d")
    core.new_events_notion_to_gcal(
        config.database_id,
        config.urlRoot,
        config.DEFAULT_CALENDAR_NAME,
        config.calendarDictionary,
        config.Task_Notion_Name,
        config.Date_Notion_Name,
        config.Initiative_Notion_Name,
        config.ExtraInfo_Notion_Name,
        config.On_GCal_Notion_Name,
        config.GCalEventId_Notion_Name,
        config.LastUpdatedTime_Notion_Name,
        config.Calendar_Notion_Name,
        config.Current_Calendar_Id_Notion_Name,
        config.Delete_Notion_Name,
        notion,
        service,
    )

    core.existing_events_notion_to_gcal(
        config.database_id,
        config.urlRoot,
        config.DEFAULT_CALENDAR_ID,
        config.DEFAULT_CALENDAR_NAME,
        config.calendarDictionary,
        config.Task_Notion_Name,
        config.Date_Notion_Name,
        config.Initiative_Notion_Name,
        config.ExtraInfo_Notion_Name,
        config.On_GCal_Notion_Name,
        config.NeedGCalUpdate_Notion_Name,
        config.GCalEventId_Notion_Name,
        config.LastUpdatedTime_Notion_Name,
        config.Calendar_Notion_Name,
        config.Current_Calendar_Id_Notion_Name,
        config.Delete_Notion_Name,
        notion,
        todayDate,
        service,
    )

    core.existing_events_gcal_to_notion(
        config.database_id,
        config.DEFAULT_CALENDAR_NAME,
        config.calendarDictionary,
        config.Date_Notion_Name,
        config.On_GCal_Notion_Name,
        config.NeedGCalUpdate_Notion_Name,
        config.GCalEventId_Notion_Name,
        config.LastUpdatedTime_Notion_Name,
        config.Calendar_Notion_Name,
        config.Current_Calendar_Id_Notion_Name,
        config.Delete_Notion_Name,
        service,
        notion,
        todayDate,
    )

    core.new_events_gcal_to_notion(
        config.database_id,
        config.calendarDictionary,
        config.Task_Notion_Name,
        config.Date_Notion_Name,
        config.ExtraInfo_Notion_Name,
        config.On_GCal_Notion_Name,
        config.GCalEventId_Notion_Name,
        config.LastUpdatedTime_Notion_Name,
        config.Calendar_Notion_Name,
        config.Current_Calendar_Id_Notion_Name,
        config.Delete_Notion_Name,
        service,
        notion,
    )
    typer.run(typer_test)
