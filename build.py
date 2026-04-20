"""
build.py — Fetches published Google Docs and converts them to Markdown.

Usage:
    python build.py

The script checks Drive API modifiedTime for each doc and skips unchanged
ones. Changed docs are fetched, converted to Markdown, and saved to output/.
"""

import json
import os
import re
import sys

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as to_md

# ── Configuration ──────────────────────────────────────────────
OUTPUT_DIR = "output"
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
STATE_PATH = os.path.join(OUTPUT_DIR, ".state")
META_PATH = os.path.join(OUTPUT_DIR, "meta.json")

DOCS = [
    {
        "name": "constitution",
        "doc_id": "1Wlbsfthj62koGAXfGN8Fz2SeNWyUGDxlKFA749OZiP0",
        "output_md": os.path.join(OUTPUT_DIR, "constitution.md"),
    },
    {
        "name": "federal-law",
        "doc_id": "1GsXK8j9ivQAArb1RPeeQJJOcstsp1eJL2OdOhrkvqvc",
        "output_md": os.path.join(OUTPUT_DIR, "federal-law.md"),
    },
    {
        "name": "server-rules",
        "doc_id": "1u45j3U72fPs5LrnOejunLFFEo8FpTxO3mREZnFemNM4",
        "output_md": os.path.join(OUTPUT_DIR, "server-rules.md"),
    },
    {
        "name": "companies",
        "doc_id": "1dQIwh4xI19mK94R9n-rQwcuUl01ywOnENOkPD75S6GU",
        "output_md": os.path.join(OUTPUT_DIR, "companies.md"),
    },
    {
        "name": "education-and-skill-scrolls",
        "doc_id": "1i0BbrYrKPfL-wFLYUdctm_PwO3_HrJSB31sPK0fA86U",
        "output_md": os.path.join(OUTPUT_DIR, "education-and-skill-scrolls.md"),
    },
    {
        "name": "government-guidelines",
        "doc_id": "1rwARG_BJvqaZ38-A7ujgYT2obTnDtWIaMZHZVeY2-g8",
        "output_md": os.path.join(OUTPUT_DIR, "government-guidelines.md"),
    },
    {
        "name": "labour-requirements",
        "doc_id": "1mcSON_ha5GO2w9pPzsD6h0Rq4u6mcFOGtv0pAeNKgLw",
        "output_md": os.path.join(OUTPUT_DIR, "labour-requirements.md"),
    },
    {
        "name": "overview",
        "doc_id": "10JmyCFhf9UvDlAhlxRBRc41b0d_tiehpyH7gZj7bb7M",
        "output_md": os.path.join(OUTPUT_DIR, "overview.md"),
    },
    {
        "name": "towns-and-countries",
        "doc_id": "1ckQMkb3d0eglJZZ9lpx03LuBfp2fl-Y0uJv1sZdT3O8",
        "output_md": os.path.join(OUTPUT_DIR, "towns-and-countries.md"),
    },
    {
        "name": "victory-conditions",
        "doc_id": "1wah3o-PVouxm-6-E8o6Dc0rK-9lbY8I3IFwmLOcq_Kw",
        "output_md": os.path.join(OUTPUT_DIR, "victory-conditions.md"),
    },
]
# ───────────────────────────────────────────────────────────────


def get_remote_modified_time(doc_id: str) -> str | None:
    """Query Drive API for the doc's modifiedTime. Returns ISO string or None on failure."""
    if not GOOGLE_API_KEY:
        return None
    url = f"https://www.googleapis.com/drive/v3/files/{doc_id}?fields=modifiedTime&key={GOOGLE_API_KEY}"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.json().get("modifiedTime")
    except Exception as e:
        print(f"WARNING: Could not fetch modifiedTime for {doc_id} ({e}), will rebuild.")
        return None


def read_cached_times() -> dict:
    """Read the last-known modifiedTime per doc_id from STATE_PATH (JSON)."""
    try:
        with open(STATE_PATH) as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return {}


def write_cached_times(times: dict) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(times, f)


def write_meta(meta: dict) -> None:
    with open(META_PATH, "w") as f:
        json.dump(meta, f, indent=2)


def set_github_output(key: str, value: str) -> None:
    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a") as f:
            f.write(f"{key}={value}\n")


def write_step_summary(built: list[str], skipped: list[str]) -> None:
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_file:
        return
    with open(summary_file, "a") as f:
        if built:
            f.write("### Updated\n")
            for name in built:
                f.write(f"- `{name}`\n")
        if skipped:
            f.write("### Unchanged (skipped)\n")
            for name in skipped:
                f.write(f"- `{name}`\n")
        if not built:
            f.write("No changes detected — deploy skipped.\n")


def fetch_doc_content(url: str) -> tuple[str, str]:
    """Download a published Google Doc and extract the body content.

    Returns (contents_html, full_page_html). The full page HTML is needed so
    that CSS class detection for superscripts can find the <style> tag in <head>.
    """
    print(f"Fetching: {url}")
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    contents = soup.find(id="contents") or soup.body

    if contents is None:
        print(f"ERROR: Could not find document content at {url}", file=sys.stderr)
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

    for span in soup.find_all("span", style=True):
        style = span["style"].replace(" ", "")
        if "vertical-align:super" in style:
            span.name = "sup"
            del span["style"]
        elif "vertical-align:sub" in style:
            span.name = "sub"
            del span["style"]

    return str(soup)


def doc_to_markdown(doc_html: str, full_html: str = "") -> str:
    """Convert Google Doc HTML to Markdown with superscript support."""
    return to_md(
        _normalize_superscripts(doc_html, full_html),
        heading_style="ATX",
        sup_symbol="<sup>",
        sub_symbol="<sub>",
    )


def main():
    if not GOOGLE_API_KEY:
        print("WARNING: GOOGLE_API_KEY not set — skipping change detection, full build will run.")

    cached_times = read_cached_times()
    remote_times = {}
    built: list[str] = []
    skipped: list[str] = []

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for doc in DOCS:
        doc_id = doc["doc_id"]
        name = doc["name"]
        url = f"https://docs.google.com/document/d/{doc_id}/pub"

        remote_time = get_remote_modified_time(doc_id)
        remote_times[doc_id] = remote_time

        if remote_time and remote_time == cached_times.get(doc_id):
            print(f"No changes detected: {name}. Skipping.")
            skipped.append(name)
            continue

        doc_html, full_html = fetch_doc_content(url)
        content_md = doc_to_markdown(doc_html, full_html)

        with open(doc["output_md"], "w", encoding="utf-8") as f:
            f.write(content_md)
        print(f"Built: {doc['output_md']}")
        built.append(name)

    new_cached = dict(cached_times)
    meta = {}
    for doc in DOCS:
        rt = remote_times.get(doc["doc_id"])
        if rt:
            new_cached[doc["doc_id"]] = rt
            meta[doc["name"]] = rt
        elif doc["doc_id"] in cached_times:
            # no API key or transient failure — carry forward the cached time
            meta[doc["name"]] = cached_times[doc["doc_id"]]
    write_cached_times(new_cached)
    write_meta(meta)

    any_changed = bool(built)
    set_github_output("changed", "true" if any_changed else "false")
    write_step_summary(built, skipped)
    if not any_changed:
        print("No changes detected across all docs. Skipping deploy.")


if __name__ == "__main__":
    main()
