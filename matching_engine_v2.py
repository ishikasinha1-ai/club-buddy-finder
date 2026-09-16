"""
Club Buddy Finder -- Matching Logic
--------------------------------------
Finds pairs of people who: play the same sport, share at least one
GENUINE (same real date + same hour) free slot, and are both open to
being matched. Also finds NEAR-MISSES -- pairs whose free slots are on
the same date but immediately adjacent (within 30 minutes of each
other) -- and uses the AI to write a genuine, reasoned suggestion for
how they might align, rather than silently missing a near-match.

STORAGE: local JSON files (via storage.py).

EMAIL SETUP (Gmail) -- LOCAL (your laptop):
    setx GMAIL_ADDRESS "youremail@gmail.com"
    setx GMAIL_APP_PASSWORD "your16digitapppassword"
    (then open a NEW PowerShell window)

Run:
    python matching_engine_v2.py
"""

import os
import json
import smtplib
import uuid
import anthropic
from email.message import EmailMessage
from storage import load_signups, save_matches
from calendar_utils import TIME_SLOTS

# Under 18 removed entirely -- matching minors with strangers sits in
# a genuinely different legal/safeguarding landscape, and isn't
# something this platform is set up to handle responsibly.
AGE_BRACKETS = ["18-29", "30-39", "40-49", "50-59", "60-69", "70+"]

NEAR_MISS_FILE = "near_misses.json"
NEAR_MISS_PROXIMITY_MINUTES = 30

client = anthropic.Anthropic()
MODEL = "claude-sonnet-4-6"


def get_credential(key):
    """
    Looks for a credential in TWO places, in order:
      1. Environment variables (set via setx) -- local laptop use
      2. Streamlit secrets -- once deployed to Streamlit Community Cloud
    """
    value = os.environ.get(key)
    if value:
        return value
    try:
        import streamlit as st
        return st.secrets.get(key)
    except Exception:
        return None


