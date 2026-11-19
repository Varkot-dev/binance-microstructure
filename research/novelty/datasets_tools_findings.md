# Novelty and prior art: datasets, delisting risk, tooling, findings

Search date: 2026-11-19. Scope: the four candidate outputs of this repo (lifecycle dataset and
monthly panel, delisting risk ranking, Python library, Q10/Q15 research findings).

## Evidence tags

- **[V]** verified: stated in the primary source's own text (vendor docs, paper abstract, official
  announcement) as returned by search, or read directly in this repo.
- **[S]** secondary: from a third party, an aggregator, a search summary that was not cross-checked,
  or a page whose details were inconsistent.
- **[I]** inference: my own judgement from the evidence.

Limits of this search: WebFetch could not reach arxiv.org, mdpi-res.com or hackernoon.com from
this session (host not resolvable), so no full texts were opened. Every claim about an outside
source rests on search-result excerpts. Vendor prices are mostly from third-party comparison pages
and should be confirmed with the vendor. Nothing in this file is invented; where a fact was not
found, it says so.

## Summary

1. **Lifecycle dataset and monthly panel: partly done.** Commercial vendors (Kaiko, CoinAPI,
   Amberdata, CCData, Coin Metrics, Tardis.dev) keep delisted instruments and expose listing or
   status metadata, and free projects (a Hugging Face klines mirror, the `binance-futures-availability`
   package) already track which Binance USDT-M perpetuals existed on each day. What none of the
   sources found document is the specific combination this repo has: first and last *trading* day
   from aggTrades rather than klines, an explicit rule and list for renames, mergers and reused
   tickers, flagged post-delisting "ghost" files in klines, funding and metrics, and a documented
   panel with SHA-256 provenance. That curation layer looks open. [I]
2. **Delisting risk ranking: open as a product, partly done as research.** Academic work predicts
   "coin death" (Feder et al. 2018 definition; Fantazzini 2022; Sakinoglu and Guvenir 2023; a 2026
   arXiv LSTM preprint) and crypto *exchange* closure, and a 2026 JRFM paper models price distress
   on Kraken. No paper or product found predicts **exchange-level delisting of futures contracts**
   with an out-of-sample lock-box against a volume baseline, and no public "delisting risk"
   dashboard for Binance futures was found. Binance's own Monitoring Tag (spot) is the closest
   public signal. [I]
3. **Python library: partly done.** Verified bulk download of data.binance.vision with SHA-256
   checks exists (`binance-datatool`, `binance-data-downloader`). Microstructure estimators exist
   in scattered packages (`priceprop` for propagators, `wraquant`, Screamer, mlfinlab, which is
   not openly licensed). Generic pre-registration locks exist (`prereg`, `falsify`, `sharpe-gate`).
   No found package combines these, and none implements sign-autocorrelation memory exponents
   with the aggTrades aggregation correction, event studies and pre-registration together. [I]
4. **Research findings: open, with close neighbours.** Long memory in order signs and its
   order-splitting origin are well established in equities and FX, and a few informal GitHub
   projects measure it on Binance. Crypto tick-size natural experiments exist (Kraken, seven
   exchanges) but study spreads, depth and undercutting, not sign persistence. Equities tick-size
   work (SEC Tick Size Pilot) studies order splitting, depth and return autocorrelation, not
   trade-sign autocorrelation. No source found shows (a) a 2023 to 2025 rise in next-sign
   predictability attributed to shrinking trade size, or (b) a two-directional causal tick-size
   effect on sign persistence from many staggered tick changes. Both look new, subject to a
   proper Google Scholar and SSRN pass, which this session could not do in full. [I]

## 1. Survivorship-free contract data

### What this repo has [V, from local files]

- `research/market_evolution/data/contract_lifecycle.md`: 924 symbols, 935 lives; dates from daily
  aggTrades only; statuses alive, delisted, renamed (10), merged (2), index (3), reused-symbol (11);
  artifact days dropped (AI16ZUSDT, KDAUSDT single 0.0-price rows); rename candidates by a price
  and ticker-ratio rule.
