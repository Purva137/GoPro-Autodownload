import requests
import os
import time
import struct
import shutil
from pathlib import Path
from datetime import datetime

GOPRO = "http://10.5.5.9"
MEDIA = Path(__file__).parent / "media"
MIN_FREE_GB = 15


def get_files():
    r = requests.get(f"{GOPRO}/gp/gpMediaList", timeout=10)
    r.raise_for_status()
    return [(d["d"], f["n"]) for d in r.json().get("media", []) for f in d.get("fs", [])]


def check_storage():
    free = shutil.disk_usage(Path(__file__).parent).free / (1024**3)
    if free < MIN_FREE_GB:
        raise RuntimeError(f"Only {free:.1f}GB free on laptop — download aborted. Need at least {MIN_FREE_GB}GB.")


def already_exists(filename):
    return any(MEDIA.rglob(filename))


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
    """Extract GPS + date from GoPro GPMF telemetry track inside MP4."""
    try:
        with open(path, "rb") as f:
            data = f.read()
        # scan for GPMF box — GoPro embeds telemetry as 'GoPro MET' or 'GPMF'
        lat = lon = date = None
        i = 0
        while i < len(data) - 8:
            # look for GPS5 atom (GoPro GPS: lat, lon, alt, speed, speed3d)
            if data[i:i+4] == b'GPS5':
                try:
                    # GPMF GPS5 value: each sample is 5 x int32, scaled
                    # header is 8 bytes: fourcc(4) + type(1) + size(1) + repeat(2)
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
            # look for GPSU atom (GPS UTC timestamp)
            elif data[i:i+4] == b'GPSU':
                try:
                    repeat = struct.unpack(">H", data[i+6:i+8])[0]
                    if repeat > 0:
                        raw = data[i+8:i+23].decode("ascii", errors="ignore")
                        # format: YYMMDDHHMMSS.sss
                        if len(raw) >= 6:
                            date = f"20{raw[0:2]}-{raw[2:4]}-{raw[4:6]}"
                except Exception:
                    pass
            if lat and date:
                break
            i += 1
        return lat, lon, date
    except Exception:
        return None, None, None


def make_thumbnail(src_path, dest_dir, filename):
    thumb_path = dest_dir / (Path(filename).stem + "_thumb.jpg")
    cmd = f'ffmpeg -y -i "{src_path}" -ss 00:00:01 -vframes 1 -vf scale=320:-1 "{thumb_path}" -loglevel quiet 2>nul'
    os.system(cmd)
    if thumb_path.exists():
        print(f"     🖼  thumbnail saved")


_geo_cache = {}
def get_city(lat, lon):
    if lat is None: return None
    key = (round(lat,2), round(lon,2))
    if key in _geo_cache: return _geo_cache[key]
    try:
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


def download_file(directory, filename):
    if already_exists(filename):
        print(f"  ⏭  {filename} already exists — skipping")
        return

    url = f"{GOPRO}/videos/DCIM/{directory}/{filename}"
    tmp = MEDIA / f"_tmp_{filename}"
    MEDIA.mkdir(parents=True, exist_ok=True)
    is_jpg = filename.lower().endswith((".jpg", ".jpeg"))
    is_mp4 = filename.lower().endswith(".mp4")

    print(f"  ↓ {filename}", end="", flush=True)
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        done = 0
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(65536):
                f.write(chunk); done += len(chunk)
                if total: print(f"\r  ↓ {filename}  {done*100//total}%  ", end="", flush=True)
    print(f"\r  ✓ {filename}        ")

    if is_jpg:
        lat, lon, date = gps_and_date_jpg(tmp)
    elif is_mp4:
        lat, lon, date = gps_and_date_mp4(tmp)
        if date and int(date[:4]) < 2022:
            date = None
    else:
        lat, lon, date = None, None, None

    date = date or datetime.now().strftime("%Y-%m-%d")
    loc = get_city(lat, lon) or "Unknown_Location"
    dest = MEDIA / loc / date
    dest.mkdir(parents=True, exist_ok=True)
    fp = dest / filename
    tmp.rename(fp)
    print(f"     → media/{loc}/{date}/{fp.name}")

    if is_mp4:
        make_thumbnail(fp, dest, filename)


def run():
    print("\n📷  GoPro connected — downloading")
    check_storage()
    files = get_files()
    if not files:
        print("No media found."); return
    print(f"Found {len(files)} file(s)\n")
    failed = []
    for d, f in files:
        try: download_file(d, f)
        except Exception as e: print(f"  ✗ {f}: {e}"); failed.append(f)
    if failed:
        print(f"\n⚠  {len(failed)} file(s) failed — GoPro NOT wiped.")
    else:
        requests.get(f"{GOPRO}/gp/gpControl/command/storage/delete/all", timeout=10)
        print("\n✓ GoPro wiped. Done.\n")


if __name__ == "__main__":
    run()