GMAIL_ADDRESS = get_credential("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = get_credential("GMAIL_APP_PASSWORD")
APP_BASE_URL = get_credential("APP_BASE_URL")


def get_slot_lookup():
    """Maps a time slot's label (e.g. '5:30pm-6:30pm') to its real
    start/end minutes, so we can measure how close two different
    slots actually are to each other."""
    return {s["label"]: s for s in TIME_SLOTS}


def get_overlapping_slots(person_a, person_b):
    """
    Returns the genuine (date, time_slot) pairs both people are free
    at the SAME time -- exact matches only. Uses real dates now, not
    repeating day names.
    """
    slots_a = {(s["date"], s["time_slot"]) for s in person_a["available_slots"]}
    slots_b = {(s["date"], s["time_slot"]) for s in person_b["available_slots"]}
    return list(slots_a & slots_b)


def find_near_miss_slot_pairs(person_a, person_b):
    """
    THE NEW FEATURE: finds slots on the SAME DATE that don't exactly
    overlap, but are close -- one person's slot ends within 30 minutes
    of the other's starting, in either direction. Returns a list of
    (date, slot_a_label, slot_b_label) near-misses.
    """
    slot_lookup = get_slot_lookup()
    near_misses = []

    for sa in person_a["available_slots"]:
        for sb in person_b["available_slots"]:
            if sa["date"] != sb["date"]:
                continue
            if sa["time_slot"] == sb["time_slot"]:
                continue  # exact match, handled separately

            info_a = slot_lookup.get(sa["time_slot"])
            info_b = slot_lookup.get(sb["time_slot"])
            if not info_a or not info_b:
                continue

            # Gap if A comes before B, or B comes before A -- whichever
            # is actually the case (the other will be negative/irrelevant).
            gap_a_then_b = info_b["start_minutes"] - info_a["end_minutes"]
            gap_b_then_a = info_a["start_minutes"] - info_b["end_minutes"]
            gap = gap_a_then_b if gap_a_then_b >= 0 else gap_b_then_a

            if 0 <= gap <= NEAR_MISS_PROXIMITY_MINUTES:
                near_misses.append((sa["date"], sa["time_slot"], sb["time_slot"]))

    return near_misses


def generate_reschedule_suggestion(person_a_name, person_b_name, date, slot_a, slot_b):
    """
    THE AGENTIC PART: rather than a hardcoded template, asks Claude to
    genuinely reason about and phrase a helpful, friendly suggestion
    for how two near-miss availabilities could be aligned.
    """
    prompt = (
        f"{person_a_name} is free on {date} during {slot_a}, and "
        f"{person_b_name} is free the same day during {slot_b} -- these "
        f"slots are close together but don't quite overlap. Write a "
        f"short (1-2 sentence), friendly suggestion for how they might "
        f"align their schedules to meet up, addressed to both of them "
        f"together. Keep it practical and specific to the actual times "
        f"given."
    )
    response = client.messages.create(
        model=MODEL, max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in response.content if b.type == "text")


def ages_are_compatible(person_a, person_b):
    """A SOFT preference: only restricts matching if either person
    asked for it, and even then allows an adjacent age bracket."""
    wants_similar_age = person_a["prefer_similar_age"] or person_b["prefer_similar_age"]
    if not wants_similar_age:
        return True
    try:
        index_a = AGE_BRACKETS.index(person_a["age_bracket"])
        index_b = AGE_BRACKETS.index(person_b["age_bracket"])
    except ValueError:
        return True
    return abs(index_a - index_b) <= 1


def get_existing_matched_pairs(existing_matches):
    pairs = set()
    for m in existing_matches:
        pair = frozenset([m["person_a_membership"], m["person_b_membership"]])
        pairs.add(pair)
    return pairs


def load_near_misses():
    if not os.path.exists(NEAR_MISS_FILE):
        return []
    with open(NEAR_MISS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_near_misses(near_misses):
    with open(NEAR_MISS_FILE, "w", encoding="utf-8") as f:
        json.dump(near_misses, f, indent=2)


def find_matches(signups, existing_matches=None):
    """
    Finds NEW exact matches -- same sport, both open to matching,
    age-compatible, and sharing at least one genuine (date, time) pair,
    not already matched before.
    """
    if existing_matches is None:
        existing_matches = []

    already_matched_pairs = get_existing_matched_pairs(existing_matches)
    matches = []

    for i in range(len(signups)):
        for j in range(i + 1, len(signups)):
            person_a, person_b = signups[i], signups[j]

            if person_a["membership_number"] == person_b["membership_number"]:
                continue

            pair = frozenset([person_a["membership_number"], person_b["membership_number"]])
            if pair in already_matched_pairs:
                continue

            if not person_a["open_to_match"] or not person_b["open_to_match"]:
                continue
            if person_a["sport"] != person_b["sport"]:
                continue
            if not ages_are_compatible(person_a, person_b):
                continue

            overlapping_slots = get_overlapping_slots(person_a, person_b)

            if overlapping_slots:
                proposed_date, proposed_time = overlapping_slots[0]
                matches.append({
                    "match_id": str(uuid.uuid4()),
                    "person_a": person_a["name"],
                    "person_a_email": person_a["email"],
                    "person_a_membership": person_a["membership_number"],
                    "person_b": person_b["name"],
                    "person_b_email": person_b["email"],
                    "person_b_membership": person_b["membership_number"],
                    "sport": person_a["sport"],
                    "overlapping_slots": overlapping_slots,
                    "proposed_date": proposed_date,
                    "proposed_time": proposed_time,
                    "person_a_status": "pending",
                    "person_b_status": "pending",
                })

    return matches


def find_near_misses(signups, existing_matches=None, existing_near_misses=None):
    """
    Finds NEW near-miss suggestions -- pairs who don't have an exact
    overlap, but whose free slots are within 30 minutes of each other
    on the same date. Skips anyone already exact-matched or already
    suggested a near-miss with.
    """
    existing_matches = existing_matches or []
    existing_near_misses = existing_near_misses or []

    already_matched = get_existing_matched_pairs(existing_matches)
    already_suggested = {
        frozenset([nm["person_a_membership"], nm["person_b_membership"]])
        for nm in existing_near_misses
    }

    suggestions = []

    for i in range(len(signups)):
        for j in range(i + 1, len(signups)):
            person_a, person_b = signups[i], signups[j]

            if person_a["membership_number"] == person_b["membership_number"]:
                continue

            pair = frozenset([person_a["membership_number"], person_b["membership_number"]])
            if pair in already_matched or pair in already_suggested:
                continue

            if not person_a["open_to_match"] or not person_b["open_to_match"]:
                continue
            if person_a["sport"] != person_b["sport"]:
                continue
            if not ages_are_compatible(person_a, person_b):
                continue

            # Only bother checking near-misses if there's no exact
            # overlap already (exact matches take priority).
            if get_overlapping_slots(person_a, person_b):
                continue

            near_miss_slots = find_near_miss_slot_pairs(person_a, person_b)
            if near_miss_slots:
                date, slot_a, slot_b = near_miss_slots[0]
                ai_suggestion = generate_reschedule_suggestion(
                    person_a["name"], person_b["name"], date, slot_a, slot_b
                )
                suggestions.append({
                    "suggestion_id": str(uuid.uuid4()),
                    "person_a": person_a["name"],
                    "person_a_email": person_a["email"],
                    "person_a_membership": person_a["membership_number"],
                    "person_b": person_b["name"],
                    "person_b_email": person_b["email"],
                    "person_b_membership": person_b["membership_number"],
                    "sport": person_a["sport"],
                    "date": date,
                    "person_a_slot": slot_a,
                    "person_b_slot": slot_b,
                    "ai_suggestion": ai_suggestion,
                })

    return suggestions


def send_email(to_address, subject, body):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = to_address
    msg.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.send_message(msg)


def send_match_emails(match):
    proposed = f"{match['proposed_date']} ({match['proposed_time']})"
    link_for_a = f"{APP_BASE_URL}/Confirm_Match_v2?match_id={match['match_id']}&person=a"
    link_for_b = f"{APP_BASE_URL}/Confirm_Match_v2?match_id={match['match_id']}&person=b"

    body_for_a = (
        f"Hi {match['person_a']},\n\nYou've been matched with {match['person_b']} "
        f"for {match['sport']}!\nProposed time: {proposed}\n\n"
        f"Confirm or suggest a different time here:\n{link_for_a}\n\nSee you at the club!"
    )
    body_for_b = (
        f"Hi {match['person_b']},\n\nYou've been matched with {match['person_a']} "
        f"for {match['sport']}!\nProposed time: {proposed}\n\n"
        f"Confirm or suggest a different time here:\n{link_for_b}\n\nSee you at the club!"
    )

    send_email(match["person_a_email"], "You've got a buddy match!", body_for_a)
    send_email(match["person_b_email"], "You've got a buddy match!", body_for_b)


def send_near_miss_email(suggestion):
    """Sends both people the AI's rescheduling suggestion."""
    body = (
        f"Hi {{name}},\n\nYou and {{other}} are almost aligned for {suggestion['sport']} "
        f"on {suggestion['date']} -- {suggestion['person_a']} is free "
        f"{suggestion['person_a_slot']}, and {suggestion['person_b']} is free "
        f"{suggestion['person_b_slot']}.\n\n{suggestion['ai_suggestion']}\n\n"
        f"Reply to each other or adjust your availability on the site if you'd like to align."
    )
    send_email(
        suggestion["person_a_email"], "A near-match for your schedule!",
        body.format(name=suggestion["person_a"], other=suggestion["person_b"]),
    )
    send_email(
        suggestion["person_b_email"], "A near-match for your schedule!",
        body.format(name=suggestion["person_b"], other=suggestion["person_a"]),
    )


if __name__ == "__main__":
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        print("Missing email credentials. See setup instructions at the top of this file.")
    else:
        from storage import load_matches

        signups = load_signups()
        existing_matches = load_matches()
        existing_near_misses = load_near_misses()
        print(f"Loaded {len(signups)} sign-up(s), {len(existing_matches)} existing match(es), "
              f"{len(existing_near_misses)} existing near-miss suggestion(s).")

        if signups:
            new_matches = find_matches(signups, existing_matches=existing_matches)
            save_matches(existing_matches + new_matches)

            new_near_misses = find_near_misses(signups, existing_matches + new_matches, existing_near_misses)
            save_near_misses(existing_near_misses + new_near_misses)

            if new_matches:
                print(f"\nFound {len(new_matches)} NEW exact match(es):\n")
                for m in new_matches:
                    slots_text = ", ".join(f"{d} {t}" for d, t in m["overlapping_slots"][:3])
                    print(f"  {m['person_a']} + {m['person_b']} -- {m['sport']}, genuinely free: {slots_text}")
                    try:
                        send_match_emails(m)
                        print(f"    -> Emails sent.")
                    except Exception as e:
                        print(f"    -> Failed to send email: {e}")

            if new_near_misses:
                print(f"\nFound {len(new_near_misses)} NEW near-miss suggestion(s):\n")
                for nm in new_near_misses:
                    print(f"  {nm['person_a']} + {nm['person_b']} -- {nm['date']}: {nm['ai_suggestion']}")
                    try:
                        send_near_miss_email(nm)
                        print(f"    -> Emails sent.")
                    except Exception as e:
                        print(f"    -> Failed to send email: {e}")

            if not new_matches and not new_near_misses:
                print("\nNo new matches or near-misses this run.")
