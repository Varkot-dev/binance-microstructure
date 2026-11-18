# Post data sources for the politics event study

Feasibility notes, written 2026-11-18. Question: where can we get complete, timestamped
posts by Trump, his children, other politicians and officials, legally and from this
machine, for a minute-level event study on Binance USDT-M futures (2019-09 onward)?

Tags: [V] verified this session (opened, cloned or downloaded and checked), [S] secondary
(search snippet or a third party's description, not opened), [I] inference.

## Summary

- **Trump on Truth Social is solved for a first version.** [V] The GitHub repo
  `mickpletcher/truthsocial-archiver` holds 38,076 posts from 2022-02-14 to 2026-11-17,
  updated daily, with UTC timestamps to the millisecond. It mirrors CNN's archive
  (`ix.cnn.io`), which is blocked here, and GitHub is the only route that works. It agrees
  post for post with the older CC0 `stiles/trump-truth-social-archive`, which stops on
  2025-10-25. Both are downloaded to `data/politics/raw/`.
- **Trump on Twitter, 2009 to 2021-01-08, is solved.** [V] `MarkHershey/CompleteTrumpTweetsArchive`
  (MIT) has 54,324 tweets. Its `Time` column has a **timezone bug** (mostly UTC+8, some rows in
  US time), so take the time from the tweet ID instead (Snowflake, exact to the millisecond).
  This covers 13,135 tweets from 2019-09 onward, which overlaps the Binance futures data.
- **Everyone else on X (Eric, Don Jr., Vance, Musk, Sacks, Gensler, Atkins, Warren, Congress)
  has no complete free dataset reachable from here.** The best free items are frozen:
  `alexlitel/congresstweets` (all of Congress, 2017-06-21 to 2023-07-11, includes Warren) [V],
  and an unlicensed Musk dump on GitHub (55,099 posts to 2025-04-13) [V]. After mid-2023 the
  only full route is the paid X API [S], or academic datasets on hosts blocked here
  (Zenodo, Harvard Dataverse) [V for the blocks].
- **Official actions (executive orders, signings) come with dates only.** The Federal Register
  gives signing and publication **dates**, not times [S]. For a minute-level study, the time
  of an official action usually has to come from Trump's own post announcing it, or from the
  first X post by an official (for example Sacks on the Bitcoin reserve order) [I].
- **Nothing found is labelled for crypto relevance at post level**, except a third-party repo
  (`Ifazawezk/trump-crypto-events`, MIT) with 14 curated events at day precision [V]. A keyword
  pass over the Truth Social archive finds 49 crypto posts, listed by hand below [V].

## Reachability from this machine (curl, 2026-11-18)

All "000" results are the session proxy refusing CONNECT (it reports `connect_rejected`,
gateway 403). No workaround was attempted.

| Host | Result |
|---|---|
| github.com (git clone of public repos) | works [V] |
| api.github.com | 200 [V]; per-repo API calls refused by session policy (403), so repos were inspected by clone |
| codeload.github.com (zip download) | 403 [V] |
| pypi.org, data.binance.vision | 200 [V] |
| trumpstruth.org, truthsocial.com API, ix.cnn.io, stilesdata.com | 000 blocked [V] |
| huggingface.co, kaggle.com, zenodo.org, dataverse.harvard.edu, osf.io, figshare.com, archive.org | 000 blocked [V] |
| x.com, api.x.com, api.twitter.com, public.api.bsky.app | 000 blocked [V] |
| federalregister.gov, whitehouse.gov, govinfo.gov, presidency.ucsb.edu, sec.gov, congress.gov | 000 blocked [V] |
| thetrumparchive.com, capitolreleases.com, coinglass.com | 000 blocked [V] |

## Source table

| # | Source | Covers | Timestamp precision, timezone | Range | Size | Licence / terms | Reachable | Quality notes |
|---|---|---|---|---|---|---|---|---|
| 1 | https://github.com/mickpletcher/truthsocial-archiver , file `docs/data/posts.jsonl` (commit 334073464e27) | @realDonaldTrump Truth Social, posts and re-truths | millisecond, UTC (`Z`) [V]; matches the Mastodon-style ID (id >> 16 = ms) to within 1 s, median 1 ms [V] | 2022-02-14 15:54:32 to 2026-11-17 03:07:24 UTC [V] | 40.2 MB, 38,076 rows, 0 duplicate IDs [V] | MIT for code; README says posts and media keep their own rights; upstream data is CNN's [V] | yes, via git clone [V] | Built from a CNN snapshot on 2026-08-20 (35,619 rows carry that `scraped_at`), then appended daily, so posts deleted before 2026-08-20 are probably missing and later deletions are kept [V for scraped_at, I for deletions]. `in_reply_to_id` and `quote_id` are always empty [V]. 20% of posts have empty text (media only) [V]. 892 posts have mojibake (`â` for curly quotes) [V]. Re-truths appear as text starting "RT @" or "RT: url" [V]. No edit history [I]. |
| 2 | https://github.com/stiles/trump-truth-social-archive , `data/truth_archive.json` and `.csv` (commit 40a883423715) | same account | millisecond, UTC [V] | 2022-02-14 to 2025-10-25, plus 60 posts in 2026-04/05 from a one-off run [V] | 15.6 MB JSON, 29,469 rows [V] | CC0 1.0 [V] | yes, via git clone [V] | README: workflow disabled 2025-10-26, points to CNN's feed instead [V]. Gap 2025-10-25 to 2026-04-27 [V]. Every one of its IDs is in source 1; source 1 has 11 posts before 2025-10-25 that it lacks [V]. Scraped hourly to four-hourly, so posts deleted within hours may be missing in both [I]. |
| 3 | https://github.com/a850762312/trump-truth-social-archive (fork of 2) | same | same | stops 2025-07-05 despite "Auto update" commits to 2026-11-08 [V] | 14.4 MB, 27,570 rows [V] | CC0 [V] | yes [V] | Stale; not used. |
| 4 | CNN archive https://ix.cnn.io/data/truth-social/truth_archive.json (also .csv, .parquet) | same, updated every 5 minutes per stiles README [V for README text] | ms UTC [I, same schema] | 2022 to now [S] | unknown | no terms found [S] | no, blocked [V] | The upstream of source 1. Would need a network allowance. |
| 5 | https://trumpstruth.org (Trump's Truth) | Truth Social archive with deletion tracking [S] | unknown | 2022 to now [S] | unknown | unknown | no, blocked [V] | Not tested. Reported to lack engagement counts [S]. |
| 6 | American Presidency Project, daily "Truth Social posts" pages, https://www.presidency.ucsb.edu/documents/app-attributes/truth-social | transcribed posts per day [S] | per post time unclear [S] | 2025 onward [S] | HTML | academic site terms | no, blocked [V] | Useful as a cross-check for deletions, not as a feed. |
| 7 | Hugging Face `notmooodoo9/TrumpsTruthSocialPosts` | about 18,476 posts plus 31.8M comments, timestamps decoded from IDs [S, from a blog] | unknown | unknown | unknown | CC BY 4.0 [S] | no, huggingface.co blocked [V] | Unverified; the card was never opened. |
| 8 | Apify Truth Social actors (many) | any Truth Social account | ms UTC [I] | live | per run | paid, roughly $1 to $4 per 1,000 results [S] | no [I] | Only route found for Eric Trump, Don Jr. or Vance on Truth Social [I]. Terms of Truth Social apply. |
| 9 | https://github.com/MarkHershey/CompleteTrumpTweetsArchive (commit 8be27c439d0c) | @realDonaldTrump Twitter, including later-deleted tweets per README [V for README] | `Time` column is minute precision with a **mixed timezone**: in-office file mostly UTC+8 (22,177 rows) and 898 rows at UTC-5 or UTC-6; before-office file UTC-5 or UTC-6 [V by comparing with tweet IDs]. Use the Snowflake ID: ms UTC = (id >> 22) + 1288834974657 [V] | 2009-05-04 to 2021-01-08 [V] | 13.2 MB, 31,249 + 23,075 rows; 10 duplicate IDs in the in-office file [V] | MIT [V] | yes, via git clone [V] | Text truncated in places; no retweet flag [I]. The 2019-07-12 Bitcoin thread is row 8812, `Time` 08:15 but ID time 00:15:22 UTC [V]. |
| 10 | Trump Twitter Archive, https://www.thetrumparchive.com | same as 9, the standard source | to the second [S] | 2009 to 2021-01-08 [S] | ~56k tweets [S] | FAQ allows download, "credit the site however you'd like" [S, quoted by repo 13] | no, blocked [V] | Code at https://github.com/bpb27/tta-elastic; older data repo https://github.com/bpb27/trump_tweet_data_archive (3.3 GB, last push 2020-04) [V for repo metadata]. |
| 11 | https://github.com/alexlitel/congresstweets (commit f5c837de11a6) | daily tweets of 1,000+ congressional campaign, office, committee and party accounts [V README] | to the second, US Eastern with offset, e.g. `2023-07-11T00:57:53-04:00` [V] | 2017-06-21 to 2023-07-11, 2,201 daily JSON files [V] | repo about 1.2 GB [V metadata] | MIT [V] | yes, via git clone, but large [V] | Warren (@SenWarren) present, 3 to 18 tweets per sampled day [V]. Ends when free Twitter API access ended [I]. Not downloaded (over 50 MB); a sparse fetch of 2019-09 to 2023-07 is feasible. Older months are on archive.org (blocked). |
| 12 | Musk dump in https://github.com/MagdalenaRomaniecka/Decompiling-MuskOS , `data/all_musk_posts (1).zip` | @elonmusk posts and replies | second, UTC, matches the Snowflake ID to within 1 s [V] | 2010-06-04 to 2025-04-13 [V] | 11.9 MB zip, 56 MB CSV, 55,099 rows [V] | **no licence**; README says the CSV came from Google Drive; schema looks like an Apify tweet scraper export [V for schema, I for origin] | yes [V] | Kept in scratchpad only, not in `data/`. Only 1,092 retweets flagged, so retweets are likely incomplete [V count, I meaning]. Read `id` as a string: parsing it as a number loses digits [V]. |
| 13 | Zenodo record 15062791 (Musk tweet history 2010-06-04 to 2025-01-24, 60,567 tweets, emotion annotations) | Musk | unknown | as stated [S] | unknown | unknown | no, blocked [V] | |
| 14 | Congressional Tweets, Zenodo 8215566 (Miller and Jiang) | official accounts of the 117th Congress | unknown | 2020-01 to 2022-06, 1,048,515 rows [S] | unknown | unknown | no, blocked [V] | |
| 15 | DAPR database (Desmarais et al., Scientific Data 12:1556, 2025), Harvard Dataverse | 28,834 officials, 5.77M X posts, 2020-01 to 2024-12 [S] | weekly aggregates in the public release [S] | 2020 to 2024 [S] | large | unknown | no, blocked [V] | Weekly aggregation would make it useless for minute-level timing even if reachable [I]. |
| 16 | X API (pay-per-use since 2026-02-06) | any public account | ms UTC [I] | full archive if the search endpoint is available on pay-per-use; official docs list it, some blogs say Enterprise only [S] | about $0.005 per post read, cap 2M or 3M reads per month [S] | X developer terms | no, api.x.com blocked [V] | Rough cost for 10 accounts over 2019-09 to 2026: Musk alone is about 17k posts in 2024 [V from source 12]; all others together likely under 50k [I]; so roughly 150k reads, about $750 [I]. Needs a key, money and a network allowance. |
| 17 | Federal Register API, https://www.federalregister.gov/developers/documentation/api/v1 | executive orders with `signing_date` and `publication_date` | **day** only for both [S]; public inspection filing has a time [I, unverified] | 1994 to now | small | public domain | no, blocked [V] | Signing time of day is not published; Trump's announcing post is the better clock [I]. |
| 18 | https://github.com/titaniumbones/download-exec-orders , `documents_scraped.json` | 54 EOs scraped from the American Presidency Project [V] | date string only ("February 05, 2025") [V] | 2025-01-20 to 2025-02-05 [V] | 425 KB | no licence [V] | yes [V] | Too short and day precision only. |
| 19 | https://github.com/Ifazawezk/trump-crypto-events (commit 091e45a2c910), `data/events.csv` | 14 curated crypto-politics events with source URLs [V] | day, except one 2019 tweet to the minute [V] | 2019-07 to 2026-05 [V] | 4 KB | MIT [V] | yes [V] | Prior work: daily event study found no detectable effect (mean CAR -0.44% over days 0 to +1, 95% CI -2.27% to 1.49%) [V README]. It omits Truth Social posts, so the minute-level post study is not a duplicate. |

## Ranked recommendation

1. **First version: Trump only, Truth Social 2022-02 to 2026-11 plus Twitter 2019-09 to
   2021-01.** Sources 1 and 9, both already in `data/politics/raw/`, both free, both with
   timestamps finer than a minute once tweet times are taken from IDs. Use source 2 (CC0) to
   cross-check overlap and to prefer for anything published from the data, since source 1's
   upstream (CNN) has no stated licence [I]. Expect about 51,000 posts in the Binance era, of
   which a few dozen are about crypto and many more about tariffs and the economy.
2. **Congress 2019-09 to 2023-07 (Warren and other Democrats and Republicans):** source 11 via
   a sparse git checkout of the needed months. Free, MIT, timestamps to the second. It
   ends 2023-07, before most of the crypto-policy period (2024 to 2026).
3. **Musk 2019-09 to 2025-04:** source 12 works technically but has no licence; use for
   exploration only, or ask the owner, or replace with the X API.
4. **Needs money and a network allowance:** X API for Eric Trump, Don Jr., Barron (no known
   public posting account found [I]), Vance, Sacks, Gensler, Atkins, Warren after 2023, and Musk
   after 2025-04 (about $750 estimate [I]); `api.x.com` would need allowing.
5. **Needs only a network allowance:** `ix.cnn.io` (fresher than GitHub's daily mirror and
   the upstream of source 1), `huggingface.co` (source 7), `zenodo.org` (sources 13, 14),
   `www.federalregister.gov` (source 17), `www.thetrumparchive.com` (source 10).

Caveat for every source: a post's `created_at` is when the platform stored it. Spread to
markets runs through alert bots and news wires, typically seconds to minutes later [I], so
the event window should start at `created_at` and allow a lag.

## Key events with times

Times from the Truth Social archive (source 1) are [V]: the post was found in the
downloaded file at that UTC time. Other times are as cited.

| Event | Time (UTC) | Source |
|---|---|---|
| Trump tweet thread "I am not a fan of Bitcoin..." | 2019-07-12 00:15:22 | tweet ID 1149472282584072192, source 9 [V] |
| Post "VERY POSITIVE AND OPEN MINDED TO CRYPTOCURRENCY COMPANIES" | 2024-05-25 19:13:35 | source 1 [V] |
| Bitcoin 2024 conference speech, Nashville ("THANK YOU, BITCOIN 2024!") | 2024-07-27 21:20:41 | source 1 [V] |
| World Liberty Financial promoted ("#WorldLibertyFi ... make America great again, this time with crypto") | 2024-09-30 15:11:13 | source 1 [V] |
| Paul Atkins nominated as SEC chair | 2024-12-04 17:47:48 | source 1 [V] |
| "CONGRATULATIONS BITCOINERS!!! $100,000!!!" | 2024-12-05 12:55:19 | source 1 [V] |
| David Sacks named White House AI and Crypto Czar | 2024-12-06 00:50:46 | source 1 [V] |
| **$TRUMP memecoin launch post** ("My NEW Official Trump Meme is HERE!") | 2025-01-18 02:00:51 (2025-01-17 21:00 ET) | source 1 [V] |
| $MELANIA launch, re-truthed by Trump | 2025-01-19 21:22:03 | source 1 [V] |
| EO 14178 on digital financial technology | 2025-01-23, day only | Federal Register via source 19 [V for the row, S for FR] |
| **Crypto strategic reserve post naming XRP, SOL, ADA** | 2025-03-02 15:24:20 (ID 114093526901586124) | source 1 [V] |
| Follow-up "And, obviously, BTC and ETH..." | 2025-03-02 17:11:00 | source 1 [V] |
| **Strategic Bitcoin Reserve EO 14233 signed** | 2025-03-06 evening ET; Sacks's X post reported at 00:11 ET 2025-03-07 (05:11 UTC) | Bitcoin in Action newsletter [S]; FR signing date 2025-03-06 [S] |
| White House Crypto Summit | 2025-03-07, day only | govinfo DCPD-202500341 via source 19 [S] |
| "THIS IS A GREAT TIME TO BUY!!! DJT" | 2025-04-09 13:37:01 | source 1 [V] |
| 90-day tariff pause and China tariff raise | 2025-04-09 17:18:40 | source 1 [V] |
| Senate passes GENIUS Act post | 2025-06-19 00:01:39 | source 1 [V] |
| "HAPPY CRYPTO WEEK!" | 2025-07-15 15:29:02 | source 1 [V] |
| GENIUS Act signed | 2025-07-18 (Trump post after the signing at 23:53:21 UTC) | source 1 [V]; date from whitehouse.gov via source 19 [S] |
| WLFI token becomes transferable | 2025-09-01, day only | WLF docs via source 19 [S] |
| **China "very strange things" post (first tariff threat)** | 2025-10-10 14:57:52 | source 1 [V] |
| **100% tariff on China post** | 2025-10-10 20:50:01 | source 1 [V]; record liquidations of about $19B reported that day [S, PYMNTS, Business Today] |
| Pardon of Changpeng Zhao | warrant 2025-10-21; public reports later | DOJ via source 19 [S] |
| Post attacking banks over the GENIUS Act | 2026-03-03 22:02:10 | source 1 [V] |
| EO 14405 on fintech regulation | 2026-05-19, day only | Federal Register via source 19 [S] |
| Post on Gensler and the "Anti-Crypto Army" | 2026-05-27 22:42:10 | source 1 [V] |
| Post urging the Senate to pass the CLARITY Act | 2026-07-13 14:26:03 | source 1 [V] |

## Files downloaded (git-ignored, `data/politics/raw/`)

| Path | Rows | Date range (UTC) | Licence |
|---|---|---|---|
| `pletcher_truth/posts.jsonl` | 38,076 | 2022-02-14 15:54:32 to 2026-11-17 03:07:24 | MIT code, content third party |
| `stiles_truth/truth_archive.json` and `.csv` | 29,469 | 2022-02-14 15:54:32 to 2026-05-02 23:12:54 (gap 2025-10-25 to 2026-04-27) | CC0 |
| `hershey_trump_twitter/realDonaldTrump_bf_office.csv` | 31,249 | 2009-05-04 to 2017-01-19 (use ID for time) | MIT |
| `hershey_trump_twitter/realDonaldTrump_in_office.csv` | 23,075 | 2017-01-20 to 2021-01-08 (use ID for time) | MIT |

Posts per year in `posts.jsonl`: 2022 3,889; 2023 9,905; 2024 10,587; 2025 6,229; 2026 7,466.
Only 2022-02 (1 post) and 2022-04 (8) have fewer than 30 posts a month; the account launched
in 2022-02 and was quiet until late April 2022 [V counts, S reason].
