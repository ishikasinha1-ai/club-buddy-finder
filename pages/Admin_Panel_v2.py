"""
Admin: Matches
----------------
This is a SECOND PAGE of the Streamlit app -- Streamlit automatically
turns any .py file inside a "pages" folder into a navigable page, with
a sidebar link added for you. No extra setup needed beyond the folder
placement.

This page reuses the exact same functions from matching_engine_v2.py --
we import them instead of copy-pasting, so there's only ever one real
version of the matching logic to maintain.

IMPORTANT: this file must sit inside a folder called "pages", which
itself sits next to app_v2.py and matching_engine_v2.py. Example:

    your_folder/
        app_v2.py
        matching_engine_v2.py
        pages/
            Admin_Panel_v2.py   <-- this file
"""

import streamlit as st
from matching_engine_v2 import (
    load_signups, find_matches, send_match_emails, get_credential,
    find_near_misses, load_near_misses, save_near_misses, send_near_miss_email,
)
from storage import load_matches, save_matches

st.set_page_config(page_title="Admin: Matches", page_icon="🔗")
st.title("🔗 Admin: Matches")

# ---- Password gate ----
# Anyone with the app's link could otherwise open this page and see
# everyone's data, or trigger real emails. This blocks the rest of the
# page from showing until the correct admin password is entered.
ADMIN_PASSWORD = get_credential("ADMIN_PASSWORD")

if "admin_authenticated" not in st.session_state:
    st.session_state.admin_authenticated = False

if not st.session_state.admin_authenticated:
    entered_password = st.text_input("Admin password", type="password")
    if st.button("Log in"):
        if ADMIN_PASSWORD and entered_password == ADMIN_PASSWORD:
            st.session_state.admin_authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    # st.stop() halts the script here -- nothing below this line runs
    # until admin_authenticated becomes True, so the rest of the page
    # (sign-up data, matching, emails) stays hidden until then.
    st.stop()

signups = load_signups()
st.write(f"**{len(signups)}** sign-up(s) currently on file.")

with st.expander("View raw sign-ups"):
    if signups:
        st.json(signups)
    else:
        st.write("No sign-ups yet.")

st.divider()

# Button to run the matching logic and show results on the page,
# instead of only printing to a terminal. This is now BATCH-SAFE --
# people stay in the pool with standing availability, and re-clicking
# this only finds genuinely NEW matches, never re-matching the same
# two people with each other again.
if st.button("Find new matches"):
    existing_matches = load_matches()
    new_matches = find_matches(signups, existing_matches=existing_matches)
    save_matches(existing_matches + new_matches)
    # Store in session_state so the results stick around even after
    # the page reruns from other button clicks below.
    st.session_state["matches"] = new_matches

# Display whatever NEW matches were last found (persists across
# reruns thanks to session_state, covered earlier).
matches = st.session_state.get("matches", [])

if matches:
    st.success(f"Found {len(matches)} new match(es):")
    for m in matches:
        slots_text = ", ".join(f"{day} {time_slot}" for day, time_slot in m["overlapping_slots"])
        st.write(
            f"**{m['person_a']}** + **{m['person_b']}** -- {m['sport']}, "
            f"genuinely free: {slots_text}"
        )

    st.divider()

    # Emailing is a separate, deliberate action -- not automatic --
    # since sending real emails shouldn't happen accidentally just
    # from viewing the page.
    if st.button("Send match emails to everyone above"):
        for m in matches:
            try:
                send_match_emails(m)
                st.success(f"Emailed {m['person_a']} and {m['person_b']}.")
            except Exception as e:
                st.error(
                    f"Failed to email {m['person_a']} and {m['person_b']}: {e}"
                )
else:
    st.info("No new matches found yet. Click 'Find new matches' above to check.")

st.divider()

with st.expander("View all match history"):
    all_matches = load_matches()
    if all_matches:
        st.write(f"{len(all_matches)} total match(es) on record:")
        st.json(all_matches)
    else:
        st.write("No matches yet.")

st.divider()
st.header("🤝 Near-Miss Suggestions")
st.caption(
    "Pairs who don't have an exact overlap, but whose free slots are "
    "within 30 minutes of each other on the same date -- the AI writes "
    "a genuine suggestion for how they might align."
)

if st.button("Find near-miss suggestions"):
    existing_matches = load_matches()
    existing_near_misses = load_near_misses()
    with st.spinner("Checking for near-misses and asking the AI to suggest alignments..."):
        new_near_misses = find_near_misses(signups, existing_matches, existing_near_misses)
    save_near_misses(existing_near_misses + new_near_misses)
    st.session_state["near_misses"] = new_near_misses

near_misses = st.session_state.get("near_misses", [])

if near_misses:
    st.success(f"Found {len(near_misses)} new near-miss suggestion(s):")
    for nm in near_misses:
        with st.container(border=True):
            st.write(f"**{nm['person_a']}** + **{nm['person_b']}** -- {nm['sport']}, {nm['date']}")
            st.write(f"{nm['person_a']}: {nm['person_a_slot']} | {nm['person_b']}: {nm['person_b_slot']}")
            st.info(nm["ai_suggestion"])

    if st.button("Send near-miss suggestion emails"):
        for nm in near_misses:
            try:
                send_near_miss_email(nm)
                st.success(f"Emailed {nm['person_a']} and {nm['person_b']}.")
            except Exception as e:
                st.error(f"Failed to email {nm['person_a']} and {nm['person_b']}: {e}")
else:
    st.info("No new near-miss suggestions found yet. Click the button above to check.")
