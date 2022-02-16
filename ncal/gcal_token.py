import pickle

from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore


def gcal_token(credentials_location, client_secret_file):
    """Set up the Google Calendar api interface"""
    scopes = ["https://www.googleapis.com/auth/calendar"]
    flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, scopes=scopes)
    credentials = flow.run_console()
    pickle.dump(credentials, open(credentials_location, "wb"))
