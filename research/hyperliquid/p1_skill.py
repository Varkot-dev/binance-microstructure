"""Project 1: a luck-adjusted Hyperliquid leaderboard (skill or luck?).

The design is fixed in `research/hyperliquid/PREREGISTRATION_P1.md`, locked on the date in
`research/hyperliquid/P1_LOCK.txt` before any cohort return or performance statistic was
computed. This script refuses to run if that file has changed, and prints its sha256 in every
output. Any analysis not specified there is labelled exploratory.

Data comes from the weekly crawl (`src/microstructure/hyperliquid/crawl.py`, release assets
`hl-p1-pass-YYYYMMDD`). Only totals and shares are reported; no address is named as skilled,
unskilled or suspicious (plan section 11).

    uv run python research/hyperliquid/p1_skill.py check

The analysis steps (formation-window bootstrap, FDR shares, holding-window test) are added
here after the holding window's data exist, each implementing the locked section it cites.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PREREG = HERE / "PREREGISTRATION_P1.md"
PREREG_SHA = "f5dcd9e48f0c3d61d1fe4414178c4f79faf9703163b592cde216596b21e378c4"
COHORT_SHA256 = "ac669f966b7ddbd4a4e5aa8ac50781c9a8d9f51a071ac3c062812046217c1a37"
FORMATION_MS = 1_795_132_731_000  # T0 = 2026-11-19T23:58:51Z
LOCK_UTC = "2026-11-22T21:21:00Z"
HOLDING_START_UTC = "2026-11-23T00:00:00Z"  # D1: 00:00 UTC on the day after the lock (plan section 7.1)


def prereg_sha(path: Path = PREREG) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_prereg(path: Path = PREREG) -> str:
    got = prereg_sha(path)
    if got != PREREG_SHA:
        raise SystemExit(f"{path.name} changed since it was locked (sha256 {got}, locked "
                         f"{PREREG_SHA}); refusing to run")
    return got


def main(argv: list[str]) -> None:
    sha = check_prereg()
    print(f"pre-registration sha256 {sha} (locked {LOCK_UTC}, holding window from "
          f"{HOLDING_START_UTC})")
    if argv[:1] != ["check"]:
        raise SystemExit("only `check` exists so far; the analysis is added after the holding "
                         "window's data exist")


if __name__ == "__main__":
    main(sys.argv[1:])
