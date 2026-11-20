# Literature: liquidation cascades, fragility and early warning

Compiled 2026-11-20 from seven scout tracks, nine deep dives, a novelty review and a citation check.

**Verification status.** No full text was read this round: arxiv.org, papers.ssrn.com, crossref,
SSRN, RePEc and journal sites were unreachable, and the web-search budget was exhausted. Each entry
carries one tag:

- **[C]** bibliographic details (authors, year, title, venue, volume, pages, DOI) confirmed by the
  citation check against its own knowledge, with corrections applied.
- **[L]** located by a scout from a publisher or repository record and not flagged by the citation
  check. Details should still be re-checked when hosts are reachable.
- **[U]** unverified lead. Listed only so it gets read. Nothing in this project relies on its
  content, and no figures from it are quoted as evidence.

Citations the check could not confirm and that are not needed have been dropped (for example
Alexander, Deng and Zou 2021; Danielsson, Shin and Zigrand 2011; Christin et al. 2022 carry trade;
the Pindza and Mashele 2026 tail model).

## 1. Closest prior work on 2025 to 2026 cascades (all [U], read first)

These set the novelty bar, so they must be read in full before any pre-registration. What repo notes
(search snippets, tag [S]) say about them is recorded only so the reader knows what to check.

| arXiv / SSRN ID | Title as recorded | Corrected attribution | What to check |
|---|---|---|---|
| arXiv 2607.27070 | Where does the criticality live? Early-warning signals are event-heterogeneous across seven crypto-perpetual liquidation cascades | Garcia Seuma (2026). Initials, date, category and "under review" claims removed as unsourced | Event dates and definitions; indicators; whether bookDepth was used and whether the 2025-10-10 ghost bid was screened; whether any cross-section is reported. Snippets: critical slowing down in 5 of 7 BTC events, none in the two tariff shocks |
| arXiv 2608.03616 | Measuring the engine of a liquidation cascade: subcritical branching inside a first-order transition | Author(s) unverified (not Garcia Seuma by default) | Venue of data (repo notes disagree: Hyperliquid fill log or Binance USDT-M). Snippets: branching about 0.1 to 0.2, no scalar pre-state grades severity |
| arXiv 2512.01112 | Autodeleveraging: Impossibilities and Optimization | Chitra, T. et al. (author list unverified), version v2 as accessed by the repo | Repo notes give incompatible figures (USD 45.0M to 51.7M taken from winners versus 0.66 to 2.1B). Quote neither until read |
| arXiv 2602.15182 | Title and authors unverified | none | Content unknown; one scout's title "Autodeleveraging as Online Learning" is not confirmed |
| arXiv 2603.15963 | Risk-Based Auto-Deleveraging | Authors unknown | ADL counts on 2025-10-10 |
| arXiv 2603.09164 | Slippage-at-Risk (SaR) | Author(s) unverified | Depth-based slippage risk on Hyperliquid books, 184 perps, 2025-10-09 to 11-03 (snippet) |
| arXiv 2602.00776 | Explainable Patterns in Cryptocurrency Microstructure | Authors unknown | Whether it used Binance depth on 2025-10-10 without masking |
| SSRN 6579278 | Lim (2026), Anatomy of a Crypto Cascade | Subtitle and initials removed | Single-event description (snippet: BTC -12.6% in ten minutes on Binance) |
| SSRN 6636998 | Lim (2026), Two-Regime Liquidity Recovery After a Perpetual Futures Liquidation Cascade: Evidence from Hyperliquid and the October 10, 2025 Event | A journal version (JFDA) was not located; cite the SSRN paper | Only order-book recovery precedent; recovery measured in depth, not spread |
| SSRN 6574205 | Lim (2026), venue-isolated stablecoin depeg (USDe on Binance) | Unverified | Collateral-oracle channel on 10-10 |
| ResearchGate 404288266 | Same Shock, Same Assets, Different Microstructure | Authors unknown; not peer reviewed | CeFi versus DeFi on 10-10 |

**Meaning for this project.** If these papers are as the snippets describe (few events, BTC or
Hyperliquid only, no masking), the open ground is a pre-registered panel across hundreds of Binance
contracts and many episodes, with a data-quality mask. If a full read shows a multi-contract Binance
panel already exists, P3 and P5 in the README lose most of their novelty.