- `research/market_evolution/data/monthly_panel.md`: 23,356 contract-months, 2020-01 to 2026-10;
  2,126 ghost months (9.1%) where klines, funding and metrics files keep publishing after trading
  stops; 65,305 zips each checked against the published SHA-256.
- `results/q16_delisting.md`: exclusions for stock, ETF, commodity and index contracts.

### Prior art table

| source | delisted contracts kept? | lifecycle / status metadata | renames, ghosts documented? | cost | tag |
|---|---|---|---|---|---|
| Binance data.binance.vision + binance-public-data repo | yes, files for dead symbols remain | none; official symbol script returns only currently running symbols; each zip has a `.CHECKSUM` | no | free | [V] |
| Binance API `exchangeInfo` / Delist Schedule doc | only upcoming: `deliveryDate` set after a delisting announcement | forward-looking only | no | free | [V] |
| Tardis.dev | "all instruments" of Binance USDT futures since 2019-11-17; OI since 2020-05-13 | per-exchange symbol list via `/v1/exchanges/:exchange` | not found | Academic tier exists; third party quotes about $450/month academic, $900 solo | [V] coverage, [S] price |
| Kaiko | v2 derivatives reference returns instruments "regardless of dates"; v3 beta has status listed, tradable, expired, delisted (Binance included) | yes | not found | third party: about $1,000/month aggregated, $1,500 tick | [V] docs, [S] price |
| CoinAPI | historical (delisted) symbols endpoint; `data_start` / `data_end` per symbol; flat files incl. delisted | yes | not found; blog explicitly markets survivorship-bias removal | credits + subscription, not verified | [V] vendor claims |
| Amberdata | futures OHLCV endpoint has a flag to include delisted instruments (default off) | partial | not found | quote only | [V] docs, [S] price |
| CCData / CoinDesk Data | statuses ACTIVE, IGNORED, RETIRED, EXPIRED (retired = ceased trading but mapped) | yes | not found | not checked | [S] (from a third-party Rust wrapper) |
| Coin Metrics | `/catalog-all/markets`; reference data page has a "Liveness and expired markets" section | yes | not read | not checked | [V] existence, content unread |
| CoinGecko | `/coins/list?status=inactive` for coins no longer listed; Analyst plan or above | coin level, not contract level | no | paid (Analyst) | [V] |
| QuantConnect (Binance crypto future price data) | not stated; a forum post notes stale symbol properties after Binance renames | unclear | no | platform subscription | [S] |
| Hugging Face `rogerdehe/klines-binance` | claims 791 futures pairs incl. delisted, "point-in-time / survivorship-bias-free"; a far-past last date marks delisting | implicit only (last date) | no ghost handling stated; README dates inconsistent | free | [S] |
| PyPI `binance-futures-availability` | DuckDB tracker of which USDT perpetuals were available each day from Binance Vision S3; MIT | daily availability | not found; likely based on file existence, which ghost files would distort [I] | free | [V] description |
| Academic: Stoeckl (survivorship and delisting bias), 3,904 coins 2014 to 2021 | coin level | n/a | n/a | paper | [S] |
| Dead-coin lists: Coinopsy (2,400+), 99Bitcoins deadcoins (community) | coin level | category labels | no | free | [S] |

### Assessment

- Vendors solve "is a delisted contract still in the archive", and several already flag status.
  None documents (in what was found) that Binance klines, funding and metrics keep publishing
  empty files after death, or gives trading-based first and last days, reused-ticker lives and a
  reviewed rename/merger map for Binance USDT-M. [I]
- The `binance-futures-availability` package is the closest free competitor; if it dates lives
  from file existence it inherits the ghost-file problem the repo found (2,126 ghost months). That
  is a concrete, testable differentiator worth checking by running it on a few dead symbols. [I]
