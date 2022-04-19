"""Google Calendar API authorization."""
import logging
import os.path
from typing import Any, Final

import google.auth.exceptions  # type: ignore
from google.auth.transport.requests import Request  # type: ignore
from google.oauth2.credentials import Credentials  # type: ignore
from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore
from googleapiclient.discovery import Resource, build  # type: ignore

# If modifying these scopes, delete the file at "token_location".
SCOPES: Final = ["https://www.googleapis.com/auth/calendar"]


def setup_google_api(
    calendar_id: str, client_secret_file: str, token_file: str
) -> tuple[Resource, Any]:
    """Set up the Google Calendar API interface.

    Args:
        calendar_id (str):
        client_secret_file (str):
        token_file (str):

    Returns:
        tuple[googleapiclient.discovery.Resource, Any]:
    """
    # credentials from json file.
    credentials = None
    if os.path.isfile(token_file):
        credentials = Credentials.from_authorized_user_file(token_file)
    if not credentials or not credentials.valid:
        # use refresh token if available
        if credentials and credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
            except google.auth.exceptions.RefreshError:
                logging.error("Failed to refresh credentials.")
                credentials = get_new_token(client_secret_file, SCOPES)
        # If no valid credentials are available, let the user log in.
        else:
            credentials = get_new_token(client_secret_file, SCOPES)
        # Save the credentials for the next run
        with open(token_file, "w") as token:
            token.write(credentials.to_json())

    # Build the service object.
    service = build("calendar", "v3", credentials=credentials)
    calendar = service.calendars()

    return (service, calendar)


def get_new_token(client_secret_file: str, scopes: list[str]):
    """Get a new user token.

    Args:
        client_secret_file: _description_
        scopes: _description_

    Returns:
        credentials: _description_
    """
    flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, scopes)
    credentials = flow.run_local_server(
        host="localhost",
        port=8080,
        authorization_prompt_message="Please visit this URL: {url}",
        success_message="The auth flow is complete; you may close this window.",
        open_browser=False,
    )

    return credentials