## 2. Theory of leverage, liquidity spirals and fire sales

- **[C] Brunnermeier, M. K. and Pedersen, L. H. (2009). Market Liquidity and Funding Liquidity.
  Review of Financial Studies 22(6), 2201-2238. https://doi.org/10.1093/rfs/hhn098.**
  Margin constraint `sum_j (x_j+ m_j+ + x_j- m_j-) <= W`; lower capital reduces market liquidity,
  which raises margins (loss spiral and margin spiral). Predicts sudden, nonlinear, commonly moving
  liquidity dry-ups, worst when liquidity is already low, and flight to quality. *For us:* depth at
  plus or minus 1 to 2% should fall together across contracts, more for alts than BTC, with a
  threshold shape. Binance's fixed maintenance brackets do not remove the margin channel: collateral
  haircuts (USDe, wBETH, BNSOL valued on Binance's own books on 10-10) and bracket changes work the
  same way.
- **[C] Geanakoplos, J. (2010). The Leverage Cycle. NBER Macroeconomics Annual 2009, 24, 1-65.
  https://doi.org/10.1086/648285.** Leverage builds in calm run-ups and collapses after
  uncertainty-raising news that wipes out the most optimistic buyers. *For us:* crash depth should
  rise with pre-event OI relative to volume across contracts (P3), and recovery should be slower
  where leverage was higher.
- **[C] Shleifer, A. and Vishny, R. W. (1992). Liquidation Values and Debt Capacity: A Market
  Equilibrium Approach. Journal of Finance 47(4), 1343-1366.
  https://doi.org/10.1111/j.1540-6261.1992.tb04661.x.** Forced sales go cheap when natural buyers
  are hit by the same shock. *For us:* larger discounts and larger later reversals in market-wide
  episodes than in single-contract ones. ADL, which closes winning positions, removes natural buyers.
- **[C] Shleifer, A. and Vishny, R. W. (2011). Fire Sales in Finance and Macroeconomics. Journal of
  Economic Perspectives 25(1), 29-48. https://doi.org/10.1257/jep.25.1.29.** Survey. Framework for
  temporary versus permanent impact after cascades.
- **[C] Brunnermeier, M. K. and Pedersen, L. H. (2005). Predatory Trading. Journal of Finance 60(4),
  1825-1863. https://doi.org/10.1111/j.1540-6261.2005.00781.x.** Others sell ahead of known forced
  sellers, then buy back: overshoot and reversal. *For us:* predicts one-sided taker flow before
  onset; the band-based version needs liquidation prices that free data does not identify, so test
  flow persistence only.
- **[C] Danielsson, J., Shin, H. S. and Zigrand, J.-P. (2004). The impact of risk regulation on
  price dynamics. Journal of Banking and Finance 28(5), 1069-1087.
  https://doi.org/10.1016/S0378-4266(03)00113-4.** VaR constraints raise volatility endogenously.
- **[C] Cont, R. and Wagalath, L. (2016). Fire Sales Forensics: Measuring Endogenous Risk.
  Mathematical Finance 26(4), 835-866. https://doi.org/10.1111/mafi.12071.** Test and estimator for
  fire-sale-induced excess covariance. *For us:* deferred, because it needs per-contract liquidation
  volumes, and with depth alone it is confounded with volatility.
- **[C] Garleanu, N. and Pedersen, L. H. (2011). Margin-based Asset Pricing and Deviations from the
  Law of One Price. Review of Financial Studies 24(6), 1980-2022. https://doi.org/10.1093/rfs/hhr027.**
  *For us:* basis (mark versus index) should widen more in high-margin, low-max-leverage contracts.
- **[C] Morris, S. and Shin, H. S. (2004). Liquidity Black Holes. Review of Finance 8(1), 1-18.
  https://doi.org/10.1023/B:EUFI.0000022155.98681.25.** (Link corrected from a malformed handle URL.)
  Traders near loss limits sell pre-emptively. *For us:* selling can start before thresholds are hit.
- **[C] Bernardo, A. E. and Welch, I. (2004). Liquidity and Financial Market Runs. Quarterly Journal
  of Economics 119(1), 135-158. https://doi.org/10.1162/003355304772839542** (DOI from the citation
  check's memory). Fear of selling later causes runs now.
- **[C] Fosset, A., Bouchaud, J.-P. and Benzaquen, M. (2020). Endogenous liquidity crises. Journal of
  Statistical Mechanics: Theory and Experiment, 063401. https://doi.org/10.1088/1742-5468/ab7c64.**
  Feedback from past price changes to liquidity provision gives a phase transition into liquidity
  crises. *For us:* predicts nonlinearity in crash depth as a function of feedback strength.
- Suggested additions from the citation check, not yet located (treat as [U] until checked):
  Huang and Wang (2009) RFS 22(7) on liquidity and crashes; Gennotte and Leland (1990) AER 80(5);
  Adrian and Shin (2010) JFI 19(3) on procyclical leverage; Gromb and Vayanos (2002) JFE 66(2-3).

## 3. Empirical crypto liquidations and crashes

- **[L] Cheng, Z., Deng, J., Wang, T. and Yu, M. (2021). Liquidation, Leverage and Optimal Margin in
  Bitcoin Futures Markets. arXiv 2102.04591. https://arxiv.org/abs/2102.04591.** Journal details
  (Applied Economics 53(47)) unverified. BitMEX daily data: liquidations average 3.51% of OI for longs,
  1.89% for shorts; margins too low under GEV fits. *For us:* a daily-level baseline only.
- **[C] Soska, K., Dong, J.-D., Khodaverdian, A., Zetlin-Jones, A., Routledge, B. and Christin, N.
  (2021). Towards Understanding Cryptocurrency Derivatives: A Case Study of BitMEX. WWW '21.
  https://doi.org/10.1145/3442381.3450059.** Descriptive; small positions liquidated
  disproportionately.
- **[L] Baumgartner, T., Guettler, A. (and possibly Kim; check the title page) (2022). Bitcoin Flash
  Crash on May 19, 2021: What Did Really Happen on Binance? IWH Discussion Paper 25/2022.
  https://www.iwh-halle.de/fileadmin/user_upload/publications/iwh_discussion_papers/iwh-discussion-paper_2022_25_Baumgartner_Guettler.pdf.**
  The later IRFA version is unverified. About 40-minute reporting gap, backfill failing Benford's law.
  *For us:* precedent that Binance data fails at exactly the events studied, as with the 2025-10-10
  ghost bid.
- **[C] Liu, J., Makarov, I. and Schoar, A. (2023). Anatomy of a Run: The Terra Luna Crash. NBER
  Working Paper 31160. https://doi.org/10.3386/w31160.** (Journal publication claim dropped as
  unverified.) Account-level crash study; a template for Hyperliquid wallet data.
