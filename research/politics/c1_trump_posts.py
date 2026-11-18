"""C1: do Trump's Truth Social posts move crypto markets, and which kinds of posts?

Part C, version 1. The design is fixed in `research/politics/PREREGISTRATION.md`, written
and hashed before any price data was downloaded or opened. Three steps:

    PYTHONPATH=src .venv/bin/python research/politics/c1_trump_posts.py convert
    PYTHONPATH=src .venv/bin/python research/politics/c1_trump_posts.py download
    PYTHONPATH=src .venv/bin/python research/politics/c1_trump_posts.py analyze

`convert` turns the Truth Social archive (data/politics/raw/pletcher_truth/posts.jsonl,
git-ignored) into research/politics/posts/truth_realDonaldTrump.csv in the data contract
of posts/README.md. Mapping choices (the archive has no reply, quote or repost flags;
`in_reply_to_id` and `quote_id` are always empty):

- repost: text starts with "RT @<handle>" or "RT: <truthsocial status url>". The handle
  after "RT @" is glued to the reposted text, so it is resolved as the longest handle
  seen elsewhere in the archive (in status URLs, or 3 or more times as an @mention
  outside RT prefixes) that is a prefix of the glued string; otherwise the leading run
  of handle characters minus a trailing "http(s)" or final capitalized word (best
  effort: the reposted handle is descriptive only and is not used in the analysis).
- quote: not a repost, and the text contains a truthsocial.com status URL; the handle
  is the account in the first such URL.
- reply: never assigned. The archive carries no reply information, and the 31 posts
  that start with "@" read as citations ("@EricTrump: ...") or shout-outs, so they are
  kept as original.
- original: everything else, including media-only posts with empty text.
- has_media: media_count > 0. Text: mojibake (UTF-8 read as Latin-1) is repaired
  segment by segment; newlines would be written as a literal backslash-n (none occur).
- Times are truncated to whole seconds (the contract format); collected_at_utc is the
  archive's scraped_at, truncated the same way.
- Two posts with empty text and no media (2024-03-05 17:23:39) fail the contract and are
  dropped.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

RAW = ROOT / "data" / "politics" / "raw" / "pletcher_truth" / "posts.jsonl"
POSTS_CSV = HERE / "posts" / "truth_realDonaldTrump.csv"
PREREG = HERE / "PREREGISTRATION.md"
KLINES = ROOT / "data" / "politics" / "klines"
OUT = HERE / "data"
COLUMNS = ["platform", "handle", "post_id", "url", "created_at_utc", "text", "kind",
           "quoted_or_reposted_handle", "has_media", "collected_at_utc"]

# ---------------------------------------------------------------------------- convert

_STATUS_URL = re.compile(r"truthsocial\.com/(?:users/|@)([A-Za-z0-9_]+)(?:/statuses/|/)\d+")
_ANY_TS_URL = re.compile(r"truthsocial\.com/(?:users/|@)([A-Za-z0-9_]+)")
_MENTION = re.compile(r"@([A-Za-z0-9_]+)(?=[^A-Za-z0-9_]|$)")
_HANDLE_RUN = re.compile(r"[A-Za-z0-9_]+")
_MOJIBAKE = re.compile(r"[\u00c2-\u00f4][\u0080-\u00bf]+")


def fix_mojibake(text: str) -> str:
    """Repair UTF-8 bytes that were decoded as Latin-1, one run at a time."""
    def one(m: re.Match) -> str:
        s = m.group(0)
        try:
            return s.encode("latin-1").decode("utf-8")
        except UnicodeError:
            return s
    return _MOJIBAKE.sub(one, text)


def known_handles(texts: list[str], min_mentions: int = 3) -> set[str]:
    """Handles seen in status URLs, or at least `min_mentions` times as @mentions
    outside an "RT @" prefix (single mentions are often glued typos)."""
    urls: set[str] = set()
    mentions: dict[str, int] = {}
    for t in texts:
        urls.update(_ANY_TS_URL.findall(t))
        body = t
        if t.startswith("RT @"):
            m = _HANDLE_RUN.match(t[4:])
            body = t[4 + (m.end() if m else 0):]
        for h in _MENTION.findall(body):
            mentions[h] = mentions.get(h, 0) + 1
    return urls | {h for h, n in mentions.items() if n >= min_mentions}


_GLUED_TAIL = re.compile(r"(?<=[a-z0-9])(?:https?|[A-Z][a-z]+)$")


def _unglue(run: str) -> str:
    """Best-effort split of an unknown handle from glued text: drop a trailing "http(s)"
    or a final capitalized word ("patriotmomfloridaHoly" -> "patriotmomflorida")."""
    m = _GLUED_TAIL.search(run)
    return run[:m.start()] if m and m.start() >= 3 else run


def classify_kind(text: str, known: set[str]) -> tuple[str, str]:
    """(kind, quoted_or_reposted_handle) from the post text alone."""
    if text.startswith("RT @"):
        glued = text[4:]
        for n in range(min(30, len(glued)), 0, -1):
            if glued[:n] in known:
                return "repost", glued[:n]
        m = _HANDLE_RUN.match(glued)
        return "repost", (_unglue(m.group(0)) if m else "unknown")
    if text.startswith("RT:"):
        m = _ANY_TS_URL.search(text)
        return "repost", (m.group(1) if m else "unknown")
    m = _STATUS_URL.search(text)
    if m:
        return "quote", m.group(1)
    return "original", ""


def _sec(ts: str) -> str:
    return ts[:19] + "Z"


def convert(raw: Path = RAW, out: Path = POSTS_CSV) -> dict:
    rows = [json.loads(line) for line in raw.open(encoding="utf-8")]
    texts = [fix_mojibake(r.get("text") or "") for r in rows]
    known = known_handles(texts)
    recs, dropped = [], []
    for r, t in zip(rows, texts, strict=True):
        kind, h = classify_kind(t, known)
        media = (r.get("media_count") or 0) > 0
        if kind != "repost" and not t.strip() and not media:
            dropped.append(r["id"])
            continue
        recs.append({
            "platform": "truth", "handle": "realDonaldTrump", "post_id": str(r["id"]),
            "url": f"https://truthsocial.com/@realDonaldTrump/{r['id']}",
            "created_at_utc": _sec(r["created_at"]),
            "text": t.replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n"),
            "kind": kind, "quoted_or_reposted_handle": h,
            "has_media": "true" if media else "false",
            "collected_at_utc": _sec(r["scraped_at"]),
        })
    recs.sort(key=lambda d: (d["created_at_utc"], d["post_id"]))
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(recs)
    kinds: dict[str, int] = {}
    for d in recs:
        kinds[d["kind"]] = kinds.get(d["kind"], 0) + 1
    return {"rows": len(recs), "dropped": dropped, "kinds": kinds,
            "first": recs[0]["created_at_utc"], "last": recs[-1]["created_at_utc"]}
