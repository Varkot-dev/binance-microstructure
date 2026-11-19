# Prompt for Claude Desktop: collecting politicians' posts

Paste everything inside the box into Claude Desktop, with the browser connected and you
logged in to X. Edit the account list or date range first if you want.

Before you start, two things to know:
- **X's terms restrict automated collection,** and heavy automated browsing can get an
  account rate-limited or locked. The prompt keeps the pace slow and stops at the first
  sign of trouble, but the risk is to your account, so it is your call.
- **Public posts only.** Nothing private (DMs, protected accounts) is collected.

**Collection order:** follow `COLLECTION_PLAN.md` in this folder (tiers and date windows); it overrides the account list below.

```text
I'm collecting public posts by politicians for a research project that measures how their
posts move crypto markets. Please collect posts with your browser tools, using my
logged-in X session, and save them as CSV files in the exact format below. Work slowly and
carefully: complete, correct timestamps matter far more than speed.

ACCOUNTS (X handles), highest priority first:
EricTrump, DonaldJTrumpJr, realDonaldTrump, POTUS, WhiteHouse, JDVance, DavidSacks,
worldlibertyfi, GetTrumpMemes, SECGov, GaryGensler, SenLummis, SenatorHagerty, SenWarren,
SenSchumer, RepMaxineWaters, KamalaHarris, JoeBiden, POTUS46Archive (the archived
Biden-era presidential account), BarackObama, elonmusk (do elonmusk last; he posts a lot).
First open each profile and confirm the handle exists and is the right person. If a
handle is wrong or suspended, note it and move on.

DATE RANGE: 2023-01-01 to today, in UTC.

HOW TO COLLECT (per account):
1. Use X search, one calendar month at a time, so nothing is cut off by the profile
   timeline limit: search  from:HANDLE since:YYYY-MM-01 until:YYYY-MM-01(next month)
   and choose the "Latest" tab. Scroll to the end of the results for that month.
2. For every post, record:
   - post_id: the number in the post's URL (.../status/NUMBER). Keep it as text.
   - url: https://x.com/HANDLE/status/NUMBER
   - created_at_utc: read the datetime attribute of the post's <time> element (it looks
     like 2025-03-02T15:24:07.000Z). Drop the milliseconds and keep the Z:
     2025-03-02T15:24:07Z. Never use the "3h" or "Mar 2" labels shown on screen.
   - text: the full text (open "Show more" if truncated). Replace newlines with \n.
   - kind: original, reply, quote (quotes another post) or repost (a plain repost with
     no own text; it shows "HANDLE reposted"). For a repost, the post_id, url and
     created_at_utc are those of the original post, so instead record the repost only if
     X shows its own time; if it does not, skip reposts and say so in the notes.
   - quoted_or_reposted_handle: the other account for quote or repost, else empty.
   - has_media: true if an image or video is attached, else false.
   - collected_at_utc: the current time in the same format.
3. Pace: pause a few seconds between scrolls and between searches, like a person
   reading. If you see a rate-limit message, a CAPTCHA, a login challenge or "Something
   went wrong" more than twice, STOP, save what you have, and tell me. Do not try to get
   around any limit, and do not use any other account or service.
4. If a month seems incomplete (for example search returns nothing for a month when the
   account was clearly active), note that month as a gap rather than guessing.

FILE FORMAT (exactly this, UTF-8 CSV with a header row), one file per account:
  file name: x_HANDLE.csv   (for example x_EricTrump.csv)
  header:
platform,handle,post_id,url,created_at_utc,text,kind,quoted_or_reposted_handle,has_media,collected_at_utc
  platform is always x. One row per post. No duplicate post_ids. No likes or view counts.

ALSO keep a coverage file, coverage_additions.csv, with one row per account:
platform,handle,first_post_utc,last_post_utc,rows,known_gaps,collected_by,notes
(collected_by = claude-desktop; known_gaps lists months you could not complete.)

OPTIONAL SECOND PHASE, Truth Social: if the browser can open
https://truthsocial.com/@realDonaldTrump without logging in, collect his posts the same
way into truth_realDonaldTrump.csv with platform = truth and
url = https://truthsocial.com/@realDonaldTrump/NUMBER. Read exact times the same way
from the <time> element. Skip this phase if it needs a login.

WHERE TO SAVE:
- If you can access my local clone of the GitHub repository binance-microstructure,
  put the CSVs in research/politics/posts/, append the coverage rows to
  research/politics/coverage.csv, run
    python research/politics/validate_posts.py
  fix anything it reports. The folder is git-ignored so post text never reaches main,
  so push the files to a separate branch instead:
    git checkout -b x-posts origin/main   (or git checkout x-posts if it exists)
    git add -f research/politics/posts/x_*.csv research/politics/coverage.csv
    git commit -m "X posts: <handles>"
    git push -u origin x-posts
  Push after each account is finished, so the analysis can start on the first ones.
  Never merge or push this branch into main.
- Otherwise save everything in a folder named politician_posts in my Downloads and tell
  me where, so I can upload it.

Start with EricTrump for January to March 2025 as a test, show me the first 10 rows,
and wait for my OK before collecting the rest.
```

## After the files arrive

1. Upload or push them to `research/politics/posts/` on a branch.
2. Run `.venv/bin/python research/politics/validate_posts.py`; every file must print OK.
3. The event-study code then aligns each post to the Binance trade data minute by minute.
