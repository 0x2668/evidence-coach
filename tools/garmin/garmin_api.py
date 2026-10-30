"""Shared helpers for the Garmin Connect Personal API scripts.

The API key is read from ~/.config/garmin/api_key (outside the repository)
or from the GARMIN_API_KEY_FILE environment variable. Data is written to
athletes/<alias>/garmin/, which is git-ignored (health data, GDPR Art. 9).
"""
import csv
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://personal.connectapi.garmin.com"
KEY_FILE = Path(os.environ.get("GARMIN_API_KEY_FILE", "~/.config/garmin/api_key")).expanduser()
ROOT = Path(__file__).resolve().parents[2]
DATA = None  # set by use_athlete()
PAUSE = 0.5  # seconds between requests
CHUNK_DAYS = 28  # largest range accepted by every daily endpoint we use

# Fields that identify the account owner; not needed for coaching.
DROP_ACTIVITY_FIELDS = {
    "ownerId", "ownerDisplayName", "ownerFullName", "ownerProfileImageUrlSmall",
    "ownerProfileImageUrlMedium", "ownerProfileImageUrlLarge", "userRoles",
}


class ApiError(RuntimeError):
    pass


def use_athlete(alias):
    """Send all output to athletes/<alias>/garmin/."""
    global DATA
    if not re.fullmatch(r"[A-Za-z0-9_-]+", alias):
        raise ApiError(f"Invalid athlete alias: {alias!r} (use letters, digits, - and _)")
    DATA = ROOT / "athletes" / alias / "garmin"


class Client:
    def __init__(self):
        if not KEY_FILE.exists():
            raise ApiError(f"API key file not found: {KEY_FILE}")
        key = KEY_FILE.read_text().strip()
        req = urllib.request.Request(
            BASE + "/personalapitoken-service/personal-api/personal-api-key/token",
            method="POST", headers={"Authorization": "ApiKey " + key})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                self.token = r.read().decode().strip()
        except urllib.error.HTTPError as e:
            raise ApiError(f"Token request failed: HTTP {e.code} (key expired or revoked?)")
        self._last = 0.0

    def _open(self, path):
        wait = PAUSE - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(
            BASE + path, headers={"Authorization": "Bearer " + self.token, "Accept": "*/*"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            # No retry loop: stop and report, the scripts are resumable.
            raise ApiError(f"GET {path.split('?')[0]} failed: HTTP {e.code}")
        except urllib.error.URLError as e:
            raise ApiError(f"GET {path.split('?')[0]} failed: {e.reason}")
        finally:
            self._last = time.monotonic()

    def json(self, path):
        status, body = self._open(path)
        if status == 204 or not body.strip():
            return None
        return json.loads(body)

    def bytes(self, path):
        return self._open(path)[1]


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1))
    tmp.replace(path)


def daterange_chunks(start, end, days=CHUNK_DAYS):
    d = start
    while d <= end:
        e = min(d + dt.timedelta(days=days - 1), end)
        yield d, e
        d = e + dt.timedelta(days=1)


def fetch_daily(client, start, end):
    """Fetch daily summary, sleep and HRV for start..end and write one raw file per day."""
    for a, b in daterange_chunks(start, end):
        summ = client.json(f"/usersummary-service/v2/dailysummaries?startDate={a}&endDate={b}") or {}
        sleep = client.json(f"/sleep-service/sleep/dailySleepSummariesByDate?startDate={a}&endDate={b}") or []
        hrv = client.json(f"/hrv-service/hrv/daily/{a}/{b}") or {}
        days = {}
        for s in summ.get("data", []):
            days.setdefault(s["calendarDate"], {})["summary"] = s
        for s in sleep:
            days.setdefault(s["calendarDate"], {})["sleep"] = s
        for s in hrv.get("hrvSummaries", []):
            days.setdefault(s["calendarDate"], {})["hrv"] = s
        for day, content in days.items():
            write_json(DATA / "raw" / "daily" / f"{day}.json", content)
        print(f"daily {a}..{b}: {len(days)} days")


def save_activity(client, act, with_fit=True):
    aid = act["activityId"]
    for k in DROP_ACTIVITY_FIELDS:
        act.pop(k, None)
    write_json(DATA / "raw" / "activities" / f"{aid}.json", act)
    fit = DATA / "raw" / "fit" / f"{aid}.zip"
    if with_fit and not fit.exists():
        fit.parent.mkdir(parents=True, exist_ok=True)
        fit.write_bytes(client.bytes(f"/download-service/files/activity/{aid}"))
        return True
    return False


