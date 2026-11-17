# Leakage-safe evaluation methodology for ML on high-frequency financial data (tick-level trades and quotes)

Target setting: Binance USDT-M perpetuals, aggTrades + bookTicker (top of book), event-time horizons h = 1..100 trades, months of data 2023-2026. Notes written 2026-11-17.

**Provenance legend (read this first).** In this session only web *search* worked; direct page fetches of arxiv.org, binance.com, developers.binance.com and skfolio.org were blocked by the sandbox network policy. Every finding is therefore tagged:

- **[S]** = stated in a search-result snippet retrieved this session (not the full text).
- **[R]** = written from the researcher's recall of the cited primary source; the link points to that source but the page was NOT re-read this session. Formulas tagged [R] are standard and I am confident in them, but anything numerical tagged [R] should be re-checked before it is quoted in a report.

Nothing here was measured on the repo's own data.

---

## 1. Purged and embargoed cross-validation, walk-forward, combinatorial purged CV

### Takeaway
For labels that span the next N trades, every train/test boundary needs a gap of at least the label span (in *time*, taken from the label end-timestamp t1, not a fixed row count) plus the feature look-back on the side after a test block; plain walk-forward with a gap is the primary, causally honest protocol, and (C)PCV is a secondary tool for getting a distribution of scores rather than one path. CPCV's main limits are that it trains on the future, its paths are not independent, and its supporting evidence is largely synthetic.

### Cited Findings

