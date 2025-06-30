import os.path
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/drive.readonly',
]


def main():
    creds = None
    # If token.pickle exists, reuse it
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If no valid token, login and get a new one
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file('client-secret.json', SCOPES)
        creds = flow.run_local_server(port=8000)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    # Connect to Gmail API
    service = build('gmail', 'v1', credentials=creds)
    # Test: List first 10 message IDs
    results = service.users().messages().list(userId='me', maxResults=10).execute()
    messages = results.get('messages', [])
    for msg in messages:
        print(msg['id'])
        # print(msg)

if __name__ == '__main__':
    main()