- **[L] Vidal-Tomas, D., Briola, A. and Aste, T. (2023). FTX's downfall and Binance's consolidation:
  the fragility of centralised digital finance. Physica A 625, 129044.
  https://doi.org/10.1016/j.physa.2023.129044** (journal details from the citation check's memory;
  arXiv 2302.11371). FTX contagion, no order-book work.
- **[L] Conlon, T., Corbet, S. and Hu, Y. (2023). The collapse of the FTX exchange. British Accounting
  Review. SSRN 4283333.** Background only.
- **[C] He, S., Manela, A., Ross, O. and von Wachter, V. (2022, rev. 2024). Fundamentals of Perpetual
  Futures. arXiv 2212.06888. https://arxiv.org/abs/2212.06888.** Perp prices deviate from no-arbitrage
  much more than FX futures. *For us:* funding and premium as one-sidedness measures.
- **[U] Makarov, I. and Schoar, A. (2020). Trading and arbitrage in cryptocurrency markets. Journal of
  Financial Economics 135(2), 293-319. https://doi.org/10.1016/j.jfineco.2019.07.001.** Cross-venue
  dislocations; suggested by the citation check from memory, not located.
- Note: the claim that August 2024 and FTX events have no published microstructure is refuted. Kaiko
  and Amberdata industry reports describe Binance depth paths around 2024-08-05 and 2025-10-10 (repo
  note `research/novelty/qfa_derived_ideas.md`, not opened). Read them before claiming novelty for
  depth narratives.