- **Rating: partly done.** New if released as a versioned, citable dataset (Zenodo DOI) with the
  ghost-file finding demonstrated, a comparison against at least one vendor or the availability
  package on the same symbols, monthly updates, and the same treatment extended to COIN-M and to
  other venues (Bybit, OKX). [I]

## 2. Delisting and coin-death prediction

### Prior art table

| work | predicts | data | method | reported performance | tag |
|---|---|---|---|---|---|
| Feder et al. 2018 | defines "dead" coin: monthly avg daily volume at or below 1% of peak; resurrected at 10% | coin level | rule | definition only | [S] |
| Fantazzini 2022 (JRFM 15(7):304; MPRA 113744) | probability of coin death, several definitions | 2,000+ coins 2015 to 2020 | ZPP, credit scoring, ML | best model depends on death definition and coin age | [S] |
| Sakinoglu and Guvenir 2023, IEEE COINS | coin death risk ranking | 4,733 dead coins; death = no activity over a year | simple RNN / LSTM on price and volume | 72.24% AUC in best scenario | [S] |
| arXiv 2610.01379 "Blockchain Lifecycle Prediction - Dead Coins" (2026) | alive vs dead | 82 assets (41/41), Coin Metrics 2020 to 2026 | LSTM, 90-day windows | held-out AUC 0.98, unseen data about 0.59 to 0.65 | [S] |
| JRFM 2026, 19(8), 599 "Regime-Dependent Predictability of Cryptocurrency Distress" | onset of severe sustained price distress (not delisting) | Kraken coins 2013 to 2025, coin-quarter panel with later failures kept | panel logit, microstructure variables | results not read | [S] |
| Milunovich and Lee 2022, J. Forecasting | which crypto exchanges stay active | 238 exchanges | 4 classifiers, random forest best | "satisfactory accuracy" | [S] |
| Fantazzini and Calabrese 2021 (MPRA 110391; JRFM) | exchange closure | exchanges 2018 to 2021 | credit scoring + ML | volume, lifespan, security score key | [S] |
| Sapkota 2025, JIFMIM | exchange bankruptcy | 845 exchanges | logit, probit, RF, SVM, stacking | about 81% accuracy (logit/probit) | [S] |
| Renwick and Gleasure, ECIS 2026 | effect of Binance's Monero delisting | XMR | synthetic control | significant negative price effect | [S] |
| Binance Monitoring Tag | Binance's own risk label on spot tokens; tokens "at risk" of delisting | n/a | exchange discretion | Binance commentary: indicator, not a prediction | [V] glossary, [S] commentary |
| HackerNoon article "The highest funding rate on Binance is usually a delisting in disguise" | observation linking extreme funding to delistings | Binance futures | informal | not read (host blocked) | [S] |

No product, dashboard or paper was found that forecasts **Binance futures delistings** or
Monitoring Tag additions. [V for the null search result, I for the general claim]

### Assessment

- The repo's Q16 result is modest and honest: the frozen logistic model beats the
  lowest-volume-rank rule on the 2026 lock-box with the final full month kept (+0.119 precision at
  top 5%), but only +0.049 [-0.016, +0.081] once that announcement-contaminated month is dropped;
  the volume-rank rule alone reaches 5.0x the base rate. [V, local]
- So the publishable claim is "volume and open-interest rank flag Binance futures delistings at
  about 5x base rate; extra features add little once announcement leakage is removed". That
  negative-leaning result plus the leakage diagnosis is itself new relative to the coin-death
  literature, which does not handle announcement leakage. [I]
