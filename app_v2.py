"""
Club Buddy Finder -- Sign-Up Form
-----------------------------------
A sign-up form where verified club members log their sport, real
availability across the next 3 weeks (actual dates, hourly slots
matching real club hours), and openness to being matched.

NOTE ON TIMETABLE SYNC: the previous .ics university-timetable sync
feature has been removed in this version, since it produced broad
"Morning/Afternoon/Evening" availability that no longer matches the
new real-date, hourly, club-hours-specific grid. It could be rebuilt
to work with this new format as a future step, but that's a separate
piece of work from this calendar redesign.

Requirements:
    pip install streamlit

Run locally:
    streamlit run app_v2.py
"""

import streamlit as st
from datetime import datetime
from storage import load_signups, save_signup
from calendar_utils import get_upcoming_dates, TIME_SLOTS

# ---- Membership verification ----
VALID_MEMBERSHIP_NUMBERS = {
    "TTC001", "TTC002", "TTC003", "TTC004", "TTC005",
    "TTC006", "TTC007", "TTC008", "TTC009", "TTC010",
    "TTC011", "TTC012", "TTC013", "TTC014", "TTC015",
}

SPORTS = ["Tennis", "Swimming", "Gym"]

# Under 18 removed entirely -- matching minors with strangers sits in
# a genuinely different legal/safeguarding landscape, and this
# platform isn't set up to handle that responsibly.
AGE_BRACKETS = ["18-29", "30-39", "40-49", "50-59", "60-69", "70+"]

SLOT_LABELS = [s["label"] for s in TIME_SLOTS]


# ---- Page setup ----
st.set_page_config(page_title="Club Buddy Finder", page_icon="🎾", layout="wide")
st.title("🎾 Club Buddy Finder")
st.write(
    "New to the club? Tick your free times below across the next 3 "
    "weeks, and we'll let you know by email when you're matched with "
    "someone free at the same time -- or someone close, with a "
    "suggestion for how to align."
)

# ---- The sign-up form ----
with st.form("signup_form", clear_on_submit=True):
    name = st.text_input("Your first name")
    membership_number = st.text_input("Membership number")
    email = st.text_input("Your email")
    sport = st.selectbox("Which sport?", SPORTS)
    age_bracket = st.selectbox("Your age group", AGE_BRACKETS)
    prefer_similar_age = st.checkbox(
        "I'd prefer to be matched with someone around my own age group"
    )

    st.write("**Tick your free times below, for each of the next 3 weeks:**")
    st.caption(f"Club hours: {SLOT_LABELS[0].split('-')[0]} - {SLOT_LABELS[-1].split('-')[1]}")

    available_slots = []
    dates_by_week = {1: [], 2: [], 3: []}
    for week_num, date in get_upcoming_dates(3):
        dates_by_week[week_num].append(date)

    week_labels = {
        w: f"Week {w} ({dates[0].strftime('%d %b')} - {dates[-1].strftime('%d %b')})"
        for w, dates in dates_by_week.items()
    }

    tabs = st.tabs([week_labels[1], week_labels[2], week_labels[3]])

    for week_num, tab in zip([1, 2, 3], tabs):
        with tab:
            # Header row: a blank corner, then one column per hourly slot.
            header_cols = st.columns([1.4] + [1] * len(SLOT_LABELS))
            header_cols[0].markdown("&nbsp;", unsafe_allow_html=True)
            for i, slot_label in enumerate(SLOT_LABELS):
                header_cols[i + 1].markdown(f"**{slot_label}**")

            # One row per DATE now (not per time slot) -- dates down
            # the side, hours across the top, matching what was asked
            # for: a real calendar layout, not repeating day names.
            for date in dates_by_week[week_num]:
                row_cols = st.columns([1.4] + [1] * len(SLOT_LABELS))
                row_cols[0].markdown(f"**{date.strftime('%a %d %b')}**")

                for i, slot in enumerate(TIME_SLOTS):
                    checked = row_cols[i + 1].checkbox(
                        "", value=False,
                        key=f"grid_{date.isoformat()}_{slot['label']}",
                        label_visibility="collapsed",
                    )
                    if checked:
                        available_slots.append({
                            "date": date.isoformat(),
                            "time_slot": slot["label"],
                        })

    open_to_match = st.checkbox(
        "I'm a newcomer and open to being matched with someone new",
        value=True,
    )

    submitted = st.form_submit_button("Submit")

    if submitted:
        if not name or not membership_number or not email:
            st.error("Please fill in your name, membership number, and email.")
        elif membership_number not in VALID_MEMBERSHIP_NUMBERS:
            st.error(
                "We couldn't verify that membership number. Please double "
                "check it, or contact the club admin if you believe this "
                "is an error."
            )
        elif membership_number in {s["membership_number"] for s in load_signups()}:
            st.error(
                "This membership number has already been used to sign up. "
                "If you need to update your availability, please contact "
                "the club admin."
            )
        elif not available_slots:
            st.error("Please select at least one free time slot.")
        else:
            entry = {
                "name": name,
                "membership_number": membership_number,
                "email": email,
                "sport": sport,
                "age_bracket": age_bracket,
                "prefer_similar_age": prefer_similar_age,
                "available_slots": available_slots,
                "open_to_match": open_to_match,
                "submitted_at": datetime.now().isoformat(),
            }
            save_signup(entry)

            slots_summary = ", ".join(f"{s['date']} {s['time_slot']}" for s in available_slots[:3])
            more_text = f" (+{len(available_slots) - 3} more)" if len(available_slots) > 3 else ""
            st.success(
                f"Thanks {name}! You're logged in for {sport}: "
                f"{slots_summary}{more_text}. We'll email you at {email} "
                f"if a match comes up."
            )

# ---- A simple admin-style view, for testing ----
with st.expander("View current sign-ups (testing only)"):
    signups = load_signups()
    if signups:
        st.write(f"{len(signups)} sign-up(s) so far:")
        st.json(signups)
    else:
        st.write("No sign-ups yet.")
