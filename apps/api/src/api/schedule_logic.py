# ruff: noqa: ANN201, BLE001
import zoneinfo
from datetime import datetime

from wrangler.schedule_data import CONFERENCE_DATA


def get_next_session():
    # PyTexas is in Dallas (Central Time)
    try:
        tz = zoneinfo.ZoneInfo("America/Chicago")
    except Exception:
        tz = None

    now = datetime.now(tz)

    # Format for matching
    today_str = now.strftime("%Y-%m-%d")
    current_time_str = now.strftime("%H:%M")

    if today_str not in CONFERENCE_DATA:
        # Check if conference is in the future
        first_day = sorted(CONFERENCE_DATA.keys())[0]
        if today_str < first_day:
            return None, f"The conference hasn't started yet! First session is on {first_day}."
        return None, "There are no sessions scheduled for today!"

    todays_talks = CONFERENCE_DATA[today_str]
    sorted_times = sorted(todays_talks.keys())

    for start_time in sorted_times:
        if start_time > current_time_str:
            return todays_talks[start_time], start_time

    return None, "All sessions for today have concluded. See you tomorrow!"


def get_current_session():
    # Helper to find what's happening RIGHT NOW
    try:
        tz = zoneinfo.ZoneInfo("America/Chicago")
    except Exception:
        tz = None

    now = datetime.now(tz)
    today_str = now.strftime("%Y-%m-%d")
    current_time_str = now.strftime("%H:%M")

    if today_str not in CONFERENCE_DATA:
        return None

    todays_talks = CONFERENCE_DATA[today_str]
    sorted_times = sorted(todays_talks.keys())

    current = None
    for _i, start_time in enumerate(sorted_times):
        if start_time <= current_time_str:
            current = (todays_talks[start_time], start_time)
        else:
            break

    return current
