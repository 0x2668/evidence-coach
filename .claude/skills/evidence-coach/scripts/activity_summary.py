#!/usr/bin/env python3
"""Summarise one activity file: GPX, TCX, CSV (one row per sample) or FIT.

Usage: python3 activity_summary.py FILE [--zones 130,150,165] [--splits] [--json]

--zones  upper heart-rate limit (bpm) of every zone except the last; prints
         time in each zone. Zone limits come from the athlete's own testing or
         the knowledge base, never from this script.
--splits per-kilometre split times (needs distance or GPS positions).

Standard library only. FIT support covers the standard record and session
messages (including compressed timestamps and developer fields); unusual
files may fail, in which case export GPX or TCX instead.
"""
import argparse
import csv
import json
import math
import struct
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

FIT_EPOCH = datetime(1989, 12, 31, tzinfo=timezone.utc)


def parse_time(text):
    text = text.strip().replace("Z", "+00:00")
    try:
        t = datetime.fromisoformat(text)
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def haversine(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def local(tag):
    return tag.rsplit("}", 1)[-1]


def num(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- readers
# Each reader returns a list of samples: dicts with keys t (datetime), and any of
# lat, lon, ele (m), dist (m, cumulative), hr (bpm), power (W), cad (rpm).

def read_gpx(path):
    samples = []
    for pt in ET.parse(path).getroot().iter():
        if local(pt.tag) != "trkpt":
            continue
        s = {"lat": num(pt.get("lat")), "lon": num(pt.get("lon"))}
        for el in pt.iter():
            name, val = local(el.tag), (el.text or "").strip()
            if name == "time":
                s["t"] = parse_time(val)
            elif name == "ele":
                s["ele"] = num(val)
            elif name == "hr":
                s["hr"] = num(val)
            elif name in ("cad", "cadence"):
                s["cad"] = num(val)
            elif name in ("power", "PowerInWatts", "watts"):
                s["power"] = num(val)
        samples.append(s)
    return samples


def read_tcx(path):
    samples = []
    for tp in ET.parse(path).getroot().iter():
        if local(tp.tag) != "Trackpoint":
            continue
        s = {}
        for el in tp.iter():
            name, val = local(el.tag), (el.text or "").strip()
            if name == "Time":
                s["t"] = parse_time(val)
            elif name == "LatitudeDegrees":
                s["lat"] = num(val)
            elif name == "LongitudeDegrees":
                s["lon"] = num(val)
            elif name == "AltitudeMeters":
                s["ele"] = num(val)
            elif name == "DistanceMeters":
                s["dist"] = num(val)
            elif name == "Value" and local(el.tag) == "Value" and "hr" not in s:
                s["hr"] = num(val)  # HeartRateBpm/Value is the only Value element in a trackpoint
            elif name == "Cadence":
                s["cad"] = num(val)
            elif name == "Watts":
                s["power"] = num(val)
        samples.append(s)
    return samples


CSV_COLUMNS = {
    "t": ("time", "timestamp", "date_time", "datetime"),
    "dist": ("distance", "distance_m", "dist"),
    "hr": ("heart_rate", "heartrate", "hr", "bpm"),
    "power": ("power", "watts"),
    "ele": ("altitude", "elevation", "ele", "enhanced_altitude"),
    "cad": ("cadence", "cad"),
    "lat": ("lat", "latitude", "position_lat"),
    "lon": ("lon", "lng", "longitude", "position_long"),
}


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return []
    keys = {k.strip().lower(): k for k in rows[0]}
    col = {field: next((keys[n] for n in names if n in keys), None) for field, names in CSV_COLUMNS.items()}
    if not col["t"]:
        sys.exit("CSV has no time/timestamp column; this script needs one row per sample. "
                 f"Columns found: {', '.join(rows[0])}")
    samples = []
    start = None
    for r in rows:
        raw_t = r[col["t"]].strip()
        t = parse_time(raw_t)
        if t is None and num(raw_t) is not None:  # seconds since start
            start = start or datetime(2000, 1, 1, tzinfo=timezone.utc)
            t = start + timedelta(seconds=float(raw_t))
        s = {"t": t}
        for field, name in col.items():
            if field != "t" and name:
                s[field] = num(r[name])
        samples.append(s)
    return samples


FIT_TYPES = {0x00: ("B", 0xFF), 0x01: ("b", 0x7F), 0x02: ("B", 0xFF), 0x83: ("h", 0x7FFF),
             0x84: ("H", 0xFFFF), 0x85: ("i", 0x7FFFFFFF), 0x86: ("I", 0xFFFFFFFF), 0x88: ("f", None),
             0x89: ("d", None), 0x0A: ("B", 0), 0x8B: ("H", 0), 0x8C: ("I", 0), 0x8E: ("q", None),
             0x8F: ("Q", None), 0x90: ("Q", 0)}
RECORD, SESSION = 20, 18


def read_fit(path):
    data = Path(path).read_bytes()
    header_size = data[0]
    if data[8:12] != b".FIT":
        sys.exit("not a FIT file (missing .FIT signature)")
    end = header_size + struct.unpack("<I", data[4:8])[0]
    pos, defs, last_ts, samples, session = header_size, {}, None, [], {}
    while pos < end:
        h = data[pos]
        pos += 1
        if h & 0x80:  # compressed timestamp header
            local_type, offset = (h >> 5) & 0x3, h & 0x1F
            if last_ts is not None:
                ts = (last_ts & ~0x1F) + offset + (0x20 if offset < (last_ts & 0x1F) else 0)
                last_ts = ts
            is_def, dev = False, False
        else:
            local_type, is_def, dev = h & 0x0F, bool(h & 0x40), bool(h & 0x20)
        if is_def:
            arch = "<" if data[pos + 1] == 0 else ">"
            gnum = struct.unpack(arch + "H", data[pos + 2:pos + 4])[0]
            n = data[pos + 4]
            pos += 5
            fields = [tuple(data[pos + 3 * i:pos + 3 * i + 3]) for i in range(n)]
            pos += 3 * n
            dev_size = 0
            if dev:
                nd = data[pos]
                pos += 1
                dev_size = sum(data[pos + 3 * i + 1] for i in range(nd))
                pos += 3 * nd
            defs[local_type] = (arch, gnum, fields, dev_size)
            continue
        if local_type not in defs:
            sys.exit(f"FIT data message before its definition at byte {pos}; export GPX or TCX instead")
        arch, gnum, fields, dev_size = defs[local_type]
        values = {}
        for fnum, size, btype in fields:
            raw = data[pos:pos + size]
            pos += size
            fmt, invalid = FIT_TYPES.get(btype, (None, None))
            if fmt and struct.calcsize(fmt) == size:
                v = struct.unpack(arch + fmt, raw)[0]
                if v != invalid:
                    values[fnum] = v
        pos += dev_size
        if 253 in values:
            last_ts = values[253]
        elif h & 0x80 and last_ts is not None:
            values[253] = last_ts
        if gnum == RECORD and 253 in values:
            s = {"t": FIT_EPOCH + timedelta(seconds=values[253])}
            if 0 in values and 1 in values:
                s["lat"], s["lon"] = values[0] * 180 / 2 ** 31, values[1] * 180 / 2 ** 31
            alt = values.get(78, values.get(2))
            if alt is not None:
                s["ele"] = alt / 5 - 500
            if 5 in values:
                s["dist"] = values[5] / 100
            for fnum, key in ((3, "hr"), (7, "power"), (4, "cad")):
                if fnum in values:
                    s[key] = values[fnum]
            samples.append(s)
        elif gnum == SESSION:
            session = values
    if not samples and session:
        print("FIT file has no record samples; showing session totals only.")
    return samples


READERS = {".gpx": read_gpx, ".tcx": read_tcx, ".csv": read_csv, ".fit": read_fit}


# ---------------------------------------------------------------- summary

def summarise(samples, zones=None, splits=False):
    samples = [s for s in samples if s.get("t")]
    samples.sort(key=lambda s: s["t"])
    if len(samples) < 2:
        sys.exit("fewer than 2 timed samples; nothing to summarise")
    # cumulative distance: use recorded distance, else GPS
    if not any(s.get("dist") is not None for s in samples):
        total, prev = 0.0, None
        for s in samples:
            if s.get("lat") is not None and s.get("lon") is not None:
                if prev:
                    total += haversine(prev, (s["lat"], s["lon"]))
                prev = (s["lat"], s["lon"])
            s["dist"] = total if prev else None
    out = {"start": samples[0]["t"].isoformat(), "elapsed_min": round((samples[-1]["t"] - samples[0]["t"]).total_seconds() / 60, 1)}
    dists = [s["dist"] for s in samples if s.get("dist") is not None]
    if dists:
        out["distance_km"] = round((max(dists) - min(dists)) / 1000, 2)
    moving = 0.0
    for a, b in zip(samples, samples[1:]):
        dt = (b["t"] - a["t"]).total_seconds()
        if a.get("dist") is not None and b.get("dist") is not None and dt > 0:
            if (b["dist"] - a["dist"]) / dt > 0.5:  # faster than 0.5 m/s counts as moving
                moving += dt
        elif dt <= 10:
            moving += dt
    out["moving_min"] = round(moving / 60, 1)
    if out.get("distance_km") and moving:
        pace = moving / out["distance_km"]
        out["avg_pace_min_per_km"] = f"{int(pace // 60)}:{int(pace % 60):02d}"
        out["avg_speed_kmh"] = round(out["distance_km"] / (moving / 3600), 1)
    eles = [s["ele"] for s in samples if s.get("ele") is not None]
    if eles:
        gain = loss = 0.0
        for a, b in zip(eles, eles[1:]):
            d = b - a
            gain, loss = gain + max(d, 0), loss + max(-d, 0)
        out["elevation_gain_m"], out["elevation_loss_m"] = round(gain), round(loss)
    for key, label in (("hr", "hr"), ("power", "power"), ("cad", "cadence")):
        vals = [s[key] for s in samples if s.get(key)]
        if vals:
            out[f"avg_{label}"], out[f"max_{label}"] = round(sum(vals) / len(vals)), round(max(vals))
    if zones:
        limits = sorted(zones)
        secs = [0.0] * (len(limits) + 1)
        for a, b in zip(samples, samples[1:]):
            dt = (b["t"] - a["t"]).total_seconds()
            if a.get("hr") and 0 < dt <= 30:
                secs[sum(a["hr"] > z for z in limits)] += dt
        total = sum(secs) or 1
        out["hr_zones"] = {f"Z{i + 1} ({'<=' + str(limits[i]) if i < len(limits) else '>' + str(limits[-1])} bpm)":
                           f"{round(sec / 60, 1)} min ({round(100 * sec / total)}%)" for i, sec in enumerate(secs)}
        # first half vs second half average HR, a rough check for cardiac drift
        hr = [s["hr"] for s in samples if s.get("hr")]
        if len(hr) > 20:
            out["avg_hr_first_half"], out["avg_hr_second_half"] = round(sum(hr[:len(hr) // 2]) / (len(hr) // 2)), \
                round(sum(hr[len(hr) // 2:]) / (len(hr) - len(hr) // 2))
    if splits and dists:
        rows, next_km, t0 = [], 1000.0, samples[0]["t"]
        base = min(dists)
        for s in samples:
            if s.get("dist") is not None and s["dist"] - base >= next_km:
                sec = (s["t"] - t0).total_seconds()
                rows.append(f"km {int(next_km / 1000)}: {int(sec // 60)}:{int(sec % 60):02d}")
                t0, next_km = s["t"], next_km + 1000
        out["splits"] = rows
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--zones", help="comma-separated HR upper limits, e.g. 130,150,165")
    ap.add_argument("--splits", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    ext = Path(a.file).suffix.lower()
    if ext not in READERS:
        sys.exit(f"unsupported file type {ext}; use GPX, TCX, CSV or FIT")
    zones = [int(z) for z in a.zones.split(",")] if a.zones else None
    out = summarise(READERS[ext](a.file), zones, a.splits)
    if a.json:
        print(json.dumps(out, indent=2))
        return
    for k, v in out.items():
        if isinstance(v, dict):
            print(f"{k}:")
            for kk, vv in v.items():
                print(f"  {kk}: {vv}")
        elif isinstance(v, list):
            print(f"{k}: " + "; ".join(v))
        else:
            print(f"{k}: {v}")
    print("note: computed from the file by this script; wrist heart rate and GPS distance have measurement error.")


if __name__ == "__main__":
    main()
