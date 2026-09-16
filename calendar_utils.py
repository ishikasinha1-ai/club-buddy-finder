"""
Calendar Utilities
---------------------
Generates the real dates for the upcoming 3 weeks, and hourly time
slots based on actual club opening/closing hours -- replacing the
old repeating "Monday/Tuesday" model with genuine specific dates.
"""

from datetime import datetime, timedelta, time

CLUB_OPEN = time(15, 30)   # 3:30pm
CLUB_CLOSE = time(22, 0)   # 10:00pm


def get_upcoming_dates(num_weeks=3):
    """
    Returns a list of (week_number, date) tuples covering today through
    the end of the specified number of weeks -- genuine calendar dates,
    not repeating day names.
    """
    today = datetime.now().date()
    dates = []
    for day_offset in range(num_weeks * 7):
        date = today + timedelta(days=day_offset)
        week_number = (day_offset // 7) + 1
        dates.append((week_number, date))
    return dates


def generate_hourly_slots(open_time=CLUB_OPEN, close_time=CLUB_CLOSE):
    """
    Builds hourly slots from opening to closing -- e.g. "3:30pm-4:30pm",
    "4:30pm-5:30pm", etc. Only includes a slot if it fully fits before
    closing time, so a 6.5-hour window (3:30-10pm) correctly produces 6
    full hourly slots, not a partial 7th one.
    """
    slots = []
    current_start = datetime.combine(datetime.today(), open_time)
    close_datetime = datetime.combine(datetime.today(), close_time)

    while current_start + timedelta(hours=1) <= close_datetime:
        current_end = current_start + timedelta(hours=1)
        label = f"{current_start.strftime('%-I:%M%p')}-{current_end.strftime('%-I:%M%p')}".lower()
        slots.append({
            "label": label,
            "start_minutes": current_start.hour * 60 + current_start.minute,
            "end_minutes": current_end.hour * 60 + current_end.minute,
        })
        current_start = current_end

    return slots


TIME_SLOTS = generate_hourly_slots()