- **Rating: partly done (research), open (product).** New if: announcement dates are collected
  (the repo's `research/announcements` project) so leakage is removed precisely; the ranking is
  published monthly with a frozen model and a public, timestamped track record (hash each month's
  list before outcomes are known); and it is extended to spot Monitoring Tag additions, where
  Binance's own signal provides a second label. [I]

## 3. Python tooling

### Prior art table

| package | verified bulk download | order-flow / sign memory | event study | pre-registration | tag |
|---|---|---|---|---|---|
| binance/binance-public-data (official scripts) | yes, `.CHECKSUM` per zip, manual `sha256sum -c` | no | no | no | [V] |
| binance-datatool (lostleaf) | yes, `verify` command, SHA-256 with cached markers; aggTrades, USD-M | no | no | no | [V] |
| binance-data-downloader | concurrent download + checksum verification | no | no | no | [S] |
| binance-bulk-downloader (aoki-h-jp) | concurrent; checksum not confirmed | no | no | no | [S] |
| binance-historical-data (npm / ltftf) | downloads; checksum not confirmed | no | no | no | [S] |
| Tardis client / tardis-machine | replay of normalized tick data (paid) | no | no | no | [I] |
| ccxt | live and REST access; no archive verification | no | no | no | [I] |
| hftbacktest | Tardis and Binance futures data utilities, queue-position fill models | no (backtesting) | no | no | [V] |
| priceprop | calibrate and simulate linear propagator models | partial (impact) | no | no | [S] |
| Screamer | OFI operator and Bouchaud 2004 propagator | partial | no | no | [S] |
| wraquant | Kyle lambda, spreads, Corwin-Schultz, VPIN | no sign memory | no | no | [S] |
| mlfinlab (Hudson & Thames) | n/a | bar-based lambdas, Roll, VPIN | no | no; licence is restrictive ("all rights reserved" per a fork) | [S] |
| prereg | n/a | n/a | n/a | freezes a plan, `prereg check` detects changes, OSF draft | [S] |
| falsify (PRML spec) | n/a | n/a | n/a | SHA-256 manifest of a claim; pass, fail, tamper exit codes | [S] |
| sharpe-gate | n/a | n/a | n/a | append-only backtest trial registry | [S] |
| GitHub pingadom/hft-microstructure; dx-li CryptoAnalysis | scripts | Binance sign ACF (one reports lag^-0.48) | no | no | [S] |

This repo already has SHA-256-checked downloads (`src/microstructure/data/binance.py`) and
estimators (`src/microstructure/estimators/acf.py`, `hawkes.py`, `propagator.py`, `ofi.py`). The
lock-box and pre-registration discipline currently lives in research scripts and frozen commits
(for example b3571a6 for Q16), not in a reusable module. [V, local]

**Rating: partly done.** Each piece exists elsewhere; the bundle does not. New if the library
ships: survivorship-aware universe selection from the lifecycle table (no ghost files); aggressor
event aggregation by default (the repo shows raw prints inflate gamma by 0.29 to 0.50); sign-memory
and Hawkes estimators with tests against published equity numbers; and a small `lock()` / `verify()`
API that hashes design, code commit and data manifest before a lock-box run. The realistic audience
is students and researchers, so this is a credibility asset more than a business. [I]

## 4. Research findings

### Prior art table

| work | market | question | relation to the student's finding | tag |
|---|---|---|---|---|
| Lillo and Farmer 2004 "The long memory of the efficient market" | LSE | sign ACF decays as tau^-0.6 approx | baseline phenomenon | [V] abstract |
| Lillo, Mike and Farmer 2005 | theory | order splitting with power-law metaorder sizes gives long memory | mechanism behind "smaller trades raise predictability" | [V] |
| Bouchaud et al. (Euronext 2001 to 2002); Toth et al. (LSE) | equities | long memory is within-broker, i.e. splitting not herding | supports splitting interpretation | [S] |
| Sato and Kanazawa 2023, PRL 131, 197401 and PRR 5, 043131 | TSE, account IDs, 9 years | quantitative confirmation of LMF | strongest evidence for splitting; does not study time trend or tick size | [V] |
| Primicerio and Challet 2019, Market Microstructure and Liquidity | equities | large-trader activity weakens long memory | related: who trades changes memory | [V] |
| Gould, Porter and Howison (arXiv 1504.04354) | FX spot | Hurst about 0.7, robust to structural breaks | cross-market benchmark | [S] |
| Axioglou and Skouras | critique | long memory as nonstationarity artifact | a caveat the student should address | [S] |
| Donier and Bonart (arXiv 1412.4503) | Bitcoin/USD (Mt. Gox era) | square-root impact; order flow Hawkes-like | earliest crypto impact evidence; no tick experiment | [S] |
| Easley, O'Hara, Yang, Zhang 2024 (SSRN 4814346) | 5 cryptos 2021 to 2023 | microstructure measures predict price dynamics | different target (returns), short window | [S] |
| arXiv 2607.09426 "The Quarter-Hour Effect" (2026) | 6 Binance perpetuals | periodic algorithmic trading; order-flow lag-1 ACF dips at quarter-hour boundaries | closest recent Binance order-flow paper; no tick or trend analysis | [V] excerpts |
| Dyhrberg, Foley and Svec 2023, JFQA "When bigger is better" | Kraken 2017 tick increases | tick up reduces undercutting, raises depth, lowers costs | crypto tick natural experiment, outcome is liquidity, not sign persistence | [V] |
| AUT working paper, tick size in crypto | 7 exchanges, 420 increases, 434 decreases | spreads by liquidity and venue dominance | bidirectional crypto tick events; outcome spreads, not signs | [S] (authors not identified) |
| Galati 2024, JBF | Binance | fee removal natural experiment | Binance natural-experiment method precedent | [S] |
| SEC Tick Size Pilot papers (Darden/Fisher; Bocconi WRBW; Song and Yao) | US small caps, 5-cent tick, 2016 | depth up, less splitting needed, return autocorrelation up | equities say a larger tick may reduce splitting; consistent with student's sign; no trade-sign ACF measured in found papers | [S] |
| Taiwan threshold study; Sirnes and Dinh 2021 | equities | tick size and return autocorrelation, order-imbalance reversal | adjacent, not trade-sign persistence | [S] |
| Binance tick-size announcements (2021 to 2025) | Binance USDT-M | many batched tick changes, both directions, old orders keep old tick | the event source for the 35 batches | [V] |
| Informal: GitHub pingadom/hft-microstructure, dx-li CryptoAnalysis | Binance BTCUSDT etc. | sign ACF power law | replications only, no causal design | [S] |

### Assessment

- **(4a) Predictability rose 2023 to 2025, driven by smaller trades.** No source found documents
  a time trend in crypto trade-sign predictability, nor attributes one to falling trade size.
  The LMF framework makes it plausible (more child orders per metaorder), so the novelty is
  empirical, not theoretical. The student's own Gelbach split is an accounting identity (trade size
  "explains" 7.80 pp of a 3.41 pp rise), so the claim should be phrased as association. **Rating:
  open.** New if framed against LMF and Sato and Kanazawa, with the aggTrades aggregation fix
  stated up front and the Axioglou and Skouras nonstationarity critique addressed. [I]
