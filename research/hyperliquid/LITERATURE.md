# Literature for the Hyperliquid skill-vs-luck project

Annotated, grouped by topic. Each entry says what it found and what it means for this project.

Tags: **[V]** standard published reference with long-established details, or a source we read;
**[S]** seen only in search snippets or secondary summaries (arxiv.org, SSRN full texts and many
vendor sites were blocked from the research machine). Read every [S] item before citing it in a
public write-up. No reference here is invented; if a URL fails, search the title.

---

## 1. Skill vs luck: the mutual-fund toolkit

**Berk, J. and van Binsbergen, J. (2015). "Measuring skill in the mutual fund industry."
Journal of Financial Economics 118(1).** [V]
Skill = dollar value added: gross excess return over the cheapest investable alternative
(Vanguard index funds) times lagged fund size. Value added persists even though investors' net
alpha is about zero. The repo's `qfa/NOTES.md` session (2026-11-04) covers it.
*For us:* measure skill in dollars against investable on-venue alternatives (BTC/ETH perps held
passively with funding, HLP). Natural fit for vault leaders, whose size is observable.

**Berk, J. and Green, R. (2004). "Mutual fund flows and performance in rational markets."
Journal of Political Economy 112(6).** [V]
Flows chase skill until decreasing returns to scale push net alpha to zero.
*For us:* the prediction to test on Hyperliquid vaults (flows, size, returns).

**Kosowski, R., Timmermann, A., Wermers, R. and White, H. (2006). "Can mutual fund 'stars'
really pick stocks?" Journal of Finance 61(6).** [V]
Bootstraps each fund's residuals under zero alpha and compares the sorted cross-section of
alpha t-stats with the bootstrap. Top-decile alphas are not all luck. Prefers t-stats because
they do not depend on volatility.
*For us:* t-stats matter even more with leveraged wallets. Their fund-by-fund version ignores
cross-wallet correlation, so combine with the next paper.

**Fama, E. and French, K. (2010). "Luck versus skill in the cross-section of mutual fund
returns." Journal of Finance 65(5).** [V]
Resamples whole months jointly across all funds, preserving common shocks. Little skill net of
costs; some in both tails before costs.
*For us:* resample whole dates across all wallets. Essential because days like 2025-10-10 hit
everyone at once.

**Barras, L., Scaillet, O. and Wermers, R. (2010). "False discoveries in mutual fund
performance." Journal of Finance 65(1).** [V]
Uses Storey's pi0 to estimate shares of zero-alpha, unskilled and skilled funds. Net of costs
about 75% zero-alpha, 24% unskilled, 0.6% skilled by 2006.
*For us:* the "skilled share" headline number.

**Andrikogiannopoulou, A. and Papakonstantinou, F. (2019). "Reassessing false discoveries in
mutual fund performance." Journal of Finance 74(5).** [V]
The pi0 estimator has low power and overstates the zero-alpha share when alphas are small and
noisy.
*For us:* short wallet histories make this a live problem. Report it as a limitation and add
a shrinkage estimate.

**Harvey, C. and Liu, Y. (2020). "False (and missed) discoveries in financial economics."
Journal of Finance 75(5).** [V]
Double bootstrap that estimates both false and missed discoveries.
*For us:* report missed discoveries too, since power is low.

**Storey, J. (2002). "A direct approach to false discovery rates." JRSS B 64(3); Benjamini, Y.
and Hochberg, Y. (1995). JRSS B 57(1).** [V]
The FDR machinery.
*For us:* with m tests at level q, a permutation p-value has floor 1/(B+1), so B must exceed
m/q (480,000 for 48k wallets at q = 0.10), or use analytic or bootstrap-t tails.

## 2. Retail speculators: base rates

**Barber, B., Lee, Y.-T., Liu, Y.-J. and Odean, T. (2014). "The cross-section of speculator
skill: Evidence from day trading." Journal of Financial Markets 18.** [V]
https://faculty.haas.berkeley.edu/odean/papers/day%20traders/Day%20Trading%20Skill%20110523.pdf
Complete Taiwan records 1992 to 2006: under 1% of day traders predictably earn positive abnormal
returns net of fees, yet the top 500 by prior-year return earn 37.9 bp/day after fees next year.
*For us:* the template for persistence by past rank, and the prior: a small skilled tail exists.

