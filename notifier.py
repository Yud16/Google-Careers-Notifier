"""Notification backends: push via ntfy.sh when configured, console/desktop otherwise."""

import os

import requests


def send_ntfy(message: str, title: str | None = None, click_url: str | None = None) -> bool:
    """Push a notification via ntfy.sh. Returns True if sent."""
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        return False

    server = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
    headers = {"Priority": "urgent"}
    if title:
        headers["Title"] = title
    if click_url:
        headers["Click"] = click_url

    resp = requests.post(f"{server}/{topic}", data=message.encode("utf-8"), headers=headers, timeout=10)
    resp.raise_for_status()
    return True


def notify(message: str, title: str = "Google Careers", click_url: str | None = None) -> None:
    """Best-effort notification through every available channel."""
    print(f"\a{message}", flush=True)

    try:
        if send_ntfy(message, title=title, click_url=click_url):
            print("(sent via ntfy)", flush=True)
        else:
            print("(ntfy not configured — set NTFY_TOPIC in .env to enable push notifications)", flush=True)
    except Exception as exc:
        print(f"(ntfy notification failed: {exc})", flush=True)

    try:
        from plyer import notification

        # Windows' balloon-tip API hard-limits szInfoTitle to 64 chars and
        # szInfo (the body) to 256 chars, including null terminators, and
        # raises inside a background thread — so truncate defensively rather
        # than relying on try/except to catch it.
        short_title = title if len(title) <= 60 else title[:57] + "..."
        short_message = message if len(message) <= 250 else message[:247] + "..."
        notification.notify(title=short_title, message=short_message, timeout=10)
    except Exception:
        pass
