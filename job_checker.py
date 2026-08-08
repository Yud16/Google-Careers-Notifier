"""Shared logic for checking whether a Google Careers job listing has an Apply button."""

import re

import requests
from bs4 import BeautifulSoup

APPLY_BUTTON_ID = "apply-action-button"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

TITLE_SUFFIX_RE = re.compile(r"\s*—\s*Google Careers\s*$")


def fetch_job(url: str) -> dict:
    """Fetch a Google Careers job listing and report its title + Apply status.

    Returns a dict: {"title": str, "apply_url": str | None}
    Raises requests.RequestException on network/HTTP failure.
    """
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    title_tag = soup.find("title")
    title = TITLE_SUFFIX_RE.sub("", title_tag.text).strip() if title_tag else url

    # The site renders an Angular <base href="…/applications/"> tag and its
    # apply links are relative to *that*, not to the job listing's own URL —
    # resolving against `url` silently drops the job-id path segment and
    # lands on a "job not found" page.
    base_tag = soup.find("base", href=True)
    base_url = requests.compat.urljoin(url, base_tag["href"]) if base_tag else url

    apply_link = soup.find(id=APPLY_BUTTON_ID)
    apply_url = None
    if apply_link and apply_link.get("href"):
        apply_url = requests.compat.urljoin(base_url, apply_link["href"])

    return {"title": title, "apply_url": apply_url}
