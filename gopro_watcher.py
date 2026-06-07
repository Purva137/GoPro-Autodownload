import time
import subprocess
import sys
from pathlib import Path
from datetime import datetime

GOPRO_SSID    = "Your GoPro Network Name Here"
POLL_INTERVAL = 150
COOLDOWN      = 60


def current_ssid():
    try:
        r = subprocess.run(["netsh","wlan","show","interfaces"], capture_output=True, text=True, timeout=5)
        for line in r.stdout.splitlines():
            line = line.strip()
            if line.lower().startswith("ssid") and "bssid" not in line.lower():
                return line.split(":",1)[1].strip()
    except Exception: pass
    return None


def main():
    print(f"Watcher started. Watching for: '{GOPRO_SSID}'")
    sys.path.insert(0, str(Path(__file__).parent))
    import gopro_downloader
    was_connected = False
    while True:
        try:
            connected = current_ssid() == GOPRO_SSID
            if connected and not was_connected:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] GoPro detected — starting download")
                try:
                    gopro_downloader.run()
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Done.")
                except Exception as e:
                    print(f"Error: {e}")
                time.sleep(COOLDOWN)
                was_connected = True
            elif not connected:
                was_connected = False
        except Exception as e:
            print(f"Watcher error: {e}")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()