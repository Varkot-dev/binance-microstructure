# Which politicians move crypto markets the most?

A new part of the project (Part C). For every post by a set of politicians and officials,
measure what Bitcoin and other Binance futures did in the minutes after it, compared with
ordinary times, and turn that into one influence number per person with an interval.

## Status

- `notes/`: research on post-data sources and on prior studies and methods (in progress).
- `accounts.csv`: the accounts to collect, grouped (Trump family, White House,
  administration, Republicans, Democrats, regulators, Musk as a separate comparison).
- `posts/`: where collected posts land locally, one CSV per account, in the format defined in
  `posts/README.md`. Post text is git-ignored; `posts_index/` holds IDs, times and topics.
- `validate_posts.py`: checks every post file against that format (tests in
  `tests/research/test_validate_posts.py`).
- `CLAUDE_DESKTOP_PROMPT.md`: the prompt for collecting X posts with Claude Desktop in
  your logged-in browser.
- `coverage.csv`: which months each account covers, and known gaps.

## Planned design (to be refined once the notes are in)

1. Align each post's UTC timestamp with Binance trades on BTC, ETH and others.
2. Measure abnormal return, volatility, volume and buy/sell imbalance over 1, 5, 15 and
   60 minutes, against matched control times (same weekday and hour, no post).
3. Check the market did not already move before the post (it may be reacting to news).
4. Split posts by topic (crypto, tariffs, the Fed, other) and estimate each person's
   average effect per post, shrunk toward the group mean for people with few posts.
