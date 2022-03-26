"""Command Line Interface for synchronising Google Calendar and Notion."""
import asyncio
import datetime
import logging
from pathlib import Path
from typing import Callable, Coroutine, Optional

import arrow
import notion_client as nc
import typer
from googleapiclient.discovery import Resource  # type: ignore
from pydantic import ValidationError

from ncal import core
from ncal.config import Settings, load_settings

from . import __version__

app = typer.Typer(help="CLI to sync a Notion database with Google Calendar.")
state = {"verbose": False}


async def scheduler(
    timedelta: datetime.timedelta, function: Callable[..., Coroutine], f_args: dict
) -> None:
    """Schedule an async function.

    Args:
        timedelta:
        function:
        f_args: arguments to pass to the function
    """
    next_run = arrow.utcnow() + timedelta
    print(f"next run: {next_run}")
    while True:
        now = arrow.utcnow()
        if now >= next_run:
            await function(**f_args)
            next_run = timedelta + next_run
            print(f"next run: {next_run}")
        await asyncio.sleep(1)


async def sync(settings: Settings, service: Resource, notion: nc.Client) -> None:
    """Sync between Google Calendar and Notion.

    Args:
        settings: Configuration settings
        service: A Google Calendar API Client
        notion: A Notion API Client
    """
    num_steps = 4
    if settings.delete_option:
        num_steps += 1

    with typer.progressbar(
        range(num_steps), label="Synchronising", show_eta=False, show_pos=True
    ) as progress:
        today_date = arrow.utcnow().isoformat()

        progress.label = "new N->G"
        core.new_events_notion_to_gcal(
            settings.database_id,
            settings.url_root,
            settings.default_calendar_name,
            settings.calendar_dictionary,
            settings.task_notion_name,
            settings.date_notion_name,
            settings.initiative_notion_name,
            settings.extrainfo_notion_name,
            settings.on_gcal_notion_name,
            settings.gcal_event_id_notion_name,
            settings.lastupdatedtime_notion_name,
            settings.calendar_notion_name,
            settings.current_calendar_id_notion_name,
            settings.delete_notion_name,
            notion,
            service,
            settings=settings,
        )
        progress.update(1)

        progress.label = "modified N->G"
        core.existing_events_notion_to_gcal(
            settings.database_id,
            settings.url_root,
            settings.default_calendar_id,
            settings.default_calendar_name,
            settings.calendar_dictionary,
            settings.task_notion_name,
            settings.date_notion_name,
            settings.initiative_notion_name,
            settings.extrainfo_notion_name,
            settings.on_gcal_notion_name,
            settings.need_gcal_update_notion_name,
            settings.gcal_event_id_notion_name,
            settings.lastupdatedtime_notion_name,
            settings.calendar_notion_name,
            settings.current_calendar_id_notion_name,
            settings.delete_notion_name,
            notion,
            today_date,
            service,
            settings=settings,
        )
        progress.update(1)

        progress.label = "modified G->N"
        core.existing_events_gcal_to_notion(
            settings.database_id,
            settings.default_calendar_name,
            settings.calendar_dictionary,
            settings.date_notion_name,
            settings.on_gcal_notion_name,
            settings.need_gcal_update_notion_name,
            settings.gcal_event_id_notion_name,
            settings.lastupdatedtime_notion_name,
            settings.calendar_notion_name,
            settings.current_calendar_id_notion_name,
            settings.delete_notion_name,
            service,
            notion,
            today_date,
            settings=settings,
        )
        progress.update(1)

        progress.label = "new G->N"
        core.new_events_gcal_to_notion(
            settings.database_id,
            settings.calendar_dictionary,
            settings.task_notion_name,
            settings.date_notion_name,
            settings.extrainfo_notion_name,
            settings.on_gcal_notion_name,
            settings.gcal_event_id_notion_name,
            settings.lastupdatedtime_notion_name,
            settings.calendar_notion_name,
            settings.current_calendar_id_notion_name,
            settings.delete_notion_name,
            service,
            notion,
            settings=settings,
        )

        if settings.delete_option:
            progress.update(1)
            progress.label = "delete done pages from GCal"
            core.delete_done_pages(
                notion=notion,
                database_id=settings.database_id,
                gcal_event_id_notion_name=settings.gcal_event_id_notion_name,
                on_gcal_notion_name=settings.on_gcal_notion_name,
                delete_notion_name=settings.delete_notion_name,
                delete_option=settings.delete_option,
                calendar_dictionary=settings.calendar_dictionary,
                calendar_notion_name=settings.calendar_notion_name,
                service=service,
            )

        progress.label = "Synchronised"
        progress.update(1)
        typer.echo(f"Synchronised at UTC {arrow.utcnow()}")


async def continuous_sync(
    interval: datetime.timedelta,
    settings: Settings,
    service: Resource,
    notion: nc.Client,
):
    """Call sync continuously.

    Args:
        interval (datetime.timedelta):
        settings (Settings):
        service (Resource):
        notion (nc.Client):
    """
    await sync(settings, service, notion)
    await scheduler(
        interval, sync, {"settings": settings, "service": service, "notion": notion}
    )


@app.command("sync")
def cli_sync(
    repeat: bool = typer.Option(False, "--repeat/--no-repeat", "-r"),
    seconds: int = 10,
    config_file: Optional[Path] = typer.Option(
        None, "--config-file", "-c", help="toml configuration file location"
    ),
    notion_api_token: Optional[str] = None,
    database_id: Optional[str] = None,
    url_root: Optional[str] = None,
    delete_pages: Optional[bool] = typer.Option(
        False,
        "--delete-pages/--no-delete-pages",
        "-d",
        help="delete pages which have been marked done",
    ),
):
    """CLI to sync a Notion database with Google Calendar."""
    typer.echo()
    typer.secho(
        "Synchronize Notion <-> GCal", bg=typer.colors.GREEN, fg="white", bold=True
    )
    typer.echo()

    try:
        if config_file:
            settings = load_settings(
                config_file_path=config_file,
                notion_api_token=notion_api_token,
                database_id=database_id,
                url_root=url_root,
                delete_option=delete_pages,
            )
        else:
            settings = load_settings(
                notion_api_token=notion_api_token,
                database_id=database_id,
                url_root=url_root,
                delete_option=delete_pages,
            )
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
    logging.info(settings)

    typer.echo("Setting up API connections...")
    service, calendar, notion = core.setup_api_connections(
        default_calendar_id=settings.default_calendar_id,
        credentials_location=settings.credentials_location,
        notion_api_token=settings.notion_api_token,
        client_secret_location=settings.client_secret_location,
    )

    if repeat:
        interval = datetime.timedelta(seconds=seconds)
        asyncio.run(continuous_sync(interval, settings, service, notion))
    else:
        asyncio.run(sync(settings, service, notion))


@app.callback(invoke_without_command=True, no_args_is_help=True)
def main(
    verbose: bool = False,
    version: bool = typer.Option(None, "--version", is_eager=True),
):
    """Main CLI entrypoint."""  # noqa: D401
    if verbose:
        state["verbose"] = True
        logging.basicConfig(level=20)
    if version:
        typer.echo(f"ncal version: {__version__}")
        raise typer.Exit()
