# X collection plan (a short supplement, not the main data)

The analysis runs on free, complete data: Trump's Truth Social archive (2022-02 to
2026-11), his 2020 tweets, and the Congress tweet archive (to 2023-07-11). Manual
collection only fills a few targeted gaps, so keep it small. Same rules, file format and
pushing as `CLAUDE_DESKTOP_PROMPT.md`: exact UTC times from the `<time datetime>`
attribute, one `x_<handle>.csv` per account, validate, push to the `x-posts` branch,
never to main, slow pace, stop on any rate limit.

## 1. Finish what is nearly done

| handle | window |
|---|---|
| EricTrump | finish 2026-03 to 2026-11; skip the re-checks of earlier months |

**Stop DonaldJTrumpJr** beyond 2025-01 to 2026-11 (about 52,500 posts in total is too
many for manual collection). If his 2025 to 2026 posts are already partly collected,
push what exists and record the gaps.

## 2. A few low-volume, crypto-relevant accounts, 2025-01 to 2026-11 only

| handle | who | notes |
|---|---|---|
| worldlibertyfi | World Liberty Financial | Trump-family crypto project |
| GetTrumpMemes | $TRUMP memecoin | official account |
| SenLummis | Cynthia Lummis | Bitcoin reserve bill |
| SenatorHagerty | Bill Hagerty | stablecoin bill |
| SenWarren | Elizabeth Warren | leading critic |
| HesterPeirce | SEC commissioner, crypto task force lead | verify handle |

That is the whole list. Anything else is optional and only if time allows.

## Not needed

- Trump on X or Truth Social, and Congress before 2023-07-11: already covered by free archives.
- High-volume accounts (DavidSacks, elonmusk, POTUS, WhiteHouse, JDVance): too large to
  collect by hand.
