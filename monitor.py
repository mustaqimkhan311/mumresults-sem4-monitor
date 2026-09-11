#!/usr/bin/env python3
"""
Monitor University of Mumbai results for:
1113161 - Master of Science(Information Technology) ( Semester - IV) ( NEP 2020 )

Set:
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID

The script stores the last detected result in state.json so it only alerts
when the target listing/link changes or appears for the first time.
"""

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
TARGET_SEMESTER = "Semester - IV"
TARGET_COURSE = "Master of Science(Information Technology)"
STATE_FILE = Path("state.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MumbaiResultsMonitor/1.0; +https://github.com/)"
}


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def fetch_page():
    r = requests.get(SITE_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


def find_target(html: str):
    soup = BeautifulSoup(html, "html.parser")

    # Look at table rows because the site presents results as tables.
    for row in soup.find_all("tr"):
        text = " ".join(row.stripped_strings)
        n = normalize(text)

        if PROGRAM_CODE not in n:
            continue
        if normalize(TARGET_SEMESTER) not in n:
            continue
        if "information technology" not in n:
            continue

        # Avoid accidentally matching unrelated courses containing the words.
        if "master of science" not in n:
            continue

        link = row.find("a", href=True)
        href = urljoin(SITE_URL, link["href"]) if link else None

        cells = row.find_all(["td", "th"])
        result_date = None
        if cells:
            # Usually the final cell is the result date.
            result_date = cells[-1].get_text(" ", strip=True)

        return {
            "found": True,
            "program_code": PROGRAM_CODE,
            "course": TARGET_COURSE,
            "semester": TARGET_SEMESTER,
            "row": text,
            "result_date": result_date,
            "url": href,
        }

    # Fallback: search the full page text in case the HTML structure changes.
    page_text = " ".join(soup.stripped_strings)
    n = normalize(page_text)
    if PROGRAM_CODE in n and normalize(TARGET_SEMESTER) in n and "information technology" in n:
        return {
            "found": True,
            "program_code": PROGRAM_CODE,
            "course": TARGET_COURSE,
            "semester": TARGET_SEMESTER,
            "row": "Target text found on page; table row could not be parsed.",
            "result_date": None,
            "url": None,
        }

    return {"found": False}


def load_state():
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {}


def save_state(data):
    STATE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def telegram_send(message: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("Telegram secrets are not configured; skipping notification.")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(
        url,
        data={
            "chat_id": chat_id,
            "text": message,
            "disable_web_page_preview": False,
        },
        timeout=30,
    )
    r.raise_for_status()


def main():
    try:
        html = fetch_page()
        current = find_target(html)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    previous = load_state()

    if not current["found"]:
        print("NOT FOUND: target Semester IV listing is not currently present.")
        # Do not overwrite a previously detected result.
        return

    # The fingerprint changes if the row/date/link changes.
    fingerprint = json.dumps(current, sort_keys=True, ensure_ascii=False)
    previous_fp = previous.get("fingerprint")

    print("FOUND:", json.dumps(current, indent=2, ensure_ascii=False))

    if fingerprint != previous_fp:
        message = (
            "🚨 Mumbai University Result Alert\n\n"
            "Target result has been found/changed:\n"
            f"Program Code: {PROGRAM_CODE}\n"
            f"Course: {TARGET_COURSE}\n"
            f"Semester: IV\n"
            f"Result Date: {current.get('result_date') or 'Not shown'}\n\n"
            f"Listing: {SITE_URL}"
        )
        if current.get("url"):
            message += f"\nPDF/Result: {current['url']}"

        telegram_send(message)
        save_state({"fingerprint": fingerprint, "result": current})
        print("ALERT SENT.")
    else:
        print("No change since the previous check.")


if __name__ == "__main__":
    main()
