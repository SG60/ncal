import datetime as dt
from typing import Optional
from pydantic import ValidationError

# from notion_client import Client
import notion_client as nc
import typer

from notion_gcal_sync import core
from notion_gcal_sync.config import Settings, load_config_file
from pathlib import Path


def sync(settings: Settings):

    service, calendar = core.setup_google_api(
        settings.runScript, settings.DEFAULT_CALENDAR_ID, settings.credentialsLocation
    )

    ##This is where we set up the connection with the Notion API

    notion = nc.Client(auth=settings.NOTION_API_TOKEN)

    todayDate = dt.datetime.today().strftime("%Y-%m-%d")

    core.new_events_notion_to_gcal(
        settings.database_id,
        settings.urlRoot,
        settings.DEFAULT_CALENDAR_NAME,
        settings.calendarDictionary,
        settings.Task_Notion_Name,
        settings.Date_Notion_Name,
        settings.Initiative_Notion_Name,
        settings.ExtraInfo_Notion_Name,
        settings.On_GCal_Notion_Name,
        settings.GCalEventId_Notion_Name,
        settings.LastUpdatedTime_Notion_Name,
        settings.Calendar_Notion_Name,
        settings.Current_Calendar_Id_Notion_Name,
        settings.Delete_Notion_Name,
        notion,
        service,
    )

    core.existing_events_notion_to_gcal(
        settings.database_id,
        settings.urlRoot,
        settings.DEFAULT_CALENDAR_ID,
        settings.DEFAULT_CALENDAR_NAME,
        settings.calendarDictionary,
        settings.Task_Notion_Name,
        settings.Date_Notion_Name,
        settings.Initiative_Notion_Name,
        settings.ExtraInfo_Notion_Name,
        settings.On_GCal_Notion_Name,
        settings.NeedGCalUpdate_Notion_Name,
        settings.GCalEventId_Notion_Name,
        settings.LastUpdatedTime_Notion_Name,
        settings.Calendar_Notion_Name,
        settings.Current_Calendar_Id_Notion_Name,
        settings.Delete_Notion_Name,
        notion,
        todayDate,
        service,
    )

    core.existing_events_gcal_to_notion(
        settings.database_id,
        settings.DEFAULT_CALENDAR_NAME,
        settings.calendarDictionary,
        settings.Date_Notion_Name,
        settings.On_GCal_Notion_Name,
        settings.NeedGCalUpdate_Notion_Name,
        settings.GCalEventId_Notion_Name,
        settings.LastUpdatedTime_Notion_Name,
        settings.Calendar_Notion_Name,
        settings.Current_Calendar_Id_Notion_Name,
        settings.Delete_Notion_Name,
        service,
        notion,
        todayDate,
    )

    core.new_events_gcal_to_notion(
        settings.database_id,
        settings.calendarDictionary,
        settings.Task_Notion_Name,
        settings.Date_Notion_Name,
        settings.ExtraInfo_Notion_Name,
        settings.On_GCal_Notion_Name,
        settings.GCalEventId_Notion_Name,
        settings.LastUpdatedTime_Notion_Name,
        settings.Calendar_Notion_Name,
        settings.Current_Calendar_Id_Notion_Name,
        settings.Delete_Notion_Name,
        service,
        notion,
    )


def typer_test(
    config_file: Optional[Path] = typer.Option(
        None,'--config-file', '-c' , help="toml configuration file location"
    )
):
    """
    CLI to sync a Notion database with Google Calendar.

    """
    typer.echo()
    typer.secho(
        f"Sychronize Notion <-> GCal", bg=typer.colors.GREEN, fg="white", bold=True
    )
    typer.echo()
    try:
        if config_file:
            file_str = typer.style(config_file, fg=typer.colors.BRIGHT_BLUE)
            typer.echo(f"Using {file_str} for configuration.")
            settings = load_config_file(config_file)
        else:
            settings = Settings()
    except ValidationError:
        typer.secho("no config provided, use --help for more information", bg="white", fg="red")
        raise typer.Exit(1)
    except FileNotFoundError:
        typer.secho("invalid config-file provided, use --help for more information", bg="white", fg="red")
        raise typer.Exit(1)
    sync(settings)


def main():
    typer.run(typer_test)
