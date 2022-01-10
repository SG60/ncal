import asyncio
import datetime as dt
import time
from pathlib import Path
from typing import Callable, Coroutine, Literal, Optional

# from notion_client import Client
import notion_client as nc
import typer
from pydantic import ValidationError

from notion_gcal_sync import core
from notion_gcal_sync.config import Settings, load_config_file, load_settings


def sync_actual(settings: Settings):

    service, calendar = core.setup_google_api(
        settings.runScript,
        settings.DEFAULT_CALENDAR_ID,
        str(settings.credentialsLocation),
    )

    ##This is where we set up the connection with the Notion API

    notion = nc.Client(auth=settings.notion_api_token)

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


app = typer.Typer(help="CLI to sync a Notion database with Google Calendar.")
state = {"verbose": False}


async def scheduler(
    timedelta: dt.timedelta, function: Callable[..., Coroutine], f_args: dict
) -> None:
    next_run = dt.datetime.now() + timedelta
    print(f"next run: {next_run}")
    while True:
        now = dt.datetime.now()
        if now >= next_run:
            await function(**f_args)
            next_run = timedelta + next_run
            print(f"next run: {next_run}")
        await asyncio.sleep(1)


async def sync(settings: Settings) -> None:
    with typer.progressbar(
        range(4), label="Sychronising", show_eta=False, show_pos=True
    ) as progress:
        # for _ in progress:
        #     await asyncio.sleep(1)
        progress.label = "modified N->G"
        time.sleep(0.3)  # sync something
        progress.update(1)
        progress.label = "modified G->N"
        time.sleep(0.3)  # etc.
        progress.update(1, "modified G->N")
        progress.label = "new N->G"
        time.sleep(0.3)
        progress.update(1)
        progress.label = "new G->G"
        time.sleep(0.3)
        progress.label = "Sychronized"
        progress.update(1)


async def continuous_sync(interval: dt.timedelta, settings: Settings):
    await sync(settings)
    await scheduler(interval, sync, {"settings": settings})


@app.command("sync")
def cli_sync(
    repeat: bool = typer.Option(False, "--repeat/--no-repeat", "-r"),
    seconds: int = 5,
    config_file: Optional[Path] = typer.Option(
        None, "--config-file", "-c", help="toml configuration file location"
    ),
    notion_api_token: Optional[str] = None,
    database_id: Optional[str] = None,
    urlRoot: Optional[str] = None,
):
    """
    CLI to sync a Notion database with Google Calendar.

    """
    typer.echo()
    typer.secho(
        f"Sychronize Notion <-> GCal", bg=typer.colors.GREEN, fg="white", bold=True
    )
    typer.echo()

    cli_settings = {}
    if notion_api_token:
        cli_settings["notion_api_token"] = notion_api_token
    if database_id:
        cli_settings["database_id"] = database_id
    if urlRoot:
        cli_settings["urlRoot"] = urlRoot

    try:
        if config_file:
            settings = load_settings(**cli_settings, config_file_path=config_file)
        else:
            settings = load_settings(**cli_settings)
    except ValidationError:
        typer.secho(
            "no valid config provided, use --help for more information",
            bg="white",
            fg="red",
        )
        typer.echo("Required options: notion_api_token, database_id, urlRoot")
        raise typer.Exit(1)
    except FileNotFoundError:
        typer.secho(
            "invalid config-file provided, use --help for more information",
            bg="white",
            fg="red",
        )
        raise typer.Exit(1)
    typer.echo(settings)
    if repeat:
        interval = dt.timedelta(seconds=seconds)
        asyncio.run(continuous_sync(interval, settings))
    else:
        asyncio.run(sync(settings))


@app.callback()
def main(verbose: bool = False):
    if verbose:
        state["verbose"] = True
