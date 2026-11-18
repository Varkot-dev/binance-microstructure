# Politician posts: the data contract

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
