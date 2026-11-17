# Short-horizon prediction of trade sign and mid-price direction from order flow (L1 focus, Binance perps)

> **Provenance note for the report writer (read first).** In this session only web *search* worked; direct page fetches (arxiv.org, ar5iv, link.springer.com, alphaxiv, UCL/LSE repositories, Cont's site) were all blocked by the network allowlist. Consequently:
> - Items marked **[S]** were confirmed from search-result snippets this session.
> - Items marked **[R]** are recalled from my prior reading of the cited primary paper and were *not* re-verified against the full text. Treat specific numbers tagged [R] as "check the table before quoting".
> - Items under "Inferences" are my own derivations or judgments, not literature claims.
> - Three search hits carry arXiv ids dated July-August 2026 (2607.09426, 2607.09230, 2608.21888). I could not open them; only snippet-level content is reported.

---

## 1. What DeepLOB and successors report, and what the LOBCAST / Briola benchmark papers found

### Takeaway
The headline numbers (F1 of 75-88% on FI-2010) are artifacts of one small, down-sampled, 10-day Finnish dataset; on fresh NASDAQ data the same 15 models fall to 48-61% F1 (3-class), performance depends strongly on tick size (large-tick predictable, small-tick near chance), and both benchmark papers conclude that classification skill does not by itself give a tradeable signal.

### Cited Findings

**DeepLOB (Zhang, Zohren, Roberts 2019, IEEE Trans. Signal Processing; arXiv 1808.03668)**
- CNN + Inception + LSTM on 10 levels x 100 past snapshots, 3-class (up / flat / down) smoothed mid-price label. Claimed FI-2010 F1 of 83.40 / 72.82 / 80.35 at horizons k = 10 / 20 / 50 events [S, quoted in the BiN paper's comparison table] — [Tran et al., BiN paper, arXiv 2109.00983](https://arxiv.org/pdf/2109.00983); primary: [arXiv 1808.03668](https://arxiv.org/abs/1808.03668)
- Also tested on one year of LSE data for 5 stocks with a 3-month test period, and on stocks not in training ("universal features" claim). A third-party summary cites 70.17% out-of-sample accuracy at k = 20 on the LSE set [S, secondary; I recall ~70% / ~64% / ~61.5% at k = 20 / 50 / 100 from the paper's LSE table, R]. Search summaries disagree on the FI-2010 k = 10 F1 (83.40 vs 77.66; the two numbers correspond to different FI-2010 experimental setups) — [arXiv 1808.03668](https://arxiv.org/abs/1808.03668)
- FI-2010 is only 10 days of down-sampled data from a less liquid market (5 Nasdaq Nordic / Helsinki stocks, 2010) [S] — [arXiv 1808.03668](https://arxiv.org/abs/1808.03668)
- Caveat [R]: labels are a *smoothed* future mid-price average versus a (sometimes smoothed) current one, with a threshold alpha that sets class balance; smoothing makes the label partly a function of information already in the input window, inflating accuracy relative to a point-in-time "mid at t+k vs mid at t" label. LOBCAST and Briola et al. both discuss labelling sensitivity — [LOBCAST, arXiv 2308.01915](https://arxiv.org/abs/2308.01915)

**LOBCAST (Prata, Masi, Berti, Arrigoni, Coletta, Cannistraci, Vyetrenko, Velardi, Bartolini; arXiv 2308.01915, 2023; Artificial Intelligence Review 57:116, 2024)**
- Benchmarks 15 state-of-the-art DL models for LOB "stock price trend prediction" in an open-source framework (preprocessing, training, evaluation, profit analysis). Headline: "all models exhibit a significant performance drop when exposed to new data" [S] — [arXiv 2308.01915](https://arxiv.org/abs/2308.01915v2); [Springer](https://link.springer.com/article/10.1007/s10462-024-10715-4)
- Best FI-2010 score: BiN-CTABL, F1 = 87.7% at k = 5 [S] — [arXiv 2308.01915](https://arxiv.org/html/2308.01915)
- On the new LOB-2021 / LOB-2022 NASDAQ datasets all models land in the range 48-61% F1 [S]. BiN-CTABL, the FI-2010 leader, loses on average about 19.6% F1 across horizons (generalizability score 73.5%) [S] — [arXiv 2308.01915](https://arxiv.org/html/2308.01915)
- Summary conclusion: best models are "robust" (the FI-2010 numbers can be reproduced) but have "poor generalizability" [S] — [Springer](https://link.springer.com/article/10.1007/s10462-024-10715-4)
- Remember that these are 3-class macro-F1 scores, where the uninformed reference is about 33%, not 50%. 48-61% is skill, but far below the 80%+ in the original papers.

**Briola, Bartolucci, Aste, "Deep limit order book forecasting: a microstructural guide" (arXiv 2403.09267; Quantitative Finance 2025, doi 10.1080/14697688.2025.2522911)**
- 15 NASDAQ stocks over a 3-year period, DeepLOB as the reference model, horizons H in {10, 50, 100} LOB updates; releases the LOBFrame code base [S] — [arXiv 2403.09267](https://arxiv.org/html/2403.09267v4); [T&F](https://www.tandfonline.com/doi/full/10.1080/14697688.2025.2522911)
- Stocks classed by spread in ticks: large-tick (mean spread < 1.5 ticks), medium-tick (1.5 to 3 ticks), small-tick (> 3 ticks) [S] — [arXiv 2403.09267](https://arxiv.org/html/2403.09267v1)
- Average MCC for small-tick stocks is 0.11 at H10 and falls nearly to zero at H100; a summary site reports about 0.29 for large-tick stocks at H10 (not confirmed in the primary text); large-tick stocks also show lower variance of MCC across horizons [S] — [PMC full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC12315853/); [emergentmind summary](https://www.emergentmind.com/papers/2403.09267)
- They argue standard ML metrics are inadequate and propose p_T, the probability of correctly forecasting a *complete transaction* (open and close). p_T falls as the probability threshold rises and increases from small-tick to large-tick stocks; the number of exploitable mid-price changes is about one order of magnitude higher for small-tick stocks [S] — [PubMed abstract](https://pubmed.ncbi.nlm.nih.gov/40755861/)
- Stated conclusion: "high forecasting power does not necessarily correspond to actionable trading signals" [S] — [arXiv 2403.09267](https://arxiv.org/pdf/2403.09267v2)
- Follow-up: HLOB (Briola, Bartolucci, Aste; arXiv 2405.18938) uses an information-filtering-network structure over LOB levels; same data family [S] — [arXiv 2405.18938](https://arxiv.org/html/2405.18938v3)

**Newer (2025-2026)**
- TLOB (Berti and Kasneci, arXiv 2502.15757, 2025): dual-attention transformer; claims SoTA on FI-2010, a NASDAQ set (Tesla, Intel) and a Bitcoin set at four horizons. Reported gains differ between arXiv versions (+2.67% / +14.16% F1 in one version; +1.3 / +7.7 F1 points in another). Two honest negative findings: predictability declined over time (-6.68 F1 points), and when the trend label is redefined using the average spread as the cost threshold, performance deteriorates, "underscoring the complexity of translating trend classification into profitable trading strategies" [S] — [arXiv 2502.15757](https://arxiv.org/abs/2502.15757)
- Other successors named in the brief (DeepLOB-Attention / seq2seq multi-horizon by Zhang and Zohren 2021, TransLOB by Wallbridge 2020, Axial-LOB arXiv 2212.01807) are all among or adjacent to the models LOBCAST re-ran; none escaped the generalization drop [S for LOBCAST's blanket statement; R for the membership list] — [arXiv 2308.01915](https://arxiv.org/abs/2308.01915)

### Inferences
- The literature's "accuracy" numbers are not comparable across papers: they depend on (a) number of classes, (b) the label-smoothing window, (c) the flat-class threshold, (d) event-time vs clock-time horizon, (e) tick-size regime. A project should fix one unsmoothed label and report against explicit baselines rather than against published numbers.
- For a CPU-only, L1-only project, reproducing DeepLOB-class models is neither feasible (they need 10 levels) nor well motivated by the evidence: the benchmark papers suggest input representation and microstructure regime matter more than architecture.

### Gaps
- Per-model LOB-2021/2022 tables from LOBCAST (Table 6) and exact MCC by tick class from Briola et al. could not be read (fetch blocked). The 0.29 large-tick MCC figure is from an aggregator only.
- LOBCAST's profit-analysis numbers were not retrieved; I only confirmed that a profit analysis exists.
- No peer-reviewed replication of TLOB's Bitcoin results was found.

---

## 2. Gradient boosting and linear models on hand-built features versus deep models

### Takeaway
The best-supported finding is about *inputs*, not architectures: stationary order-flow features (OFI and its multi-level variants) beat raw book states, and once such features are used, simple networks, linear ARX models and gradient-boosted trees are close to each other; the genuinely large R-squared numbers attached to OFI are contemporaneous (explanatory), not predictive.

### Cited Findings

**Cont, Kukanov, Stoikov (2014), "The price impact of order book events", J. Financial Econometrics 12(1):47-88; arXiv 1011.6402**
- Defines order flow imbalance (OFI) from changes in size and price at the best bid and ask (an L1-only quantity). Over short intervals price changes are linear in OFI with slope inversely proportional to depth; robust across time scales and 50 US stocks (NYSE TAQ) [S] — [arXiv 1011.6402](https://arxiv.org/abs/1011.6402); [JFEC](https://ideas.repec.org/a/oup/jfinec/v12y2013i1p47-88.html)
- The OFI relation is less noisy and more robust than the trade-volume / square-root relation [S] — [arXiv 1011.6402](https://arxiv.org/abs/1011.6402)
- The commonly quoted figure is an average R-squared of about 65% for 10-second windows, versus about 32% for trade imbalance [R; search could not confirm the number]. Critical point: this is a regression of the price change on OFI over the *same* window. It is an impact (explanatory) relation, not a forecast — [arXiv 1011.6402](https://arxiv.org/abs/1011.6402)

**Kolm, Turiel, Westray (2023), "Deep order flow imbalance: Extracting alpha at multiple horizons from the limit order book", Mathematical Finance 33(4):1044-1081; SSRN 3900141**
- 115 Nasdaq stocks, LOBSTER data, Jan 2019 to Jan 2020; models: ARX (linear), MLP, LSTM, LSTM-MLP, stacked LSTM, CNN-LSTM; output is an "alpha term structure" (vector of mid-price return forecasts over multiple horizons) [S] — [SSRN 3900141](https://papers.ssrn.com/abstract=3900141); [Wiley](https://onlinelibrary.wiley.com/doi/10.1111/mafi.12413)
- "Models trained on order flow significantly outperform most models trained directly on order books"; simple off-the-shelf networks on stationary order-flow inputs reach state-of-the-art accuracy [S] — [SSRN 3900141](https://papers.ssrn.com/abstract=3900141)
- Effective horizon of stock-specific forecasts is about two average price changes; accuracy peaks there and then declines [S] — [SSRN 3900141](https://papers.ssrn.com/abstract=3900141)
- "Information-rich" stocks (more book updates per price change, i.e. large-tick-like) are predicted more accurately [S] — [SSRN 3900141](https://papers.ssrn.com/abstract=3900141)
- An independent replication on IEX data (GitHub, not peer reviewed) reports mean out-of-sample R-squared of 0.35% (CNN-LSTM), 0.30% (LSTM), 0.27% (ARX ridge). That is, the deep model's edge over the linear OFI model was about 0.03 to 0.08 percentage points of R-squared [S] — [GitHub replication](https://github.com/Sudarikovamaria/DEEP-ORDER-FLOW-IMBALANCE-EXTRACTING-ALPHA-AT-MULTIPLE-HORIZONS-FROM-THE-LIMIT-ORDER-BOOK)
- Flag: one search summary attributed "R-squared rising from about 55% to about 80% across ten levels" to this paper. That pattern matches contemporaneous multi-level/integrated OFI regressions (Cont, Cucuringu, Zhang 2023, "Cross-impact of order flow imbalance in equity markets", Quantitative Finance) rather than Kolm et al.'s forecasting results; treat the attribution as unreliable [S for the snippet; R for the correction] — [ResearchGate record](https://www.researchgate.net/publication/372568099_Deep_order_flow_imbalance_Extracting_alpha_at_multiple_horizons_from_the_limit_order_book)

**Lucchese, Pakkanen, Veraart (2024), "The short-term predictability of returns in order book markets: a deep learning perspective", Int. J. Forecasting 40(4):1587-1621; arXiv 2211.13777**
- Systematic large-scale study of whether high-frequency returns show order-book-driven predictability and which representation (raw book, order flow, volume) works best; conclusion that predictability exists at high frequency and is representation dependent [S] — [arXiv 2211.13777](https://arxiv.org/abs/2211.13777); [author page](https://www.lorenzolucchese.com/research)
- Mechanism they emphasise: the thinner side of the book erodes faster, moving the price toward it (queue-imbalance logic) [S] — [arXiv 2211.13777](https://arxiv.org/pdf/2211.13777)

**Gould and Bonart (2016), "Queue imbalance as a one-tick-ahead price predictor in a limit order book", Market Microstructure and Liquidity 2(2); arXiv 1512.03492**
- Logistic regression of next mid-price move direction on L1 queue imbalance I = (q_bid - q_ask)/(q_bid + q_ask), 10 liquid Nasdaq stocks. Strongly statistically significant for every stock; versus a null model the improvement in binary and probabilistic classification is "considerable" for large-tick stocks and "moderate" for small-tick stocks; local/semi-parametric fits only "slightly outperform" logistic regression [S] — [arXiv 1512.03492](https://ideas.repec.org/p/arx/papers/1512.03492.html); [SSRN 2702117](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2702117)

**Sirignano and Cont (2019), "Universal features of price formation in financial markets: perspectives from deep learning", Quantitative Finance 19(9):1449-1459; arXiv 1803.06917**
- LSTM-type network trained on billions of quotes and transactions for roughly 500-1000 US stocks, predicting the direction of the next mid-price move (binary; metric = fraction correct) [S] — [arXiv 1803.06917](https://arxiv.org/pdf/1803.06917v1); [EconPapers](https://econpapers.repec.org/article/tafquantf/v_3a19_3ay_3a2019_3ai_3a9_3ap_3a1449-1459.htm)
- Claims: a single "universal" model trained on all stocks beats stock-specific models, generalises to stocks not in training, is stable out of sample in time, and benefits from long history (path dependence). Secondary summaries quote a 19-month training window improving average accuracy by 7.2% over one month, and give conflicting figures for universal vs held-out-stock comparisons (-0.15% vs +1.45%) [S, secondary and internally inconsistent] — [GitHub paper summary](https://github.com/jjakimoto/research-issues/issues/1884)
- The outcome is next-mid-direction accuracy, not executable profitability [S] — [GitHub paper summary](https://github.com/jjakimoto/research-issues/issues/1884)

**Gradient boosting specifically**
- "Explainable Patterns in Cryptocurrency Microstructure" (arXiv 2602.00776, Jan 2026): gradient-boosted trees + SHAP on Binance Futures perpetual order books and trades at 1-second frequency, 1 Jan 2022 to 12 Oct 2025, for BTC, LTC, ETC, ENJ, ROSE. Top SHAP features consistently: order flow imbalance, bid-ask spread, VWAP-to-mid deviation. OFI effect is monotone with concavity at extremes; wide spreads associate with reduced predictability; feature-response shapes are similar across assets spanning an order of magnitude in market cap. Economic test: a conservative top-of-book taker backtest and a fixed-depth maker backtest [S; headline metrics not retrieved] — [arXiv 2602.00776](https://arxiv.org/abs/2602.00776)
- "Exploring Microstructural Dynamics in Cryptocurrency Limit Order Books" (arXiv 2506.05764, 2025): argues supply-demand asymmetries precede short-horizon mid moves [S]; my recollection is that its central claim is that with careful denoising/feature construction, logistic regression and XGBoost match or beat DeepLOB-style networks on BTC/USDT book data, i.e. "better inputs matter more than another hidden layer" [R, not re-verified; exchange and exact numbers unconfirmed] — [arXiv 2506.05764](https://arxiv.org/html/2506.05764v2)

### Inferences
- Consistent pattern across Kolm et al., Lucchese et al., the IEX replication and the 2025-2026 crypto papers: feature engineering toward stationarity (flows and imbalances rather than levels) captures most of the available signal; the marginal gain of deep sequence models over ARX/boosted trees is small in absolute R-squared terms (order 0.01-0.1 percentage points in the one replication with numbers).
- For tabular features at 100M rows on CPU, LightGBM (histogram method) and L2-regularised logistic regression are the appropriate model families; an LSTM/CNN adds cost without evidence of material gain in the L1 setting.
- Always separate "contemporaneous R-squared" (OFI explains the concurrent price change, 50-80%) from "predictive R-squared" (lagged OFI forecasts the next interval, typically well under 1% for returns). Papers and blog posts routinely blur this.

### Gaps
- I found no peer-reviewed head-to-head of LightGBM/XGBoost vs DeepLOB on identical L1-only inputs with matched tuning budgets.
- Kolm et al.'s exact out-of-sample R-squared by model and horizon, Lucchese et al.'s L1-vs-deeper tables, Gould-Bonart's per-stock AUC values and Sirignano-Cont's headline accuracy could not be read (fetch blocked).
- Headline predictive metrics and net-of-cost backtest results of arXiv 2602.00776 not retrieved.

---

## 3. What is achievable with L1 only versus deeper levels; crypto / Binance evidence

### Takeaway
L1 data already contains the two strongest documented predictors (queue imbalance and best-level OFI) plus the full trade tape, and for large-tick instruments most of the next-move signal sits at the touch; deeper levels help mainly for explanatory R-squared and for small-tick assets. Honest crypto evidence is thin, mostly preprint-level, and where costs are addressed the signal is generally not taker-tradeable.

### Cited Findings
- OFI as defined by Cont-Kukanov-Stoikov uses only best bid/ask price and size changes, so it is computable from Binance bookTicker; queue imbalance likewise [S] — [arXiv 1011.6402](https://arxiv.org/abs/1011.6402); [arXiv 1512.03492](https://ideas.repec.org/p/arx/papers/1512.03492.html)
- L1 queue imbalance alone gives "considerable" classification improvement for large-tick stocks, only "moderate" for small-tick [S] — [Gould and Bonart](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2702117)
- Deep models' skill is concentrated in large-tick stocks (dense, compact books) and collapses for small-tick stocks (MCC 0.11 at H10, about 0 at H100) [S] — [Briola et al., PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC12315853/)
- Stocks with more book updates per price change are more predictable [S] — [Kolm et al., SSRN 3900141](https://papers.ssrn.com/abstract=3900141)
- Binance perps, 1-second, 2022-2025, boosted trees: OFI, spread and VWAP-to-mid are the dominant features across five assets [S]. VWAP-to-mid needs depth; OFI and spread are L1 — [arXiv 2602.00776](https://arxiv.org/abs/2602.00776)
- Binance perpetual LOB snapshots (from 27 Nov 2024, several coins) used for mid-price forecasting with image-style representations; claims SoTA; out-of-sample protocol not confirmed from excerpts [S] — [arXiv 2504.13521](https://arxiv.org/html/2504.13521v2)
- LSTM on Binance BTC-USDT trade-by-trade data claims accuracy above 60%; the same line of work is flagged for possibly reflecting skewed class distributions [S] — [arXiv 2010.07404](https://arxiv.org/pdf/2010.07404)
- 2026 preprint on short-horizon mean reversion in crypto (uses Binance kline taker-buy volume to sign flow, no book data): "adding twelve lags of imbalance to the sign path adds nothing out of sample, while the sign path beats flow alone" [S, snippet only] — [arXiv 2608.21888](https://arxiv.org/pdf/2608.21888)
- 2026 preprint on six Binance perpetuals: signed order flow and returns show serial dependence at quarter-hour boundaries, concentrated in the first seconds (periodic algorithmic execution) [S, snippet only] — [arXiv 2607.09426](https://arxiv.org/html/2607.09426v2)
- 2026 preprint "When Does Order Flow Matter? State-Dependent L2 Liquidity-State Transitions in Crypto Futures" exists; content not retrieved [S, title only] — [arXiv 2607.09230](https://arxiv.org/pdf/2607.09230)
- Hawkes-based crypto LOB forecasting (arXiv 2312.16190) exists as an alternative model family [S, title only] — [arXiv 2312.16190](https://arxiv.org/pdf/2312.16190)
- A MathWorks LOB backtest example illustrates the class-imbalance trap: one model reaches 91% accuracy by predicting the constant class; a useful model scored about 61% [S] — [MathWorks](https://www.mathworks.com/help/finance/backtest-deep-learning-model-for-algorithmic-trading-of-limit-order-book-data.html)

### Inferences
- BTCUSDT and ETHUSDT perps on Binance are large-tick instruments in the Briola/Gould-Bonart sense (the spread is pinned at one tick nearly all the time). The equity literature therefore predicts that (a) L1 queue imbalance is a strong predictor of the direction of the next mid change, and (b) deeper levels would add comparatively little for that specific target. This is the favourable regime for an L1-only study.
- The same fact makes the signal untradeable for a taker: the next mid move is typically one tick, which is a tiny fraction of a basis point at BTC prices, while taker fees on Binance USDT-M are several basis points per side (fee schedule: [Binance](https://www.binance.com/en/fee/futureFee); not re-verified this session). Predicting a one-tick move correctly 70% of the time is worth far less than the round-trip cost. Any value is in maker-side queue/skew decisions or execution timing, which cannot be evaluated properly without queue-position data.
- bookTicker limitations to state up front: no depth beyond the touch (no multi-level OFI, no depth-weighted microprice), updates may be coalesced, and aggTrades merge fills of one taker order at one price, so "event" and "trade" definitions differ from the equity LOBSTER literature. Trade-to-quote timestamp alignment (transaction time vs event time) is a material look-ahead risk.
- Alt-coin perps with wider spreads in ticks are the small-tick regime; expect markedly lower L1 predictability there. A tick-size-stratified comparison (BTC vs a small-tick alt) would be a cheap, publishable-quality replication of the Briola/Gould-Bonart tick-size effect in crypto.

### Gaps
- I found no peer-reviewed paper reporting out-of-sample next-trade-sign or next-mid-direction accuracy for Binance USDT-M perps using only bookTicker + aggTrades. The closest items are preprints using depth data or klines.
- The three mid-2026 arXiv preprints could not be opened; their methods and robustness are unassessed.
- No verified quantitative comparison of "L1 only" vs "L1 + depth" on the same crypto dataset was retrieved.

---

## 4. Theory-derived baselines: optimal linear predictor of a long-memory sign series

### Takeaway
The order-sign series is long-memory (ACF C(l) ~ c0 * l^(-gamma), gamma typically 0.2-0.7), so the next sign is substantially predictable by a linear filter of past signs; the best linear predictor follows from the ACF via Yule-Walker (FARIMA closed form: weights decaying as k^(-(3-gamma)/2)), and it implies roughly 60-70% sign accuracy for typical gamma. I found no published study benchmarking modern ML sign predictors against this filter, which makes it the natural, under-used baseline.

### Cited Findings
- Lillo and Farmer (2004), "The long memory of the efficient market", Studies in Nonlinear Dynamics and Econometrics 8(3); arXiv cond-mat/0311053: LSE order signs are a long-memory process, ACF ~ tau^(-alpha) with alpha about 0.6, Hurst H about 0.7; this would make signs "fairly predictable" and imply inefficiency, but is compensated by anti-correlated fluctuations in transaction size and liquidity that keep returns nearly uncorrelated [S] — [arXiv cond-mat/0311053](https://arxiv.org/abs/cond-mat/0311053)
- Persistence remains statistically significant beyond 10^4 transactions (Vodafone example: about ten trading days); cross-sectional Hurst exponents of 0.75-0.88 are reported in the related Mike-Farmer work [S, secondary summaries] — [paper summary](https://github.com/jjakimoto/research-issues/issues/1603); [arXiv 0709.0159](https://arxiv.org/pdf/0709.0159)
- Origin: order splitting of large hidden (meta)orders. If metaorder sizes have a Pareto tail with exponent alpha, the sign ACF decays with gamma = alpha - 1 (Lillo, Mike, Farmer 2005) [S] — [arXiv cond-mat/0412708](https://arxiv.org/abs/cond-mat/0412708); [Bouchaud, Farmer, Lillo 2009, arXiv 0809.0822](https://arxiv.org/pdf/0809.0822)
- Bouchaud, Gefen, Potters, Wyart (2004), "Fluctuations and response in financial markets: the subtle nature of random price changes", Quantitative Finance 4(2):176-190 (arXiv cond-mat/0307332): introduces the propagator (transient impact) model p_t = sum_{s<t} G(t-s) eps_s + noise; with C(l) ~ l^(-gamma), price diffusivity requires G(l) ~ l^(-beta) with beta = (1 - gamma)/2 [R; the search confirmed only that "persistent order signs require power-law-decaying propagator impact", not the exponent formula] — [BFL 2009, arXiv 0809.0822](https://arxiv.org/pdf/0809.0822)
- Bouchaud, Farmer, Lillo (2009), "How markets slowly digest changes in supply and demand", in Handbook of Financial Markets: Dynamics and Evolution (arXiv 0809.0822): typical gamma about 0.5; shows that with an infinite-order linear sign predictor, the "surprise" (history-dependent) impact model is mathematically equivalent to the propagator model [S] — [arXiv 0809.0822](https://arxiv.org/pdf/0809.0822)
- The surprise model [R for exact notation]: r_t = theta * (eps_t - eps_hat_t) + eta_t, with eps_hat_t = E[eps_t | past] = sum_{k>=1} a_k eps_{t-k}. Returns are then uncorrelated by construction because only the unpredictable part of the sign moves the price. Equivalently ("asymmetric liquidity", Lillo-Farmer): a trade in the expected direction has smaller impact r+ than one against it r-, with p*r+ = (1-p)*r- where p is the predicted probability — [arXiv 0809.0822](https://arxiv.org/pdf/0809.0822); [arXiv cond-mat/0311053](https://arxiv.org/abs/cond-mat/0311053)
- Taranto, Bormetti, Bouchaud, Lillo, Toth (2018), "Linear models for the impact of order flow on prices I: history dependent impact models", Quantitative Finance 18(6):903-915 (arXiv 1602.02735): compares the Transient Impact Model (TIM, propagator on raw signs) with the History Dependent Impact Model (HDIM, impact of sign surprises). Both miss that prices respond to their own past moves, so they extend to two event types (price-changing vs non-price-changing). The extension improves fit notably for large-tick stocks; HDIMs do somewhat better than TIMs but the gap is small, which the authors find surprising [S] — [arXiv 1602.02735](https://arxiv.org/abs/1602.02735); [QF](https://econpapers.repec.org/RePEc:taf:quantf:v:18:y:2018:i:6:p:903-915)
- Part II (Quantitative Finance 18(6):917-931, arXiv 1604.07556) models the signed event stream itself with a Mixture Transition Distribution (MTD) model rather than treating order flow as exogenous [S] — [arXiv 1604.07556](https://econpapers.repec.org/paper/arxpapers/1604.07556.htm)
- DAR(p) sign model: X_n is copied from X_{n-i} with probability chi*phi_i or drawn fresh with probability 1 - chi; its conditional expectation is exactly linear: E[X_n | past] = chi * sum_i phi_i X_{n-i} + mu(1 - chi) [S] — [Taranto et al., "The adaptive nature of liquidity taking in limit order books", arXiv 1403.0842](https://arxiv.org/pdf/1403.0842)
- Order-sign long memory with similar exponents is also documented in FX spot [S, title/abstract level] — [arXiv 1504.04354](https://arxiv.org/pdf/1504.04354)
- General theory of finite-past linear prediction error for long-memory processes [S, title] — [arXiv 0705.1927](https://arxiv.org/pdf/0705.1927)
- Only direct "ML vs autoregressive sign baseline" comparison found: a Kinetic Ising Model for *trader-level* order signs beats an autoregressive logistic benchmark by about 5 to over 10 points, with about 60% average accuracy and 70% best case; multivariate extension gave no significant gain [S]. This is for identified traders, not the anonymous market sign series — [arXiv 1909.10807](https://arxiv.org/pdf/1909.10807)

### Inferences (derivations; mine, not quoted from the literature)

**Best linear predictor from the ACF.** For a zero-mean stationary sign series with ACF C(l) (C(0) = 1), the order-p predictor eps_hat_t = sum_{k=1..p} a_k eps_{t-k} has weights solving Yule-Walker: sum_{j=1..p} a_j C(|k - j|) = C(k) for k = 1..p (Levinson-Durbin, O(p^2)). Because eps is +/-1, E[eps_t | past] = 2 P(eps_t = +1 | past) - 1, so the implied probability is P(+1) = (1 + eps_hat_t)/2. Under the DAR model this linear form is the exact conditional expectation, not an approximation.

**FARIMA(0,d,0) closed form.** With d = H - 1/2 = (1 - gamma)/2: a_k = -Gamma(k - d) / (Gamma(k + 1) Gamma(-d)) ~ k^(-1-d) = k^(-(3-gamma)/2). ACF rho(1) = d/(1 - d); one-step R-squared (fraction of sign variance that is predictable) = 1 - Gamma(1-d)^2 / Gamma(1-2d).

**Implied accuracy.** Predict sign(eps_hat). Accuracy = E[max(p, 1-p)] = (1 + E|eps_hat|)/2. With a Gaussian approximation for eps_hat (sd = sqrt(R2)), E|eps_hat| = sqrt(2 R2 / pi):

| gamma | d | H | rho(1) | R2 | approx. accuracy | lag-1-only accuracy (1+rho(1))/2 |
|---|---|---|---|---|---|---|
| 0.8 | 0.10 | 0.60 | 0.11 | 0.019 | 0.555 | 0.556 |
| 0.6 | 0.20 | 0.70 | 0.25 | 0.090 | 0.62 | 0.625 |
| 0.5 | 0.25 | 0.75 | 0.33 | 0.153 | 0.66 | 0.667 |
| 0.4 | 0.30 | 0.80 | 0.43 | 0.238 | 0.69 | 0.714 |
| 0.3 | 0.35 | 0.85 | 0.54 | 0.359 | 0.74 | 0.769 |

Caveats on this table: (i) pure FARIMA(0,d,0) ties the ACF prefactor c0 to gamma; real sign ACFs have a free prefactor, so compute R2 and accuracy from the *empirical* ACF via Yule-Walker rather than from gamma alone. (ii) The Gaussian approximation for eps_hat is crude for a bounded binary process, as shown by the last column: the trivial "repeat last sign" rule has accuracy exactly (1 + C(1))/2 and under FARIMA comes out equal to or above the Gaussian-approximated full-filter number, which cannot be true of the actual optimal filter in MSE terms. The right reading: in hard-classification accuracy, "repeat last sign" captures nearly all of what the long-memory filter delivers; the long filter's gain shows up in *probabilistic* metrics (log-loss, Brier, AUC, calibration) and when the last few signs disagree. A project should report both.

**Baseline ladder this implies for sign prediction:** (0) unconditional majority class; (1) repeat last sign, accuracy (1 + C(1))/2; (2) AR(p)/Yule-Walker or FARIMA linear filter with p in the hundreds to thousands; (3) DAR/MTD; (4) logistic regression on lagged signs (the same information set as (2), a fair "linear in logit" comparator); (5) logistic/LightGBM adding L1 state (queue imbalance, spread, recent OFI, inter-trade durations, sizes). The scientifically interesting quantity is the increment from (2) to (5): how much the book state knows about the next sign beyond the sign history.

### Gaps
- I could not open Lillo-Farmer or BFL 2009 to quote their exact predictor formulas, the FARIMA coefficient expression or any stated sign-prediction accuracy; the formulas above are standard time-series results (Hosking-type FARIMA) and my own arithmetic.
- The exponent relation beta = (1 - gamma)/2 and the asymmetric-liquidity condition are recalled, not re-verified.
- No published comparison of gradient boosting or deep nets against the Yule-Walker/FARIMA sign predictor on market-wide anonymous trade signs was found. Absence of evidence after a limited search; a dedicated arXiv search might find one.
- No measured gamma or C(1) for Binance perp aggTrades was found in the literature; the project must estimate it (and note that aggTrade aggregation changes C(1) relative to raw fills).

---

## 5. Why sign predictability does not imply price predictability

### Takeaway
Sign persistence is public information, so liquidity providers price it in: only the *surprise* component of order flow moves the price, impact is transient/history-dependent in exactly the way needed to cancel the sign correlations, and returns stay near-uncorrelated. An ML model's sign accuracy therefore measures how well it recovers publicly known flow structure, not alpha.

### Cited Findings
- Lillo and Farmer: the predictability of signs "would imply market inefficiency" but is offset by anti-correlated, also long-memory, fluctuations in transaction size and liquidity, leaving returns approximately uncorrelated [S] — [arXiv cond-mat/0311053](https://arxiv.org/abs/cond-mat/0311053)
- BFL 2009: if market order signs are strongly autocorrelated and impact were fixed and permanent, returns would be strongly autocorrelated and prices predictable; efficiency requires either a power-law decaying propagator or the equivalent asymmetric-liquidity (surprise) mechanism, and the two descriptions are equivalent under a linear predictor [S] — [arXiv 0809.0822](https://arxiv.org/pdf/0809.0822)
- Critical balance [R]: with C(l) ~ l^(-gamma) and G(l) ~ l^(-beta), beta < (1-gamma)/2 gives super-diffusion (trending), beta > (1-gamma)/2 sub-diffusion (mean reversion); markets sit at beta = (1-gamma)/2 — [arXiv 0809.0822](https://arxiv.org/pdf/0809.0822); see also [Bouchaud, "The endogenous dynamics of markets: price impact and feedback loops", arXiv 1009.2928](https://arxiv.org/pdf/1009.2928)
- Theoretical grounding of the same result under competitive market making with autocorrelated flow [S, title/abstract level] — [Farmer, Gerig, Lillo, Waelbroeck, "Market impact with autocorrelated order flow under perfect competition", arXiv 1212.4770](https://arxiv.org/pdf/1212.4770)
- Empirically the cancellation is close but not exact: HDIM (surprise) fits only slightly better than TIM, and both need the price-changing / non-price-changing event split, especially for large-tick stocks [S] — [arXiv 1602.02735](https://arxiv.org/abs/1602.02735)
- Deep-learning literature reaches the same conclusion from the other side: "high forecasting power does not necessarily correspond to actionable trading signals" [S] — [Briola et al.](https://arxiv.org/pdf/2403.09267v2); spread-aware labels erase much of the measured skill [S] — [TLOB](https://arxiv.org/abs/2502.15757)

### Inferences
- Interpretation rules for the project's ML results:
  1. High next-sign accuracy (60-75%) is the *expected* outcome and is fully compatible with an efficient market. Report it against the linear long-memory baseline, not against 50%.
  2. The mid-price a trade prints against already reflects the expected sign. The relevant test of price information is whether predicted sign *surprise*, or the model's residual signal beyond eps_hat, forecasts future mid returns.
  3. Next-mid-direction predictability from queue imbalance in a large-tick market is partly mechanical (the thin queue depletes first) and bounded by one tick; it is a statement about queue dynamics inside the spread, not about returns exceeding costs.
  4. A direct, cheap efficiency check: regress r_t on eps_hat_t and on (eps_t - eps_hat_t). The surprise model predicts a zero coefficient on eps_hat and a positive one on the surprise; a response-function plot R(l) = E[(m_{t+l} - m_t) * eps_t] conditioned on predicted vs unpredicted signs makes the same point visually.
  5. Microstructure artifacts masquerade as price predictability: bid-ask bounce in trade prices (use mid or microprice targets), stale or coalesced quotes, timestamp misalignment between the trade and quote streams, and overlapping labels.

### Gaps
- No study testing the surprise/asymmetric-liquidity relation on Binance perpetuals was found.
- Whether crypto perps deviate measurably from critical balance (e.g. residual short-lag return autocorrelation) is an open empirical question in the retrieved literature; the 2026 quarter-hour-effect preprint hints at localized exceptions but was not read in full.

---

## 6. Realistic, defensible accuracy / AUC ranges at horizons of 1 to 100 events

### Takeaway
Defensible numbers are modest and target-specific: roughly 60-75% accuracy for next-trade sign (most of it from sign history alone), a strong but one-tick-bounded edge for next-mid-change direction in large-tick markets, and rapid decay toward chance within tens of events; anything far above these ranges for unsmoothed, point-in-time labels should be presumed leakage or label artifact until proven otherwise.

### Cited Findings
- Sign ACF exponent gamma about 0.5-0.6 (H about 0.7-0.75) in equities; persistence detectable past 10^4 trades [S] — [arXiv cond-mat/0311053](https://arxiv.org/abs/cond-mat/0311053); [arXiv 0809.0822](https://arxiv.org/pdf/0809.0822)
- Trader-level sign prediction: about 60% average, 70% best case, 5-10 points above an AR-logistic benchmark [S] — [arXiv 1909.10807](https://arxiv.org/pdf/1909.10807)
- Binance BTC-USDT trade-by-trade LSTM: "over 60%" accuracy, with a class-skew caveat [S] — [arXiv 2010.07404](https://arxiv.org/pdf/2010.07404)
- 3-class mid-trend on fresh NASDAQ data, 15 deep models, full 10-level book: 48-61% F1 [S] — [LOBCAST](https://arxiv.org/html/2308.01915)
- DeepLOB on LSE, 3-class smoothed labels: about 70% at k = 20 declining to about 61-64% at k = 50-100 [S secondary / R] — [arXiv 1808.03668](https://arxiv.org/abs/1808.03668)
- MCC with DeepLOB: 0.11 (small-tick, H10), about 0 (small-tick, H100); roughly 0.3 reported for large-tick at H10 by a secondary source [S] — [Briola et al., PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC12315853/); [emergentmind](https://www.emergentmind.com/papers/2403.09267)
- Forecast horizon for return prediction from order flow is about two average price changes [S] — [Kolm et al.](https://papers.ssrn.com/abstract=3900141)
- Predictive return R-squared from OFI-type models in an independent replication: 0.27-0.35% [S] — [GitHub replication](https://github.com/Sudarikovamaria/DEEP-ORDER-FLOW-IMBALANCE-EXTRACTING-ALPHA-AT-MULTIPLE-HORIZONS-FROM-THE-LIMIT-ORDER-BOOK)
- Predictability has declined over time (-6.68 F1 points across the periods TLOB compares) [S] — [arXiv 2502.15757](https://arxiv.org/abs/2502.15757)
- Practitioner (non-peer-reviewed) reference point for much longer horizons: BTC 4-hour direction LightGBM AUC about 0.58 [S, blog; low reliability] — [Medium post](https://medium.com/@laostjen/machine-learning-models-that-actually-work-in-crypto-trading-78a6735b5639)

### Inferences (my judgment; ranges are priors to be tested, not literature values)

| Target | Horizon | Plausible out-of-sample range | Basis |
|---|---|---|---|
| Next aggTrade sign, sign history only | 1 trade | accuracy 0.60-0.72; AUC 0.65-0.78 | (1 + C(1))/2 with C(1) in 0.2-0.45; FARIMA table in section 4 |
| Next aggTrade sign, plus L1 state (queue imbalance, spread, OFI, durations) | 1 trade | a few points above the row above; accuracy 0.65-0.78 | Book state informs which side is about to be hit; no direct published number |
| Sign of trade t+h | 10 trades | accuracy 0.55-0.62 | ACF decay h^(-gamma) from the lag-1 level |
| Sign of trade t+h | 100 trades | accuracy 0.51-0.56 | Same; long memory keeps it measurably above 0.5 |
| Net signed-flow direction over next h trades | 10-100 | higher than single-sign at the same h (aggregation) | Persistent flow sums coherently; compare with the linear filter |
| Direction of next mid *change* (binary, conditional on a change), large-tick (BTC/ETH) | next change | accuracy 0.60-0.75; AUC 0.65-0.80 | Gould-Bonart "considerable" for large-tick; Sirignano-Cont; Briola large-tick |
| Same, small-tick alt perps | next change | accuracy 0.52-0.58 | Gould-Bonart "moderate"; Briola MCC about 0.1 |
| Mid direction at fixed event horizon, unsmoothed, 3-class with flat | 10 events | MCC 0.1-0.3 | Briola et al. |
| Same | 100 events | MCC 0.0-0.1; binary accuracy 0.50-0.53 | Briola; Kolm (horizon about 2 price changes) |
| Mid *return* regression | 1-100 events | predictive R2 well under 1% | IEX replication of Kolm et al. |

- Red flags that a result is too good: 3-class accuracy above about 75% or binary mid-direction above about 80% on unsmoothed labels; skill that does not decay with horizon; skill that vanishes when quotes are lagged by one update or when the test period is moved by a year; "accuracy" dominated by the flat class.
- Metrics to report: accuracy and AUC *with* class base rates, MCC, log-loss/Brier skill score relative to each baseline in the ladder, calibration curves, and performance by horizon, by month (2023-2026 drift) and by tick-size regime.
- With about 100M trades, statistical significance is trivial to obtain; effect size versus the theory baseline and stability across walk-forward folds are the meaningful evidence. Use block bootstrap or day-clustered standard errors because of the long memory.

### Gaps
- No published, peer-reviewed accuracy/AUC for next-trade-sign prediction on anonymous market data with ML models plus book state was found; the ranges above are derived, not sourced.
- No published sign ACF exponent for Binance perps located.

---

## 7. What a small rigorous project should use as models and baselines (L1 + trades, CPU only)

### Takeaway
Use a baseline ladder rooted in theory (repeat-last-sign, Yule-Walker/FARIMA filter, queue-imbalance logistic), then logistic regression and LightGBM on a compact L1 feature set, evaluated by purged walk-forward on unsmoothed labels; the defensible contribution is the measured increment over the theory baselines and its tick-size and time dependence, not a headline accuracy.

### Cited Findings
- Stationary order-flow inputs beat raw book levels [S] — [Kolm et al.](https://papers.ssrn.com/abstract=3900141)
- L1 OFI and queue imbalance are established predictors computable from best quotes [S] — [Cont et al.](https://arxiv.org/abs/1011.6402); [Gould and Bonart](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2702117)
- On Binance perps, boosted trees rank OFI, spread and VWAP-to-mid highest, with stable response shapes across assets [S] — [arXiv 2602.00776](https://arxiv.org/abs/2602.00776)
- Deep models generalise poorly out of period and their skill is tick-size dependent [S] — [LOBCAST](https://arxiv.org/abs/2308.01915v2); [Briola et al.](https://arxiv.org/html/2403.09267v4)
- Logistic regression is within a small margin of more flexible local fits for queue imbalance [S] — [Gould and Bonart](https://ideas.repec.org/p/arx/papers/1512.03492.html)
- Evaluating by complete-transaction probability and with spread-aware labels gives a more honest picture than raw classification metrics [S] — [Briola et al., PubMed](https://pubmed.ncbi.nlm.nih.gov/40755861/); [TLOB](https://arxiv.org/abs/2502.15757)
- The linear sign predictor and surprise decomposition are the standard theoretical reference [S] — [BFL 2009](https://arxiv.org/pdf/0809.0822); [Taranto et al. 2018](https://arxiv.org/abs/1602.02735)

### Inferences (recommendations)
- **Targets:** (A) sign of next aggTrade and of trade t+h for h in {1, 2, 5, 10, 20, 50, 100}; (B) direction of the next mid change; (C) sign of mid_{t+h} - mid_t at fixed event horizons, unsmoothed, with an explicit flat class or conditional on change; optionally (D) net signed volume over the next h trades. Avoid FI-2010-style smoothed labels.
- **Baselines:** majority class; repeat last sign; Yule-Walker AR(p) / FARIMA(0,d,0) on signs; DAR(p); queue-imbalance-only logistic (Gould-Bonart); lagged L1 OFI linear model (Cont et al.); logistic on lagged signs only.
- **Models:** L2 logistic regression (interpretable, calibrated) and LightGBM (histogram trees; 100M rows x about 30-60 features is feasible on 8-16 cores, especially with subsampling for tuning). A small MLP or 1D-CNN on lagged features is optional and should be justified only if it beats LightGBM out of period; the literature gives little reason to expect that.
- **Features from aggTrades + bookTicker:** lagged signs and signed sizes at multiple exponential time/event scales; trade-flow imbalance over windows; trade intensity and inter-trade durations (event and clock time); L1 queue imbalance; L1 OFI over windows; spread in ticks; microprice minus mid; quote update intensity; time since last mid change and direction of last mid change; realised volatility; time-of-day and funding/quarter-hour boundary dummies (given the 2026 quarter-hour finding).
- **Protocol:** strict causal joins (use the last quote strictly before the trade's transaction timestamp; test robustness with a one-update lag); walk-forward by month over 2023-2026 with a purge/embargo gap of at least the longest horizon and feature lookback; hyperparameters tuned only on past folds; report per-fold results to show drift; compare BTC/ETH (large-tick) against at least one small-tick alt.
- **Economic honesty:** state that with taker fees of several bps and one-tick moves of a fraction of a bp, no taker strategy is implied; if any cost analysis is included, use spread-crossing plus fees and treat maker fills as unverifiable without queue data.
- **Theory link worth including:** estimate C(l) and gamma, compute the Yule-Walker filter, and test the surprise relation (return on predicted vs unpredicted sign component). Then ask whether the ML model's improvement over eps_hat carries any incremental information about future mid returns. This ties the ML exercise to the efficiency argument and is, as far as this search found, not already done for Binance perps.

### Gaps
- No vetted public reference implementation for an L1-only Binance pipeline with leakage controls was identified.
- Binance bookTicker coalescing behaviour and timestamp semantics across 2023-2026 should be checked against Binance's own documentation; not researched here.
- Current Binance USDT-M fee tiers were not re-verified this session.
