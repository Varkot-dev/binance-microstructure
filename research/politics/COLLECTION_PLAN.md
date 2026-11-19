# X collection plan (read this before collecting)

Work top to bottom. Same rules, file format and pushing as `CLAUDE_DESKTOP_PROMPT.md`:
exact UTC times from the `<time datetime>` attribute, one `x_<handle>.csv` per account,
validate, push to the `x-posts` branch after each account (or every 30 minutes), never
to main. Confirm each handle is the right person before collecting; if a handle is
wrong or missing, note it in `coverage.csv` and move on.

**Why this order:** the free Congress archive already covers members of Congress up to
2023-07-11, and Trump's Truth Social posts are covered to 2026-11. The gaps are the Trump
family, the administration, regulators, and everyone after mid-2023. Accounts that post
rarely but matter for crypto come first because they are fast to collect and each post
counts.

## In progress (keep going)

| handle | window |
|---|---|
| EricTrump | finish 2026-03 to 2026-11, then the re-checks |
| DonaldJTrumpJr | 2023-01 to 2026-11 (large; 10-day windows) |

## Tier 1: crypto policy, 2025-01 to 2026-11 (do these next)

| handle | who | notes |
|---|---|---|
| worldlibertyfi | World Liberty Financial | Trump-family crypto project |
| GetTrumpMemes | $TRUMP memecoin | official account |
| DavidSacks | White House AI and crypto czar | |
| SECGov | U.S. SEC | |
| HesterPeirce | SEC commissioner, crypto task force lead | verify handle |
| SenLummis | Cynthia Lummis | Bitcoin reserve bill |
| SenatorHagerty | Bill Hagerty | stablecoin bill |
| SenatorTimScott | Tim Scott | Senate Banking chair from 2025 |
| RepFrenchHill | French Hill | House Financial Services chair from 2025; verify handle |
| SenWarren | Elizabeth Warren | leading critic |
| JDVance | JD Vance | Vice President |
| WhiteHouse | White House | official statements |
| POTUS | Office of the President | |

## Tier 2: the Biden era and the bridge from 2023-07 to 2025-01

The Congress archive stops on 2023-07-11; these fill 2023-07-12 to 2025-01-20.

| handle | who | window |
|---|---|---|
| JoeBiden | Joe Biden | 2023-07-12 to 2025-01-20 |
| POTUS46Archive | Biden-era presidential account | 2023-07-12 to 2025-01-20; verify handle |
| GaryGensler | SEC chair until January 2025 | 2023-07-12 to 2025-01-20 |
| SECGov | U.S. SEC | 2023-07-12 to 2024-12-31 |
| SenWarren | Elizabeth Warren | 2023-07-12 to 2024-12-31 |
| SenLummis | Cynthia Lummis | 2023-07-12 to 2024-12-31 |
| SenatorHagerty | Bill Hagerty | 2023-07-12 to 2024-12-31 |
| PatrickMcHenry | House Financial Services chair | 2023-07-12 to 2025-01-03 |
| RepMaxineWaters | Maxine Waters | 2023-07-12 to 2024-12-31 |
| KamalaHarris | Kamala Harris | 2024-07-01 to 2024-11-30 (campaign) |

## Tier 3: comparisons (only after tiers 1 and 2)

| handle | who | window | why |
|---|---|---|---|
| BarackObama | Barack Obama | 2023-01 to 2026-11 | negative control: should show no effect |
| elonmusk | Elon Musk | 2025-01 to 2025-06 only | separate comparison; he posts constantly |

## Not needed

- `realDonaldTrump` on X and Truth Social: already covered by public archives.
- Members of Congress before 2023-07-11: already covered by the Congress archive.
- Likes, views, replies by others, images: not used.
