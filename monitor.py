#!/usr/bin/env python3

import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


SITE_URL = "https://www.mumresults.in/"

PROGRAM_CODE = "1113161"
TARGET_COURSE = "Master of Science(Information Technology)"
TARGET_SEMESTER = "Semester - IV"

# We specifically want the current First Half 2026 result.
TARGET_SESSION = "First Half 2026"

# Do NOT alert for old supplementary results.
EXCLUDE_WORDS = [
    "SUPPLEMENTARY",
]

STATE_FILE = Path("state.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(compatible; MumbaiUniversityResultMonitor/1.0)"
    )
}


def normalize(text):
    return re.sub(r"\s+", " ", text or "").strip().lower()


def fetch_page():
    response = requests.get(
        SITE_URL,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    return response.text


def find_target(html):

    soup = BeautifulSoup(html, "html.parser")

    # Find the "First Half 2026" section.
    session_heading = None

    for element in soup.find_all(
        ["h1", "h2", "h3", "h4", "h5", "h6", "div", "p"]
    ):
        text = normalize(element.get_text(" ", strip=True))

        if text == normalize(TARGET_SESSION):
            session_heading = element
            break

    if not session_heading:
        print(f"Session '{TARGET_SESSION}' not found.")

        return {
            "found": False
        }

    # The results immediately following the session heading
    # are contained in the next table.
    table = session_heading.find_next("table")

    if not table:
        print("Could not find results table.")

        return {
            "found": False
        }

    for row in table.find_all("tr"):

        cells = row.find_all(["td", "th"])

        if not cells:
            continue

        row_text = " ".join(
            cell.get_text(" ", strip=True)
            for cell in cells
        )

        normalized_row = normalize(row_text)

        # Program code must match.
        if PROGRAM_CODE.lower() not in normalized_row:
            continue

        # Course must match.
        if "master of science" not in normalized_row:
            continue

        if "information technology" not in normalized_row:
            continue

        # Semester IV must match.
        if normalize(TARGET_SEMESTER) not in normalized_row:
            continue

        # CRITICAL:
        # Ignore Supplementary results.
        if any(
            word.lower() in normalized_row
            for word in EXCLUDE_WORDS
        ):
            print("Matching old supplementary result ignored.")

            continue

        # Find result/PDF link.
        link = row.find("a", href=True)

        result_url = None

        if link:
            result_url = urljoin(
                SITE_URL,
                link["href"]
            )

        result_date = None

        if len(cells) >= 2:
            result_date = cells[-1].get_text(
                " ",
                strip=True
            )

        return {
            "found": True,
            "session": TARGET_SESSION,
            "program_code": PROGRAM_CODE,
            "course": TARGET_COURSE,
            "semester": TARGET_SEMESTER,
            "result_date": result_date,
            "row": row_text,
            "url": result_url,
        }

    return {
        "found": False
    }


def load_state():

    if not STATE_FILE.exists():
        return {}

    try:
        return json.loads(
            STATE_FILE.read_text()
        )

    except Exception:
        return {}


def save_state(data):

    STATE_FILE.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False
        )
    )


def telegram_send(message):

    token = os.environ.get(
        "TELEGRAM_BOT_TOKEN"
    )

    chat_id = os.environ.get(
        "TELEGRAM_CHAT_ID"
    )

    if not token or not chat_id:

        print(
            "Telegram credentials are not configured."
        )

        return

    url = (
        f"https://api.telegram.org/"
        f"bot{token}/sendMessage"
    )

    response = requests.post(
        url,
        data={
            "chat_id": chat_id,
            "text": message,
            "disable_web_page_preview": False,
        },
        timeout=30,
    )

    response.raise_for_status()


def main():

    try:

        html = fetch_page()

        current = find_target(html)

    except Exception as exc:

        print(
            f"ERROR: {exc}",
            file=sys.stderr
        )

        sys.exit(1)

    previous = load_state()

    if not current["found"]:

        print(
            "Target First Half 2026 Semester IV "
            "result is NOT currently published."
        )

        return

    print(
        "TARGET FOUND:"
    )

    print(
        json.dumps(
            current,
            indent=2,
            ensure_ascii=False
        )
    )

    fingerprint = json.dumps(
        current,
        sort_keys=True,
        ensure_ascii=False
    )

    previous_fingerprint = previous.get(
        "fingerprint"
    )

    # Alert only when this is a new/changed result.
    if fingerprint != previous_fingerprint:

        message = (
            "🚨 Mumbai University Result Alert\n\n"
            "TARGET RESULT FOUND!\n\n"
            f"Session: {TARGET_SESSION}\n"
            f"Program Code: {PROGRAM_CODE}\n"
            f"Course: {TARGET_COURSE}\n"
            f"Semester: IV\n"
            f"Result Date: "
            f"{current.get('result_date') or 'Not shown'}\n\n"
            f"Listing: {SITE_URL}"
        )

        if current.get("url"):

            message += (
                f"\nPDF/Result: "
                f"{current['url']}"
            )

        telegram_send(message)

        save_state(
            {
                "fingerprint": fingerprint,
                "result": current,
            }
        )

        print("ALERT SENT.")

    else:

        print(
            "Target already notified. "
            "No duplicate alert."
        )


if __name__ == "__main__":
    main()