## 4. DeFi liquidations (mechanism background)

- **[C] Qin, K., Zhou, L., Gamito, P., Jovanovic, P. and Gervais, A. (2021). An Empirical Study of
  DeFi Liquidations. IMC '21. https://doi.org/10.1145/3487552.3487811.** 28,138 liquidations.
- **[C] Perez, D., Werner, S. M., Xu, J. and Livshits, B. (2021). Liquidations: DeFi on a Knife-edge.
  Financial Cryptography 2021, 457-476. https://doi.org/10.1007/978-3-662-64331-0_24.** A 3% move makes
  over USD 10M liquidable on Compound. *For us:* the "liquidable at a given move" concept, which
  Binance's public bracket table (current only) could approximate.
- **[C] Lehar, A. and Parlour, C. A. (2022). Systemic fragility in decentralised markets. BIS Working
  Paper 1062. https://www.bis.org/publ/work1062.htm.** Liquidation impact moves from DEXs to Binance.
- **[C] Gudgeon, L., Perez, D., Harz, D., Livshits, B. and Gervais, A. (2020). The Decentralized
  Financial Crisis. arXiv 2002.08099.** Stress-test simulation.

## 5. Fragility measures, flash crashes and the VPIN debate

- **[C] Kirilenko, A., Kyle, A. S., Samadi, M. and Tuzun, T. (2017). The Flash Crash: High-Frequency
  Trading in an Electronic Market. Journal of Finance 72(3), 967-998.
  https://doi.org/10.1111/jofi.12498.** HFTs amplified but did not cause the crash; "hot potato" volume.
  *For us:* volume spikes during cascades can overstate liquidity.
- **[C] Easley, D., Lopez de Prado, M. M. and O'Hara, M. (2011). The Microstructure of the 'Flash
  Crash'. Journal of Portfolio Management 37(2), 118-128.** The original VPIN warning claim.
- **[C] Easley, D., Lopez de Prado, M. M. and O'Hara, M. (2012). Flow Toxicity and Liquidity in a
  High-frequency World. Review of Financial Studies 25(5), 1457-1493.
  https://doi.org/10.1093/rfs/hhs053.** VPIN = sum over n buckets of |V_S - V_B| / (nV). Binance
  aggTrades give exact signs, so no bulk classification is needed.
- **[C] Andersen, T. G. and Bondarenko, O. (2014). VPIN and the Flash Crash. Journal of Financial
  Markets 17, 1-46. https://doi.org/10.1016/j.finmar.2013.05.005.** VPIN peaked after the crash; its
  forecasting power is mostly mechanical through volume. Rejoinder: Easley, Lopez de Prado and O'Hara
  (2014), JFM 17, 47-52, https://doi.org/10.1016/j.finmar.2013.06.007. Reply: Andersen and Bondarenko
  (2014), "Reflecting on the VPIN dispute", JFM 17, 53-64, https://doi.org/10.1016/j.finmar.2013.08.002.
  *For us:* the single most important design lesson. Every warning signal faces a pre-window volume
  plus realized-volatility baseline, and timing is audited.
- **[L] Andersen, T. G. and Bondarenko, O. (2015). Assessing Measures of Order Flow Toxicity and Early
  Warning Signals for Market Turbulence. Review of Finance 19(1), 1-54.
  https://doi.org/10.1093/rof/rfu041** (DOI from the citation check's memory). Bulk versus true-sign
  VPIN behave differently.
- **[L] Abad, D., Massot, M. and Pascual, R. (2018). Evaluating VPIN as a trigger for single-stock
  circuit breakers. Journal of Banking and Finance 86, 21-36.
  https://doi.org/10.1016/j.jbankfin.2017.08.009.** Differences vanish after volatility controls.
  Design template.
- **[C] Kyle, A. S. (1985). Continuous Auctions and Insider Trading. Econometrica 53(6), 1315-1335.
  https://doi.org/10.2307/1913210.** Kyle lambda: `r_t = a + lambda (2 taker_buy_vol - vol)_t + e`.
  Our one-day probe found lambda falls in busy pre-crash hours (2.9 to 3.9 bp per 100 BTC at
  14:00 to 20:00) and rises after, so it is not a monotone warning.
