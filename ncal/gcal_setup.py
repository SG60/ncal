"""Google Calendar API authorization."""
import pickle
from typing import Any

from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore
import google.auth.exceptions  # type: ignore
import googleapiclient.discovery  # type: ignore


def gcal_token(credentials_location, client_secret_file):
    """Produce an access token for the Google Calendar API."""
    scopes = ["https://www.googleapis.com/auth/calendar"]
    flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, scopes=scopes)
    credentials = flow.run_console()
    pickle.dump(credentials, open(credentials_location, "wb"))


def setup_google_api(
    calendar_id: str, credentials_location: str
) -> tuple[googleapiclient.discovery.Resource, Any]:
    """Set up the Google Calendar API interface."""
    credentials = pickle.load(open(credentials_location, "rb"))
    service = googleapiclient.discovery.build("calendar", "v3", credentials=credentials)

    # There could be a hiccup if the Google Calendar API token expires.
    # If the token expires, we create a new token for the program to use
    try:
        calendar = service.calendars().get(calendarId=calendar_id).execute()
    except google.auth.exceptions.RefreshError:
        # refresh the token

        gcal_token(credentials_location, "client_secret.json")

        # SET UP THE GOOGLE CALENDAR API INTERFACE

        credentials = pickle.load(open(credentials_location, "rb"))
        service = googleapiclient.discovery.build(
            "calendar", "v3", credentials=credentials
        )

        calendar = service.calendars().get(calendarId=calendar_id).execute()

    return (service, calendar)