- **(4b) Tick size causes sign persistence in both directions (35 batches).** Crypto tick papers
  study spreads and depth; the SEC pilot literature studies splitting and return autocorrelation;
  none found measures trade-sign autocorrelation as the outcome, and none uses many staggered
  batches with both cuts and increases. The lock-box result is mixed (lag-1 ACF confirms, repeat
  rate weakens), which should be reported as is. **Rating: open**, with the caveat that a full
  Google Scholar and SSRN search for "tick size" with "order sign" or "trade sign autocorrelation"
  was not possible here. [I]
- A plausible venue is a short empirical paper (Quantitative Finance, Market Microstructure and
  Liquidity, Finance Research Letters) or an arXiv q-fin.TR preprint. [I]

## Ratings

| candidate | rating | closest prior work | what would make it new |
|---|---|---|---|
| (1) lifecycle dataset + monthly panel | partly done | Kaiko/CoinAPI status metadata; `binance-futures-availability`; HF `rogerdehe/klines-binance` | trading-based dates, ghost-file flags demonstrated against a competitor, rename/merge/reuse map, DOI, monthly refresh, more venues |
| (2) monthly delisting-risk ranking | partly done (research), open (product) | Fantazzini 2022; Sakinoglu and Guvenir 2023; Binance Monitoring Tag | futures delisting target, announcement-date leakage control, frozen model with hashed monthly forecasts and a public track record |
| (3) Python library | partly done | binance-datatool; priceprop; prereg/falsify | one package joining verified survivorship-aware download, aggressor aggregation, sign-memory estimators, event studies and a lock/verify API |
| (4a) predictability trend and trade size | open | LMF 2005; Sato and Kanazawa 2023; Quarter-Hour Effect 2026 | first documented crypto trend, tied to splitting theory |
| (4b) tick size causes sign persistence | open | Dyhrberg et al. 2023; AUT 7-exchange study; SEC Tick Size Pilot papers | trade-sign ACF as outcome, 35 staggered bidirectional batches, pre-registered lock-box |

