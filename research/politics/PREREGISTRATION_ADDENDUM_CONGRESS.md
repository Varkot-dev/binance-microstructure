# C2 addendum: members of Congress from the congresstweets archive

Written 2026-11-18, **before any tweet of this extension has been loaded and before any
price has been looked at for it**. The only things read so far are the archive's README,
its account metadata (`data/historical-users-filtered.json` in
`alexlitel/congresstweets-automator`, commit `002e949c8534`) and the parser code that
formats tweet text (`src/twitter/parseTweet.js`). No daily tweet file has been opened.
The sha256 of this file is sent to the main session for commit before any analysis.
`PREREGISTRATION_RANKING.md` is not changed; this addendum only adds post files and
`accounts.csv` rows. Anything reported that is not specified here or there is labelled
**exploratory**.

## (a) Data source and period

- **Tweets of Congress**: `alexlitel/congresstweets` (MIT), commit `f5c837de11a6`,
  `data/YYYY-MM-DD.json` daily files (2017-06-21 to 2023-07-11), cloned with
  `GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1` into `data/politics/raw/congresstweets/`
  (git-ignored). Each tweet has `id`, `screen_name`, `user_id`, `time`, `link`, `text`,
  `source`.
- **Account metadata**: `historical-users-filtered.json` from
  `alexlitel/congresstweets-automator` commit `002e949c8534` (person name, chamber,
  party, and each account's numeric user id, screen name and type).
- **Trump's pre-2021 Twitter**: `data/politics/raw/hershey_trump_twitter/
  realDonaldTrump_in_office.csv` (MIT), already on disk.
- **Period of this extension**: the overlap of the archive with the ranking sample
  (2020-01-01 to 2026-10-31), that is tweets with a UTC time from 2020-01-01 00:00:00 to
  2023-07-11 23:59:59 (whatever the last daily file holds). For Trump's Twitter file:
  2020-01-01 00:00:00 UTC to the file's end (2021-01-08).
- **Time of each tweet**: from the tweet id (Twitter snowflake: milliseconds = (id >> 22)
  + 1288834974657, UTC), truncated to the second. For congresstweets the archive's own
  `time` field (US Eastern with offset) is converted to UTC only as a check; the number of
  disagreements over 60 seconds is reported. For the Trump file the `Time` column (mixed
  timezones) is not used.

## (b) Who is selected (fixed without looking at any tweet or outcome)

Rule: (1) the chair and the ranking member, at any time from 2020-01 to 2023-07, of the
Senate Banking Committee, the House Financial Services Committee, the Senate Agriculture
Committee and the House Agriculture Committee (CFTC oversight); (2) the Senate and House
majority leaders and minority leaders in that period (floor leaders; the Speaker is not a
floor leader and is not added for that role); (3) every member of Congress listed in
`accounts.csv` (anyone there who served in Congress at some time in the period); (4)
Donald Trump's pre-2021 tweets as a separate account row of the same person.

For each person, every account listed under that person in the archive metadata is used
(office and campaign), matched on the numeric `user_id`, not on the screen name. Each
account becomes `posts/x_<screen_name>.csv`, with an `accounts.csv` row mapping it to the
person, so all of a person's accounts are pooled into one post stream as
`PREREGISTRATION_RANKING.md` section 0 already specifies.

| person | role giving selection | group | accounts (metadata screen name, type) |
|---|---|---|---|
| Mike Crapo | Senate Banking chair 2020 | republicans | MikeCrapo (office), crapoforsenate (campaign) |
| Sherrod Brown | Senate Banking ranking 2020, chair 2021 to 2023 | democrats | SenSherrodBrown (office), SherrodBrown (campaign) |
| Pat Toomey | Senate Banking ranking 2021 to 2022 | republicans | SenToomey (office), PatToomey (campaign) |
| Tim Scott | Senate Banking ranking 2023 | republicans | SenatorTimScott (office), votetimscott (campaign), TimScottSC (campaign) |
| Maxine Waters | HFSC chair 2020 to 2022, ranking 2023 (also in accounts.csv) | democrats | RepMaxineWaters (office), MaxineWaters (campaign) |
| Patrick McHenry | HFSC ranking 2020 to 2022, chair 2023 | republicans | PatrickMcHenry (office), McHenryCampaign (campaign) |
| Pat Roberts | Senate Agriculture chair 2020 | republicans | SenPatRoberts (office), PatRoberts (campaign) |
| Debbie Stabenow | Senate Agriculture ranking 2020, chair 2021 to 2023 | democrats | SenStabenow (office), stabenow (campaign) |
| John Boozman | Senate Agriculture ranking 2021 to 2023 | republicans | JohnBoozman (office), Boozman4AR (campaign) |
| Collin Peterson | House Agriculture chair 2020 | democrats | collinpeterson (campaign) |
| Mike Conaway | House Agriculture ranking 2020 | republicans | ConawayTX11 (office) |
| David Scott | House Agriculture chair 2021 to 2022, ranking 2023 | democrats | repdavidscott (office), Electdavidscott (campaign) |
| Glenn Thompson | House Agriculture ranking 2021 to 2022, chair 2023 | republicans | CongressmanGT (office), GT_TeamGT (campaign) |
| Mitch McConnell | Senate majority leader 2020 to 2021-01, minority leader 2021 to 2023 | republicans | LeaderMcConnell (office), McConnellPress (office), SRCC (office), Team_Mitch (campaign) |
| Chuck Schumer | Senate minority leader 2020, majority leader 2021 to 2023 (also in accounts.csv) | democrats | SenSchumer (office), chuckschumer (campaign) |
| Steny Hoyer | House majority leader 2020 to 2022 | democrats | LeaderHoyer (office), StenyHoyer (campaign) |
| Kevin McCarthy | House minority leader 2020 to 2022 | republicans | GOPLeader (office), kevinomccarthy (campaign) |
| Steve Scalise | House majority leader 2023 | republicans | SteveScalise (office), SteveScaliseGOP (campaign) |
| Hakeem Jeffries | House minority leader 2023 | democrats | RepJeffries (office), hakeemjeffries (campaign) |
| Cynthia Lummis | accounts.csv (senator from 2021-01-03) | republicans | SenLummis (office), CynthiaMLummis (campaign) |
| Bill Hagerty | accounts.csv (senator from 2021-01-03) | republicans | SenatorHagerty (office), BillHagertyTN (campaign) |
| Elizabeth Warren | accounts.csv | democrats | SenWarren (office), ewarren (campaign) |
| Kamala Harris | accounts.csv (senator until 2021-01-18) | democrats | KamalaHarris (campaign), only tweets up to 2021-01-18 23:59:59 UTC |
| JD Vance | accounts.csv (senator from 2023-01-03) | republicans | none: not in the archive metadata, so no data |
| Donald Trump | separate row, pre-2021 Twitter | trump_family | realDonaldTrump, from the Hershey file, 2020-01-01 to 2021-01-08 |

Rules for the special cases, fixed now:

- **Kamala Harris**: selected as a member of Congress, so only her tweets while a
  senator are used (to 2021-01-18, the day she resigned). The metadata also lists `VP`
  (office) under her name; that account was Mike Pence's office account until
  2021-01-20 and hers as Vice President afterwards, never a congressional account of
  hers, so it is **not used**.
- **JD Vance**: in the rule but not followed by the archive; reported as "no data".
- **Barack Obama, Joe Biden** and the other non-members in `accounts.csv` are not
  members of Congress in the period and are not added by this addendum.
- **Donald Trump**: his 2020 tweets are written to `posts/x_realDonaldTrump.csv`
  (the validator requires the file stem to equal `x_<handle>`; the handle is his real
  one). `accounts.csv` already maps (x, realDonaldTrump) to the person Donald Trump, so
  these tweets pool with his Truth Social posts (2022-02 onward; the two never overlap in
  time). If X posts since 2022 are collected later they go into the same file. His Truth
  Social file stays the frozen v1 file.
- Persons already in `accounts.csv` keep their name there (for example "Cynthia Lummis",
  not the metadata's "Cynthia M. Lummis"); new people are added with the group of their
  party (`republicans` or `democrats`).

## Mapping the archive to the post data contract (fixed now)

From the archive's parser (`parseTweet.js`): a retweet's text is `RT @<user> <text>`; a
quote tweet's text is `<own text> QT @<user> <quoted text>`; replies carry no flag;
t.co links are expanded, photos to `pbs.twimg.com/media/...` and videos to
`video.twimg.com/...` URLs.

- `kind`: `repost` if the text starts with `RT @<user>` (handle = user); else `quote` if
  the text contains ` QT @<user> ` (handle = the user of the first occurrence); else
  `reply` if the text starts with `@`; else `original`. Replies to oneself (threads) and
  originals that start with an @mention are therefore labelled reply, and are not events.
- `text`: for quotes only the own part before ` QT @`, so the topic label sees only the
  member's own words (as in the contract, "the post as shown" without the quoted post);
  otherwise the full text. Newlines as `\n`.
- `has_media`: true if the own text contains a `pbs.twimg.com/media/`,
  `pbs.twimg.com/ext_tw_video_thumb/`, `pbs.twimg.com/tweet_video_thumb/` or
  `video.twimg.com/` URL.
- `post_id` = `id`; `url` = `https://x.com/<screen_name>/status/<id>` (the account's own
  status id, also for retweets, whose archive `link` points to the original);
  `collected_at_utc` = the conversion time.
