# Politician posts: the data contract

**Post text is not stored in git.** CSVs in this folder are git-ignored. The repository
keeps `../posts_index/<platform>_<handle>.csv` instead: platform, handle, post_id, url,
created_at_utc, kind, has_media and the pre-registered topic label, without the text.
Rebuild the full files locally as described in "Rebuilding the text" below.

Every file of collected posts lands in this folder as one CSV per account and platform:

```
research/politics/posts/<platform>_<handle>.csv      e.g. x_EricTrump.csv, truth_realDonaldTrump.csv
```

`validate_posts.py` (one folder up) checks every file before any analysis reads it. A
file that fails the check is not used.

## Columns (exactly these, in this order, UTF-8, comma-separated, header row)

| column | type | rule |
|---|---|---|
| `platform` | text | `x` or `truth` |
| `handle` | text | account handle without `@`, same as in the file name |
| `post_id` | text | the platform's numeric post id from the post URL (keep as text; X ids exceed 64-bit float precision) |
| `url` | text | the post's permanent URL |
| `created_at_utc` | text | ISO 8601 in UTC with seconds, ending in `Z`, e.g. `2025-03-02T15:24:07Z`. On X, copy the `datetime` attribute of the post's `<time>` element; never use the "3h" style relative label |
| `text` | text | full post text as shown, newlines replaced by `\n`, quotes escaped CSV-style |
| `kind` | text | `original`, `reply`, `repost` (retweet / ReTruth, no own text) or `quote` |
| `quoted_or_reposted_handle` | text | handle of the quoted or reposted account, else empty |
| `has_media` | `true` / `false` | image or video attached |
| `collected_at_utc` | text | when this row was collected, same format as `created_at_utc` |

## Rules

- **Public posts only**, from the accounts listed in `../accounts.csv`.
- **One row per post id.** Duplicates are an error.
- **No engagement counts** (likes, views): they change over time and depend on when the
  page was loaded, so they are not a fixed property of the post.
- **Keep posts that were later deleted** if they were collected before deletion; do not
  try to recover deleted posts from elsewhere.
- **Coverage matters more than speed.** A missing week of posts biases the influence
  estimate more than a slow collection does. Each file's coverage (first and last post
  date, and any gaps the collector knows about) goes in `../coverage.csv`.

## Rebuilding the text

Trump's Truth Social posts come from the public archive
`mickpletcher/truthsocial-archiver` (code MIT; the post text is not covered by that
licence), commit `334073464e27`:

```bash
git clone https://github.com/mickpletcher/truthsocial-archiver /tmp/truth-archive
git -C /tmp/truth-archive checkout 334073464e27
mkdir -p data/politics/raw/pletcher_truth
cp /tmp/truth-archive/docs/data/posts.jsonl data/politics/raw/pletcher_truth/
PYTHONPATH=src .venv/bin/python research/politics/c1_trump_posts.py convert
```

The analysis checks the rebuilt file's sha256 against the one recorded in
`data/c1_trump_posts.md`, so a rebuild that differs is refused rather than used silently.

X posts collected with `../CLAUDE_DESKTOP_PROMPT.md` are handled the same way: keep the
CSVs local (or send them over directly), and commit only their index.

Members of Congress (2020-01-01 to 2023-07-11) and Trump's 2020 tweets
(`x_realDonaldTrump.csv`) come from `alexlitel/congresstweets` (MIT) and the Hershey
Trump Twitter file, as fixed in `../PREREGISTRATION_ADDENDUM_CONGRESS.md`:

```bash
R=data/politics/raw/congresstweets
GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 --filter=blob:none --no-checkout \
  https://github.com/alexlitel/congresstweets $R/repo     # commit f5c837de11a6
git -C $R/repo checkout HEAD -- 'data/2019-12-31.json' 'data/2020-*' 'data/2021-*' \
  'data/2022-*' 'data/2023-*'                             # about 1.6 GB
git clone --depth 1 --filter=blob:none --no-checkout \
  https://github.com/alexlitel/congresstweets-automator $R/automator  # commit 002e949c8534
git -C $R/automator checkout HEAD -- data/historical-users-filtered.json
PYTHONPATH=src .venv/bin/python research/politics/convert_congress.py
```

Each selected account is one file `x_<screen_name>.csv`; `../accounts.csv` maps the
accounts of one person (office and campaign) to that person, and the analysis pools
them. Trump's 2020 tweets use his real handle, so they share the (x, realDonaldTrump)
row with any X posts collected later and pool with his Truth Social posts.
