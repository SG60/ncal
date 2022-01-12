import pickle

from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore

# from googleapiclient.discovery import build  # type: ignore

# SET UP THE GOOGLE CALENDAR API INTERFACE


def gcal_token(credentials_location, client_secret_file):
    scopes = ["https://www.googleapis.com/auth/calendar"]
    flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, scopes=scopes)
    credentials = flow.run_console()
    pickle.dump(credentials, open(credentials_location, "wb"))
    # credentials = pickle.load(open("token.pkl", "rb"))
    # service = build("calendar", "v3", credentials=credentials)
