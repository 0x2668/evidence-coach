# Garmin data

Downloads your Garmin Connect data to `athletes/<alias>/garmin/`, which is excluded from git. Use an alias, not a full name. Run the commands from the root of a clone of this repository: `npx skills` does not install these scripts.

```
athletes/<alias>/garmin/
  daily.csv                 one row per day: steps, resting HR, stress, Body Battery, sleep, HRV
  activities.csv            one row per activity: type, distance, duration, HR, load, time in HR zones
  raw/                      API responses (daily/, activities/) and original activity files (fit/, zipped)
```

The scripts use Garmin's official [Personal API](https://developer.garmin.com/gc-developer-program/personal/personal-api/), which gives you read-only access to your own data. They need only the Python standard library.

1. In Garmin Connect on the web, open the Personal API Key page, select Create Key, accept the terms and choose an expiry period. The key is shown only once.
2. Save the key outside the repository, and don't paste it into a chat with the coach. To keep it out of your shell history, paste it at the prompt of this command:

   ```bash
   mkdir -p ~/.config/garmin && (umask 077; read -rs -p "Garmin API key: " k && printf '%s' "$k" > ~/.config/garmin/api_key)
   ```

   For a second athlete, keep a separate key file and set `GARMIN_API_KEY_FILE` to its path when running the scripts.
3. Download the archive once. You can re-run it if it stops: existing FIT files are skipped.

   ```bash
   python3 tools/garmin/init_archive.py --athlete <alias>                       # daily data from 2024-01-01
   python3 tools/garmin/init_archive.py --athlete <alias> --since 2020-01-01    # further back
   ```

4. Sync the last 7 days whenever you like, or on a schedule (twice a day is plenty):

   ```bash
   python3 tools/garmin/sync_recent.py --athlete <alias>
   ```

   With cron on Linux or macOS (use the absolute path of your clone):

   ```
   0 7,20 * * * python3 /path/to/evidence-coach/tools/garmin/sync_recent.py --athlete <alias>
   ```

   On Windows with WSL, cron runs only while WSL is running, so use Task Scheduler. Run this once per time of day in PowerShell:

   ```
   schtasks /Create /TN "GarminSync-0700" /SC DAILY /ST 07:00 /TR "wsl.exe python3 /path/to/evidence-coach/tools/garmin/sync_recent.py --athlete <alias>"
   ```

5. Tell the coach your alias, for example "my data is in athletes/<alias>/garmin".

On an API error the scripts stop with a message instead of retrying, so run them again later. A token error usually means the key has expired: create a new one and overwrite the key file.