## Startup opportunities

### A. Survivorship-free crypto contract reference data

- **Product:** a point-in-time contract master for crypto derivatives (listing, last trade, renames,
  redenominations like `1000X`, mergers, reused tickers, stock and commodity perps, ghost-file
  flags) across Binance, Bybit, OKX, Hyperliquid. Free tier for Binance USDT-M; paid API and
  history for multi-venue. [I]
- **Customers:** quant funds and prop shops backtesting cross-sectional perp strategies; academic
  researchers; index and ETP providers needing constituent histories; data vendors as an OEM
  layer. [I]
- **Competitors:** Kaiko, CoinAPI, Amberdata (a single third-party source says Kaiko acquired
  Amberdata in June 2026, unconfirmed [S]), CCData, Coin Metrics, Tardis.dev; free mirrors. [V/S]
- **Defensibility:** low on raw data (Binance publishes it free); moderate on curation quality,
  audit trail and multi-venue consistency; reputation via citations. [I]
- **Risks:** vendors add a "status" field and close the gap; Binance changes the archive; small
  market for reference data alone; licensing of exchange data redistribution must be checked. [I]

### B. Delisting and Monitoring Tag risk alerts

- **Product:** monthly or weekly ranked watchlist of contracts and tokens at risk of Binance (and
  other venue) delisting or Monitoring Tag, with alerts when a contract enters the top decile. [I]
- **Customers:** market makers and liquidity providers (inventory and margin risk), token projects
  and their treasuries (listing-compliance monitoring), funds holding long-tail perps, retail
  traders via a freemium dashboard. [I]
- **Competitors:** none found offering forecasts; substitutes are Binance announcements, news
  aggregators (CryptoRank feeds), and announcement scrapers. [V for none found]
- **Defensibility:** track record (published, hashed forecasts) and labelled announcement history;
  the model itself is simple and easy to copy, since volume rank alone gets about 5x base rate. [I]
- **Risks:** weak edge after leakage control (+0.049, interval includes zero); delistings come in
  batches, so few independent events; reflexivity (a public list could pressure projects or be
  accused of moving prices); exchange policy shifts; legal exposure if seen as market-moving
  claims about specific tokens. [I]

### C. Research tooling and reproducibility

- **Product:** open-source library plus hosted notebooks: verified archive sync, aggressor-event
  aggregation, memory and Hawkes estimators, event-study templates with pre-registration locks;
  revenue from courses, academic site licences or a paid managed data cache. [I]
- **Customers:** finance students and faculty, crypto research desks, bootcamps. [I]
- **Competitors:** hftbacktest, mlfinlab, QuantConnect, Tardis tooling, generic prereg tools. [V/S]
- **Defensibility:** low commercially; high as a portfolio and credibility signal. [I]
- **Risks:** small paying market; maintenance burden as Binance formats change. [I]

