"""
Keep the Streamlit Community Cloud app awake.

Community Cloud puts an app to sleep after 12 hours without visitors, and a
plain HTTP request does not count as a visit: the app only sees a browser
session that opens its websocket. This script opens the app in headless
Chromium, presses "Yes, get this app back up!" if the app is asleep, and
waits until the Streamlit app has rendered.

    python tools/wake_streamlit.py https://<your-app>.streamlit.app

The keep-awake GitHub Actions workflow runs it every few hours. It only loads
the page, so it sends no chat message and no request to the Langflow backend.
Exit code 1 means the app did not render in time; GitHub then emails the
repository owner about the failed run.
"""

import argparse
import sys
import time

WAKE_BUTTON_TEXT = "get this app back up"
APP_SELECTOR = '[data-testid="stApp"]'


def app_rendered(page):
    # On Community Cloud the app runs in an iframe inside the share page.
    return any(frame.query_selector(APP_SELECTOR) for frame in page.frames)


def wake(url, timeout_s, channel=None):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel=channel)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_s * 1000)

        woke = False
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if app_rendered(page):
                # Stay a moment so the session registers as a visit.
                page.wait_for_timeout(10_000)
                browser.close()
                print("awake" + (" (woken from sleep)" if woke else ""))
                return True
            button = page.get_by_role("button", name=WAKE_BUTTON_TEXT)
            if not woke and button.count():
                button.first.click()
                woke = True
                print("app was asleep, wake button pressed")
            page.wait_for_timeout(5_000)

        browser.close()
        print(f"app did not render within {timeout_s} s", file=sys.stderr)
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(description="Open a Streamlit Cloud app and wake it if it sleeps.")
    parser.add_argument("url", help="the app's public URL")
    parser.add_argument("--timeout", type=int, default=300, help="seconds to wait for the app (default 300)")
    parser.add_argument("--channel", help="installed browser instead of Playwright's Chromium, e.g. chrome")
    args = parser.parse_args(argv)
    return 0 if wake(args.url, args.timeout, args.channel) else 1


if __name__ == "__main__":
    sys.exit(main())
