"""Convert the congresstweets archive and Trump's 2020 tweets into posts/ CSV files.

Implements the mapping fixed in `PREREGISTRATION_ADDENDUM_CONGRESS.md` (written and
hashed before any tweet was loaded). Run from the repository root:

    PYTHONPATH=src .venv/bin/python research/politics/convert_congress.py

Inputs (git-ignored): data/politics/raw/congresstweets/repo/data/2020-*.json to
2023-07-11.json (alexlitel/congresstweets, commit f5c837de11a6), the account metadata
data/politics/raw/congresstweets/automator/data/historical-users-filtered.json
(alexlitel/congresstweets-automator, commit 002e949c8534), and
data/politics/raw/hershey_trump_twitter/realDonaldTrump_in_office.csv. Outputs:
posts/x_<screen_name>.csv per selected account (text, git-ignored), x_realDonaldTrump.csv,
and a summary printed as JSON (rows per kind, drops, time-check disagreements, months
without posts) for coverage.csv.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RAW = ROOT / "data" / "politics" / "raw"
TWEETS = RAW / "congresstweets" / "repo" / "data"
META = RAW / "congresstweets" / "automator" / "data" / "historical-users-filtered.json"
HERSHEY = RAW / "hershey_trump_twitter" / "realDonaldTrump_in_office.csv"
POSTS = HERE / "posts"
COLUMNS = ["platform", "handle", "post_id", "url", "created_at_utc", "text", "kind",
           "quoted_or_reposted_handle", "has_media", "collected_at_utc"]
START = dt.datetime(2020, 1, 1, tzinfo=dt.UTC)
END = dt.datetime(2023, 7, 12, tzinfo=dt.UTC)  # exclusive: through 2023-07-11 23:59:59
TRUMP_END = dt.datetime(2021, 1, 9, tzinfo=dt.UTC)
EPOCH_MS = 1288834974657

# Selection of the addendum, section (b): metadata name -> (accounts.csv person, group,
# role, accounts used, last UTC instant used or None).
SELECTED = {
    "Mike Crapo": ("Mike Crapo", "republicans", "Senate Banking chair 2020",
                   ["MikeCrapo", "crapoforsenate"], None),
    "Sherrod Brown": ("Sherrod Brown", "democrats",
                      "Senate Banking ranking 2020, chair 2021 to 2023",
                      ["SenSherrodBrown", "SherrodBrown"], None),
    "Pat Toomey": ("Pat Toomey", "republicans", "Senate Banking ranking 2021 to 2022",
                   ["SenToomey", "PatToomey"], None),
    "Tim Scott": ("Tim Scott", "republicans", "Senate Banking ranking 2023",
                  ["SenatorTimScott", "votetimscott", "TimScottSC"], None),
    "Maxine Waters": ("Maxine Waters", "democrats", "HFSC chair 2020 to 2022, ranking 2023",
                      ["RepMaxineWaters", "MaxineWaters"], None),
    "Patrick McHenry": ("Patrick McHenry", "republicans",
                        "HFSC ranking 2020 to 2022, chair 2023",
                        ["PatrickMcHenry", "McHenryCampaign"], None),
    "Pat Roberts": ("Pat Roberts", "republicans", "Senate Agriculture chair 2020",
                    ["SenPatRoberts", "PatRoberts"], None),
    "Debbie Stabenow": ("Debbie Stabenow", "democrats",
                        "Senate Agriculture ranking 2020, chair 2021 to 2023",
                        ["SenStabenow", "stabenow"], None),
    "John Boozman": ("John Boozman", "republicans",
                     "Senate Agriculture ranking 2021 to 2023",
                     ["JohnBoozman", "Boozman4AR"], None),
    "Collin Peterson": ("Collin Peterson", "democrats", "House Agriculture chair 2020",
                        ["collinpeterson"], None),
    "Mike Conaway": ("Mike Conaway", "republicans", "House Agriculture ranking 2020",
                     ["ConawayTX11"], None),
    "David Scott": ("David Scott", "democrats",
                    "House Agriculture chair 2021 to 2022, ranking 2023",
                    ["repdavidscott", "Electdavidscott"], None),
    "Glenn Thompson": ("Glenn Thompson", "republicans",
                       "House Agriculture ranking 2021 to 2022, chair 2023",
                       ["CongressmanGT", "GT_TeamGT"], None),
    "Mitch McConnell": ("Mitch McConnell", "republicans",
                        "Senate majority leader 2020, minority leader 2021 to 2023",
                        ["LeaderMcConnell", "McConnellPress", "SRCC", "Team_Mitch"], None),
    "Chuck Schumer": ("Chuck Schumer", "democrats",
                      "Senate minority leader 2020, majority leader 2021 to 2023",
                      ["SenSchumer", "chuckschumer"], None),
    "Steny Hoyer": ("Steny Hoyer", "democrats", "House majority leader 2020 to 2022",
                    ["LeaderHoyer", "StenyHoyer"], None),
    "Kevin McCarthy": ("Kevin McCarthy", "republicans", "House minority leader 2020 to 2022",
                       ["GOPLeader", "kevinomccarthy"], None),
    "Steve Scalise": ("Steve Scalise", "republicans", "House majority leader 2023",
                      ["SteveScalise", "SteveScaliseGOP"], None),
    "Hakeem Jeffries": ("Hakeem Jeffries", "democrats", "House minority leader 2023",
                        ["RepJeffries", "hakeemjeffries"], None),
    "Cynthia M. Lummis": ("Cynthia Lummis", "republicans", "accounts.csv member",
                          ["SenLummis", "CynthiaMLummis"], None),
    "Bill Hagerty": ("Bill Hagerty", "republicans", "accounts.csv member",
                     ["SenatorHagerty", "BillHagertyTN"], None),
    "Elizabeth Warren": ("Elizabeth Warren", "democrats", "accounts.csv member",
                         ["SenWarren", "ewarren"], None),
    "Kamala Harris": ("Kamala Harris", "democrats", "accounts.csv member, senator to 2021-01-18",
                      ["KamalaHarris"], dt.datetime(2021, 1, 19, tzinfo=dt.UTC)),
}

RT_RE = re.compile(r"^RT @(\w+)")
QT_RE = re.compile(r" QT @(\w+) ")
MEDIA_RE = re.compile(r"pbs\.twimg\.com/(media|ext_tw_video_thumb|tweet_video_thumb)/|"
                      r"video\.twimg\.com/")
TW_STATUS_RE = re.compile(r"twitter\.com/(\w+)/status(?:es)?/\d+", re.IGNORECASE)


def snowflake_time(tweet_id: str) -> dt.datetime:
    """UTC creation time from a Twitter snowflake id, truncated to the second."""
    ms = (int(tweet_id) >> 22) + EPOCH_MS
    return dt.datetime.fromtimestamp(ms // 1000, tz=dt.UTC)


def fmt(ts: dt.datetime) -> str:
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def map_archive_text(text: str) -> tuple[str, str, str, bool]:
    """(kind, quoted_or_reposted_handle, own text, has_media) for a congresstweets text."""
    m = RT_RE.match(text)
    if m:
        return "repost", m.group(1), text, bool(MEDIA_RE.search(text))
    q = QT_RE.search(text)
    if q:
        own = text[:q.start()]
        return "quote", q.group(1), own, bool(MEDIA_RE.search(own))
    kind = "reply" if text.startswith("@") else "original"
    return kind, "", text, bool(MEDIA_RE.search(text))


def map_trump_text(text: str) -> tuple[str, str, bool]:
    """(kind, handle, has_media) for a Hershey Trump tweet text."""
    m = RT_RE.match(text)
    if m:
        return "repost", m.group(1), "pic.twitter.com" in text
    if text.startswith("@"):
        return "reply", "", "pic.twitter.com" in text
    for h in TW_STATUS_RE.findall(text):
        if h.lower() != "realdonaldtrump":
            return "quote", h, "pic.twitter.com" in text
    return "original", "", "pic.twitter.com" in text


def _clean(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n")


def _write(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)


def _ok(row: dict) -> bool:
    """False for rows the contract rejects (empty non-repost text without media)."""
    return row["kind"] == "repost" or bool(row["text"].strip()) or row["has_media"] == "true"


def selected_accounts(meta_path: Path = META) -> dict[str, dict]:
    """{user_id: {screen_name, person, group, role, until}} from the metadata."""
    meta = {x["name"]: x for x in json.loads(meta_path.read_text(encoding="utf-8"))}
    out = {}
    for name, (person, group, role, handles, until) in SELECTED.items():
        accs = {a["screen_name"]: a for a in meta[name]["accounts"]}
        for h in handles:
            a = accs[h]
            out[a["id"]] = {"screen_name": h, "person": person, "group": group,
                            "role": role, "type": a["account_type"], "until": until}
    return out


def convert_congress(collected: str) -> dict:
    accs = selected_accounts()
    rows: dict[str, dict[str, dict]] = {a["screen_name"]: {} for a in accs.values()}
    stats = {"files": 0, "time_mismatch_60s": 0, "dropped_empty": 0, "dup": 0,
             "outside": 0}
    files = sorted(p for p in TWEETS.glob("*.json") if "2020-01-01" <= p.stem <= "2023-07-11")
    # 2019-12-31 can hold tweets after 2020-01-01 00:00 UTC (Eastern day boundary)
    prev = TWEETS / "2019-12-31.json"
    if prev.exists():
        files.insert(0, prev)
    for p in files:
        stats["files"] += 1
        for t in json.loads(p.read_text(encoding="utf-8")):
            a = accs.get(str(t.get("user_id")))
            if a is None:
                continue
            ts = snowflake_time(t["id"])
            if not START <= ts < END or (a["until"] is not None and ts >= a["until"]):
                stats["outside"] += 1
                continue
            try:
                at = dt.datetime.fromisoformat(t["time"]).astimezone(dt.UTC)
                if abs((at - ts).total_seconds()) > 60:
                    stats["time_mismatch_60s"] += 1
            except (KeyError, ValueError):
                stats["time_mismatch_60s"] += 1
            h = a["screen_name"]
            if t["id"] in rows[h]:
                stats["dup"] += 1
                continue
            kind, other, own, media = map_archive_text(t["text"] or "")
            row = {"platform": "x", "handle": h, "post_id": t["id"],
                   "url": f"https://x.com/{h}/status/{t['id']}", "created_at_utc": fmt(ts),
                   "text": _clean(own), "kind": kind, "quoted_or_reposted_handle": other,
                   "has_media": "true" if media else "false", "collected_at_utc": collected}
            if not _ok(row):
                stats["dropped_empty"] += 1
                continue
            rows[h][t["id"]] = row
    per = {}
    for h, d in rows.items():
        rs = sorted(d.values(), key=lambda r: (r["created_at_utc"], r["post_id"]))
        if rs:  # an account with no tweet in the period gets no file
            _write(POSTS / f"x_{h}.csv", rs)
        a = next(v for v in accs.values() if v["screen_name"] == h)
        per[h] = _summary(rs) | {"person": a["person"], "group": a["group"],
                                 "role": a["role"], "type": a["type"]}
    return {"stats": stats, "accounts": per}


def convert_trump(collected: str) -> dict:
    rows = {}
    stats = {"outside": 0, "dropped_empty": 0, "dup": 0}
    with HERSHEY.open(newline="", encoding="utf-8") as f:
        rd = csv.reader(f, skipinitialspace=True)
        next(rd)
        for rec in rd:
            if len(rec) < 4:
                continue
            m = re.search(r"/status/(\d+)", rec[2])
            if not m:
                continue
            pid = m.group(1)
            ts = snowflake_time(pid)
            if not START <= ts < TRUMP_END:
                stats["outside"] += 1
                continue
            if pid in rows:
                stats["dup"] += 1
                continue
            text = rec[3]
            kind, other, media = map_trump_text(text)
            row = {"platform": "x", "handle": "realDonaldTrump", "post_id": pid,
                   "url": f"https://x.com/realDonaldTrump/status/{pid}",
                   "created_at_utc": fmt(ts), "text": _clean(text), "kind": kind,
                   "quoted_or_reposted_handle": other,
                   "has_media": "true" if media else "false", "collected_at_utc": collected}
            if not _ok(row):
                stats["dropped_empty"] += 1
                continue
            rows[pid] = row
    rs = sorted(rows.values(), key=lambda r: (r["created_at_utc"], r["post_id"]))
    _write(POSTS / "x_realDonaldTrump.csv", rs)
    return {"stats": stats, "summary": _summary(rs)}


def _summary(rs: list[dict]) -> dict:
    kinds: dict[str, int] = {}
    months: dict[str, int] = {}
    for r in rs:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
        months[r["created_at_utc"][:7]] = months.get(r["created_at_utc"][:7], 0) + 1
    return {"rows": len(rs), "kinds": kinds,
            "first": rs[0]["created_at_utc"] if rs else None,
            "last": rs[-1]["created_at_utc"] if rs else None, "months": months}


def main() -> int:
    collected = fmt(dt.datetime.now(dt.UTC))
    out = {"congress": convert_congress(collected), "trump": convert_trump(collected)}
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
