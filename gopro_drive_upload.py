import os
import pickle
from pathlib import Path
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES         = ["https://www.googleapis.com/auth/drive"]
CREDS_FILE     = Path(__file__).parent / "credentials.json"
TOKEN_FILE     = Path(__file__).parent / "token.pickle"
MEDIA_DIR      = Path(__file__).parent / "media"
DRIVE_FOLDER   = "GoPro"
MIN_FREE_GB    = 3  # minimum free space on Drive before stopping


def authenticate():
    creds = None
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)
    return build("drive", "v3", credentials=creds)


def get_or_create_folder(service, name, parent_id=None):
    query = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]
    meta = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        meta["parents"] = [parent_id]
    folder = service.files().create(body=meta, fields="id").execute()
    return folder["id"]


def file_exists_in_folder(service, filename, folder_id):
    query = f"name='{filename}' and '{folder_id}' in parents and trashed=false"
    results = service.files().list(q=query, fields="files(id)").execute()
    return len(results.get("files", [])) > 0


def check_drive_storage(service):
    about = service.about().get(fields="storageQuota").execute()
    quota = about["storageQuota"]
    used = int(quota["usage"])
    total = int(quota["limit"])
    free_gb = (total - used) / (1024**3)
    if free_gb < MIN_FREE_GB:
        raise RuntimeError(f"Only {free_gb:.1f}GB free on Drive — upload aborted.")
    print(f"Drive storage: {free_gb:.1f}GB free")


def upload_file(service, filepath, folder_id):
    filename = filepath.name
    if file_exists_in_folder(service, filename, folder_id):
        print(f"  ⏭  {filename} already on Drive — skipping")
        return
    mime = "video/mp4" if filename.lower().endswith(".mp4") else "image/jpeg"
    media = MediaFileUpload(str(filepath), mimetype=mime, resumable=True)
    meta = {"name": filename, "parents": [folder_id]}
    print(f"  ↑ {filename}", end="", flush=True)
    request = service.files().create(body=meta, media_body=media, fields="id")
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"\r  ↑ {filename}  {int(status.progress()*100)}%  ", end="", flush=True)
    print(f"\r  ✓ {filename}        ")


def run():
    print("\n☁  GoPro → Google Drive upload")
    print("─" * 45)
    service = authenticate()
    check_drive_storage(service)

    # get all local files
    all_files = list(MEDIA_DIR.rglob("*"))
    all_files = [f for f in all_files if f.is_file() and not f.name.startswith("_tmp")]

    if not all_files:
        print("No media found in media/ folder."); return

    print(f"Found {len(all_files)} file(s) to sync\n")

    # create root GoPro folder on Drive
    root_id = get_or_create_folder(service, DRIVE_FOLDER)

    failed = []
    for filepath in all_files:
        try:
            # mirror the city/date folder structure
            rel = filepath.relative_to(MEDIA_DIR)
            parts = rel.parts[:-1]  # e.g. ('Ahmedabad', '2026-06-03')
            folder_id = root_id
            for part in parts:
                folder_id = get_or_create_folder(service, part, folder_id)
            upload_file(service, filepath, folder_id)
        except Exception as e:
            print(f"  ✗ {filepath.name}: {e}")
            failed.append(filepath.name)

    print(f"\n{'─'*45}")
    if failed:
        print(f"⚠  {len(failed)} file(s) failed: {', '.join(failed)}")
    else:
        print("✓ All files synced to Google Drive.")
    print(f"Folder: Drive → {DRIVE_FOLDER}/\n")


if __name__ == "__main__":
    run()