- **[C] Amihud, Y. (2002). Illiquidity and stock returns. Journal of Financial Markets 5(1), 31-56.
  https://doi.org/10.1016/S1386-4181(01)00024-6.** Cheap cross-sectional price-impact measure.
- **[C] Cont, R., Kukanov, A. and Stoikov, S. (2014). The Price Impact of Order Book Events. Journal
  of Financial Econometrics 12(1), 47-88. https://doi.org/10.1093/jjfinec/nbt003.** Impact linear in
  OFI with slope inversely proportional to depth. Top-of-book OFI is possible only while bookTicker
  exists (2023-05-16 to 2024-03-30).

## 6. Resilience and slicing

- **[C] Large, J. (2007). Measuring the resiliency of an electronic limit order book. Journal of
  Financial Markets 10(1), 1-25. https://doi.org/10.1016/j.finmar.2006.09.001.** Reference definition
  of resiliency for P4.
- **[C] Obizhaeva, A. A. and Wang, J. (2013). Optimal trading strategy and supply/demand dynamics.
  Journal of Financial Markets 16(1), 1-32. https://doi.org/10.1016/j.finmar.2012.09.001.** Book refills
  at rate rho; half-life ln2/rho is P4's outcome.
- **[C] Foucault, T., Kadan, O. and Kandel, E. (2005). Limit Order Book as a Market for Liquidity.
  Review of Financial Studies 18(4), 1171-1217. https://doi.org/10.1093/rfs/hhi029.** Resiliency rises
  with the share of patient traders and falls with arrival rate. P4's main prediction.
- **[C] Lillo, F., Mike, S. and Farmer, J. D. (2005). Theory for long memory in supply and demand.
  Physical Review E 71, 066122. https://doi.org/10.1103/PhysRevE.71.066122.** Sign ACF decays as
  lag^-(alpha-1) from split hidden orders. *For us:* unsplit liquidation-engine orders should break
  this relation during cascades.
- **[C] Toth, B., Palit, I., Lillo, F. and Farmer, J. D. (2015). Why is equity order flow so
  persistent? Journal of Economic Dynamics and Control 51, 218-239.
  https://doi.org/10.1016/j.jedc.2014.10.007.** Splitting, not herding, drives persistence.
- **[L] Primicerio, K. and Challet, D. (2019). Large large-trader activity weakens the long memory of
  limit order markets. Market Microstructure and Liquidity 4.** Predicts short-lag sign ACF may fall
  as many traders exit at once; gives a signed hypothesis for P5.
- **[C] Donier, J. and Bouchaud, J.-P. (2015). Why do markets crash? Bitcoin data offers
  unprecedented insights. PLoS ONE 10(10), e0139356. https://doi.org/10.1371/journal.pone.0139356.**
  Latent buy-side liquidity thinned before the 2013 crash. The direct hypothesis behind "thinning
  books".
- Suggested by the citation check, to locate: Degryse, de Jong, van Ravenswaaij and Wuyts (2005),
  Review of Finance 9(2), on aggressive orders and resiliency; Kyle and Obizhaeva (2016), Econometrica
  84(4), on market microstructure invariance; Bouchaud, Bonart, Donier and Gould (2018), Trades,
  Quotes and Prices, Cambridge University Press.

## 7. Hawkes processes, reflexivity and criticality

- **[C] Filimonov, V. and Sornette, D. (2012). Quantifying reflexivity in financial markets: toward
  a prediction of flash crashes. Physical Review E 85, 056108.
  https://doi.org/10.1103/PhysRevE.85.056108.** Rising branching ratio before the 2010 flash crash.
- **[C] Hardiman, S. J., Bercot, N. and Bouchaud, J.-P. (2013). Critical reflexivity in financial
  markets: a Hawkes process analysis. European Physical Journal B 86, 442.
  https://doi.org/10.1140/epjb/e2013-40107-3.** Power-law kernels give near-critical, stable n.
