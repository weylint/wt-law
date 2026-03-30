"""
build.py — Fetches a published Google Doc and bakes its content
into index.html so it loads instantly on GitHub Pages.

Usage:
    python build.py

The script:
  1. Downloads the published Google Doc HTML
  2. Converts it to Markdown via markdownify (saved as output/content.md)
  3. Writes the timestamped template to output/index.html
"""

import os
import re
import sys
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as to_md

# ── Configuration ──────────────────────────────────────────────
DOC_ID = "1Wlbsfthj62koGAXfGN8Fz2SeNWyUGDxlKFA749OZiP0"
PUBLISHED_URL = f"https://docs.google.com/document/d/{DOC_ID}/pub"
TEMPLATE_PATH = "index.html"
OUTPUT_DIR = "output"
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "index.html")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
STATE_PATH = os.path.join(OUTPUT_DIR, ".state")
CONTENT_MD_PATH = os.path.join(OUTPUT_DIR, "content.md")
DRIVE_API_URL = f"https://www.googleapis.com/drive/v3/files/{DOC_ID}?fields=modifiedTime&key={GOOGLE_API_KEY}"
# ───────────────────────────────────────────────────────────────


def get_remote_modified_time() -> str | None:
    """Query Drive API for the doc's modifiedTime. Returns ISO string or None on failure."""
    if not GOOGLE_API_KEY:
        print("WARNING: GOOGLE_API_KEY not set — skipping change detection, full build will run.")
        return None
    try:
        resp = requests.get(DRIVE_API_URL, timeout=15)
        resp.raise_for_status()
        return resp.json().get("modifiedTime")
    except Exception as e:
        print(f"WARNING: Could not fetch modifiedTime ({e}), falling back to full build.")
        return None


def read_cached_time() -> str | None:
    """Read the last-known modifiedTime from STATE_PATH."""
    try:
        with open(STATE_PATH) as f:
            return f.read().strip() or None
    except FileNotFoundError:
        return None


def write_cached_time(modified_time: str) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(STATE_PATH, "w") as f:
        f.write(modified_time)


def set_github_output(key: str, value: str) -> None:
    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a") as f:
            f.write(f"{key}={value}\n")


def fetch_doc_content() -> tuple[str, str]:
    """Download the published Google Doc and extract the body content.

    Returns (contents_html, full_page_html). The full page HTML is needed so
    that CSS class detection for superscripts can find the <style> tag in <head>.
    """
    print(f"Fetching: {PUBLISHED_URL}")
    resp = requests.get(PUBLISHED_URL, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    contents = soup.find(id="contents") or soup.body

    if contents is None:
        print("ERROR: Could not find document content.", file=sys.stderr)
        sys.exit(1)

    return str(contents), resp.text


def _find_super_sub_classes(soup: BeautifulSoup) -> tuple[set, set]:
    """Return (superscript_classes, subscript_classes) from all <style> blocks in the page."""
    css = "".join(st.get_text() for st in soup.find_all("style")).replace(" ", "")
    sup_classes: set = set()
    sub_classes: set = set()
    for m in re.finditer(r"\.(c\w+)\{([^}]+)\}", css):
        body = m.group(2)
        if "vertical-align:super" in body:
            sup_classes.add(m.group(1))
        elif "vertical-align:sub" in body:
            sub_classes.add(m.group(1))
    return sup_classes, sub_classes


def _normalize_superscripts(html: str, full_html: str = "") -> str:
    """Convert Google Docs superscript/subscript spans to <sup>/<sub>."""
    soup = BeautifulSoup(html, "html.parser")

    # Detect which CSS classes carry vertical-align:super/sub.
    # The <style> block lives in <head>, so we need the full page HTML.
    full_soup = BeautifulSoup(full_html, "html.parser") if full_html else soup
    sup_classes, sub_classes = _find_super_sub_classes(full_soup)

    for span in soup.find_all("span", class_=True):
        classes = set(span.get("class", []))
        if classes & sup_classes:
            span.name = "sup"
            del span["class"]
        elif classes & sub_classes:
            span.name = "sub"
            del span["class"]

    # Also handle explicit inline vertical-align styles
    for span in soup.find_all("span", style=True):
        style = span["style"].replace(" ", "")
        if "vertical-align:super" in style:
            span.name = "sup"
            del span["style"]
        elif "vertical-align:sub" in style:
            span.name = "sub"
            del span["style"]

    return str(soup)


def build_page(doc_html: str, full_html: str = "") -> str:
    """Save content.md and stamp the sync timestamp into the template."""
    content_md = to_md(_normalize_superscripts(doc_html, full_html), heading_style="ATX", sup_symbol="<sup>", sub_symbol="<sub>")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(CONTENT_MD_PATH, "w", encoding="utf-8") as f:
        f.write(content_md)

    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = BeautifulSoup(f.read(), "html.parser")

    updated_el = template.find(id="last-updated")
    if updated_el:
        now = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")
        updated_el.string = f"Last synced: {now}"

    return str(template)


def main():
    remote_time = get_remote_modified_time()
    cached_time = read_cached_time()

    if remote_time and remote_time == cached_time:
        print(f"No changes detected (modifiedTime: {remote_time}). Skipping build.")
        set_github_output("changed", "false")
        return

    doc_html, full_html = fetch_doc_content()
    page_html = build_page(doc_html, full_html)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(page_html)

    if remote_time:
        write_cached_time(remote_time)

    set_github_output("changed", "true")
    print(f"Built: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
