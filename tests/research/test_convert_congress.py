from __future__ import annotations

import datetime as dt
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "convert_congress", ROOT / "research" / "politics" / "convert_congress.py")
cc = importlib.util.module_from_spec(_spec)
sys.modules["convert_congress"] = cc
_spec.loader.exec_module(cc)


def test_snowflake_time():
    # an id built from 2020-01-01T00:00:00.999Z truncates to the second
    tid = ((1577836800999 - cc.EPOCH_MS) << 22) + 12345
    assert cc.snowflake_time(str(tid)) == dt.datetime(2020, 1, 1, tzinfo=dt.UTC)
    assert cc.snowflake_time(str(((1577836800000 - cc.EPOCH_MS) << 22) + 5)) == dt.datetime(
        2020, 1, 1, tzinfo=dt.UTC)


def test_archive_kinds():
    assert cc.map_archive_text("RT @SECGov Today we charged")[:2] == ("repost", "SECGov")
    kind, h, own, media = cc.map_archive_text(
        "Exactly right. https://pbs.twimg.com/media/x.jpg QT @CFTC Bitcoin futures")
    own_text = "Exactly right. https://pbs.twimg.com/media/x.jpg"
    assert (kind, h, own, media) == ("quote", "CFTC", own_text, True)
    assert cc.map_archive_text("@SenWarren thanks for this")[0] == "reply"
    k, h, own, media = cc.map_archive_text("Crypto needs rules.")
    assert (k, h, own, media) == ("original", "", "Crypto needs rules.", False)
    # a retweet of a quote stays a repost
    assert cc.map_archive_text("RT @a hi QT @b there")[:2] == ("repost", "a")


def test_trump_kinds():
    assert cc.map_trump_text("RT @WhiteHouse: great day")[:2] == ("repost", "WhiteHouse")
    assert cc.map_trump_text("@FoxNews wrong!")[0] == "reply"
    assert cc.map_trump_text("So true https://twitter.com/GOP/status/123")[:2] == (
        "quote", "GOP")
    assert cc.map_trump_text("See https://twitter.com/realDonaldTrump/status/1")[0] == (
        "original")


def test_selection_has_no_vp_account():
    handles = [h for v in cc.SELECTED.values() for h in v[3]]
    assert "VP" not in handles
    assert len(handles) == len(set(handles))
    assert cc.SELECTED["Kamala Harris"][4] == dt.datetime(2021, 1, 19, tzinfo=dt.UTC)
