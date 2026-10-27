#!/usr/bin/env python3
"""Collect WWOZ archive stream URLs for selected shows from the last N days.

Stream URLs look like:
  https://wwoz-od.streamguys1.com/wwoz/20261025000009-16-170-blues-in-the-night-with-jamie-dellapa.mp3
i.e. YYYYMMDDHHMMSS-<n>-<n>-<show-slug>.mp3. The air time and slug come from the
filename, and the two numbers (e.g. 16-170) are a stable per-show ID, so shows.txt
can list either IDs (preferred) or title text.
"""
import argparse, json, re, sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ARCHIVE_URL = "https://www.wwoz.org/listen/archive/"
MP3_RE = re.compile(
    r"https?://wwoz-od\.streamguys1\.com/wwoz/"
    r"(?P<ts>\d{14})-(?P<a>\d+)-(?P<b>\d+)-(?P<slug>[a-z0-9\-]+)\.mp3",
    re.I,
)
ID_RE = re.compile(r"^\d+-\d+$")


def slugify(text):
    text = text.lower().replace("'", "").replace("\u2019", "")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def load_shows(path):
    """Return (ids, slugs). Entries like '29-157' are IDs; anything else is title text."""
    ids, slugs = set(), []
    for line in Path(path).read_text().splitlines():
        line = line.split("#", 1)[0].strip()  # allow trailing comments
        if not line:
            continue
        if ID_RE.match(line):
            ids.add(line)
        else:
            slugs.append(slugify(line))
    return ids, slugs


def parse_episodes(html):
    """Return {url: episode dict} for every stream URL in the page."""
    eps = {}
    for m in MP3_RE.finditer(html):
        url = m.group(0)
        if url not in eps:
            eps[url] = {
                "aired": datetime.strptime(m["ts"], "%Y%m%d%H%M%S"),
                "show_id": f"{m['a']}-{m['b']}",
                "slug": m["slug"].lower(),
                "url": url,
            }
    return eps


def is_wanted(ep, ids, slugs):
    if not ids and not slugs:
        return True
    return ep["show_id"] in ids or any(s in ep["slug"] for s in slugs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--shows", default="shows.txt")
    ap.add_argument("--out", default="output")
    ap.add_argument("--list-shows", action="store_true",
                    help="print every show ID and slug found on the page, then exit")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(exist_ok=True)

    resp = requests.get(ARCHIVE_URL, timeout=30,
                        headers={"User-Agent": "Mozilla/5.0 (personal archive indexer)"})
    resp.raise_for_status()
    (out_dir / "archive.html").write_text(resp.text)

    eps = parse_episodes(resp.text)
    print(f"Found {len(eps)} stream URLs on the page.")
    if not eps:
        print("No stream URLs in the raw HTML: they are probably loaded by JavaScript "
              "when 'Get URL' is clicked. Re-run with --debug and inspect output/archive.html.",
              file=sys.stderr)
        sys.exit(1)

    if args.list_shows:
        shows = sorted({(e["show_id"], e["slug"]) for e in eps.values()}, key=lambda s: s[1])
        for sid, slug in shows:
            print(f"{sid}\t{slug}")
        return

    ids, slugs = load_shows(args.shows)
    # Timestamps are station-local time (New Orleans)
    cutoff = datetime.now(ZoneInfo("America/Chicago")).replace(tzinfo=None) - timedelta(days=args.days)

    picked = sorted((e for e in eps.values() if e["aired"] >= cutoff and is_wanted(e, ids, slugs)),
                    key=lambda e: e["aired"], reverse=True)

    final = [{"aired": e["aired"].isoformat(sep=" "), "show_id": e["show_id"],
              "show": e["slug"], "url": e["url"]} for e in picked]
    (out_dir / "streams.json").write_text(json.dumps(final, indent=2))
    (out_dir / "streams.txt").write_text("".join(f"{r['url']}\n" for r in final))

    if args.debug:
        for r in final:
            print(r["aired"], r["show_id"], r["show"], r["url"])
    print(f"{len(final)} episodes matched your shows in the last {args.days} days.")


if __name__ == "__main__":
    main()
