import os
import shutil
import struct
import time
from pathlib import Path
from datetime import datetime

UNORG   = Path(__file__).parent / "unorg_data"
MEDIA   = Path(__file__).parent / "media"
MIN_YEAR = 2022


def gps_and_date_jpg(path):
    try:
        with open(path, "rb") as f:
            data = f.read(65536)
        if data[:2] != b'\xff\xd8':
            return None, None, None
        i = 2
        while i < len(data) - 1:
            if data[i] == 0xFF and data[i+1] == 0xE1:
                length = struct.unpack(">H", data[i+2:i+4])[0]
                app1 = data[i+4:i+2+length]
                if app1[:4] == b'Exif':
                    return _parse_exif(app1[6:])
                i += 2 + length
            else:
                i += 1
    except Exception:
        pass
    return None, None, None


def _parse_exif(e):
    try:
        le = e[:2] == b'II'
        sh, lo = ("<H","<I") if le else (">H",">I")
        ifd0 = struct.unpack(lo, e[4:8])[0]
        n = struct.unpack(sh, e[ifd0:ifd0+2])[0]
        gps_off, date = None, None
        for i in range(n):
            p = ifd0 + 2 + i*12
            tag = struct.unpack(sh, e[p:p+2])[0]
            val = struct.unpack(lo, e[p+8:p+12])[0]
            if tag == 0x8825: gps_off = val
            elif tag in (0x9003, 0x0132):
                date = e[val:val+10].decode("ascii", errors="ignore").replace(":", "-")
        lat = lon = None
        if gps_off:
            gc = struct.unpack(sh, e[gps_off:gps_off+2])[0]
            gps = {}
            for i in range(gc):
                p = gps_off + 2 + i*12
                gps[struct.unpack(sh, e[p:p+2])[0]] = struct.unpack(lo, e[p+8:p+12])[0]
            def rats(off):
                fmt = "<II" if le else ">II"
                return [struct.unpack_from(fmt,e,off+k*8)[0]/max(struct.unpack_from(fmt,e,off+k*8)[1],1) for k in range(3)]
            if 1 in gps and 2 in gps:
                d = rats(gps[2]); lat = d[0]+d[1]/60+d[2]/3600
                if chr(e[gps[1]]) == 'S': lat = -lat
            if 3 in gps and 4 in gps:
                d = rats(gps[4]); lon = d[0]+d[1]/60+d[2]/3600
                if chr(e[gps[3]]) == 'W': lon = -lon
        return lat, lon, date
    except Exception:
        return None, None, None


def gps_and_date_mp4(path):
    try:
        with open(path, "rb") as f:
            data = f.read()
        lat = lon = date = None
        i = 0
        while i < len(data) - 8:
            if data[i:i+4] == b'GPS5':
                try:
                    repeat = struct.unpack(">H", data[i+6:i+8])[0]
                    if repeat > 0:
                        raw_lat = struct.unpack(">i", data[i+8:i+12])[0]
                        raw_lon = struct.unpack(">i", data[i+12:i+16])[0]
                        lat = raw_lat / 1e7
                        lon = raw_lon / 1e7
                        if abs(lat) > 90 or abs(lon) > 180:
                            lat = lon = None
                except Exception:
                    pass
            elif data[i:i+4] == b'GPSU':
                try:
                    repeat = struct.unpack(">H", data[i+6:i+8])[0]
                    if repeat > 0:
                        raw = data[i+8:i+23].decode("ascii", errors="ignore")
                        if len(raw) >= 6:
                            date = f"20{raw[0:2]}-{raw[2:4]}-{raw[4:6]}"
                except Exception:
                    pass
            if lat and date:
                break
            i += 1
        if date and int(date[:4]) < MIN_YEAR:
            date = None
        return lat, lon, date
    except Exception:
        return None, None, None


def file_creation_date(path):
    ts = os.path.getmtime(path)
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


_geo_cache = {}
def get_city(lat, lon):
    if lat is None: return None
    key = (round(lat,2), round(lon,2))
    if key in _geo_cache: return _geo_cache[key]
    try:
        import requests
        r = requests.get("https://nominatim.openstreetmap.org/reverse",
            params={"lat":lat,"lon":lon,"format":"json","zoom":10},
            headers={"User-Agent":"GoPro-AutoDownloader/1.0"}, timeout=8)
        a = r.json().get("address", {})
        name = (a.get("city") or a.get("town") or a.get("village") or
                a.get("county") or a.get("state") or "Unknown").replace(" ","_")
        _geo_cache[key] = name
        return name
    except Exception:
        return None


def already_exists(filename):
    return any(MEDIA.rglob(filename))


def organise_file(filepath):
    filename = filepath.name
    ext = filepath.suffix.lower()
    is_jpg = ext in (".jpg", ".jpeg")
    is_mp4 = ext == ".mp4"

    if already_exists(filename):
        print(f"  ⏭  {filename} already in media/ — skipping")
        return

    lat = lon = date = None
    if is_jpg:
        lat, lon, date = gps_and_date_jpg(filepath)
    elif is_mp4:
        lat, lon, date = gps_and_date_mp4(filepath)

    if not date:
        date = file_creation_date(filepath)
    if date and int(date[:4]) < MIN_YEAR:
        date = file_creation_date(filepath)

    loc = get_city(lat, lon) or "Unknown_Location"
    dest = MEDIA / loc / date
    dest.mkdir(parents=True, exist_ok=True)
    fp = dest / filename
    if fp.exists():
        fp = dest / f"{filepath.stem}_{int(time.time())}{ext}"
    shutil.copy2(str(filepath), str(fp))
    print(f"  ✓ {filename} → media/{loc}/{date}/")


def run():
    if not UNORG.exists():
        print("Create a folder called 'unorg_data' in GoproAutomation and dump your files there.")
        return
    files = [f for f in UNORG.rglob("*") if f.is_file()]
    if not files:
        print("unorg_data/ is empty."); return
    print(f"\n🗂  Organising {len(files)} file(s) from unorg_data/\n")
    failed = []
    for f in files:
        try: organise_file(f)
        except Exception as e: print(f"  ✗ {f.name}: {e}"); failed.append(f.name)
    print(f"\n{'─'*45}")
    if failed:
        print(f"⚠  {len(failed)} failed: {', '.join(failed)}")
    else:
        print("✓ All files organised into media/")
    print("\nOriginal files still in unorg_data/ — delete manually once you've verified.\n")


if __name__ == "__main__":
    run()