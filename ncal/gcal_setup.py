"""Google Calendar API authorization."""
import os.path
from typing import Any, Final

import google.auth.exceptions  # type: ignore
import google.auth.transport.requests  # type: ignore
import googleapiclient.discovery  # type: ignore
from google.oauth2.credentials import Credentials  # type: ignore
from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore

# If modifying these scopes, delete the file at "token_location".
SCOPES: Final = ["https://www.googleapis.com/auth/calendar"]


def setup_google_api(
    calendar_id: str, client_secret_file: str, token_file: str
) -> tuple[googleapiclient.discovery.Resource, Any]:
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
    # If no valid credentials are available, let the user log in.
    if not credentials or not credentials.valid:
        # use refresh token if available
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(google.auth.transport.requests.Request())
        # otherwise, get new credentials
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, SCOPES)
            credentials = flow.run_local_server(port=0, open_browser=False)
        # Save the credentials for the next run
        with open(token_file, "w") as token:
            token.write(credentials.to_json())

    # Build the service object.
    service = googleapiclient.discovery.build("calendar", "v3", credentials=credentials)
    calendar = service.calendars().get(calendarId=calendar_id).execute()

    return (service, calendar)