**Overall:** the strongest near-term value is academic and reputational: publish the dataset with
a DOI, the findings as a preprint, and the library on PyPI. A delisting-alert product is the only
idea with a clear buyer, but the measured edge is thin, so it should start as a free public track
record before any paid offer. [I]

## References

Datasets and vendors
- Tardis.dev, Binance USDT Futures details: https://docs.tardis.dev/historical-data-details/binance-futures
- Tardis.dev billing FAQ (Academic tier): https://docs.tardis.dev/faq/billing-and-subscriptions
- Kaiko derivatives contract details v3: https://docs.kaiko.com/rest-api/misc-custom-and-legacy-endpoints/derivatives-contract-details-v3
- Kaiko derivatives reference: https://docs.kaiko.com/kaiko-rest-api/data-feeds/reference-data/derivatives-reference
- CoinAPI, survivorship bias blog: https://www.coinapi.io/blog/how-to-eliminate-survivorship-bias-in-crypto-backtesting
- CoinAPI, historical symbols glossary: https://www.coinapi.io/learn/glossary/historical-symbols
- CoinAPI, data_start / data_end: https://www.coinapi.io/learn/glossary/data_start-and-data_end
- Amberdata futures OHLCV information: https://docs.amberdata.io/http/market/futures-ohlcv-information.md
- Amberdata derivatives coverage: https://docs.amberdata.io/docs/ad-derivatives-coverage
- CCData derivatives: https://ccdata.io/data/derivatives
- ccdata-api Rust wrapper (status enum): https://docs.rs/crate/ccdata-api/0.1.6/source/src/schemas/data_api.rs
- Coin Metrics market reference data: https://docs.coinmetrics.io/market-data/market-data-overview/market-reference-data
- CoinGecko coins list (status=inactive): https://docs.coingecko.com/reference/coins-list.md
- Binance public data repo: https://github.com/binance/binance-public-data/
- Binance USDS-M Delist Schedule doc: https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Delist-Schedule
- Hugging Face rogerdehe/klines-binance: https://huggingface.co/datasets/rogerdehe/klines-binance
- binance-futures-availability (PyPI): https://pypi.org/project/binance-futures-availability/
- QuantConnect Binance crypto future price data: https://www.quantconnect.com/docs/v2/writing-algorithms/datasets/quantconnect/binance-crypto-future-price-data
- Vendor price comparison (third party): https://coinranking.com/blog/best-historical-crypto-data-apis/
- Spark crypto data API comparison: https://www.spark.money/tools/crypto-data-api-comparison
- Binance TSLAUSDT equity perpetual (secondary): https://en.cryptonomist.ch/2026/01/26/tsla-perpetual-futures-binance

Delisting and coin death
- Stoeckl, survivorship and delisting bias: https://alexandria.unisg.ch/handle/20.500.14171/108037
- Fantazzini 2022, probability of death: https://www.mdpi.com/1911-8074/15/7/304
- Fantazzini MPRA 113744: https://mpra.ub.uni-muenchen.de/113744/1/MPRA_paper_113744.pdf
- Sakinoglu and Guvenir 2023, IEEE: https://ieeexplore.ieee.org/document/10189205
- Blockchain Lifecycle Prediction - Dead Coins: https://arxiv.org/pdf/2610.01379 ; summary https://www.emergentmind.com/papers/2610.01379
- JRFM 2026 19(8) 599: https://mdpi-res.com/d_attachment/jrfm/jrfm-19-00599/article_deploy/jrfm-19-00599.pdf
- Milunovich and Lee 2022: https://econpapers.repec.org/RePEc:wly:jforec:v:41:y:2022:i:5:p:945-955
- Fantazzini and Calabrese 2021: https://mpra.ub.uni-muenchen.de/110391/1/MPRA_paper_110391.pdf
- Renwick and Gleasure, ECIS 2026: https://aisel.aisnet.org/ecis2026/gen_track/gen_track/13/
- Binance Monitoring Tag glossary: https://www.binance.com/en/academy/glossary/monitoring-tag
- HackerNoon funding-rate article (not read): https://hackernoon.com/the-highest-funding-rate-on-binance-is-usually-a-delisting-in-disguise

