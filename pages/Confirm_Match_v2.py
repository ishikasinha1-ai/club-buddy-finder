"""
Confirm Meetup
----------------
This is where the personal link in each match email leads. No login
is needed -- the link itself contains a match_id and which person
("a" or "b") is viewing it, which is enough to safely show only THEIR
side of the exchange.

This is intentionally NOT an open-ended chat. Following the safety
principles from earlier (no direct contact details shared, structured
rather than freeform), this only lets someone:
  - Accept the currently proposed day/time, or
  - Suggest a different one from the SAME shared availability pool
    already calculated during matching (not any day/time they like)

HOW THE LINK WORKS:
A URL like ?match_id=abc123&person=a is read using st.query_params --
Streamlit's way of reading values from the page's own URL, similar to
how a website might read search terms from its address bar.
"""

import streamlit as st
from storage import get_match_by_id, update_match

st.set_page_config(page_title="Confirm Meetup", page_icon="🤝")
st.title("🤝 Confirm Meetup")

# ---- Read who's viewing this page, from the URL itself ----
match_id = st.query_params.get("match_id")
person = st.query_params.get("person")  # "a" or "b"

if not match_id or person not in ("a", "b"):
    st.error(
        "This link looks incomplete or invalid. Please use the link "
        "from your match email directly."
    )
    st.stop()

match = get_match_by_id(match_id)

if not match:
    st.error("We couldn't find this match. It may have been removed.")
    st.stop()

# ---- Work out who's who, based on the link ----
if person == "a":
    my_name = match["person_a"]
    other_name = match["person_b"]
    my_status_key = "person_a_status"
    other_status_key = "person_b_status"
else:
    my_name = match["person_b"]
    other_name = match["person_a"]
    my_status_key = "person_b_status"
    other_status_key = "person_a_status"

my_status = match[my_status_key]
other_status = match[other_status_key]

st.write(f"Hi **{my_name}**! You're matched with **{other_name}** for **{match['sport']}**.")
st.write(f"**Proposed:** {match['proposed_date']} ({match['proposed_time']})")

if other_status == "accepted":
    st.info(f"{other_name} has already accepted this time.")
elif other_status.startswith("suggested:"):
    st.info(f"{other_name} suggested a different time -- see options below.")

st.divider()

# ---- Accept the currently proposed time ----
if st.button("✅ Accept this time"):
    update_match(match_id, {my_status_key: "accepted"})
    st.success("You've confirmed this time. See you at the club!")
    st.rerun()

st.write("Or, if this time doesn't work:")

# ---- Suggest a different time, but ONLY from genuinely shared pairs ----
# This is what keeps this "structured" rather than open-ended. IMPORTANT:
# this is a SINGLE dropdown of real (day, time) pairs, not two separate
# day/time dropdowns -- two independent dropdowns could combine into a
# pair that was never actually free for both people (the same bug fixed
# in matching_logic.py's overlap detection).
slot_options = [f"{date} - {time_slot}" for date, time_slot in match["overlapping_slots"]]
chosen_slot = st.selectbox("Suggest a different time instead", slot_options)

if st.button("Suggest this instead"):
    alt_date, alt_time = chosen_slot.split(" - ", 1)
    update_match(match_id, {
        my_status_key: f"suggested:{alt_date},{alt_time}",
        "proposed_date": alt_date,
        "proposed_time": alt_time,
    })
    st.success(f"Suggested {alt_date} ({alt_time}) to {other_name}.")
    st.rerun()