- **[L] Filimonov, V. and Sornette, D. (2015). Apparent criticality and calibration issues in the
  Hawkes self-excited point process model. Quantitative Finance 15(8), 1293-1314.**
  Non-stationarity biases n upward. *For us:* the repo's monthly n (0.71 MLE, 0.96 count-variance,
  2023-06) is not a valid baseline for 6-hour stress windows; estimate on equal-length matched
  windows and pre-register the repo's baseline drift control as an exclusion rule.
- **[C] Wheatley, S., Wehrli, A. and Sornette, D. (2019). The endo-exo problem in high frequency
  financial price fluctuations and rejecting criticality. Quantitative Finance 19(7), 1165-1178.
  https://doi.org/10.1080/14697688.2018.1550266.**
- **[U] Mark, M., Sila, J. and Weber, T. A. (2022). Quantifying endogeneity of cryptocurrency
  markets. European Journal of Finance 28(7), 784-799.** Details from memory; check. Crypto benchmark
  for branching ratios.
- **[C] Ait-Sahalia, Y., Cacho-Diaz, J. and Laeven, R. J. A. (2015). Modeling financial contagion
  using mutually exciting jump processes. Journal of Financial Economics 117(3), 585-606.
  https://doi.org/10.1016/j.jfineco.2015.03.002.** BTC-to-alt jump contagion template.
- **[L] Boswijk, H. P., Laeven, R. J. A. and Yang, X. (2018). Testing for self-excitation in jumps.
  Journal of Econometrics 203(2), 256-266. https://doi.org/10.1016/j.jeconom.2017.11.007.**
- **[L] Chavez-Demoulin, V., Davison, A. C. and McNeil, A. J. (2005). Estimating value-at-risk: a
  point process approach. Quantitative Finance 5(2), 227-234.** Hawkes-POT alternative.
- **[C] Scheffer, M. et al. (2009). Early-warning signals for critical transitions. Nature 461, 53-59.
  https://doi.org/10.1038/nature08227.** Generic variance and AR(1) baseline indicators.
- **[C] Diks, C., Hommes, C. and Wang, J. (2019). Critical slowing down as an early warning signal
  for financial crises? Empirical Economics 57(4), 1201-1228.
  https://doi.org/10.1007/s00181-018-1527-3.** Prior scepticism; content not read.
- Suggested by the citation check: Dakos et al. (2012) PLoS ONE 7(7) e41010 (methods for early-warning
  indicators); Boettiger and Hastings (2012) J. R. Soc. Interface 9(75) (false positives and selection
  bias in early-warning claims); Bacry, Mastromatteo and Muzy (2015) Market Microstructure and
  Liquidity 1(1) (Hawkes survey).

## 8. Jump tests and event dating

- **[C] Lee, S. S. and Mykland, P. A. (2008). Jumps in Financial Markets: A New Nonparametric Test
  and Jump Dynamics. Review of Financial Studies 21(6), 2535-2563. https://doi.org/10.1093/rfs/hhm056.**
  `L(i) = r_i / sigma_hat_i`, Gumbel threshold. Our probe flagged 9 BTCUSDT mark-price minutes in
  20:52 to 21:21 UTC on 2025-10-10 (K = 120, |L| > 5.78), including two positive ones.
- **[L] Lee, S. S. and Mykland, P. A. (2012). Jumps in equilibrium prices and market microstructure
  noise. Journal of Econometrics 168(2), 396-406. https://doi.org/10.1016/j.jeconom.2012.03.001.**
  Pre-averaged version for tick data on thin alts.
- **[C] Barndorff-Nielsen, O. E. and Shephard, N. (2006). Econometrics of Testing for Jumps in
  Financial Economics Using Bipower Variation. Journal of Financial Econometrics 4(1), 1-30.
  https://doi.org/10.1093/jjfinec/nbi022.**
- **[C] Ait-Sahalia, Y. and Jacod, J. (2009). Testing for jumps in a discretely observed process.
  Annals of Statistics 37(1), 184-222. https://doi.org/10.1214/07-AOS568.**
- **[C] Andersen, T. G., Dobrev, D. and Schaumburg, E. (2012). Jump-robust volatility estimation
  using nearest neighbor truncation. Journal of Econometrics 169(1), 75-93.
  https://doi.org/10.1016/j.jeconom.2012.01.011.** MedRV, robust to adjacent jumps, which cascades
  produce (21:16 to 21:19 on 10-10 were consecutive).