Definitions
- [R] Purging (AFML ch. 7.4.1): a label Y_i is a function of information in [t_i,0 , t_i,1]. A training observation i is removed if its interval overlaps any test label interval [t_j,0 , t_j,1], i.e. if any of: (a) t_j,0 <= t_i,0 <= t_j,1; (b) t_j,0 <= t_i,1 <= t_j,1; (c) t_i,0 <= t_j,0 <= t_j,1 <= t_i,1. — [Lopez de Prado 2018, Advances in Financial Machine Learning, Wiley](https://www.wiley.com/en-us/Advances+in+Financial+Machine+Learning-p-9781119482086)
- [S] "Purged cross-validation ... remov[es] overlapping observations and, optionally, add[s] a temporal buffer ('embargo') around the test set"; purging cannot be done correctly unless label intervals (start, end) are recorded per sample. — [Wikipedia: Purged cross-validation](https://en.wikipedia.org/wiki/Purged_cross-validation)
- [R] Embargo (AFML ch. 7.4.2): additionally drop training observations whose start time falls in [t_j,1 , t_j,1 + h] immediately AFTER each test block, to absorb serial correlation in features that purging by label interval does not catch. No embargo is needed before the test block because training labels there only use information available before the test starts. The book's suggested size is h ~ 0.01*T (1% of the bars). — [Lopez de Prado 2018](https://www.wiley.com/en-us/Advances+in+Financial+Machine+Learning-p-9781119482086); [S] the 1% rule of thumb and "embargo only after the test set" are both repeated in [Wikipedia](https://en.wikipedia.org/wiki/Purged_cross-validation)
- [R] Combinatorial purged CV (AFML ch. 12): partition T observations into N contiguous groups, take every combination of k groups as the test set, purge/embargo each boundary. Number of splits = C(N, k); number of full backtest paths phi = (k/N) * C(N, k). Example N=6, k=2: 15 splits, 5 paths. Each path is stitched from out-of-sample predictions of different fitted models. — [Lopez de Prado 2018](https://www.wiley.com/en-us/Advances+in+Financial+Machine+Learning-p-9781119482086); implementation with `n_folds`, `n_test_folds`, `purged_size`, `embargo_size`: [skfolio CombinatorialPurgedCV](https://skfolio.org/generated/skfolio.model_selection.CombinatorialPurgedCV.html)
- [R] Walk-forward in scikit-learn: `TimeSeriesSplit(n_splits, max_train_size, test_size, gap)`; `gap` = number of samples excluded from the end of each train set before the test set (default 0, i.e. NO purging unless you set it). `max_train_size` turns the expanding window into a rolling one. — [scikit-learn TimeSeriesSplit docs](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)
- [R] Lopez de Prado's stated drawbacks of walk-forward: only one historical path is tested (easy to overfit to it), the path is not necessarily representative of future regimes, and early decisions are made on a small fraction of the data. — [Lopez de Prado 2018, ch. 11-12](https://www.wiley.com/en-us/Advances+in+Financial+Machine+Learning-p-9781119482086)

Evidence for and against CPCV
- [S] Arian, Norouzi Mobarekeh and Seco (2024, Knowledge-Based Systems, DOI 10.1016/j.knosys.2024.112477) compare K-Fold, Purged K-Fold, Walk-Forward and CPCV and report CPCV has lower PBO and better DSR test statistic; they criticise walk-forward for "increased temporal variability and weaker stationarity" of its false-discovery prevention, and propose Bagged and Adaptive CPCV. The comparison is run in a SYNTHETIC environment (Heston stochastic volatility plus other components), not on real tick data. — [Arian et al. 2024](https://doi.org/10.1016/j.knosys.2024.112477)
- [S] A 2025 walk-forward framework paper on microstructure signals summarises the same work as CPCV being superior for overfitting control while walk-forward "remains the industry standard for realistic trading" — i.e. the practical debate is open. — [arXiv 2512.12924](https://arxiv.org/pdf/2512.12924)
- [S] The 1% embargo is a convention, not a derived optimum; combinatorial splits multiply the number of evaluated paths. — [Wikipedia](https://en.wikipedia.org/wiki/Purged_cross-validation)

### Inferences
Choosing purge and embargo when the label spans N future events (protocol recommendation):
- Record per sample: `t0` = decision timestamp, `t1` = timestamp of the event that closes the label (the trade at index i+N, or the last quote used). Purge by timestamp interval overlap, never by a fixed row offset, because an N-trade span is milliseconds in a burst and minutes in a lull, and because with several symbols row indices are not comparable.
- Before a test block (train earlier than test): drop train samples with `t1 >= test_start`. In single-symbol event time that is exactly the last N_max samples, N_max = largest horizon evaluated (100). If you train one model per horizon, still purge with N_max so the splits are identical across horizons.
- After a test block (only relevant for K-fold/CPCV, where training data follows test data): drop train samples with `t0 <= max(t1 of test) + L`, where L is the longest feature look-back (rolling windows, EWMA effective memory ~ 3-5 half-lives, sequence length of a neural input). Rationale: a train sample just after the test block has features computed from the test block's label window. So gap_after >= N_max + L, then add an embargo for residual persistence.
- Embargo size: the "1% of T" rule is meaningless at tick scale (1% of 3 years = 11 days; 1% of one day is ~15 min). Set it from measured dependence instead: the lag at which the ACF of the features and of the per-sample loss falls inside the noise band, with a floor of N_max + L. Because volatility/activity are long-memory, no finite embargo removes all dependence; the pragmatic fix is to make fold boundaries coincide with natural breaks (whole UTC days or weeks) and embargo at least minutes-to-an-hour each side.
- Sampling every trade with an N-trade label means consecutive labels share (N-1)/N of their window. Purging fixes the boundary only; inside the training set the effective sample size is still ~n/N (see section 2).

Recommended harness design:
- Primary: rolling or anchored walk-forward on whole-day (or whole-week) blocks, gap = max(N_max events in time, feature look-back), periodic refit. This is the only scheme whose every prediction is made with strictly past data, which matters over 2023-2026 because fee tiers, tick sizes, liquidity and participant mix drift.
- Secondary: purged K-fold / CPCV on the development period only, used for (i) hyperparameter selection with more test folds than walk-forward gives, (ii) a distribution of scores across paths. Never quote a CPCV number as "the backtest".
- Final: one untouched contiguous period at the END of the sample (e.g. the last 3-6 months), evaluated once (section 5).

Limits / criticisms of purged CV and CPCV (my synthesis; the first two are widely made, I found no single authoritative critique paper):
- Non-causal training: K-fold and CPCV train on data after the test block. Purging removes label overlap but not regime knowledge (the model has seen the future volatility level, future spread regime, future fee/tick regime). This flatters any model with non-stationary features or un-normalised levels.
- CPCV paths are not independent: they share most of their training data and all of the same test observations, so the spread of path scores understates true uncertainty. Do not feed "number of paths" into a t-test as if it were n.
- Purging handles label overlap only. Leakage through preprocessing (global scalers, feature selection, threshold tuning on the full sample) passes straight through unless the whole pipeline is refit inside each fold.
- Hyperparameter search inside CPCV still counts as multiple testing; each (config x split) is a trial.
- The supporting evidence (Arian et al.) is synthetic-data-based.

### Gaps
- I could not open the skfolio or mlfinlab docs or the AFML text this session, so the exact skfolio parameter semantics (whether `purged_size`/`embargo_size` are in observations and applied on which side) need checking against the docs before the harness relies on them.
- I found no peer-reviewed paper that specifically critiques CPCV on real intraday data; the criticisms above are inference plus common practitioner argument.
- No source gives a principled embargo length for tick data with long-memory features; the ACF-based rule above is my recommendation, not a cited result.

---

## 2. Label construction pitfalls

### Takeaway
At 1-100 trade horizons most of what looks like directional skill comes from the label definition (overlap, smoothing with past prices, a large "stationary" class, bounce and one-tick mechanics), so the harness should use raw, unsmoothed, point-to-point mid (or microprice) returns, record t0/t1, de-duplicate same-timestamp sweep prints, and always report a model against microstructure baselines rather than against 33% or 50%.

### Cited Findings

Overlap and uniqueness
- [R] Concurrency and average uniqueness (AFML ch. 4): c_t = number of labels whose span covers time t; uniqueness of label i at t is u_t,i = 1_t,i / c_t; average uniqueness u_bar_i = (sum_t u_t,i) / (sum_t 1_t,i). Weights and bagging `max_samples` should be scaled by u_bar; the sequential bootstrap draws samples with probability decreasing in overlap with already-drawn samples. — [Lopez de Prado 2018](https://www.wiley.com/en-us/Advances+in+Financial+Machine+Learning-p-9781119482086); [S] the same summary (count concurrent labels, average uniqueness over the label's lifespan, set bagging max_samples to average uniqueness, sequential bootstrap, weights as a function of uniqueness and return size; sections 4.4, 4.5, 4.5.1) appears in [reading notes on AFML](https://reasonabledeviations.com/notes/adv_fin_ml)

FI-2010 and smoothed labels
- [R] FI-2010 (Ntakaris, Magris, Kanniainen, Gabbouj, Iosifidis 2018, Journal of Forecasting 37(8), arXiv:1705.03233): 5 Finnish stocks on Nasdaq Nordic, 10 trading days in June 2010, 10 LOB levels, one sample per 10 events, shipped pre-normalised (z-score, min-max, decimal precision), labels for horizons k in {10, 20, 30, 50, 100}, anchored day-based 9-fold split. Label: l_t = (m_plus(t) - p_t)/p_t with m_plus(t) = mean of the next k mid-prices, classed up/stationary/down with threshold alpha (0.002 in the common setup). — [Ntakaris et al. 2018](https://arxiv.org/abs/1705.03233)
- [S] LOBCAST states the adopted labelling "compares the current mid-price to the average mid-prices in a future horizon of k time units". — [Prata et al. 2023, arXiv:2308.01915](https://arxiv.org/abs/2308.01915)
- [R] DeepLOB (Zhang, Zohren, Roberts 2019, IEEE Trans. Signal Processing, arXiv:1808.03668) uses, for its LSE data, the doubly-smoothed label l_t = (m_plus(t) - m_minus(t)) / m_minus(t), where m_minus(t) = mean of the PREVIOUS k mid-prices (following Tsantekidis et al. 2017). — [Zhang et al. 2019](https://arxiv.org/abs/1808.03668)
- [S] DeepLOB itself notes the FI-2010 labels are "less consistent" because smoothing is applied only to future prices, that the FI-2010 method gave "rather stochastic" labels on LSE data (hence the switch), and that FI-2010 is only ten consecutive days of downsampled data from a less liquid market. — [DeepLOB via ar5iv](https://ar5iv.labs.arxiv.org/html/1808.03668)
- [S] The LOBCAST journal version says the labelling method is "prone to instability". — [Prata et al. 2024, Artificial Intelligence Review](https://link.springer.com/article/10.1007/s10462-024-10715-4)
- [S] LOBCAST benchmarks 15 deep models on FI-2010 and on LOBSTER (NASDAQ) data: "all models exhibit a significant performance drop when exposed to new data"; F1 on the LOBSTER sets falls to roughly 48-61%; the authors attribute it to higher data complexity and to overfitting FI-2010. — [Prata et al. 2023](https://arxiv.org/pdf/2308.01915)
- [S] TLOB (Berti and Kasneci 2025, arXiv:2502.15757) introduces a new labelling "removing the horizon bias" of the earlier smoothed schemes. — [Berti and Kasneci 2025](https://arxiv.org/html/2502.15757v2)
- [S] FI-2010 classes are unbalanced, which is why follow-up papers report F1 rather than accuracy. — [Zhang and Zohren 2021, arXiv:2105.10430](https://arxiv.org/pdf/2105.10430); [Axial-LOB, arXiv:2212.01807](https://arxiv.org/pdf/2212.01807)
- [S] A 2025-2026 LOB paper (UQ-LOB) makes the general point explicit: any context window whose label horizon runs past the prediction time "would leak future price information", so only labels fully known at prediction time may be used as inputs. — [UQ-LOB, arXiv id as returned by search: 2609.31491 — id looks unusual, verify](https://arxiv.org/pdf/2609.31491)

Tick size, bounce, mechanical predictability
- [R] Roll (1984, Journal of Finance): with a constant spread s and an efficient value, bid-ask bounce gives Cov(dp_t, dp_t-1) = -s^2/4 for TRADE prices, hence spread = 2*sqrt(-Cov). So next-trade-price direction is predictable from the last trade's side with zero economic content. — [Roll 1984](https://doi.org/10.1111/j.1540-6261.1984.tb03897.x)
- [R] Gould and Bonart (2016, Market Microstructure and Liquidity, arXiv:1512.03492): top-of-book queue imbalance is a strong predictor of the direction of the next mid-price move, especially for large-tick stocks. — [Gould and Bonart 2016](https://arxiv.org/abs/1512.03492)
- [S] Briola, Bartolucci, Aste (2024/2025, Quantitative Finance, arXiv:2403.09267), 15 NASDAQ stocks with DeepLOB: "large-tick stocks are more predictable than small-tick stocks"; at the 10-tick horizon average MCC is 0.29 for large-tick vs 0.11 for small-tick stocks; for small-tick stocks average MCC is 0.01 at H100. — [Briola et al.](https://arxiv.org/abs/2403.09267); [journal version](https://doi.org/10.1080/14697688.2025.2522911)
- [S] Kolm, Turiel, Westray (2023, Mathematical Finance 33(4):1044-1081; 115 Nasdaq stocks, Jan 2019-Jan 2020, LOBSTER): stock-level alphas "peak at a time scale of about two price changes and decline thereafter"; models on order-flow inputs beat models on raw book states; predictability is linked to microstructure characteristics ("information-rich" stocks). — [Kolm et al. 2023](https://econpapers.repec.org/RePEc:bla:mathfi:v:33:y:2023:i:4:p:1044-1081); [SSRN](https://papers.ssrn.com/abstract=3900141)
- [S] One 2025 crypto LOB paper frames the null explicitly: mid-price movement is noisy and under efficient-market reasoning one should expect about 50% accuracy. — [Exploring Microstructural Dynamics in Cryptocurrency LOBs, 2025](https://www.researchgate.net/publication/392513905_Exploring_Microstructural_Dynamics_in_Cryptocurrency_Limit_Order_Books_Better_Inputs_Matter_More_Than_Stacking_Another_Hidden_Layer)

### Inferences
Why smoothed labels inflate scores (the "smoothed-label leakage" issue):
- With l_t = (m_plus - m_minus)/m_minus, half of the label is a function of the past k mids, which are inside the model's input window. A model can score well by reconstructing the already-realised drift m_t - m_minus(t); that is label information present in the features, not forecasting. Even the FI-2010 one-sided version (mean of next k mids vs current mid) mixes horizons 1..k, so it is dominated by the nearest, easiest steps and its effective horizon is about k/2.
- Smoothing makes adjacent labels nearly identical (moving average of overlapping windows), so random shuffles or any split without purging put near-duplicates of test labels in train. Reported 80%+ F1 on FI-2010 with collapse to ~50-60% on fresh LOBSTER data (LOBCAST) is consistent with this, though LOBCAST's own stated causes are data complexity and overfitting.
- Neither label corresponds to a trade you can do: you cannot transact at an average of future mids.

Recommended label for this repo:
- Primary: point-to-point r_t,h = (mid at the quote prevailing just before trade i+h) - (mid just before decision) in ticks or bps. Keep the raw signed return; derive classes from it. Also store the executable versions (bid_t+h - ask_t for a long, bid_t - ask_t+h for a short).
- Robustness target: microprice / imbalance-weighted mid, to check the signal is not just half-tick mid flicker when the spread briefly opens to 2 ticks (mid moves half a tick and reverts — a "mid bounce").
- Never use trade price as the target (Roll bounce).
- Event definition: one aggressive order that sweeps several price levels prints several aggTrades with the same timestamp and side. Counting each as an "event" makes h=1 trivially predictable (continuation of the same sweep). Collapse same-timestamp same-side aggTrades into one event before defining horizons, or at least report both.
- Sample-uniqueness in this setting: sampling every event with an h-event label gives c_t = h and u_bar = 1/h. Use sample weights 1/h, or subsample every h-th event for training diagnostics; for inference use the dependent-data methods of section 6. Nominal n of 10^8 trades at h=100 is ~10^6 independent-ish labels at most, far fewer after volatility clustering.

Threshold and class imbalance:
- BTCUSDT/ETHUSDT perps are large-tick instruments (spread is almost always one tick), so at h=1..10 the overwhelming majority of labels are "no mid change". A 3-class model gets high accuracy by predicting "stationary"; a 2-class model conditioned on "mid moved" silently conditions on the future.
- Any threshold theta must be (i) fixed from training data only and frozen for the test period, or (ii) set a priori in economic units (ticks; half-spread; round-trip cost). Re-tuning theta per period to rebalance classes changes the task between folds and makes scores non-comparable. Report class frequencies per fold.
- Report conditional results both ways: unconditional 3-class, and "direction given a move" clearly labelled as not tradeable on its own.

Baselines every result must beat (same splits, same metric): majority class; last-trade-sign persistence; top-of-book queue imbalance sign / logistic regression on imbalance; short trade-flow imbalance (OFI). A deep model that does not beat logistic regression on imbalance out of sample has found nothing new.

### Gaps
- I could not open LOBCAST or TLOB full text. The precise wording of LOBCAST's label critique, the definition of TLOB's "horizon bias" (my understanding: earlier labels tie the smoothing-window length to the prediction horizon; TLOB decouples them), and LOBCAST's profit-analysis results are NOT verified. The search explicitly returned no source linking LOBCAST to "label leakage" in those words; the leakage argument above is my inference from the formulas.
- The often-repeated claim that FI-2010's shipped z-score normalisation uses statistics from the full sample (look-ahead) is not verified here.
- The alpha=0.002 FI-2010 threshold and the exact sample counts are from recall.
- BTCUSDT perp tick size (0.10 USDT from recall) and the fraction of time at one-tick spread must be measured from the repo's own exchangeInfo and bookTicker data.
- Briola et al.'s exact label/threshold construction was not retrievable.

---

## 3. Normalization and feature leakage; timestamp alignment and latency

### Takeaway
Every statistic that touches the data (scalers, thresholds, feature selection, rolling windows, resampling) must be computable from information time-stamped strictly before the decision instant, and trades must be joined to the last quote strictly before the trade in exchange transaction time (with an added latency assumption), with an automated sanity check that buyer-initiated trades print at the prior ask.

### Cited Findings
- [R] Kapoor and Narayanan (2023, Patterns 4(9)) give a taxonomy of leakage in ML-based science, including: no clean train/test separation, preprocessing on train+test together, feature selection on the full data, illegitimate features (proxies for the outcome), temporal leakage, and test sets not drawn from the distribution of interest. — [Kapoor and Narayanan 2023](https://doi.org/10.1016/j.patter.2023.100804)
- [S] Briola et al. describe using "a standardization procedure that prevents any data leakage" and choosing validation days from within the training period. — [Briola et al.](https://arxiv.org/html/2403.09267v3)
- [R] DeepLOB normalises each day of LSE data with the mean and standard deviation of the previous 5 trading days (rolling, backward-looking z-score). — [Zhang et al. 2019](https://arxiv.org/abs/1808.03668)
- [S] Binance timestamp semantics (developer-forum / vendor wording, not the official spec): transaction time `T` is when the matching engine updated the data; event time `E` is when the server generated/pushed the message; E is always >= T in raw data. — [Binance developer forum](https://dev.binance.vision/t/meaning-of-event-time-transaction-time-fields/5449); [Tardis.dev roadmap note](https://roadmap.tardis.dev/feature-requests/p/switch-to-use-transaction-timestamp-for-binance-where-available-futures-order-bo)
- [S] Binance user-data-stream docs: messages are "strictly ordered by both T (transaction time from Matching Engine) and E (event time when the message is generated)". — [Binance developer docs](https://developers.binance.com/en/docs/products/derivatives-trading-portfolio-margin/user-data-streams)
- [S] A forum poster observed timestamps differing between aggTrade, trade and bookTicker for the same event; no authoritative Binance answer was found. — [Binance developer forum](https://dev.binance.vision/t/exchange-timestamps/11798)
- [S] Tardis.dev: its Binance USDS-M futures history has the same format as the real-time WebSocket API "with addition of local timestamps" (i.e. a receive timestamp exists only if you or a vendor recorded it). — [Tardis.dev docs](https://docs.tardis.dev/historical-data-details/binance-futures)
- [S] hftbacktest docs: its Binance futures converter finds cases where the local timestamp is ahead of the exchange timestamp and re-orders events; feed latency (local minus exchange) must be positive and a `correct_local_timestamp` helper enforces a base latency; some data carries the server "sent" timestamp rather than the matching-engine timestamp; depth@0ms is still aggregated while bookTicker captures every BBO change. — [hftbacktest Data Preparation](https://hftbacktest.readthedocs.io/en/latest/tutorials/Data%20Preparation.html); [hftbacktest Fusing Depth Data](https://hftbacktest.readthedocs.io/en/latest/tutorials/Fusing%20Depth%20Data.html)
- [S] Binance order-book ticker docs: Retail Price Improvement (RPI) orders are "not visible and excluded" from the standard book response; a separate RPI depth endpoint includes them. — [Binance WebSocket API market data](https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/websocket-api); [RPI Order Book](https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Order-Book-RPI)
- [S] Lee and Ready (1991, Journal of Finance 46(2):733-746): quotes may be recorded AHEAD of the trades that triggered them, so a trade must be matched to a quote that is older than the trade by a lag; implementations match "the most recent good quote that is at least X seconds older than the trade". — [Lee and Ready 1991](https://econpapers.repec.org/RePEc:bla:jfinan:v:46:y:1991:i:2:p:733-46); [OneTick lee_and_ready docs](https://docs.pip.distribution.sol.onetick.com/api/source/lee_and_ready.html)
- [R] Field layout: futures aggTrade stream = {e, E event time, s, a agg id, p, q, f first id, l last id, T trade time, m buyer-is-maker}; futures bookTicker stream = {e, u update id, E, T, s, b, B, a, A}. Fills from one taker order at the same price are aggregated into one aggTrade (the futures stream aggregates same-price same-side fills per 100 ms). `m = true` means the buyer was resting, i.e. the aggressor SOLD, so no Lee-Ready/tick-rule inference is needed. — [Binance bookTicker stream docs](https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Individual-Symbol-Book-Ticker-Streams)

### Inferences
Normalisation rules for the harness:
- Fit scalers, winsorisation limits, PCA, feature selection, class thresholds and calibration maps on the training window only, inside each fold; serialise them with the model. A "fit on the full sample" scaler leaks the future volatility/price level; on a 2023-2026 crypto sample (price level changed by multiples) this is a first-order effect for any level-type feature.
- Prefer features that are stationary by construction (imbalance ratios, returns in ticks or in units of trailing volatility, sizes relative to trailing median) over globally z-scored levels. Trailing normalisers must be shifted by one event: the rolling window for row i ends at i-1 (pandas `rolling(...).mean().shift(1)`, or `closed='left'` on time windows). Centered windows, `bfill`, interpolation across gaps, and `pct_change(-k)`-style helpers are look-ahead.
- Day-level statistics (today's volume, today's high/low, today's realised vol) are look-ahead unless they are cumulative-to-now.
- Resampling and bar construction: a bar's close is known only at bar end; a feature stamped at bar start that uses the bar's content is leakage.
- Target-derived features (anything computed with `shift(-k)`) should live in a separate module/namespace from features; add a unit test that features at row i are unchanged when all rows > i are replaced with NaN or garbage (a "truncation invariance" test). This single test catches most look-ahead bugs.

Trade/quote alignment:
- Join on matching-engine time `T`, not `E` and not file order. The feature snapshot for a decision made "at trade i" must use the last bookTicker row with T_quote strictly less than T_trade (`merge_asof(..., allow_exact_matches=False)`), because a bookTicker update carrying the same millisecond as the trade is typically the book AFTER the trade consumed liquidity. Using it leaks the trade's own impact into the "pre-trade" quote and into trade-sign-vs-quote features.
- Millisecond resolution means many events share a timestamp and cross-stream ordering inside one millisecond is not recoverable from T alone. Treat every same-millisecond cross-stream pair as ambiguous and resolve conservatively (quote strictly before). Within a stream, order by aggTrade id / bookTicker update id, not by timestamp.
- Decide whether the prediction is made BEFORE trade i (features exclude trade i; label starts at trade i) or AFTER trade i (features include trade i's price/size/sign; label measured from the first quote strictly after trade i, to trade i+h). Mixing these — features include trade i, label base is the pre-trade mid — hands the model the impact of trade i. Write the convention down and test it.
- Sanity checks to automate per day: (1) share of taker-buy aggTrades with price >= prior ask and taker-sells with price <= prior bid should be near 100%; a low share means the join is wrong or clocks are skewed; (2) repeat with the exact-match join — if agreement drops, same-timestamp quotes are post-trade; (3) distribution of E - T per stream; (4) monotonic ids; (5) gaps in update ids / missing intervals flagged and excluded with a purge around them.
- Standard bookTicker excludes RPI liquidity, so the visible BBO may differ from what a taker actually receives; note as a caveat on cost estimates.

Latency:
- Public dumps carry exchange timestamps only. A real consumer sees an event at T + feed latency and its order reaches the engine at T + feed latency + compute + order latency. Evaluate with an explicit delay delta: features use only events with T <= t - delta_feed; the label entry price is the quote prevailing at t + delta_order. Report the metric as a function of total delay (e.g. 0, 1, 5, 20, 100 ms and "next event"). A signal that exists only at delta = 0 is a statistical description of the book, not a strategy.
- If self-recorded data with receive timestamps exists for part of the sample, use it to calibrate delta; do not mix receive-time ordering and exchange-time ordering in one feature set.

### Gaps
- Official Binance field definitions for futures `aggTrade` and `bookTicker` could not be opened; the layouts and the "aggregated per 100 ms" detail are from recall and must be confirmed in the docs, as must whether aggTrade `T` and bookTicker `T` for the same match are guaranteed identical.
- Whether a same-millisecond bookTicker row is pre- or post-trade is an empirical question for this dataset; I found no authoritative statement. The sanity check above answers it.
- Availability of historical USDT-M bookTicker files on data.binance.vision across the whole 2023-2026 span is not verified (my recollection is that futures bookTicker archive coverage is incomplete for recent periods); check before fixing the evaluation calendar.
- No sourced figure for realistic Binance futures feed/order latency was found; the delays listed are placeholders for a sensitivity sweep.

---

## 4. Cost-aware and economically meaningful metrics

### Takeaway
Report proper scoring (log-loss vs a baseline) and MCC for statistical skill, but judge tradeability on executable prices net of fees: at the regular Binance USDT-M tier a taker round trip costs about 10 bps in fees alone, which is orders of magnitude larger than a typical 1-100-trade mid move on a one-tick-spread contract, so a statistically real signal at these horizons is almost never a stand-alone taker strategy and should be described as such.

### Cited Findings
Fees (third-party pages; the official fee page was unreachable from this sandbox)
- [S] Binance USDT-M futures, Regular (VIP 0): maker 0.0200%, taker 0.0500%. Regular = under about $15M 30-day volume or under 25 BNB (Finder's wording). — [Finder](https://www.finder.com/cryptocurrency/trading/binance-futures-fees); [Traders Union](https://tradersunion.com/brokers/crypto/view/binance/futures-fees/); official table (not opened): [Binance futures fee schedule](https://www.binance.com/en/fee/futureFee), [Binance Futures Fee Structure FAQ](https://www.binance.com/support/faq/360033544231)
- [S] VIP 1: maker 0.0160%, taker 0.0400%; VIP 9: maker 0.0000%, taker 0.0170% (requires about $30B volume or 5,500 BNB). 10 tiers, Regular through VIP 9. — [CoinPerps comparison, citing Binance VIP programme](https://www.coinperps.com/learn/bybit-vs-binance-perpetual-futures-fees). Conflict: one blog lists Regular maker as 0.0100% and another table lists VIP 1 as 0.0080%/0.0450%; these are outliers against the majority. — [Bitsgap](https://bitsgap.com/blog/binance-trading-fees-explained-what-it-costs)
- [S] Paying fees in BNB gives about 10% off USDT-M futures fees (taker 0.05% -> ~0.045%). — [CryptoPotato](https://cryptopotato.com/binance-fees/)
- [S] USDC-M contracts are reported at 0.00% maker / 0.04% taker. — [CoinPerps](https://www.coinperps.com/learn/bybit-vs-binance-perpetual-futures-fees)
- [S] Negative maker fees exist only in specific programmes: a Binance liquidity-provider/new-listing promotion lists maker -0.006% (-0.6 bps) for an incentive period; dates not confirmed. — [Binance announcement](https://www.binance.com/en-AE/support/announcement/detail/06f67008a3ea4caebecc0cb266c26401)

Briola et al. operational metric
- [S] Briola, Bartolucci, Aste argue "traditional machine learning metrics fail to adequately assess the quality of forecasts in the Limit Order Book context" and propose judging forecasts by "the probability of accurately forecasting complete transactions"; "a transaction happens when one is able to open a position and then close it". — [Briola et al., arXiv:2403.09267](https://arxiv.org/abs/2403.09267); [Quantitative Finance version](https://www.tandfonline.com/doi/full/10.1080/14697688.2025.2522911)
- [S] One summary gives the metric as p_T = CT / (PT + TT - CT), with (as I read the notation) TT = transactions in the true label sequence, PT = transactions in the predicted sequence, CT = correctly predicted transactions — a Jaccard-style overlap. — [alphaXiv summary of 2403.09267](https://www.alphaxiv.org/abs/2403.09267)
- [S] MCC and p_T can diverge completely: one reported case has MCC = 0.59 with p_T = 0 (not one complete transaction captured), another MCC = 0.11 with p_T = 1.00. — [Briola et al.](https://arxiv.org/html/2403.09267v4)
- [S] Across probability thresholds 0.3/0.5/0.7/0.9, MCC rises with the threshold while p_T falls; p_T rises from small-tick to large-tick stocks; for small-tick stocks p_T at thresholds above 0.5 is always 0; average PT for large-tick stocks is 5.3x10^4, about one third of that for small-tick stocks. — [Briola et al.](https://arxiv.org/html/2403.09267v4)
- [S] The DeepLOB trading simulation is reported (secondary summary) to trade at mid-prices with no transaction costs. — [GitHub summary of DeepLOB](https://github.com/jjakimoto/research-issues/issues/1738)

Classification metrics
- [R] MCC = (TP*TN - FP*FN) / sqrt((TP+FP)(TP+FN)(TN+FP)(TN+FN)); it is high only if the classifier does well on all four confusion-matrix cells, unlike accuracy and F1 which can be high on imbalanced data from the majority class alone. Multiclass generalisation: Gorodkin's R_K (what `sklearn.metrics.matthews_corrcoef` computes). — [Chicco and Jurman 2020, BMC Genomics 21:6](https://doi.org/10.1186/s12864-019-6413-7)
- [R] Log-loss and the Brier score are strictly proper scoring rules: they are optimised in expectation only by reporting the true probabilities, so they reward calibration as well as discrimination. — [Gneiting and Raftery 2007, JASA 102(477)](https://doi.org/10.1198/016214506000001437)

### Inferences
Which metric says what:
- Accuracy: misleading here because of the dominant "no change" class and because it ignores the size of moves. Always print it next to the majority-class and persistence baselines, or drop it.
- MCC: good single-number summary of directional skill under imbalance; threshold-dependent; says nothing about magnitude or cost. Report per horizon and per fold/month.
- AUC (one-vs-rest): threshold-free ranking skill; invariant to class prior and to any monotone distortion of scores, so it hides miscalibration and can look fine when all skill sits in un-tradeable tiny moves.
- Log-loss: reports calibrated probabilistic skill. Report as skill versus a baseline, e.g. 1 - LL_model / LL_baseline with baseline = training-set class frequencies (or the imbalance logistic model). Add a reliability curve.
- Because none of these is in money units, add return-based statistics: information coefficient (rank correlation of prediction with the signed h-event mid return in ticks), and mean signed forward return conditional on prediction decile ("markout curve" over h = 1..100).

Net-of-cost measures (formulas for the harness; f = fee rate per side, quotes strictly after the decision plus latency):
- Taker round trip, long: r_net = (bid_exit - ask_entry)/ask_entry - 2*f_taker. Short: (bid_entry - ask_exit)/bid_entry - 2*f_taker. Equivalent in mid terms: signed mid return - (half-spread_entry + half-spread_exit)/mid - 2*f_taker.
- Break-even: E[signed mid move | trade] > spread + 2*f_taker*price. At Regular tier, 2*f_taker = 10 bps (about 9 bps with BNB discount; 3.4 bps at VIP 9). With BTCUSDT near one-tick spread, the spread term is a small fraction of a basis point, so FEES, not spread, are the binding cost — the opposite of the equity LOB literature, where "crossing the spread" is the hurdle. A "probability of crossing the spread" metric alone is therefore far too lenient for Binance; use "probability that the h-event move exceeds spread + 2 fees".
- Suggested tradeability metrics: (1) P(|mid move over h| > c) unconditional, for c = round-trip cost at each fee tier — the base rate of even having an opportunity; (2) precision at that hurdle: P(signed executable return > 2f | model fires), with a dependent-data CI; (3) mean net return per signal and per day at several firing thresholds, including the count of signals (a positive mean on 12 trades is not a result); (4) the Briola-style transaction metric: turn predictions into open/close events, count CT, PT, TT, report p_T — and report it at executable prices, not at mid.
- Maker framing: passive entry earns the half-spread and pays f_maker (2 bps Regular, i.e. still a cost; zero or negative only at top tiers / programmes), but fills are adversely selected and uncertain. Top-of-book data without queue position cannot simulate passive fills honestly; at most report an optimistic bound ("filled if price trades through the level") and a pessimistic one ("filled only when the mid subsequently moves against you"), labelled as bounds.
- Other costs to mention but not model at these horizons: funding (irrelevant intra-minute), market impact of own size (ignored; state the assumed size is one lot at touch), RPI/hidden liquidity.

Statistically real vs tradeable — how to word results:
- Level 1 "statistically real": out-of-sample log-loss/MCC improvement over the imbalance baseline with a dependent-data CI excluding zero, stable across months.
- Level 2 "economically visible at mid": conditional markout in bps is non-zero and survives a realistic latency delta.
- Level 3 "tradeable": net-of-fee executable return positive with CI excluding zero at a stated fee tier, after multiple-testing deflation (section 5).
- Expect most findings at 1-100 trades to stop at level 1-2. That is still useful (execution timing, quote skewing for a market maker who trades anyway), and should be reported as a signal for cost reduction rather than as alpha.

### Gaps
- The official Binance fee table could not be opened; the Regular/VIP 1/VIP 9 numbers come from third-party pages that agree with each other, with two noted outliers. Fee tiers, the USDC-M schedule, and promotions changed several times in 2023-2026, so a backtest spanning that period strictly needs a dated fee history; I found none. www.binance.com must be allowed in the session network settings (or checked manually) to confirm current values.
- The exact definition of a "transaction" and of PT/TT/CT in Briola et al., and whether their metric uses the phrase "probability of crossing the spread" anywhere, could not be confirmed from the full text; the formula comes from a summary snippet. Their metric as described is prediction-sequence based, not price/cost based — the cost-hurdle versions above are my extension.
- No sourced typical magnitude of the 1-100-trade mid move in bps for BTCUSDT/ETHUSDT perps; compute from the repo's data.

---

## 5. Multiple testing and backtest overfitting

### Takeaway
Keep an append-only log of every configuration evaluated, deflate the best result by the number (and dispersion) of trials using the Deflated Sharpe Ratio or a reality-check bootstrap, estimate PBO with CSCV if a trials-by-time performance matrix is available, and reserve one final contiguous period that is scored exactly once.

### Cited Findings
- [S] Deflated Sharpe Ratio (Bailey and Lopez de Prado 2014, Journal of Portfolio Management; SSRN 2460551): the Probabilistic Sharpe Ratio evaluated at a hurdle equal to the expected maximum Sharpe ratio among N unskilled trials; corrects for selection bias, backtest overfitting and non-normal returns; with one trial it reduces to the PSR of Bailey and Lopez de Prado (2012). — [Wikipedia: Deflated Sharpe ratio](https://en.wikipedia.org/wiki/Deflated_Sharpe_ratio); [SSRN 2460551](https://papers.ssrn.com/abstract=2460551)
- [S] Formulas: PSR(SR*) = Phi( (SR_hat - SR*) * sqrt(T-1) / sqrt(1 - g3*SR_hat + ((g4-1)/4)*SR_hat^2) ), T = number of return observations, g3 skewness, g4 kurtosis, SR in per-observation (non-annualised) units. Expected maximum under the null: E[max SR] ~ mu + sigma * [ (1-gamma)*Phi^-1(1 - 1/N) + gamma*Phi^-1(1 - 1/(N*e)) ], gamma ~ 0.5772 (Euler-Mascheroni), sigma = cross-trial standard deviation of the Sharpe estimates. DSR = PSR(SR* = E[max SR]). — [LuxAlgo concept page](https://www.luxalgo.com/library/concept/deflated-sharpe-ratio/); [endgame library source](https://endgame-ml.readthedocs.io/en/latest/_modules/endgame/utils/sharpe.html)
- [S] N should be the number of effectively independent trials; trials are correlated, so the literal count overstates it; Lopez de Prado proposes clustering strategies (ONC algorithm) to estimate effective N; in practice N is a judgement call. — [Wikipedia: Deflated Sharpe ratio](https://en.wikipedia.org/wiki/Deflated_Sharpe_ratio)
- [S] Probability of Backtest Overfitting (Bailey, Borwein, Lopez de Prado, Zhu; Journal of Computational Finance 20(4), 2017, DOI 10.21314/JCF.2016.322): a general framework implemented via combinatorially symmetric cross-validation (CSCV), "generic, model-free and nonparametric". — [SSRN 2326253](https://papers.ssrn.com/abstract=2326253); [Risk.net](https://www.risk.net/journal-of-computational-finance/2471206/the-probability-of-backtest-overfitting); [open PDF](https://escholarship.org/content/qt4w1110bb/qt4w1110bb.pdf)
- [R] CSCV procedure: build a T x N matrix M of per-period performance for N configurations; cut the rows into S equal contiguous blocks (S even); for each of the C(S, S/2) ways to choose half the blocks as in-sample (the rest out-of-sample): pick the in-sample-best configuration n*, compute its relative OOS rank w in (0,1), and the logit lambda = ln(w/(1-w)). PBO = fraction of combinations with lambda <= 0, i.e. the probability that the in-sample winner lands at or below the OOS median. Also reported: the IS-vs-OOS performance regression (degradation) and probability of OOS loss. — [Bailey et al. 2017](https://papers.ssrn.com/abstract=2326253)
- [R] Minimum backtest length (Bailey, Borwein, Lopez de Prado, Zhu 2014, Notices of the AMS 61(5), "Pseudo-mathematics and financial charlatanism"): with N independent trials on pure noise, the expected maximum in-sample annualised Sharpe grows roughly like sqrt(2 ln N)/sqrt(years), so the years of data needed to keep it below a target SR grows like 2 ln N / SR^2. — [Bailey et al. 2014](https://www.ams.org/notices/201405/rnoti-p458.pdf)
- [R] White's Reality Check (2000, Econometrica 68(5)) and Hansen's SPA test (2005, JBES 23(4)) test whether the BEST of many models beats a benchmark, using the stationary bootstrap over the joint loss-differential series; the Model Confidence Set (Hansen, Lunde, Nason 2011, Econometrica 79(2)) returns the set of models not distinguishable from the best. — [White 2000](https://doi.org/10.1111/1468-0262.00152); [Hansen 2005](https://doi.org/10.1198/073500105000000063); [Hansen, Lunde, Nason 2011](https://doi.org/10.3982/ECTA5771)
- [R] Harvey, Liu, Zhu (2016, Review of Financial Studies 29(1)) argue that, given the volume of data mining, a newly proposed factor should clear a t-statistic of about 3.0 rather than 2.0. — [Harvey, Liu, Zhu 2016](https://doi.org/10.1093/rfs/hhv059)

### Inferences
What a small project should do and report:
- Data budget fixed up front: development period (walk-forward / purged CV; touch freely), and a final lock-box = the most recent contiguous months, with a purge gap before it. The lock-box is scored once, by a script committed before it is run, on a frozen model/feature/threshold configuration identified by commit hash. If it is ever looked at twice, say so and report both.
- Trial log (append-only, machine-written by the harness): every evaluated configuration with timestamp, commit, feature set, label/horizon, model family, hyperparameters, split scheme, metric values. Count as trials: horizons, symbols, thresholds, label variants, feature subsets, cost assumptions, and "informal" notebook looks. Report N in every results table.
- Report alongside the headline number: N trials; the full distribution of the development metric across trials (median and best, not only best); DSR for any Sharpe-type statistic using the cross-trial variance; PBO from CSCV when the trial matrix exists (per-day metric for each configuration is the natural M, with S = 8-16 blocks of whole days); and the lock-box result with a dependent-data CI.
- For classification-skill metrics (log-loss, MCC), which are not Sharpe ratios, the analogous correction is a reality-check / SPA style bootstrap of the maximum improvement over the baseline across all tried configurations, or simply a Bonferroni/Holm-adjusted CI across the pre-declared family (horizons x symbols).
- Pre-declare the primary hypothesis (one metric, one horizon set, one symbol set, one cost tier) in the repo before running the lock-box; everything else is exploratory and labelled so.
- Caveats of the tools: DSR assumes the trial Sharpe ratios are a draw from one null distribution and needs an honest N; intraday PnL is heavy-tailed and autocorrelated, so T should be the number of roughly independent return periods (use daily PnL, not per-trade). CSCV assumes blocks are exchangeable (no regime trend) and, like CPCV, its combinations are far from independent; it is a diagnostic, not a p-value.

### Gaps
- The DSR and PSR formulas were confirmed only via secondary pages (which the search notes frame slightly differently from each other); verify against SSRN 2460551 before implementing. The CSCV steps are from recall of the paper.
- I found no source giving guidance specific to deflating classification metrics (MCC/log-loss) for the number of configurations; the reality-check suggestion is my adaptation.

---

## 6. Statistical inference for dependent data

### Takeaway
Never use i.i.d. standard errors on per-event losses: overlapping h-event labels make them at least MA(h-1) and volatility clustering adds long memory, so use a day-block (cluster) bootstrap as the default, the stationary bootstrap with Politis-White block length as a within-day check, and the Diebold-Mariano test with HAC variance (lags >= h-1) and the Harvey-Leybourne-Newbold correction for pairwise forecast comparison.

### Cited Findings
- [S] Stationary bootstrap (Politis and Romano 1994, JASA): resamples blocks whose lengths are geometric with mean b, so the resampled series is stationary. — [Politis and White paper copy](https://bashtage.github.io/kevinsheppard.com/files/teaching/mfe/advanced-econometrics/Politiswhite.pdf); original: [Politis and Romano 1994](https://doi.org/10.1080/01621459.1994.10476870)
- [S] Politis and White (2004, Econometric Reviews 23(1):53-70) give automatic estimators of the optimal block size for the stationary and circular block bootstraps, based on flat-top lag-window spectral estimation. — [EconPapers](https://econpapers.repec.org/RePEc:taf:emetrv:v:23:y:2004:i:1:p:53-70)
- [S] Patton, Politis and White (2009, Econometric Reviews 28(4):372-375) correct the 2004 paper: the stationary-bootstrap constant should be D_SB = 2*g(0)^2 (following Nordman's 2008 correction of Lahiri 1999); the optimal-block formulas otherwise stand. — [Patton, Politis, White 2009](https://public.econ.duke.edu/~ap172/Patton_Politis_White_2009.pdf)
- [S] Software: R `blocklength::pwsd()` implements the corrected method (c = 2 as suggested by Politis and White; default cap on block length ceil(min(3*sqrt(n), n/3))). — [CRAN blocklength](https://cran.r-project.org/web/packages/blocklength/readme/README.html). [R] Python: `arch.bootstrap.optimal_block_length`, `StationaryBootstrap`, `CircularBlockBootstrap`. — [arch docs](https://arch.readthedocs.io/en/latest/bootstrap/generated/arch.bootstrap.optimal_block_length.html)
- [R] The MSE-optimal block length for variance estimation grows like n^(1/3) with a constant that increases with the persistence of the series. — [Politis and White 2004](https://econpapers.repec.org/RePEc:taf:emetrv:v:23:y:2004:i:1:p:53-70)
- [R] Diebold-Mariano (1995, JBES 13(3):253-263): for loss differential d_t = L(e1_t) - L(e2_t), DM = d_bar / sqrt(LRV_hat(d)/n) -> N(0,1) under equal predictive accuracy, with LRV the long-run variance (for an h-step forecast the differential is at most MA(h-1), so use autocovariances up to lag h-1 or a HAC estimator). — [Diebold and Mariano 1995](https://doi.org/10.1080/07350015.1995.10524599)
- [R] Harvey, Leybourne, Newbold (1997, International Journal of Forecasting 13:281-291): small-sample correction DM* = DM * sqrt( (n + 1 - 2h + h(h-1)/n) / n ), compared with Student-t(n-1). — [Harvey, Leybourne, Newbold 1997](https://doi.org/10.1016/S0169-2070(96)00719-4)
- [R] Diebold (2015, JBES 33(1)) stresses that DM compares FORECASTS, not models, and assumes the loss differential is covariance-stationary; Giacomini and White (2006, Econometrica 74(6)) give a conditional predictive ability test valid for rolling-window estimation including nested models. — [Diebold 2015](https://doi.org/10.1080/07350015.2014.983236); [Giacomini and White 2006](https://doi.org/10.1111/j.1468-0262.2006.00718.x)

### Inferences
Recommended inference recipe:
- Unit of resampling = the per-event out-of-sample record (y, p_model, p_baseline, forward return). For any statistic that is not a mean (AUC, MCC, F1), recompute the statistic on each bootstrap replicate; for DIFFERENCES between two models resample both models' records with the same indices (paired bootstrap), then take percentile or BCa intervals of the difference.
- Default: day-block bootstrap. Resample whole UTC days (or sessions/8-hour funding windows) with replacement, 2,000+ replicates. This is valid under arbitrary within-day dependence, sidesteps block-length choice, respects intraday seasonality, and with 100s of days gives a usable number of clusters. With < ~30 days use weeks-as-folds t-statistics with caution or a wild cluster bootstrap, and say the CI is weak.
- Equivalent quick check: compute the metric per day, then treat the daily series (still mildly autocorrelated) with a stationary bootstrap or HAC t-test. A result that is significant per-event but not on the daily series is not significant.
- Within-day stationary bootstrap: choose b on the per-event loss (or loss-differential) series with Politis-White/Patton; enforce a floor b >= ~2-3 x h (label overlap) and report sensitivity at b, 2b, 4b. If the CI keeps widening as b grows, dependence is not being captured — fall back to day blocks.
- Long memory: block-length selectors assume summable autocovariances; under long-range dependence (absolute returns, volume, spread) the "optimal" b keeps growing with n and block-bootstrap CIs are too narrow. Mitigations: (i) bootstrap the loss DIFFERENTIAL between model and baseline, which is far less persistent than the raw loss because the common volatility component cancels; (ii) standardise returns by trailing volatility before computing return-based metrics; (iii) use day/week blocks; (iv) check the ACF of the series actually being resampled and state it.
- DM in this setting: use loss = per-event log-loss (or squared error on the return), HAC lags >= h-1 (in events) with a Bartlett kernel wider than that if the ACF warrants, HLN correction; or run DM on DAILY mean loss differentials with a small lag, which is cleaner. For nested comparisons (model = baseline + extra features) with rolling refits, prefer Giacomini-White; plain DM is conservative/non-standard for nested models estimated on expanding windows.
- For many models at once use the reality check / SPA / MCS family (section 5) rather than many pairwise DMs.
- Always show the time profile: per-month (or per-fold) metric with CI. A pooled significant result driven by two months of 36 is a regime artefact.

### Gaps
- The DM/HLN formulas and the long-memory caveat are from recall; the search returned nothing on block-length choice under long memory. I believe Lahiri (1993, Statistics and Probability Letters) is the standard reference showing the moving-block bootstrap fails under long-range dependence without modification, but I could not confirm the citation this session, so it is not listed as a finding.
- No source was found that validates block-bootstrap CIs for AUC/MCC specifically on tick-level LOB predictions; coverage of the recommended recipe on this data is untested (a placebo test on shuffled-by-day labels would check it).

---

## 7. Checklist of the most common flaws in published LOB / crypto prediction papers

### Takeaway
The recurring failures are (i) evaluation splits that are not purged or are tuned on the test set, (ii) labels that embed past prices or mechanical one-tick effects, (iii) preprocessing fitted on the whole sample, (iv) mid-price "backtests" with no fees, spread or latency, and (v) no accounting for the number of things tried; LOBCAST and Briola et al. document the consequences empirically.

### Cited Findings
- [S] 15 deep LOB models re-implemented in LOBCAST: strong on FI-2010, "significant performance drop" on new LOBSTER data; most appear to overfit FI-2010. — [Prata et al. 2023/2024](https://arxiv.org/abs/2308.01915); [journal](https://link.springer.com/article/10.1007/s10462-024-10715-4)
- [S] FI-2010 limits acknowledged by DeepLOB's authors: ten consecutive days, downsampled, a less liquid market; labels unbalanced and "less consistent". — [DeepLOB](https://ar5iv.labs.arxiv.org/html/1808.03668); [Zhang and Zohren 2021](https://arxiv.org/pdf/2105.10430)
- [S] High classification scores need not translate into executable transactions (MCC 0.59 with p_T = 0); predictability is concentrated in large-tick names. — [Briola et al.](https://arxiv.org/html/2403.09267v4)
- [S] DeepLOB's trading simulation reportedly uses mid-prices and no transaction costs (secondary summary). — [GitHub summary](https://github.com/jjakimoto/research-issues/issues/1738)
- [S] Alpha in LOB data peaks at about two price changes and decays (Kolm et al.), so results quoted at a single convenient horizon are not informative about others. — [Kolm et al. 2023](https://econpapers.repec.org/RePEc:bla:mathfi:v:33:y:2023:i:4:p:1044-1081)
- [R] Generic leakage taxonomy across ML-based science. — [Kapoor and Narayanan 2023](https://doi.org/10.1016/j.patter.2023.100804)

### Inferences
Checklist (each item phrased as a test the harness or reviewer can apply):

Splits and selection
1. Random shuffle or stratified K-fold on overlapping time-series samples (near-duplicate neighbours in train and test).
2. Chronological split but no gap: label windows of the last train samples run into the test period; sequence-model input windows straddle the boundary.
3. Validation set used for early stopping / hyperparameters is also the reported test set; or the test set is reused across many paper revisions.
4. Single short test period (days), one regime, one symbol; no per-period breakdown.
5. Train period later than test period (CPCV/K-fold numbers presented as a backtest).

Labels
6. Smoothed labels using past mids (DeepLOB-style) or averaged future mids (FI-2010-style): partly computable from inputs, heavily autocorrelated, not executable.
7. Class thresholds tuned on the full sample or re-tuned per test period to balance classes.
8. Dropping "stationary" samples at test time (conditioning on the future), then reporting 2-class accuracy.
9. Target is last trade price (bid-ask bounce) or mid on a large-tick asset where "direction" is the queue-imbalance mechanic.
10. Event-time horizons counted on raw prints, so one sweep order fills several "future events".

Features and preprocessing
11. Scaler / PCA / feature selection fitted on train+test; dataset shipped pre-normalised with unknown window (FI-2010).
12. Rolling statistics not lagged by one step; centered windows; forward/back-fill across gaps; day-level aggregates known only at day end.
13. Trade joined to the same-timestamp (post-trade) quote; cross-stream ordering by arrival/file order; mixing event time and transaction time.
14. Features computed after snapshot resampling that peeks at the bar's end.

Economics
15. Accuracy/F1 only; no majority, persistence or imbalance-logit baseline; no calibration or proper score.
16. PnL at mid; zero fees; zero spread; zero latency; instantaneous fills; unlimited size at touch; passive fills assumed whenever price touches.
17. Fee tier assumed at the best VIP level or a rebate programme without saying so; crypto papers ignoring that the fee, not the spread, is the dominant cost.
18. Statistical significance claimed from i.i.d. standard errors on millions of overlapping samples.

Research process
19. Number of architectures/horizons/symbols/thresholds tried not reported; best-of-many presented as the result.
20. No code/data, no fixed seeds, no variance across seeds (deep models' seed variance is often as large as the claimed gains).
21. Comparing against baselines the authors did not tune, on splits/labels different from the original papers'.
22. Data hygiene: exchange outages, missing intervals, tick-size or contract-spec changes, clock skews silently interpolated.

Positive version (minimum reporting standard for this repo): purged walk-forward on whole days with stated gap; raw point-to-point mid and executable labels with stored t0/t1; fold-local preprocessing with a truncation-invariance test; strictly-before quote join with daily sanity statistics; baselines (majority, persistence, imbalance logit); log-loss skill, MCC, IC, markout curve; net-of-fee executable return at stated tier and latency; day-block bootstrap CIs and per-month profile; trial count, DSR/PBO or reality-check; one lock-box period scored once.

### Gaps
- I did not find a survey that systematically audits published crypto LOB prediction papers for these flaws with counts; the checklist is assembled from the cited benchmark papers plus general leakage literature and my own judgement, not from a quantified audit.
- LOBCAST's and Briola et al.'s full texts were not readable this session, so finer points they may make (e.g. on seeds, hyperparameter sensitivity, profit analysis) are not captured.
- Several recent arXiv ids returned by search for 2026 papers (e.g. 2609.31491, 2609.16930) could not be opened or verified and should not be cited without checking.
