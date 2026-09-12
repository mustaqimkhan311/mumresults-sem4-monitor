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

STATE_FILE = Path("state.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(compatible; MumbaiUniversityResultMonitor/1.0)"
    )
}


def normalize(text):
    return re.sub(r"\s+", " ", text or "").strip()


def fetch_page():
    response = requests.get(
        SITE_URL,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    return response.text


def find_results(html):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    results = []

    # Search every link on the page.
    # Program Code 1113161 is the ONLY detection criterion.
    for link in soup.find_all("a", href=True):

        link_text = normalize(
            link.get_text(" ", strip=True)
        )

        href = normalize(
            link.get("href", "")
        )

        combined_text = (
            f"{link_text} {href}"
        )

        if PROGRAM_CODE not in combined_text:
            continue

        result_url = urljoin(
            SITE_URL,
            link["href"]
        )

        # Get the complete table row when available.
        row = link.find_parent("tr")

        if row:

            row_text = normalize(
                row.get_text(
                    " ",
                    strip=True
                )
            )

        else:

            row_text = link_text

        results.append(
            {
                "program_code": PROGRAM_CODE,
                "text": row_text,
                "url": result_url,
            }
        )

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
            "ERROR: Telegram credentials "
            "are not configured."
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
        f"listing(s) containing program code "
        f"{PROGRAM_CODE}."
    )

    previous = load_state()

    seen = set(
        previous.get(
            "seen",
            []
        )
    )

    # ---------------------------------------------------------
    # CHECK FOR NEW RESULTS
    # ---------------------------------------------------------

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

    # ---------------------------------------------------------
    # SEND NEW RESULTS
    # ---------------------------------------------------------

    if not new_results:

        print(
            "No new result listing detected."
        )

    else:

        print(
            f"Found {len(new_results)} "
            f"new result listing(s)."
        )

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
                f"Program Code: {PROGRAM_CODE}\n\n"
                f"Details:\n"
                f"{result.get('text') or 'Not available'}\n\n"
                f"Listing: {SITE_URL}"
            )

            if result.get("url"):

                message += (
                    f"\n\nPDF/Result:\n"
                    f"{result['url']}"
                )

            telegram_send(message)

            seen.add(
                fingerprint
            )

            print(
                "TELEGRAM ALERT SENT."
            )

    # ---------------------------------------------------------
    # SAVE ALL SEEN RESULTS
    # ---------------------------------------------------------

    save_state(
        {
            "seen": list(seen)
        }
    )

    print(
        f"Monitor state saved. "
        f"Total unique listing(s) tracked: {len(seen)}"
    )


if __name__ == "__main__":
    main()