- **[L] Bajgrowicz, P., Scaillet, O. and Treccani, A. (2016). Jumps in High-Frequency Data: Spurious
  Detections, Dynamics, and News. Management Science 62(8), 2198-2217.
  https://doi.org/10.1287/mnsc.2015.2234.** Up to 90% of raw detections spurious. Over about 4.7e8
  contract-minutes, family-wise control is essential.
- **[C] Christensen, K., Oomen, R. C. A. and Podolskij, M. (2014). Fact or friction: Jumps at ultra
  high frequency. Journal of Financial Economics 114(3), 576-599.
  https://doi.org/10.1016/j.jfineco.2014.07.007.**
- **[C] Christensen, K., Oomen, R. and Reno, R. (2022). The drift burst hypothesis. Journal of
  Econometrics 227(2), 461-497. https://doi.org/10.1016/j.jeconom.2020.11.004.** Cascades look like
  drift bursts; most negative bursts reverse. Second detector.
- **[C] Scaillet, O., Treccani, A. and Trevisan, C. (2020). High-Frequency Jump Analysis of the
  Bitcoin Market. Journal of Financial Econometrics 18(2), 209-232.
  https://doi.org/10.1093/jjfinec/nby013.** Order-flow imbalance predicts BTC jumps on Mt. Gox.
- **[C] Boudt, K., Croux, C. and Laurent, S. (2011). Robust estimation of intraweek periodicity in
  volatility and jump detection. Journal of Empirical Finance 18(2), 353-367.
  https://doi.org/10.1016/j.jempfin.2010.11.005.** Needed because of funding hours 00/08/16 UTC and the
  US open.
- **[C] Chen, J., Hong, H. and Stein, J. C. (2001). Forecasting crashes. Journal of Financial
  Economics 61(3), 345-381. https://doi.org/10.1016/S0304-405X(01)00066-6.** NCSKEW and DUVOL as
  continuous crash outcomes for P3.

## 9. Early-warning evaluation and rare-event econometrics

- **[L] Kaminsky, G., Lizondo, S. and Reinhart, C. M. (1998). Leading Indicators of Currency Crises.
  IMF Staff Papers 45(1), 1-48.** Noise-to-signal ratio
  `NSR = P(signal | no event within h) / P(signal | event within h)`.
- **[L] King, G. and Zeng, L. (2001). Logistic Regression in Rare Events Data. Political Analysis
  9(2), 137-163.** Case-control sampling with prior correction.
- **[C] Abadie, A. and Imbens, G. W. (2006). Large Sample Properties of Matching Estimators for
  Average Treatment Effects. Econometrica 74(1), 235-267.
  https://doi.org/10.1111/j.1468-0262.2006.00655.x.** Bias correction for matched calm windows.
- **[L] Beutel, J., List, S. and von Schweinitz, G. (2019). Does machine learning help us predict
  banking crises? Journal of Financial Stability 45, 100693. https://doi.org/10.1016/j.jfs.2019.100693.**
  (Link corrected; the earlier link was the Bundesbank DP 48/2018.) Logit beats ML out of sample.
- **[C] Saito, T. and Rehmsmeier, M. (2015). The precision-recall plot is more informative than the
  ROC plot when evaluating binary classifiers on imbalanced datasets. PLOS ONE 10(3), e0118432.
  https://doi.org/10.1371/journal.pone.0118432.**
- **[L] Tatbul, N., Lee, T. J., Zdonik, S., Alam, M. and Gottschlich, J. (2018). Precision and Recall
  for Time Series. NeurIPS 31.** Range-based scoring.
- **[L] Zechar, J. D. and Jordan, T. H. (2008). Testing alarm-based earthquake predictions.
  Geophysical Journal International 172(2), 715-724. https://doi.org/10.1111/j.1365-246X.2007.03676.x.**
  Molchan diagram scoring.
- **[L] Molchan, G. and Keilis-Borok, V. (2008). Earthquake prediction: probabilistic aspect.
  Geophysical Journal International 173(3); arXiv 0802.1126.** Journal DOI unverified.
