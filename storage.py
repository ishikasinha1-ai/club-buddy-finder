"""
Local Storage (JSON files)
-----------------------------
Same job as sheets_storage.py would do, but using local JSON files
instead of Google Sheets -- since Google Sheets needs a one-time setup
(Cloud project, service account, sharing) that isn't done yet, and
testing demand matters more right now than data persistence.

IMPORTANT: because this uses the SAME function names as sheets_storage.py
(load_signups, save_signup, load_matches, save_matches, get_match_by_id,
update_match), switching to Google Sheets later is a drop-in change --
just change the import line in the other files from
"from storage import ..." to "from sheets_storage import ...", nothing
else needs to change.

Requirements:
    (none extra -- just Python's built-in json/os/uuid)
"""

import json
import os

SIGNUPS_FILE = "signups.json"
MATCHES_FILE = "matches.json"


def load_signups():
    if not os.path.exists(SIGNUPS_FILE):
        return []
    with open(SIGNUPS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_signup(entry):
    signups = load_signups()
    signups.append(entry)
    with open(SIGNUPS_FILE, "w", encoding="utf-8") as f:
        json.dump(signups, f, indent=2)


def load_matches():
    if not os.path.exists(MATCHES_FILE):
        return []
    with open(MATCHES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_matches(matches):
    with open(MATCHES_FILE, "w", encoding="utf-8") as f:
        json.dump(matches, f, indent=2)


def get_match_by_id(match_id):
    """Finds a single match by its unique ID, or returns None if not found."""
    for m in load_matches():
        if m["match_id"] == match_id:
            return m
    return None


def update_match(match_id, updates):
    """Updates specific fields of one match by rewriting the whole file."""
    matches = load_matches()
    for m in matches:
        if m["match_id"] == match_id:
            m.update(updates)
    save_matches(matches)
