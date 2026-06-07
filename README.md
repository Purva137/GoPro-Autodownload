# GoPro AutoDownload

Automate GoPro media offload — auto-detects camera Wi-Fi, downloads footage organized by city and date using GPS metadata, and syncs to Google Drive. No GoPro app needed. Windows & Mac compatible.

---

## Why?

GoPro killed their desktop app. The only official way to transfer footage is their mobile app or physically removing the SD card. This project fixes that — connect your laptop to GoPro Wi-Fi and everything downloads automatically, organized and backed up.

---

## Features

- Auto-detects GoPro Wi-Fi and triggers download automatically
- Organizes by city then date — `media/Ahmedabad/2026-06-03/`
- GPS extraction from JPEGs (EXIF) and MP4s (GPMF telemetry)
- Reverse geocoding via OpenStreetMap — no API key needed
- Duplicate detection — never downloads the same file twice
- Storage check — won't download if laptop is low on space
- Auto-wipes GoPro after successful download
- Google Drive sync with duplicate check
- Organizes existing unorganized footage by city and date
- No logs, no telemetry, nothing leaves your device unless you run Drive sync

---

## Files

| File | Purpose |
|---|---|
| `gopro_downloader.py` | Core download logic. Run manually or triggered by watcher. |
| `gopro_watcher.py` | Background watcher — detects GoPro Wi-Fi and auto-triggers download. |
| `gopro_drive_upload.py` | Manual Google Drive sync. |
| `gopro_organise.py` | Organizes existing unorganized footage into city/date folders. |

---

## Requirements

**Python 3.8+**

Install dependencies:
```bash
pip install requests google-auth-oauthlib google-api-python-client
```

---

## Setup

### Step 1 — Clone the repo

```bash
git clone https://github.com/Purva137/GoPro-Autodownload.git
cd GoPro-Autodownload
```

### Step 2 — Install dependencies

```bash
pip install requests google-auth-oauthlib google-api-python-client
```

### Step 3 — Find your GoPro Wi-Fi name

On your GoPro: swipe down → tap the wireless icon → Connect → Camera on Phone → this activates the hotspot.

On your laptop, check available Wi-Fi networks. You'll see a network like `GP24500XXXX` or whatever you've named it.

Open `gopro_watcher.py` and set line 7:
```python
GOPRO_SSID = "Your GoPro Network Name Here"
```

### Step 4 — Test the downloader

Connect your laptop to GoPro Wi-Fi, then run:
```bash
python gopro_downloader.py
```

You should see files downloading into `media/city/date/` folders. If GPS was locked when shooting, city names will appear. If indoors, files go to `Unknown_Location/`.

### Step 5 — Set up background watcher (Windows)

This makes the watcher start automatically every time you log into Windows.

1. Press `Win` → search **Task Scheduler** → open it
2. Click **Create Basic Task** on the right
3. Name: `GoPro AutoDownload` → Next
4. Trigger: **When I log on** → Next
5. Action: **Start a program** → Next
6. Program: full path to your Python exe, e.g.
   `C:\Users\YourName\AppData\Local\Programs\Python\Python314\python.exe`
7. Arguments: full path to `gopro_watcher.py`, e.g.
   `"C:\Users\YourName\Desktop\GoPro-Autodownload\gopro_watcher.py"`
8. Click Next → Finish
9. Find the task in the list → right-click → Properties → Triggers → Edit → set **Delay task for: 3 minutes** → OK

From now on, every time you log in and connect to GoPro Wi-Fi, download starts automatically within 2-3 minutes.

To run the watcher right now without rebooting:
```bash
python gopro_watcher.py
```

### Step 6 — Google Drive sync (optional)

**6a. Create Google Cloud credentials**

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project — name it anything e.g. `GoPro Sync`
3. Search for **Google Drive API** → Enable it
4. Go to **Google Auth Platform** → Branding → Get Started → fill in app name and your email → save
5. Go to **Audience** → Add your Gmail as a test user
6. Go to **Clients** → Create OAuth Client → Desktop App → Create → Download JSON
7. Rename the downloaded file to `credentials.json`
8. Place `credentials.json` in the project folder

**6b. Run first-time auth**

```bash
python gopro_drive_upload.py
```

A browser window opens — sign in with Google and allow access. This only happens once. A `token.pickle` file is saved for future runs.

**6c. Run sync anytime**

```bash
python gopro_drive_upload.py
```

All media from your `media/` folder uploads to a `GoPro` folder on Drive, mirroring the same city/date structure. Already uploaded files are skipped automatically.

---

## Organizing Existing Footage

If you have old unorganized GoPro footage:

1. Create a folder called `unorg_data` inside the project directory
2. Dump all your media files into it (any structure, just dump everything)
3. Run:
```bash
python gopro_organise.py
```

Files are **copied** (not moved) into `media/city/date/` — originals stay in `unorg_data/` until you verify everything looks right and delete manually.

---

## Folder Structure
media/
  location/
    date/
      image.jpg/video.mp4

---

## Tips

- Shoot outdoors for GPS lock — city names won't work indoors
- For geocoding during GoPro download (both Wi-Fi connections needed), plug your phone via USB and enable USB tethering on your phone — laptop gets internet through phone while staying on GoPro Wi-Fi or connect it with a Dongle/Wi-Fi adaptors/Network adaptors
- Quality is never touched — raw byte-for-byte copy at every step, nothing is re-encoded
- `credentials.json` and `token.pickle` are in `.gitignore` — never commit these

---

## Compatibility

| Feature | Windows | Mac |
|---|---|---|
| Manual download | ✅ | ✅ |
| Auto Wi-Fi watcher | ✅ | ❎ Manual only |
| Google Drive sync | ✅ | ✅ |
| Organise existing footage | ✅ | ✅ |

---

Made by [Purva Patel](https://github.com/Purva137)