- **[L] Lopez de Prado, M. (2018). Advances in Financial Machine Learning. Wiley.
  ISBN 978-1-119-48208-6.** Purged k-fold with embargo.
- **[C] Bailey, D. H., Borwein, J. M., Lopez de Prado, M. and Zhu, Q. J. (2017). The probability of
  backtest overfitting. Journal of Computational Finance 20(4). https://doi.org/10.21314/jcf.2016.322.**

## 10. Machine learning on order books and crash prediction

- **[C] Zhang, Z., Zohren, S. and Roberts, S. (2019). DeepLOB. IEEE Transactions on Signal
  Processing 67(11), 3001-3012. https://doi.org/10.1109/TSP.2019.2907260.** Needs L10 books, which free
  Binance data lacks for 2023 to 2026.
- **[L] Prata, M. et al. (2024). LOB-based deep learning models for stock price trend prediction: a
  benchmark study. Artificial Intelligence Review 57, 116. https://doi.org/10.1007/s10462-024-10715-4.**
  All 15 models degrade on new data.
- **[L] Briola, A., Bartolucci, S. and Aste, T. (2025). Deep limit order book forecasting: a
  microstructural guide. Quantitative Finance 25(7), 1101-1131.
  https://doi.org/10.1080/14697688.2025.2522911.**
- **[L] Lucchese, L., Pakkanen, M. S. and Veraart, A. E. D. (2024). The short-term predictability of
  returns in order book markets: a deep learning perspective. International Journal of Forecasting
  40(4), 1587-1621. https://doi.org/10.1016/j.ijforecast.2024.02.001.**
- **[C] Kolm, P. N., Turiel, J. and Westray, N. (2023). Deep order flow imbalance. Mathematical Finance
  33(4), 1044-1081. https://doi.org/10.1111/mafi.12413.** Stationary engineered inputs beat raw books.
- **[L] Makinen, Y., Kanniainen, J., Gabbouj, M. and Iosifidis, A. (2019). Forecasting jump arrivals in
  stock prices. Quantitative Finance 19(12), 2033-2050.** 1-minute horizon, far shorter than ours.
- **[C] Shu, M. and Zhu, W. (2020). Real-time prediction of Bitcoin bubble crashes. Physica A 548,
  124477.** LPPLS confidence indicator at 1h scale.
- **[C] Gerlach, J.-C., Demos, G. and Sornette, D. (2019). Dissection of Bitcoin's multiscale bubble
  history. Royal Society Open Science 6, 180643. https://doi.org/10.1098/rsos.180643.**
- **[L] Geraskin, P. and Fantazzini, D. (2013). Everything you always wanted to know about log-periodic
  power laws. European Journal of Finance 19(5), 366-391. https://doi.org/10.1080/1351847X.2011.601657.**
- **[L] Liu, Z., Shu, M. and Zhu, W. (2024). Contrastive learning framework for Bitcoin crash
  prediction. Stats 7(2), 402-433.** Scored by balanced accuracy only; an example of what not to copy.

## 11. Documentation and data-issue sources

- Binance official connector docstrings (GitHub, read via code search and raw.githubusercontent.com):
  the forceOrder stream pushes "only the latest one liquidation order within 1000ms"; aggTrades and
  trades exclude "insurance fund trades and ADL trades".
  https://github.com/binance/binance-connector-python (derivatives_trading_usds_futures and
  coin_futures market_data_api.py, websocket_streams.py).
- Binance FAQ via CMS API, articleCodes 360033525271 (liquidation protocols: IOC orders, bankrupt
  remainder taken over by the insurance fund), 360033525371 (insurance funds, pooled by group,
  confidential takeover capacity), 360033525471 (ADL ranking: PNL% x effective leverage).
- GitHub binance/binance-public-data issues #361 and #420 (USDT-M liquidationSnapshot withdrawn),
  #431 (bookDepth far from mark, which is the 2025-04-16 to 05-19 freeze), #437 and #447 (bookDepth
  generation: 30 s, depth from mid), #491 (metrics create_time change 2026-06-25), #496 (inner ask bands
  frozen from 2026-09-03), #503, #512, #525, #529. The citation check could not re-read these; dates and
  details are from earlier agents and should be re-checked.
