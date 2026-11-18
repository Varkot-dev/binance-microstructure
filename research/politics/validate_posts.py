"""Check collected politician-post CSVs against the data contract in posts/README.md.

Run from the repository root:
    .venv/bin/python research/politics/validate_posts.py            # every file in posts/
    .venv/bin/python research/politics/validate_posts.py FILE.csv   # one file

Exits non-zero if any file fails, and prints one line per problem.
"""
from __future__ import annotations

import csv
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
POSTS = HERE / "posts"
COLUMNS = ["platform", "handle", "post_id", "url", "created_at_utc", "text", "kind",
           "quoted_or_reposted_handle", "has_media", "collected_at_utc"]
PLATFORMS = {"x", "truth"}
KINDS = {"original", "reply", "repost", "quote"}
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
URL_RE = {
    "x": re.compile(r"^https://(x|twitter)\.com/([A-Za-z0-9_]+)/status/(\d+)"),
    "truth": re.compile(r"^https://truthsocial\.com/@([A-Za-z0-9_]+)/(?:posts/)?(\d+)"),
}
# Posts before this date are outside every study window and usually a parsing error.
EARLIEST = datetime(2009, 1, 1, tzinfo=UTC)


def _parse_ts(value: str) -> datetime | None:
    if not TS_RE.match(value):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None


def check_rows(name: str, header: list[str], rows: list[dict], now: datetime) -> list[str]:
    """Return a list of problems for one file's header and rows (empty when valid)."""
    problems: list[str] = []
    if header != COLUMNS:
        return [f"{name}: header must be exactly {','.join(COLUMNS)}"]
    stem = Path(name).stem
    seen: set[str] = set()
    for i, r in enumerate(rows, start=2):
        where = f"{name}:{i}"
        if r["platform"] not in PLATFORMS:
            problems.append(f"{where}: platform {r['platform']!r} not in {sorted(PLATFORMS)}")
            continue
        if stem != f"{r['platform']}_{r['handle']}":
            problems.append(f"{where}: file name does not match platform_handle "
                            f"{r['platform']}_{r['handle']}")
        if not r["post_id"].isdigit():
            problems.append(f"{where}: post_id must be digits, got {r['post_id']!r}")
        elif r["post_id"] in seen:
            problems.append(f"{where}: duplicate post_id {r['post_id']}")
        seen.add(r["post_id"])
        m = URL_RE[r["platform"]].match(r["url"])
        if not m:
            problems.append(f"{where}: url is not a {r['platform']} post URL")
        elif m.groups()[-1] != r["post_id"]:
            problems.append(f"{where}: post_id differs from the id in the url")
        created = _parse_ts(r["created_at_utc"])
        collected = _parse_ts(r["collected_at_utc"])
        if created is None:
            problems.append(f"{where}: created_at_utc must look like 2025-03-02T15:24:07Z")
        elif not EARLIEST <= created <= now:
            problems.append(f"{where}: created_at_utc {r['created_at_utc']} is out of range")
        if collected is None:
            problems.append(f"{where}: collected_at_utc must look like 2025-03-02T15:24:07Z")
        elif created is not None and collected < created:
            problems.append(f"{where}: collected before it was created")
        if r["kind"] not in KINDS:
            problems.append(f"{where}: kind {r['kind']!r} not in {sorted(KINDS)}")
        elif r["kind"] in ("repost", "quote") and not r["quoted_or_reposted_handle"]:
            problems.append(f"{where}: {r['kind']} needs quoted_or_reposted_handle")
        if r["has_media"] not in ("true", "false"):
            problems.append(f"{where}: has_media must be true or false")
        if r["kind"] != "repost" and not r["text"].strip() and r["has_media"] == "false":
            problems.append(f"{where}: empty text with no media")
    return problems


def check_file(path: Path, now: datetime | None = None) -> list[str]:
    now = now or datetime.now(UTC)
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        rows = list(reader) if header == COLUMNS else []
    return check_rows(path.name, list(header), rows, now)


def main(argv: list[str]) -> int:
    files = [Path(a) for a in argv] or sorted(POSTS.glob("*.csv"))
    if not files:
        print("no CSV files found in", POSTS)
        return 0
    bad = 0
    for path in files:
        problems = check_file(path)
        if problems:
            bad += 1
            print("\n".join(problems[:50]))
            if len(problems) > 50:
                print(f"{path.name}: {len(problems) - 50} more problems not shown")
        else:
            n = sum(1 for _ in path.open(encoding="utf-8")) - 1
            print(f"{path.name}: OK ({n} posts)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
