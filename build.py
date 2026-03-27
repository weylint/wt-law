"""
build.py — Fetches a published Google Doc and bakes its content
into index.html so it loads instantly on GitHub Pages.

Usage:
    python build.py

The script:
  1. Downloads the published Google Doc HTML
  2. Extracts the body content
  3. Injects it into index.html (replacing the #doc-content div)
  4. Writes the result to output/index.html
"""

import os
import sys
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

# ── Configuration ──────────────────────────────────────────────
DOC_ID = "1Wlbsfthj62koGAXfGN8Fz2SeNWyUGDxlKFA749OZiP0"
PUBLISHED_URL = f"https://docs.google.com/document/d/{DOC_ID}/pub"
TEMPLATE_PATH = "index.html"
OUTPUT_DIR = "output"
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "index.html")
# ───────────────────────────────────────────────────────────────


def fetch_doc_content() -> str:
    """Download the published Google Doc and extract the body content."""
    print(f"Fetching: {PUBLISHED_URL}")
    resp = requests.get(PUBLISHED_URL, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Google wraps the doc body in a div with id="contents"
    contents = soup.find(id="contents")
    if contents is None:
        # Fallback: grab the whole <body>
        contents = soup.body

    if contents is None:
        print("ERROR: Could not find document content.", file=sys.stderr)
        sys.exit(1)

    # Optionally strip Google's inline styles for cleaner output
    # (uncomment the next 3 lines if you want fully clean HTML)
    # for tag in contents.find_all(True):
    #     if 'style' in tag.attrs:
    #         del tag.attrs['style']

    return str(contents)


def build_page(doc_html: str) -> str:
    """Inject the doc content into the template HTML."""
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = BeautifulSoup(f.read(), "html.parser")

    # Replace the #doc-content div
    container = template.find(id="doc-content")
    if container is None:
        print("ERROR: #doc-content not found in template.", file=sys.stderr)
        sys.exit(1)

    # Parse doc HTML and replace container contents
    doc_soup = BeautifulSoup(doc_html, "html.parser")
    container.clear()
    for child in doc_soup.children:
        container.append(child)

    # Update the "last updated" timestamp
    updated_el = template.find(id="last-updated")
    if updated_el:
        now = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")
        updated_el.string = f"Last synced: {now}"

    # Remove the client-side fetch script (no longer needed)
    for script in template.find_all("script"):
        if "DOC_ID" in script.get_text():
            script.decompose()

    return str(template)


def main():
    doc_html = fetch_doc_content()
    page_html = build_page(doc_html)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(page_html)

    print(f"Built: {OUTPUT_PATH}")
    print("Done!")


if __name__ == "__main__":
    main()
