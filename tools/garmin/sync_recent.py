#!/usr/bin/env python3
"""Sync the last 7 days (activities, FIT files, daily summary, sleep, HRV) into
athletes/<alias>/garmin/ and rebuild the CSV files. Meant to run twice a day.

Daily files are overwritten (Garmin revises recent days); FIT files are only
downloaded when missing.

  python3 tools/garmin/sync_recent.py --athlete <alias> [--days 7]
"""
import argparse
import datetime as dt

import garmin_api as g


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--athlete", required=True, help="alias: data goes to athletes/<alias>/garmin/")
    ap.add_argument("--days", type=int, default=7)
    args = ap.parse_args()
    today = dt.date.today()
    start = today - dt.timedelta(days=args.days - 1)
    g.use_athlete(args.athlete)
    client = g.Client()
    g.fetch_activities(client, start=start, end=today)
    g.fetch_daily(client, start, today)
    g.rebuild_csv()


if __name__ == "__main__":
    g.run(main)