**Barber, Lee, Liu, Odean and Zhang (2020). "Learning, fast or slow." Review of Asset Pricing
Studies 10(1).** [V]
74% of day-trading volume comes from traders with a history of losses.
*For us:* expect many persistent losers; test learning too.

**Chague, F., De-Losso, R. and Giovannetti, B. "Day trading for a living?" SSRN 3423101.** [S]
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3423101
Brazil: of those who day-traded futures for 300+ days, 97% lost money.
*For us:* condition on persistence and report the full earnings distribution, not the mean.

**Abbey, B. and Doukas, J. (2015). "Do individual currency traders make money?" Journal of
International Money and Finance.** [S]
Account-level skill vs luck in retail FX; a missing off-chain analogue.

**Kogan, Makarov, Niessner and Schoar. "Are cryptos different? Evidence from retail trading."
NBER w31317 (JFE 2024).** [S] https://www.nber.org/papers/w31317
eToro traders trade momentum in crypto but contrarian in stocks. Behaviour, not skill.

## 3. Skill on crypto and on-chain venues

**Placebo (github.com/cyberhooman/placebo), results 2026-10-05.** [S, repo summarized by our
skeptic agent]
Pre-registered, hash-locked (sha256 of `score.py`) timing-placebo permutation test with BH
q = 0.10 on the top 500 Hyperliquid accounts and top 100 vaults; publishes an on-chain
`isSkilled(address)` registry. 4 of 216 accounts pass; 0 of 52 vaults; timing does not persist
(rho -0.09 on 125 accounts).
*For us:* **closest prior work. Cite it and state the increment** (full cohort, PnL alpha,
entity merging, investable benchmarks, future window, correct p-value floor). Its result is our
stated prior. Do not copy the per-address on-chain labels (defamation risk).

**Dennim89/hyperliquid-copytrade-study (2026-09-25).** [S]
https://github.com/Dennim89/hyperliquid-copytrade-study
Pre-registered leaderboard persistence test, 929 requests, NO-GO; rank correlations swing with
market phase. Encodes the API weight table in code.
*For us:* proves free data suffices, shows the need for a bigger universe and a proper null.

**Zhai (2026). "Public trader identity: adverse selection and return predictability."
arXiv 2608.04373.** [S]
147,113 Hyperliquid wallets; toxicity rank persists (rho 0.52 across ten-day windows); identity
adds 13.2% to 1-second R2.
*For us:* skill exists at the seconds horizon as adverse selection. Our question is PnL skill
after luck.

**"Wallet identity for return prediction", arXiv 2611.05218.** [S]
Order-flow paper using Hyperliquid wallet identity; not about vaults or luck.

**Gomez-Cram, R., Guo, Jensen, T. and Kung, H. "Prediction market accuracy: crowd wisdom or
informed minority?" SSRN 6687418.** [S] https://papers.ssrn.com/abstract=6687418
Sign-randomization: replay each account's trades 10,000 times with directions flipped. About
3.14% of 1.72M Polymarket accounts are skilled winners; 44% stay skilled out of sample (vs
about 10% for funds). Critique: flipping changes market exposure.
*For us:* benchmark-free, leverage-free null that suits perps. De-mean or flip in matched pairs
to avoid crediting long bias in a trending market.

**Akey, Gregoire, Harvie and Martineau. "Who wins and who loses in prediction markets?"
SSRN 6443103.** [S]
Top 1% take 76.5% of profits; winners often supply liquidity.
*For us:* expect maker-style wallets to dominate winners; test skill within wallet type.

**Mitts, J. and Ofir, M. "From Iran to Taylor Swift: informed trading in prediction markets."**
[S] (HLS Forum summary)
Permutation null on wallet-market pairs.
*For us:* template for "who exits before collapses".

**Bianchi, D. and Babiak, M. (2022). "On the performance of cryptocurrency funds." Journal of
Banking and Finance 138.** [S]
https://eprints.lancs.ac.uk/id/eprint/169953
Panel bootstrap preserving cross-fund correlation weakens skill evidence.
*For us:* resample dates jointly across wallets.

