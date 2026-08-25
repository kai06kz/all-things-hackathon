import os
import io
import base64
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/gmail.readonly'
]

SYNC_FOLDER = "./my_knowledge_folder"
os.makedirs(SYNC_FOLDER, exist_ok=True)

def authenticate_google():
    # Load or request user OAuth tokens
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds

def sync_drive_files(creds):
    # Fetch recent files from Google Drive
    service = build('drive', 'v3', credentials=creds)
    results = service.files().list(
        pageSize=10, 
        fields="files(id, name, mimeType)",
        q="trashed = false"
    ).execute()
    
    files = results.get('files', [])
    print(f"[*] Found {len(files)} files in Google Drive.")
    
    # MIME mapping for Google Workspace files
    export_mime_map = {
        'application/vnd.google-apps.document': ('text/plain', '.txt'),
        'application/vnd.google-apps.spreadsheet': ('text/csv', '.csv'),
        'application/vnd.google-apps.presentation': ('text/plain', '.txt')
    }
    
    for f in files:
        file_id = f['id']
        # Clean file name from illegal characters
        raw_name = "".join(c for c in f['name'] if c.isalnum() or c in (' ', '_', '-')).rstrip()
        mime = f.get('mimeType', '')
        
        if mime == 'application/vnd.google-apps.folder':
            continue
            
        try:
            if mime in export_mime_map:
                export_mime, ext = export_mime_map[mime]
                dest_path = os.path.join(SYNC_FOLDER, f"drive_{raw_name}{ext}")
                if os.path.exists(dest_path):
                    continue
                print(f"[+] Exporting Google Workspace file: {raw_name}{ext}")
                request = service.files().export_media(fileId=file_id, mimeType=export_mime)
            else:
                dest_path = os.path.join(SYNC_FOLDER, f"drive_{raw_name}")
                if os.path.exists(dest_path):
                    continue
                print(f"[+] Downloading file: {raw_name}")
                request = service.files().get_media(fileId=file_id)
                
            with open(dest_path, "wb") as fh:
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
        except Exception as e:
            print(f"[-] Skipped {raw_name} due to error: {e}")

def sync_gmail_threads(creds):
    # Fetch recent engineering emails
    service = build('gmail', 'v1', credentials=creds)
    results = service.users().messages().list(
        userId='me', 
        q='subject:(deploy OR architecture OR bug OR decision OR release)', 
        maxResults=5
    ).execute()
    
    messages = results.get('messages', [])
    print(f"[*] Found {len(messages)} matching Gmail messages.")
    
    for m in messages:
        msg_id = m['id']
        dest_path = os.path.join(SYNC_FOLDER, f"email_{msg_id}.txt")
        if os.path.exists(dest_path):
            continue
            
        msg = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
        headers = {h['name']: h['value'] for h in msg['payload']['headers'] if h['name'] in ['Subject', 'From', 'Date']}
        
        # Decode body text from payload parts
        body = ""
        payload = msg.get('payload', {})
        if 'parts' in payload:
            for part in payload['parts']:
                if part.get('mimeType') == 'text/plain' and 'data' in part.get('body', {}):
                    body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                    break
        elif 'body' in payload and 'data' in payload['body']:
            body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')
            
        email_content = f"Date: {headers.get('Date', '')}\nFrom: {headers.get('From', '')}\nSubject: {headers.get('Subject', '')}\n\n{body or msg.get('snippet', '')}"
        
        with open(dest_path, "w", encoding="utf-8") as f:
            f.write(email_content)
        print(f"[+] Synced email: {headers.get('Subject', 'No Subject')}")

if __name__ == '__main__':
    # Run sync pipeline
    google_creds = authenticate_google()
    sync_drive_files(google_creds)
    sync_gmail_threads(google_creds)