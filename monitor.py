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

# We only monitor the current First Half 2026 section.
TARGET_SESSION = "First Half 2026"

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


def find_session_table(soup):
    """
    Locate the table belonging to First Half 2026.
    """

    session_heading = None

    for element in soup.find_all(
        ["h1", "h2", "h3", "h4", "h5", "h6", "div", "p"]
    ):
        text = normalize(
            element.get_text(" ", strip=True)
        )

        if text == normalize(TARGET_SESSION):
            session_heading = element
            break

    if not session_heading:
        print(
            f"Session '{TARGET_SESSION}' not found."
        )
        return None

    table = session_heading.find_next("table")

    if not table:
        print(
            "Could not find results table."
        )
        return None

    return table


def find_results(html):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    table = find_session_table(soup)

    if not table:
        return []

    results = []

    for row in table.find_all("tr"):

        cells = row.find_all(
            ["td", "th"]
        )

        if not cells:
            continue

        row_text = " ".join(
            cell.get_text(
                " ",
                strip=True
            )
            for cell in cells
        )

        normalized_row = normalize(
            row_text
        )

        # PROGRAM CODE IS THE ONLY RESULT FILTER.
        if PROGRAM_CODE.lower() not in normalized_row:
            continue

        # Find the result/PDF link.
        link = row.find(
            "a",
            href=True
        )

        result_url = None

        if link:
            result_url = urljoin(
                SITE_URL,
                link["href"]
            )

        # Try to identify the result date.
        result_date = None

        if len(cells) >= 2:
            result_date = cells[-1].get_text(
                " ",
                strip=True
            )

        result = {
            "session": TARGET_SESSION,
            "program_code": PROGRAM_CODE,
            "row": row_text,
            "result_date": result_date,
            "url": result_url,
        }

        results.append(result)

    return results


def load_state():

    if not STATE_FILE.exists():
        return {
            "seen": []
        }

    try:
        data = json.loads(
            STATE_FILE.read_text()
        )

        if "seen" not in data:
            data["seen"] = []

        return data

    except Exception:
        return {
            "seen": []
        }


def save_state(data):

    STATE_FILE.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False
        )
    )


def create_fingerprint(result):

    return json.dumps(
        result,
        sort_keys=True,
        ensure_ascii=False
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

        current_results = find_results(
            html
        )

    except Exception as exc:

        print(
            f"ERROR: {exc}",
            file=sys.stderr
        )

        sys.exit(1)

    print(
        f"Found {len(current_results)} "
        f"listing(s) for program code "
        f"{PROGRAM_CODE} in "
        f"{TARGET_SESSION}."
    )

    previous = load_state()

    seen = set(
        previous.get(
            "seen",
            []
        )
    )

    new_results = []

    for result in current_results:

        fingerprint = create_fingerprint(
            result
        )

        if fingerprint not in seen:

            new_results.append(
                (
                    fingerprint,
                    result
                )
            )

    # First run after installing this version:
    # establish existing listings as the baseline.
    if not previous.get("initialized", False):

        for result in current_results:

            seen.add(
                create_fingerprint(result)
            )

        save_state(
            {
                "initialized": True,
                "seen": list(seen),
            }
        )

        print(
            "Initial baseline created."
        )

        print(
            f"{len(current_results)} existing "
            f"listing(s) recorded."
        )

        return

    # Alert only for genuinely NEW listings.
    if not new_results:

        print(
            "No new result listing detected."
        )

        return

    for fingerprint, result in new_results:

        print(
            "\nNEW RESULT FOUND:"
        )

        print(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False
            )
        )

        message = (
            "🚨 Mumbai University Result Alert\n\n"
            "NEW RESULT FOUND!\n\n"
            f"Session: {TARGET_SESSION}\n"
            f"Program Code: {PROGRAM_CODE}\n"
            f"Result Date: "
            f"{result.get('result_date') or 'Not shown'}\n\n"
            f"Listing: {SITE_URL}"
        )

        if result.get("url"):

            message += (
                f"\nPDF/Result: "
                f"{result['url']}"
            )

        telegram_send(message)

        seen.add(
            fingerprint
        )

        print(
            "TELEGRAM ALERT SENT."
        )

    save_state(
        {
            "initialized": True,
            "seen": list(seen),
        }
    )


if __name__ == "__main__":
    main()