def fetch_activities(client, start=None, end=None, page=99):
    """Page through activities (newest first); returns the number saved."""
    q = ""
    if start:
        q += f"&startDate={start}"
    if end:
        q += f"&endDate={end}"
    offset = n = new_fit = 0
    while True:
        batch = client.json(
            f"/activitylist-service/activities/search/activities?start={offset}&limit={page}{q}") or []
        for act in batch:
            new_fit += save_activity(client, act)
            n += 1
        print(f"activities: {n} saved so far ({new_fit} new FIT files)")
        if len(batch) < page:
            return n
        offset += page


def _g(d, *path):
    for p in path:
        if not isinstance(d, dict):
            return None
        d = d.get(p)
    return d


def rebuild_csv():
    """Rebuild daily.csv and activities.csv from the raw files."""
    rows = []
    for f in sorted((DATA / "raw" / "daily").glob("*.json")):
        d = json.loads(f.read_text())
        s, sl, h = d.get("summary", {}), d.get("sleep", {}), d.get("hrv", {})
        steps = _g(s, "movement", "steps")
        rows.append({
            "date": f.stem,
            "steps": steps.get("value") if isinstance(steps, dict) else steps,
            "resting_hr": _g(s, "heartRate", "restingValue"),
            "min_hr": _g(s, "heartRate", "minValue"),
            "max_hr": _g(s, "heartRate", "maxValue"),
            "stress_avg": _g(s, "stress", "avgLevel"),
            "body_battery_min": _g(s, "bodyBattery", "minValue"),
            "body_battery_max": _g(s, "bodyBattery", "maxValue"),
            "intensity_min_moderate": _g(s, "intensityMinutes", "moderate"),
            "intensity_min_vigorous": _g(s, "intensityMinutes", "vigorous"),
            "kcal_total": _g(s, "calories", "burnedTotal"),
            "sleep_h": round(sl["sleepTimeSeconds"] / 3600, 2) if sl.get("sleepTimeSeconds") else None,
            "sleep_deep_min": round(sl["deepSleepSeconds"] / 60) if sl.get("deepSleepSeconds") is not None else None,
            "sleep_rem_min": round(sl["remSleepSeconds"] / 60) if sl.get("remSleepSeconds") is not None else None,
            "sleep_score": _g(sl, "sleepScores", "overall", "value"),
            "hrv_last_night": h.get("lastNightAvg"),
            "hrv_weekly_avg": h.get("weeklyAvg"),
            "hrv_status": h.get("status"),
        })
    _write_csv(DATA / "daily.csv", rows)

    arows = []
    for f in (DATA / "raw" / "activities").glob("*.json"):
        a = json.loads(f.read_text())
        arows.append({
            "start_local": a.get("startTimeLocal"),
            "activity_id": a.get("activityId"),
            "type": _g(a, "activityType", "typeKey"),
            "name": a.get("activityName"),
            "distance_km": round(a["distance"] / 1000, 2) if a.get("distance") else None,
            "duration_min": round(a["duration"] / 60, 1) if a.get("duration") else None,
            "elev_gain_m": a.get("elevationGain"),
            "avg_hr": a.get("averageHR"),
            "max_hr": a.get("maxHR"),
            "avg_power": a.get("avgPower"),
            "training_load": a.get("activityTrainingLoad"),
            "aerobic_te": a.get("aerobicTrainingEffect"),
            "hr_zone1_s": a.get("hrTimeInZone_1"), "hr_zone2_s": a.get("hrTimeInZone_2"),
            "hr_zone3_s": a.get("hrTimeInZone_3"), "hr_zone4_s": a.get("hrTimeInZone_4"),
            "hr_zone5_s": a.get("hrTimeInZone_5"),
        })
    arows.sort(key=lambda r: r["start_local"] or "")
    _write_csv(DATA / "activities.csv", arows)
    print(f"csv: {len(rows)} days, {len(arows)} activities -> {DATA}")


def _write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def run(main):
    try:
        main()
    except ApiError as e:
        print("ERROR:", e, file=sys.stderr)
        sys.exit(1)