**Industry:** Saulius, hierarchical Bayesian trader skill
(https://saulius.io/blog/bayesian-hierarchical-model-trader-skill), single walk-forward, 77% vs
54% winning copies, much of the edge was HYPE concentration; Tessera decile transitions
(https://tesseralytics.dev/blog/wallet-behaviour); "I analyzed 10,000 Hyperliquid traders"
(https://medium.com/@envyprotocol/i-analyzed-10-000-hyperliquid-traders-the-results-are-brutal-a29adcca8c2a);
BeInCrypto profitability count (https://beincrypto.com/hyperliquid-traders-profitability/). [S]
*For us:* baselines and motivation; none report significance.

## 4. Crypto factors and benchmarks

**Liu, Y., Tsyvinski, A. and Wu, X. (2022). "Common risk factors in cryptocurrency." Journal of
Finance 77(2).** [V]
https://cowles.yale.edu/sites/default/files/2022-10/LiuTsyvinskiWu2019%20COMMON%20RISK%20FACTORS.pdf
Market, size and short-horizon (3-week) momentum price crypto returns, weekly.
*For us:* factor rung of the benchmark ladder. Our own Hyperliquid-built versions were all
insignificant over 146 weeks (market t 0.34, size t -1.16, momentum t 0.91), so lead with
investable benchmarks.

**Stoeckl, Open Crypto Asset Pricing replication.** [S]
https://sstoeckl.github.io/crypto_data/replication.html
Free factor series; size premium mostly disappears on investable breakpoints.
*For us:* external check on our factors.

**Schmeling, M., Schrimpf, A. and Todorov, K. "Crypto carry." BIS Working Paper 1087.** [S]
https://www.bis.org/publ/work1087.pdf
Carry is large and time-varying, driven by leveraged trend-chasers.
*For us:* add a funding-carry factor; per-wallet funding is exactly observable (`userFunding`).

**Agarwal, V. and Naik, N. (2004). "Risks and portfolio decisions involving hedge funds."
Review of Financial Studies 17(1); Fung, W. and Hsieh, D. (2001). RFS 14(2).** [V]
Option-like factors for nonlinear payoffs.
*For us:* liquidation harvesting and volatility selling look like skill under linear alpha;
use HLP and squared-return terms.

## 5. ML for picking managers (and its pitfalls)

**Kaniel, R., Lin, Z., Pelger, M. and Van Nieuwerburgh, S. (2023). "Machine-learning the skill
of mutual fund managers." Journal of Financial Economics 150(1).** [S]
https://www.nber.org/papers/w29723
Neural nets on fund characteristics predict outperformers; momentum and flows matter most.

**DeMiguel, V., Gil-Bazo, J., Nogales, F. and Santos, A. (2023). "Machine learning and fund
characteristics help to select mutual funds with positive alpha." JFE.** [S]
About 2.4% per year out-of-sample net alpha.

**Fausch et al. (2025), correction to DeMiguel et al.** [S]
https://data.mendeley.com/datasets/rpgb99m5zy
A look-ahead bug in replication code; after the fix, elastic net matched the ML models and
long-only alpha vanished (later partly restored).
*For us:* the cautionary story. Pre-register purge gaps, hash-lock, and use elastic net as the
main baseline.

## 6. Hyperliquid mechanics and incidents

**Official docs** (blocked here; seen via snippets) [S]:
HIP-1 token standard
https://hyperliquid.gitbook.io/hyperliquid-docs/hyperliquid-improvement-proposals-hips/hip-1-native-token-standard ;
HIP-2 Hyperliquidity
https://hyperliquid.gitbook.io/Hyperliquid-docs/hyperliquid-improvement-proposals-hips/hip-2-hyperliquidity ;
HIP-3 builder perps
https://hyperliquid.gitbook.io/hyperliquid-docs/hyperliquid-improvement-proposals-hips/hip-3-builder-deployed-perpetuals ;
delisting https://hyperliquid.gitbook.io/hyperliquid-docs/trading/delisting ;
historical data https://hyperliquid.gitbook.io/hyperliquid-docs/historical-data ;
rate limits https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/rate-limits-and-user-limits ;
vaults https://hyperliquid.gitbook.io/hyperliquid-docs/hypercore/vaults/for-vault-leaders .
Python SDK (readable): https://github.com/hyperliquid-dex/hyperliquid-python-sdk
*For us:* deploy mechanics (31-hour Dutch gas auction; freeze privilege; deployer fee share
default 100%), delisting by validator vote, vault 10% profit share.

**JELLY, 2025-03-26.** [S, partly V by our reconstruction]
https://info.arkm.com/research/jellyjelly-exploit-on-hyperliquid ;
https://www.theblock.co/post/348314 ;
https://thedefiant.io/hyperliquid-to-compensate-jellyjelly-traders-and-strengthen-risk-protocols ;
https://blockworks.co/news/hyperliquid-decentralization-validator-put
A short was liquidated into HLP while spot was pumped; validators delisted and settled at
$0.0095 (the attacker's entry, not the oracle TWAP), turning HLP's loss into about +$700k.
*For us:* delistings are discretionary in price and timing; the on-chain ledger confirms the
short's margin was withdrawn before liquidation.

**XPL pre-market, 2025-08-26.** [S, partly V]
https://www.theblock.co/amp/post/368486/hyperliquid-new-safeguards-following-whale-driven-xpl-pre-market-liquidations ;
https://www.dlnews.com/articles/defi/hyperliquid-whale-inflates-xpl-token-future-contract-price-exposing-vulnerabilities/
Profit figures from $15M to $48M in the press; on-chain the main whale realized $14.1M, $12.0M
of it via ADL. HLP was not the loss bearer.

**POPCAT, 2025-11-12.** [S, partly V]
https://www.theblock.co/news/defi/2025-11-12-hyperliquid-pauses-deposits-withdrawals-popcat-trading-scheme-speculation-378606 ;
https://thedefiant.io/large-popcat-trades-result-in-usd5-million-loss-for-hyperliquid-vault ;
https://cointelegraph.com/news/hyperliquid-hlp-popcat-attack-3m-wipeout
Press: 19 wallets, $4.9M HLP bad debt. On-chain: 40 accounts backstop-liquidated into HLP and
-$5.46M realized for the Liquidator. Gap not reconciled.

**FARTCOIN, 2026-04-08; XPL flash crash, 2026-11-01.** [S, V on-chain]
https://beincrypto.com/fartcoin-hyperliquid-manipulation-hlp-loss/ ;
https://www.chaincatcher.com/en/article/2300887

**HyperVault rug (HyperEVM), 2025-09-26.** [S]
https://www.theblock.co/news/defi/2025-09-26-defi-protocol-hypervault-vanishes-after-3-6-million-suspected-rugpull-372497 ;
https://rekt.news/hypervault-rugged
EVM-side, outside HyperCore data.

**Auto-deleveraging papers on 2025-10-10.** arXiv 2512.01112 (Gauntlet; $45.0M to $51.7M taken
from winners), arXiv 2603.15963. [S]
*For us:* ADL transfers profit from winners on crash days; a luck-relevant shock to model.

**HLP analyses.** https://www.coingecko.com/learn/hyperliquid-hlp-vault-analysis [S]
Blog-level only; no academic HLP alpha study found.

## 7. Memecoins and rug-pull detection

**Sun et al. (2024). SoK on rug pulls. arXiv 2403.16082.** [S]
34 root causes; token-distribution rugs are the most damaging category (about 35% of losses).
*For us:* genesis concentration is the HIP-1 analogue of that category.

**Mazorra, B., Adan, V. and Daza, V. (2022). "Do not rug on me." Mathematics 10(6):949;
arXiv 2201.07220.** [S]
27,588 Uniswap tokens; label = inactive over a month plus liquidity removed or price down 90%;
HHI and transaction-graph features; accuracy 0.99.
*For us:* borrow the label shape. Treat near-perfect accuracy as a sign of label leakage.
The 97% headline is disputed: https://blockworks.co/news/are-97-of-tokens-on-uniswap-really-rug-pulls

**Xia et al. (2021). Uniswap scam tokens. SIGMETRICS; arXiv 2109.00229.** [S]
About half of Uniswap listings were scams; guilt-by-association features.

**Cernera, F. et al. (2023). "Token spammers, rug pulls, and sniper bots." USENIX Security.**
[S] https://www.usenix.org/conference/usenixsecurity23/presentation/cernera
1-day rug pulls; 60% of tokens live under a day; 1% of addresses create over 20% of tokens.
*For us:* serial deployers are a feature; Hyperliquid exposes deployer identity natively.

**MemeTrans, arXiv 2602.13480.** [S] https://arxiv.org/html/2602.13480
41,470 pump.fun tokens, 122 pre-migration features; code at github git-disl/MemeTrans.
*For us:* feature list to port (holder concentration, early trading behaviour).

**"Catching the Rug", arXiv 2608.20271.** [S]
6.4M Solana tokens; XGBoost on the first 5 minutes of trading, no code features needed.
*For us:* trade-based early features work, but we only have them for launches we record.

**TON rug detection, arXiv 2509.01168.** [S]
Gradient boosting in the first 5 minutes; AUC up to 0.891; compares label definitions.

**SolRPDS, arXiv 2504.07132.** [S] https://huggingface.co/datasets/DeFiLab/SolRPDS
Public Solana rug dataset, CC BY 4.0.

**MemeChain, arXiv 2601.22185 (Zenodo 18246856).** [S]
Free cross-chain memecoin dataset for comparison.

**Mongardini and Mei, "A midsummer meme's dream", arXiv 2507.01963.** [S]
34,988 memecoins on 4 chains; wash trading often precedes pump-and-dumps; 17,000+ victims.

**SBFC 2025 pump.fun paper.** [S]
https://sbfc.sydney.edu.au/2025/papers/SBFC2025_4G3_P154.pdf
Creators and snipers over-represented among wallets with significant PnL t-stats.
*For us:* "luck on launches" is partly done; persistence across launches with FDR is open.

**Coordinated sniper cohorts on pump.fun, arXiv 2607.02795; predicting token success,
arXiv 2602.14860.** [S]
The second uses early participation by previously successful traders as a predictor, which
links directly to our skill question.

**Pine Analytics, "Exit liquidity machines".** [S]
https://pineanalytics.substack.com/p/exit-liquidity-machines
Funding-flow linking of snipers to deployers; vendor work.

**Solidus Labs pump.fun report.** [S]
https://www.soliduslabs.com/reports/solana-rug-pulls-pump-dumps-crypto-compliance
98.6% of pump.fun tokens show rug traits; disputed. Base-rate context only.

**Descriptive Hyperliquid launch dashboards:** ASXN auction dashboard, hl.eco deployer
rankings. [S] Descriptive only; no survival analysis.

## 8. Wallet linking and clustering

**Victor, F. (2020). "Address clustering heuristics for Ethereum." Financial Cryptography.** [S]
https://link.springer.com/doi/10.1007/978-3-030-51280-4_33
Deposit-address reuse is the strongest heuristic.
*For us:* shared funding addresses in `send`/`withdraw` ledger records.

**Victor and Weintraud (2021), wash trading on DEXs, arXiv 2102.07001; Cong, Li, Tang and
Yang (2023), "Crypto wash trading", Management Science 69(11).** [S]
Trade-cycle and statistical tests; baselines any ML detector must beat.

**Sybil detection:** arXiv 2505.09313 (LightGBM subgraph), arXiv 2607.27370 (behavioural
similarity on Ethereum), Arbitrum Foundation sybil repo
https://www.github.com/ArbitrumFoundation/sybil-detection [S].

**Arrakis wallet classifier for HIP-3.** [S]
https://arrakis.finance/blog/who-is-trading-on-hip3 ; https://arrakis.finance/blog/trade-xyz
Maker/taker ratio, fill frequency, cancels, tif; 79,622 wallets; about 70% unclassified.
*For us:* closest prior work for wallet typology.

## 9. Vaults and copy trading

**tradingstrategy.ai Hyperliquid vault tracker.** [S] https://tradingstrategy.ai/vaults/hyperliquid
Flow-cleaned vault returns; no value-added or FDR study.

**Deng, Yang, Pelster and Tan (2023), copy trading on eToro/ZuluTrade.** [S]
https://wiwi.uni-paderborn.de/fileadmin-wiwi/cetar/TAF_Working_Paper_Series/TAF_WP_074_DengYangPelsterTan2023_rev.pdf
Link formation and risk-taking, not value added.

**Sirri and Tufano (1998) JF; Chevalier and Ellison (1997) JPE; Dichev (2007) AER; Friesen and
Sapp (2007) JBF.** [V]
Flow-performance convexity and investor timing gaps.
*For us:* tests for vault depositors. Caveat: the 2026-04-13 vault-fee change coincided with
deprecation of legacy vaults, which confounds any natural experiment there.