Tooling
- binance-datatool: https://pypi.org/project/binance-datatool/ ; https://github.com/lostleaf/binance_datatool
- binance-bulk-downloader: https://github.com/aoki-h-jp/binance-bulk-downloader
- binance-data-downloader: https://socket.dev/pypi/package/binance-data-downloader
- hftbacktest: https://hftbacktest.readthedocs.io/
- priceprop: https://awesome.ecosyste.ms/projects/github.com%2Ffelixpatzelt%2Fpriceprop
- Screamer microstructure: https://screamer.readthedocs.io/en/latest/microstructure.html
- wraquant microstructure: https://wraquant.readthedocs.io/en/latest/api/microstructure.html
- mlfinlab release notes: https://hudsonthames.org/?p=3825
- prereg: https://pypi.org/project/prereg/
- falsify: https://pypi.org/project/falsify/0.1.4/
- sharpe-gate: https://pypi.org/project/sharpe-gate/
- pingadom/hft-microstructure: https://github.com/pingadom/hft-microstructure
- dx-li CryptoAnalysis: https://dx-li.github.io/CryptoAnalysis/Analysis.html

Order flow, long memory, tick size
- Lillo and Farmer 2004: https://arxiv.org/abs/cond-mat/0311053
- Lillo, Mike, Farmer 2005: https://arxiv.org/pdf/cond-mat/0412708
- Sato and Kanazawa, PRL 2023: https://link.aps.org/doi/10.1103/PhysRevLett.131.197401 ; preprint https://arxiv.org/abs/2301.13505v2
- Sato and Kanazawa, PRR 2023: https://physics.aps.org/featured-article-pdf/10.1103/PhysRevResearch.5.043131
- Primicerio and Challet: https://arxiv.org/pdf/1803.08390
- Gould, Porter, Howison FX long memory: https://arxiv.org/pdf/1504.04354
- Bitcoin square-root impact: https://arxiv.org/pdf/1412.4503
- Easley, O'Hara, Yang, Zhang: https://stoye.economics.cornell.edu/docs/Easley_ssrn-4814346.pdf
- The Quarter-Hour Effect: https://arxiv.org/pdf/2607.09426
- Dyhrberg, Foley, Svec, JFQA 2023: https://econpapers.repec.org/RePEc:cup:jfinqa:v:58:y:2023:i:6:p:2387-2416_4
- AUT crypto tick size paper: https://acfr.aut.ac.nz/__data/assets/pdf_file/0008/926567/Tick-size-paper.pdf
- Galati 2024 JBF: https://cris.unibo.it/retrieve/ae1c7f77-aec4-4fa0-9733-60753ce00768/Galati2024_JBF.pdf
- US Tick Size Pilot (Darden): https://finance.darden.virginia.edu/wp-content/uploads/2018/04/U.S.-Tick-Size-Pilot.pdf
- US Tick Size Pilot (Bocconi): https://didattica.unibocconi.it/mypage/upload/48636_20190131_054242_USTICKSIZEPILOT_20190125_COMPLETE.PDF
- Sirnes and Dinh 2021: https://econpapers.repec.org/RePEc:gam:jijfss:v:9:y:2021:i:2:p:19-:d:523899
- Binance tick size announcement example (2023-08-29): https://www.binance.com/en/support/announcement/updates-on-tick-size-for-multiple-usd%E2%93%A2-m-perpetual-futures-contracts-2023-08-29-8764f0d84e6b4c7abc97f036bb6f9ebc
