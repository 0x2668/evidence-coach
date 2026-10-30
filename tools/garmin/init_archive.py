#!/usr/bin/env python3
"""One-off: download the whole Garmin Connect archive (activities with FIT files,
daily summaries, sleep, HRV) into athletes/<alias>/garmin/.

Safe to re-run: activity FIT files that already exist are skipped, daily files
are overwritten with the same data. On an API error it stops (no retry loop);
just run it again.

  python3 tools/garmin/init_archive.py --athlete <alias> [--since 2024-01-01]
"""
import argparse
import datetime as dt

import garmin_api as g


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--athlete", required=True, help="alias: data goes to athletes/<alias>/garmin/")
    ap.add_argument("--since", default="2024-01-01", type=dt.date.fromisoformat,
                    help="first day to request for daily data (empty days are skipped)")
    args = ap.parse_args()
    g.use_athlete(args.athlete)
    client = g.Client()
    g.fetch_activities(client)
    g.fetch_daily(client, args.since, dt.date.today())
    g.rebuild_csv()


if __name__ == "__main__":
    g.run(main)