- One row per post id per account (duplicates across daily files dropped); rows the
  validator would reject (empty non-repost text with no media) are dropped and counted.
- **Trump file**: post id from the `Tweet URL`; time from the id; `repost` if the text
  starts with `RT @<user>`; `reply` if it starts with `@`; `quote` if the text contains a
  `twitter.com/<user>/status/` link to another user's status (handle = that user);
  otherwise `original`; `has_media` true if the text contains `pic.twitter.com`. Text as
  in the file (it may be truncated; that is a known topic-label limitation).

## (c) Everything else follows PREREGISTRATION_RANKING.md unchanged

Outcome (BTCUSDT abnormal rv over +1 to +5), events (only original and quote posts,
5-minute chaining, 60-minute clean rule), controls (16 same-minute-of-week controls with
no post of the same person within 60 minutes), placebo pool, minimum of 10 analysable
clean events to be ranked, empirical-Bayes shrinkage over all ranked people, rank
intervals, Benjamini-Hochberg FDR across all ranked people, the pre-window test, the
2025-10-10 sensitivity, per-topic results, Musk separate, Obama negative control, and the
one-sentence answer, all exactly as pre-registered. The **cross-person overlap rule is
applied across all selected people together** (and every other used post file): an event
of any person within 5 minutes of another person's original or quote post is excluded for
both.

Known consequences accepted in advance, not corrected:

- Each Congress account's posts are observed only to 2023-07-11 (Trump's Twitter only in
  2020 within the sample), but the control and placebo minutes come from the full
  2020-01 to 2026-10 sample. Controls or pool minutes after a person's coverage ends can
  hide unobserved posts by that person; this can only bias effects toward zero.
- The archive collected tweets daily, so tweets deleted within a day are missing.
- Many people tweet at the same news moments; the overlap rule will remove those events,
  which removes the busiest moments for everyone.
- Retweets carry no own text and are never events; quote detection relies on the
  archive's ` QT @` marker; reply detection on a leading `@`.
