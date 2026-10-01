# Q4b: tick-size confound

## Question

Q4 found `p_flip ~ log10(n_events)` with slope +0.1114 (R² = 0.2632, n = 121): more actively traded symbols flip sign more often. One alternative is relative tick size (`tickSize / price`), a mechanical driver of bid-ask bounce that plausibly correlates with activity. If it is the real driver, "activity" in Q4's regression is a proxy and the competitive-response reading is an artifact of bid-ask bounce. This analysis runs the regression that separates the two.

## Method

1. **Tick size**: from the Binance futures `exchangeInfo` endpoint (`https://testnet.binancefuture.com/fapi/v1/exchangeInfo`, public, unauthenticated), taking each symbol's `PRICE_FILTER.tickSize`. The raw response is cached in `exchangeinfo_snapshot.json`.

   The endpoint used differs from the default; see Caveats.
2. **Mean price**: for each of Q4's 121 successful symbols, the mean aggTrades price over 2023-06, from a lazy Polars scan of the parquet Q4 used. `rel_tick = tickSize / mean_price`.
3. **Regressions**: three OLS fits (`numpy.linalg.lstsq`) on the usable symbols (in Q4's successful set, in the exchangeInfo snapshot, with a readable mean price): (a) `p_flip ~ log10(n_events)`, Q4's law on this possibly smaller sample; (b) `p_flip ~ log10(rel_tick)`; (c) `p_flip ~ log10(n_events) + log10(rel_tick)`, which shows whose coefficient survives once the other is controlled. I also report `corr(log10(n_events), log10(rel_tick))`.

**t-ratios** are the coefficient over its classical-OLS stderr, which assumes i.i.d. homoskedastic residuals. That is unverified and likely violated in a heterogeneous cross-section of 121 assets with no correction for cross-sectional dependence or heteroskedasticity (the same caveat as Q4). Read them as coefficient size relative to noise, not as a test with a valid p-value.

## Run summary

Q4 successful symbols: 121. Usable for this analysis (tick size found + mean price computed): 111. Skipped: 10.

## Regressions

**(a) p_flip ~ log10(n_events)** [Q4's law, reproduced on this sample]: intercept = **-0.2140** (stderr 0.1000, t≈-2.14), log10_n_events = **0.1060** (stderr 0.0157, t≈6.75), R² = 0.2945, n = 111

**(b) p_flip ~ log10(rel_tick)**: intercept = **0.4814** (stderr 0.0439, t≈10.97), log10_rel_tick = **0.0053** (stderr 0.0108, t≈0.50), R² = 0.0022, n = 111

**(c) p_flip ~ log10(n_events) + log10(rel_tick)** [joint]: intercept = **-0.1812** (stderr 0.0997, t≈-1.82), log10_n_events = **0.1130** (stderr 0.0158, t≈7.14), log10_rel_tick = **0.0192** (stderr 0.0092, t≈2.09), R² = 0.3220, n = 111

corr(log10(n_events), log10(rel_tick)) = -0.2113, the collinearity between activity and relative tick size.

## Verdict

**Both variables survive jointly.** In regression (c), log10(n_events) (coef 0.1130, t≈7.14) and log10(rel_tick) (coef 0.0192, t≈2.09) both remain distinguishable from zero despite their collinearity (corr = -0.2113). Each carries at least partly independent information about p_flip in this cross-section, so the tick-size confound is present but does not fully explain away the activity effect. Univariate R² is 0.2945 for activity alone and 0.0022 for relative tick size alone, versus 0.3220 jointly.

## Skipped symbols

| symbol | reason |
|---|---|
| RNDRUSDT | no tickSize in exchangeInfo snapshot |
| MATICUSDT | no tickSize in exchangeInfo snapshot |
| BTCBUSD | no tickSize in exchangeInfo snapshot |
| ETHBUSD | no tickSize in exchangeInfo snapshot |
| GALUSDT | no tickSize in exchangeInfo snapshot |
| SOLBUSD | no tickSize in exchangeInfo snapshot |
| LDOBUSD | no tickSize in exchangeInfo snapshot |
| GALABUSD | no tickSize in exchangeInfo snapshot |
| ICPUSDT | no tickSize in exchangeInfo snapshot |
| XRPBUSD | no tickSize in exchangeInfo snapshot |

## Caveats

- **exchangeInfo source substitution**: The specified mainnet endpoint (fapi.binance.com/fapi/v1/exchangeInfo) returned HTTP 451 (geo-restricted) from this execution environment, as did every other fapi.binance.com/api.binance.com/dapi.binance.com path tried. The futures TESTNET exchangeInfo endpoint (testnet.binancefuture.com) was reachable and returns the same PRICE_FILTER schema; its BTCUSDT tickSize (0.10) matches the known mainnet value, but testnet contract specs are not guaranteed identical to mainnet for every symbol and this snapshot is missing 10 of Q4's 121 symbols (all delisted/renamed BUSD or discontinued pairs) that mainnet's live exchangeInfo would likely still list historically. Treat tick sizes in this run as a best-effort proxy for mainnet, not a verified mainnet snapshot.
- **Tick size is current, not June-2023.** `exchangeInfo` returns the tick size as of the day the analysis is run, not for the June 2023 period behind the trade data and Q4's p_flip. Binance occasionally changes `PRICE_FILTER.tickSize`, usually after large price moves. For a symbol whose price regime shifted materially since June 2023, `rel_tick` may not match the tick size in force during the data window. This error is probably small for most symbols and is not corrected.
- 121-symbol sample, reduced to the usable subset above. Symbols missing from the snapshot (e.g. delisted or renamed since June 2023) are dropped, not imputed.
- Single month (2023-06), as in Q4: one market regime, not tested on other periods.
- The OLS assumptions are unverified (see Method), so the reported stderr, t-ratios and R² are descriptive. Same reasons as Q4: heteroskedastic, non-i.i.d. residuals across heterogeneous assets.
- Even a clean result in (c) shows which variable better explains this cross-section statistically. It does not identify the mechanism generating p_flip.
