# HIP-1 launch census: crawl report (coverage only)

This report gives coverage numbers for the raw crawl behind `PREREGISTRATION_DRAFT.md`. It
contains no prices, returns, drawdowns, volumes or survival quantities, on purpose: those
wait for the pre-registration to be locked.

## Crawl identity

| Item | Value |
|---|---|
| `crawl_id` | `20261120T002608Z` |
| Fixed `end_ms` (candle `endTime`) | 1795134372109 (2026-11-20 UTC) |
| Location | `data/hyperliquid/memecoin/raw/20261120T002608Z/` (git-ignored) |
| Size on disk | 11 MB gzipped, 716 files in `manifest.jsonl` (sha256 per file) |
| `spotMeta.json.gz` sha256 | `b78e16ea3f6237cc620cc657c12c344209f8125507df0803d207d932fd7adbef` |
| Code | `research/hyperliquid/memecoin/census.py` (`crawl`, then `coverage`) |
| Pacing | one request per 1.5 s, up to 3 attempts, exponential backoff (429 waits double) |

The crawl ran in two passes with the same `crawl_id` on 2026-11-20. The first pass stopped
after token index 251 without writing its status file, so for the 188 tokens it fetched
successfully the per-attempt history is lost (they show as cached with 0 recorded attempts).
The second pass reused those cached files and fetched everything else. A re-crawl of failed
`tokenDetails` at least 24 hours later is planned before locking (draft section 2).

## Tokens and pairs

| Item | Count |
|---|---|
| Tokens in `spotMeta.tokens` | 519 |
| Largest token index | 1338 |
| Token indices 0 to 1338 absent from `spotMeta` | 820 |
| Tokens with an EVM contract linked | 194 |
| Pairs in `spotMeta.universe` | 354 |
| Largest pair index | 1192 |
| Pair indices 0 to 1192 absent from `spotMeta.universe` | 839 |
| Asset contexts in `spotMetaAndAssetCtxs` | 1,193 (354 match listed pairs; 839 are for unlisted pair indices) |
| Pairs by quote token: USDC (0) / token 360 / USDT0 (268) / USDE (235) | 337 / 11 / 5 / 1 |
| Distinct base tokens with at least one pair | 340 |
| Tokens with a USDC pair (candidate reference pair) | 337 |
| Base tokens with more than one pair | 12 |

The 839 contexts for pair indices not in `spotMeta.universe` are a second missing-data layer
next to the 820 missing token indices. They are noted here and will be handled in the
selection section of the pre-registration before locking; no field of them was analysed.

## tokenDetails

| Item | Count |
|---|---|
| Requested (every token in `spotMeta`) | 519 |
| Final `ok` | 360 |
| Final `http_500` after 3 attempts | 159 |
| JSON `null` responses | 0 |
| Attempt outcomes recorded in pass 2 | 172 ok, 476 HTTP 500, 1 HTTP 429 |
| `ok` on first attempt in pass 2 / cached from pass 1 | 172 / 188 |
| `ok` responses carrying `deployTime` | 358 of 360 |
| `deployTime` range among `ok` | 2024-05-16 to 2026-11-19 |

Every failure returned HTTP 500 on all three attempts (one also saw a 429 first), and a
manual retry of one failing token (`EDGE`, index 200) returned 500 again, so the failures
look deterministic rather than load-related.

Failures by token-index band (index order is roughly deploy order):

| Index band | Failed | OK |
|---|---|---|
| 0-99 | 18 | 82 |
| 100-199 | 25 | 75 |
| 200-299 | 43 | 57 |
| 300-399 | 51 | 49 |
| 400-499 | 12 | 50 |
| 500-799 | 0 | 5 |
| 800-899 | 3 | 31 |
| 1000-1099 | 0 | 2 |
| 1200-1299 | 2 | 5 |
| 1300-1338 | 5 | 4 |

## Daily candles

| Item | Count |
|---|---|
| Pairs requested (`interval` 1d, `startTime` 0 to `end_ms`) | 354 |
| Final `ok` | 354 (all on the first attempt) |
| Total bars | 170,186 |
| Bars with volume above zero | 92,021 |
| Pairs with at least one bar with volume above zero | 339 |
| Pairs with no bar with volume above zero | 15 |
| Most bars for one pair | 949 (below the 5,000-bar API cap, so no truncation) |
| First date with volume above zero, any pair | 2024-04-16 |
| Last date with volume above zero, any pair | 2026-11-20 |

Bars before a pair lists are back-filled with zero volume by the API (`DATA.md` section 4),
which is why total bars exceed traded bars.

## Reproduce

    uv run python research/hyperliquid/memecoin/census.py crawl --crawl-id 20261120T002608Z
    uv run python research/hyperliquid/memecoin/census.py coverage --crawl-id 20261120T002608Z

The second command writes `coverage.json` next to the raw files.
