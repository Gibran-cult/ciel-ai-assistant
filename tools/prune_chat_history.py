"""
Delete Langflow chat messages older than the retention period.

The privacy page tells users that server-side chat history is kept for at
most CHAT_RETENTION_DAYS (default 30) days. Run this on the Langflow host,
for example daily with Windows Task Scheduler (see README):

    python tools/prune_chat_history.py --days 30 --dry-run
    python tools/prune_chat_history.py --days 30

It reads LANGFLOW_API_KEY from the environment or a .env file, pages through
all messages of the account's flows (main flow and sub-flows), and deletes
the expired ones by ID. Long-term memory (Chroma) is not touched.
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

import requests

PAGE_SIZE = 200          # Langflow's maximum page size for /monitor/messages
DELETE_BATCH = 200


def parse_timestamp(value):
    """Parse Langflow timestamps such as '2026-10-14 11:28:48 UTC' as UTC."""
    text = str(value or "").strip().replace("Z", "+00:00")
    if text.endswith(" UTC"):
        text = text[:-4] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def select_expired(messages, cutoff):
    """IDs of messages with a timestamp before `cutoff`; unparsable ones are kept."""
    expired = []
    for message in messages:
        stamp = parse_timestamp(message.get("timestamp"))
        if stamp is not None and stamp < cutoff and message.get("id"):
            expired.append(str(message["id"]))
    return expired


def fetch_all_messages(base_url, headers):
    messages, offset = [], 0
    while True:
        response = requests.get(
            f"{base_url}/api/v1/monitor/messages",
            headers=headers,
            params={"limit": PAGE_SIZE, "offset": offset},
            timeout=60,
        )
        response.raise_for_status()
        page = response.json()
        messages.extend(page)
        if len(page) < PAGE_SIZE:
            return messages
        offset += PAGE_SIZE


def main(argv=None, now=None):
    parser = argparse.ArgumentParser(description="Delete Langflow chat messages older than N days.")
    parser.add_argument("--days", type=int, default=int(os.getenv("CHAT_RETENTION_DAYS", "30")))
    parser.add_argument("--base-url", default=os.getenv("LANGFLOW_BASE_URL", "http://127.0.0.1:7860"))
    parser.add_argument("--dry-run", action="store_true", help="only report what would be deleted")
    args = parser.parse_args(argv)

    if args.days < 1:
        parser.error("--days must be at least 1")

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    api_key = os.getenv("LANGFLOW_API_KEY")
    if not api_key:
        parser.error("LANGFLOW_API_KEY is not set (environment or .env)")

    base_url = args.base_url.rstrip("/")
    headers = {"x-api-key": api_key, "Accept": "application/json"}
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=args.days)

    messages = fetch_all_messages(base_url, headers)
    expired = select_expired(messages, cutoff)
    print(f"Messages: {len(messages)}; older than {args.days} days (before {cutoff:%Y-%m-%d %H:%M} UTC): {len(expired)}")

    if args.dry_run or not expired:
        if args.dry_run:
            print("Dry run: nothing deleted.")
        return 0

    for start in range(0, len(expired), DELETE_BATCH):
        response = requests.delete(
            f"{base_url}/api/v1/monitor/messages",
            headers=headers,
            json=expired[start:start + DELETE_BATCH],
            timeout=60,
        )
        response.raise_for_status()

    print(f"Deleted {len(expired)} messages.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
