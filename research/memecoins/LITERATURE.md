# Literature: memecoins, lottery demand, attention and harm

Compiled 2026-11-20 from six scout tracks, five deep dives, a novelty review and a citation check.

**How to read this file.** No full text was read: arxiv.org, doi.org, papers.ssrn.com, nber.org, publisher sites and RePEc full-text hosts were blocked in every session, and the shared web-search budget ran out. Entries rest on abstracts, publisher and RePEc records, and search summaries. Tags:
- **[V]** bibliographic record confirmed by a scout or the citation checker (title, venue, volume). Numbers may still need checking against the PDF.
- **[U]** unverified: some detail (authors, venue, DOI, article number or figures) could not be confirmed. Do not put a [U] number into a pre-registration without reading the source.
- **[I]** industry or news source, not peer reviewed.

Dropped after the citation check: Zhao, Wang and Liu (2024, "Someone like you"), Caglayan, Duarte, Duarte and Lu (2025, "Compounding money and nominal price illusions"), the Chainplay $TRUMP report, the SBFC 2025 pump.fun paper with placeholder title and no authors, Flynn et al. (2026, Journal of Financial Markets) and Long, Wong and Cai (2025), none of which could be confirmed. Duplicates have been merged.

## 1. Lottery preferences and probability weighting

- **Tversky, A. and Kahneman, D. (1992).** Advances in prospect theory: Cumulative representation of uncertainty. *Journal of Risk and Uncertainty* 5(4), 297-323. https://doi.org/10.1007/BF00122574 [V]. Probability weighting w(P) = P^d / (P^d + (1-P)^d)^(1/d); estimates a = 0.88, lambda = 2.25, gamma = 0.61 (gains), delta = 0.69 (losses). *For us:* the parameters used to compute a prospect-theory value of memecoin return paths.
- **Barberis, N. and Huang, M. (2008).** Stocks as lotteries: The implications of probability weighting for security prices. *American Economic Review* 98(5), 2066-2100. https://doi.org/10.1257/aer.98.5.2066 [V]. Positively skewed securities can be overpriced and earn negative average excess returns in equilibrium. *For us:* the core reason memecoins can stay overpriced even when buyers know most fail.
- **Bali, T. G., Cakici, N. and Whitelaw, R. F. (2011).** Maxing out: Stocks as lotteries and the cross-section of expected returns. *Journal of Financial Economics* 99(2), 427-446. https://doi.org/10.1016/j.jfineco.2010.08.014 [V]. MAX (largest daily return last month) predicts returns more than 1% a month lower. *For us:* MAX_{i,w} = max of daily log returns over the prior window, computable from free klines (P3).
- **Kumar, A. (2009).** Who gambles in the stock market? *Journal of Finance* 64(4), 1889-1933. https://doi.org/10.1111/j.1540-6261.2009.01483.x [V]. Lottery-type stocks (low price, high idiosyncratic volatility and skewness) attract investors who resemble state-lottery players and underperform. Exact percentile cutoffs [U]. *For us:* memecoins sit at the extreme of all three lottery traits.
- **Kumar, A., Page, J. K. and Spalt, O. G. (2011).** Religious beliefs, gambling attitudes, and financial market outcomes. *Journal of Financial Economics* 102(3), 671-708. https://doi.org/10.1016/j.jfineco.2011.07.001 [V]. Local gambling culture shapes lottery-stock demand. *For us:* a limitation; crypto data have no geography.
- **Barberis, N., Mukherjee, A. and Wang, B. (2016).** Prospect theory and stock returns: An empirical test. *Review of Financial Studies* 29(11), 3068-3107. https://doi.org/10.1093/rfs/hhw049 [V]. High prospect-theory value from past returns predicts low returns. *For us:* a robustness arm of P3 only; collinear with MAX on short windows.
- **Mitton, T. and Vorkink, K. (2007).** Equilibrium underdiversification and the preference for skewness. *Review of Financial Studies* 20(4), 1255-1288. https://doi.org/10.1093/rfs/hhm011 [V]. Skewness lovers hold concentrated portfolios. *For us:* predicts concentrated Hyperliquid memecoin positions (P4).
- **Brunnermeier, M. K. and Parker, J. A. (2005).** Optimal expectations. *American Economic Review* 95(4), 1092-1118. https://doi.org/10.1257/0002828054825493 [V, DOI inferred from numbering]. Optimism has anticipatory value, producing a taste for skewness.
- **Brunnermeier, M. K., Gollier, C. and Parker, J. A. (2007).** Optimal beliefs, asset prices, and the preference for skewed returns. *American Economic Review* 97(2), 159-165. https://doi.org/10.1257/aer.97.2.159 [V, DOI inferred]. Belief-based route to overpricing of skewed assets.
- **Snowberg, E. and Wolfers, J. (2010).** Explaining the favorite-long shot bias: Is it risk-love or misperceptions? *Journal of Political Economy* 118(4), 723-746. https://doi.org/10.1086/655844 [V]. Misperceived probabilities explain longshot overbetting.
- **Garrett, T. A. and Sobel, R. S. (1999).** Gamblers favor skewness, not risk. *Economics Letters* 63(1), 85-90 [U, added by citation checker].
- **Bordalo, P., Gennaioli, N. and Shleifer, A. (2012).** Salience theory of choice under risk. *Quarterly Journal of Economics* 127(3), 1243-1285. https://doi.org/10.1093/qje/qjs018 [U, added by citation checker]. An alternative to probability weighting: a salient jump draws demand.

**Crypto evidence on lottery demand (sign disputed):**
- **Grobys, K. and Junttila, J. (2021).** Speculation and lottery-like demand in cryptocurrency markets. *Journal of International Financial Markets, Institutions and Money* 71, 101289. https://ideas.repec.org/a/eee/intfin/v71y2021ics1042443121000081.html [V; article number U]. Low-minus-high weekly MAX spread above 1.5% a week, 20 coins, 2016-2019.
- **Ozdamar, M., Akdeniz, L. and Sensoy, A. (2021).** Lottery-like preferences and the MAX effect in the cryptocurrency market. *Financial Innovation* 7, article 74. https://doi.org/10.1186/s40854-021-00291-9 [V]. Opposite sign: high-minus-low +3.03% a week raw, +1.99% risk-adjusted.
- **Li, Y., Urquhart, A., Wang, P. and Zhang, W. (2021).** MAX momentum in cryptocurrency markets. *International Review of Financial Analysis* 77, 101829 [U for volume and article number]. https://research.birmingham.ac.uk/en/publications/max-momentum-in-cryptocurrency-markets/. High MAX coins keep rising.
- **Yadav (2025).** Intraday lottery demands in cryptocurrency market. *Studies in Economics and Finance*. https://econpapers.repec.org/RePEc:eme:sefpps:sef-07-2024-0461 [U: author full name and volume]. Hourly: 1 SD higher MAX predicts -0.043% next return.
- **Wu, S.-F., Tuan-Mu, C. and Yen, K.-C. (2024).** Lottery-like effect and cryptocurrency. SSRN 4959218. https://doi.org/10.2139/ssrn.4959218 [U]. Monthly MAX predicts lower returns.
- **Liu, Y., Tsyvinski, A. and Wu, X. (2022).** Common risk factors in cryptocurrency. *Journal of Finance* 77(2), 1133-1177 [V]. Market, size and momentum factors. *For us:* required controls in any MAX test.

*What it means for the projects:* the sign in crypto is genuinely open, so P3 pre-registers a two-sided test by horizon. The meme segment has only about 50 to 65 perps, so P3 cannot "settle" a dispute rooted in spot universes of thousands of coins; it answers a narrower question (is lottery demand priced in meme perps, net of funding).

## 2. Trading as entertainment, overconfidence and gambling substitution

- **Dorn, D. and Sengmueller, P. (2009).** Trading as entertainment? *Management Science* 55(4), 591-603. https://doi.org/10.1287/mnsc.1080.0962 [V]. Investors who enjoy gambling turn over portfolios twice as fast.
- **Barber, B. M. and Odean, T. (2000).** Trading is hazardous to your wealth. *Journal of Finance* 55(2), 773-806. https://doi.org/10.1111/0022-1082.00226 [V]. Most active households earn 11.4% a year net against 17.9% for the market. *For us:* the turnover-performance benchmark for P4.
- **Barber, B. M. and Odean, T. (2001).** Boys will be boys. *Quarterly Journal of Economics* 116(1), 261-292. https://doi.org/10.1162/003355301556400 [V]. Men trade 45% more and lose more.
- **Odean, T. (1999).** Do investors trade too much? *American Economic Review* 89(5), 1279-1298. https://doi.org/10.1257/aer.89.5.1279 [V per citation checker].
- **Grinblatt, M. and Keloharju, M. (2009).** Sensation seeking, overconfidence, and trading activity. *Journal of Finance* 64(2), 549-578 [V]. Speeding tickets predict turnover (per-ticket figure U).
- **Barber, B. M., Lee, Y.-T., Liu, Y.-J. and Odean, T. (2009).** Just how much do individual investors lose by trading? *Review of Financial Studies* 22(2), 609-632. https://doi.org/10.1093/rfs/hhn046 [V per citation checker]. Taiwan's 2002 lottery launch coincided with lower turnover (descriptive).
- **Barber, B. M., Lee, Y.-T., Liu, Y.-J., Odean, T. and Zhang, K. (2020).** Learning, fast or slow. *Review of Asset Pricing Studies* 10(1), 61-93 [U]. Losing day traders persist. *For us:* the persistence prior for losers in P4.
- **Gao, X. and Lin, T.-C. (2015).** Do individual investors treat trading as a fun and exciting gambling activity? *Review of Financial Studies* 28(7), 2128-2166. https://doi.org/10.1093/rfs/hhu075 [V]. Jackpots above NT$500m (148 on trading days, 2002-2009) cut volume 6.8% to 8.6% in lottery-like stocks. Spec: log V_{i,t} on a jackpot dummy plus log mean V over t-22 to t-1 (full controls U).
- **Dorn, A. J., Dorn, D. and Sengmueller, P. (2015).** Trading as gambling. *Management Science* 61(10), 2376-2393. https://doi.org/10.1287/mnsc.2014.1979 [V]. Large US jackpots reduce small trades in stocks and options, not bonds or funds. The "about 1% per SD" magnitude comes from a review [U].
- **Ehrmann, M. and Jansen, D.-J. (2017).** The pitch rather than the pit: Investor inattention, trading activity, and FIFA World Cup matches. *Journal of Money, Credit and Banking* 49(4), 807-821. https://econpapers.repec.org/RePEc:wly:jmoncb:v:49:y:2017:i:4:p:807-821 [V]. Volume falls up to 48% while the national team plays. *For us:* the direct template for P7.
- **Baker, S. R., Balthrop, J., Johnson, M. J., Kotter, J. D. and Pisciotta, K. (2024).** Gambling away stability: Sports betting's impact on vulnerable households. NBER Working Paper 33108. https://doi.org/10.3386/w33108 [V as WP]. Legalization lowers net investment (about 14% in the WP, about 20% reported for the journal version, conflict unresolved) and crypto purchases. A JFE 2026 publication (vol. 183, 104330) is reported only by a press release [U].
- **Chen, Y., Kumar, A. and Zhang, C. (2021).** Searching for gambles: Gambling sentiment and stock market outcomes. *JFQA* 56(6), 2010-2038 [U]. The complementarity channel: gambling sentiment raises lottery-stock demand. *For us:* any substitution test must allow both signs.

*What it means:* substitution designs are the cleanest causal tests of the "memecoins as gambling" story, but the shock must hit the venue's users. Binance.com excludes US residents, so P7 uses European football; US jackpot tests are deprioritised.

## 3. Attention and retail herding

- **Barber, B. M. and Odean, T. (2008).** All that glitters. *Review of Financial Studies* 21(2), 785-818. https://doi.org/10.1093/rfs/hhm079 [V]. Individuals are net buyers of attention-grabbing stocks.
- **Da, Z., Engelberg, J. and Gao, P. (2011).** In search of attention. *Journal of Finance* 66(5), 1461-1499 [V]. Abnormal search = log SVI minus log median of prior 8 weeks; predicts a rise then reversal.
- **Barber, B. M., Huang, X., Odean, T. and Schwarz, C. (2022).** Attention-induced trading and returns: Evidence from Robinhood users. *Journal of Finance* 77(6), 3141-3190. https://doi.org/10.1111/jofi.13183 [V]. Top herding stocks average -4.7% over 20 days.
- **Han, B. and Kumar, A. (2013).** Speculative retail trading and asset prices. *JFQA* 48(2), 377-404 [V]. High retail-trading-proportion stocks earn negative alphas.
- **Eaton, G. W., Green, T. C., Roseman, B. S. and Wu, Y. (2022).** Retail trader sophistication and stock market quality: Evidence from brokerage outages. *Journal of Financial Economics* 146(2), 502-528. https://doi.org/10.1016/j.jfineco.2022.08.002 [V].
- **Welch, I. (2022).** The wisdom of the Robinhood crowd. *Journal of Finance* 77(3), 1489-1527. https://doi.org/10.1111/jofi.13128 [V]. A counterweight: the aggregate retail portfolio timed March 2020 well.
- **Liu, Y. and Tsyvinski, A. (2021).** Risks and returns of cryptocurrency. *Review of Financial Studies* 34(6), 2689-2727 [V]; NBER w24877. Attention proxies predict crypto returns (magnitudes vary between summaries: 1.84% vs 2.5% per SD [U]).
- **Kristoufek, L. (2013).** BitCoin meets Google Trends and Wikipedia. *Scientific Reports* 3, 3415. https://doi.org/10.1038/srep03415 [V]. Two-way causality between attention and price. *For us:* every attention design needs pre-trend and reverse-direction tests.
- **ElBahrawy, A., Alessandretti, L. and Baronchelli, A. (2019).** Wikipedia and cryptocurrencies. *Frontiers in Blockchain* 2, 12. https://doi.org/10.3389/fbloc.2019.00012 [V]. *For us:* Wikipedia-for-memecoins is largely done; not ranked.
- **Ante, L. (2023).** How Elon Musk's Twitter activity moves cryptocurrency markets. *Technological Forecasting and Social Change* 186 (Part A), 122112 (article number U). https://ideas.repec.org/a/eee/tefoso/v186y2023ipas0040162522006333.html [V]. 47 events; price effects significant only for DOGE.
- **Shahzad, S. J. H., Anas, M. and Bouri, E. (2022).** Price explosiveness in cryptocurrencies and Elon Musk's tweets. *Finance Research Letters* 47, 102695. https://doi.org/10.1016/j.frl.2022.102695 [V].
- **Cary, M. (2021).** Down with the #Dogefather. *J. Theoretical and Applied Electronic Commerce Research* 16(6), 2230-2240. https://doi.org/10.3390/jtaer16060123 [V]. DOGE fell 23.4% during Musk's SNL appearance.
- **Merkley, K. J., Pacelli, J., Piorkowski, M. and Williams, B. (2024).** Crypto-influencers. *Review of Accounting Studies* 29(3). https://doi.org/10.1007/s11142-024-09837-5 [V]. Short-lived gains after influencer tweets; memecoins reportedly excluded.
- **Kogan, S., Makarov, I., Niessner, M. and Schoar, A. (2024).** Are cryptos different? Evidence from retail trading. *Journal of Financial Economics* 159, 103897. https://doi.org/10.1016/j.jfineco.2024.103897 [V]. Same eToro traders: contrarian in stocks, momentum in crypto. *For us:* the main competing explanation (adoption beliefs) for every lottery test.
- **Hackethal, A., Hanspal, T., Lammer, D. M. and Rink, K. (2022).** The characteristics and portfolio behavior of bitcoin investors. *Review of Finance* 26(4), 855-898. https://doi.org/10.1093/rof/rfab034 [V]. Logins rise after the first crypto purchase.
- **Benetton, M. and Compiani, G. (2024).** Investors' beliefs and cryptocurrency prices. *Review of Asset Pricing Studies* 14(2), 197-236 [U]. Late entrants more optimistic.

## 4. Social contagion and narratives

- **Hirshleifer, D. (2020).** Social transmission bias in economics and finance. *Journal of Finance* 75(4), 1779-1831. https://doi.org/10.1111/jofi.12906 [V].
- **Han, B., Hirshleifer, D. and Walden, J. (2022).** Social transmission bias and investor behavior. *JFQA* 57(1), 390-412 [V]; earlier version NBER WP 24281. Winners talk, losers stay quiet.
- **Shiller, R. J. (2017).** Narrative economics. *American Economic Review* 107(4), 967-1004. https://doi.org/10.1257/aer.107.4.967 [V]. Stories spread like epidemics and exhaust their susceptible pool.
- **Pedersen, L. H. (2022).** Game on: Social networks and markets. *Journal of Financial Economics* 146(3), 1097-1119. https://doi.org/10.1016/j.jfineco.2022.05.002 [V, open access]. Influencers and fanatics generate bubbles, volume bursts, momentum and reversal.
- **Cookson, J. A., Engelberg, J. E. and Mullins, W. (2023).** Echo chambers. *Review of Financial Studies* 36(2), 450-500. https://doi.org/10.1093/rfs/hhac058 [V].
- **Hu, D., Jones, C. M., Li, S., Zhang, V. and Zhang, X.** The rise of Reddit. Working paper (ABFER 2024). https://www.abfer.org/media/abfer-events-2024/annual-conference/papers-investment/AC24P3076-The-Rise-of-Reddit-How-Social-Media-Affects-Belief-Formation-and-Price-Discovery.pdf [V, unpublished].
- **Baumgartner, J., Zannettou, S., Keegan, B., Squire, M. and Blackburn, J. (2020).** The Pushshift Reddit dataset. *Proceedings of ICWSM* 14, 830-839. arXiv 2001.08435 [V per citation checker]. Companion: The Pushshift Telegram dataset, ICWSM 14, 840-847, arXiv 2001.08438.

*What it means:* social contagion is the mechanism with the least free, licensed data. Reddit's academic torrents were removed at Reddit's request around 2026-09, X costs money, and Telegram needs a personal account. The repo tests contagion only indirectly (price co-excitation, positioning) until a licensed text source is settled.

## 5. Meme stocks

- **Bradley, D., Hanousek, J., Jame, R. and Xiao, Z. (2024).** Place your bets? The value of investment research on Reddit's Wallstreetbets. *Review of Financial Studies* 37(5), 1409-1459. https://doi.org/10.1093/rfs/hhad098 [V]. Due-diligence posts stopped predicting returns after GameStop.
- **Allen, F., Haas, M., Nowak, E., Pirovano, M. and Tengulov, A.** Squeezing shorts through social media platforms. *Management Science* 72(9), 7940-7969 (year presumably 2026, U). https://doi.org/10.1287/mnsc.2023.02887; earlier SSRN 3823151. Retail coordination plus options gamma. *For us:* perps have no borrow constraint; squeezes run through leverage and liquidation.
- **Hasso, T., Muller, D., Pelster, M. and Warkulat, S. (2022).** Who participated in the GameStop frenzy? *Finance Research Letters* 45, 102140. https://doi.org/10.1016/j.frl.2021.102140 [V]. Same gamblers, new venue.
- **Lyocsa, S., Baumohl, E. and Vyrost, T. (2022).** YOLO trading. *Finance Research Letters* 46, 102359. https://doi.org/10.1016/j.frl.2021.102359 [V].
- **Aloosh, A., Ouzan, S. and Shahzad, S. J. H. (2022).** Bubbles across meme stocks and cryptocurrencies. *Finance Research Letters* 49, 103155. https://doi.org/10.1016/j.frl.2022.103155 [V].
- **Brunnermeier, M. K. and Pedersen, L. H. (2005).** Predatory trading. *Journal of Finance* 60(4), 1825-1863. https://doi.org/10.1111/j.1540-6261.2005.00781.x [V].

## 6. Retail identification and nominal price

- **Boehmer, E., Jones, C. M., Zhang, X. and Zhang, X. (2021).** Tracking retail investor activity. *Journal of Finance* 76(5), 2249-2305. https://doi.org/10.1111/jofi.13033 [V].
- **Barber, B. M., Huang, X., Jorion, P., Odean, T. and Schwarz, C. (2024).** A (sub)penny for your thoughts. *Journal of Finance* 79(4), 2403-2427. https://doi.org/10.1111/jofi.13334 [V]. The subpenny method finds only 35% of known retail trades. *For us:* the model for P6.
- **Lee, C. M. C. and Radhakrishna, B. (2000).** Inferring investor behavior: Evidence from TORQ data. *Journal of Financial Markets* 3(2), 83-111 [V; cutoffs U].
- **Cready, W. M., Kumas, A. and Subasi, M. (2014).** Are trade size-based inferences about traders reliable? *Journal of Accounting Research* 52(4), 877-909 [U, author order and pages per citation checker]. Small trades contain much institutional flow.
- **Cong, L. W., Li, X., Tang, K. and Yang, Y. (2023).** Crypto wash trading. *Management Science* 69(11), 6427-6454. https://doi.org/10.1287/mnsc.2021.02709 [V]. Round-size clustering as a human signature.
- **Shue, K. and Townsend, R. R. (2021).** Can the market multiply and divide? *Journal of Finance* 76(5), 2307-2357. https://doi.org/10.1111/jofi.13059 [V].
- **Birru, J. and Wang, B. (2016).** Nominal price illusion. *Journal of Financial Economics* 119(3), 578-598. https://doi.org/10.1016/j.jfineco.2016.01.027 [V].
- **Weld, W. C., Michaely, R., Thaler, R. H. and Benartzi, S. (2009).** The nominal share price puzzle. *Journal of Economic Perspectives* 23(2), 121-142. https://doi.org/10.1257/jep.23.2.121 [V].
- **Baker, M., Greenwood, R. and Wurgler, J. (2009).** Catering through nominal share prices. *Journal of Finance* 64(6), 2559-2590 [V].
- **Green, T. C. and Hwang, B.-H. (2009).** Price-based return comovement. *Journal of Financial Economics* 93(1), 37-50 [V].
- **Aloosh, A. and Ouzan, S. (2020).** The psychology of cryptocurrency prices. *Finance Research Letters* 33 (article number U) [V].
- **Garcia Londono, A. and Alonso Diaz, S. (2024).** Small price bias in the cryptocurrency market. *Finance Research Letters* 69 [V].
- **Hu, B., McInish, T., Miller, J. and Zeng, L. (2019).** Intraday price behavior of cryptocurrencies. *Finance Research Letters* 28, 337-342 [V]. Round-number clustering is not automatically human.
- **Binance (2025).** What is an RPI order? Support FAQ, published 2025-11-17. https://www.binance.com/en/support/faq/detail/92c83c53173947c4a44f9a7277c3b9ce [V, title and date confirmed live]. RPI orders fill only against website or app orders, never API orders.

*What it means:* the default answer to "is small-trade share retail?" is "unknown, probably not" (82% of 1000PEPEUSDT fill rows under 100 USDT on one day). P6 is the only route to a ground truth. Denomination tests are deprioritised because tick and lot rules differ 100-fold between spot PEPE and perp 1000PEPE.

## 7. Pump-and-dumps, rug pulls and manipulation

- **Kamps, J. and Kleinberg, B. (2018).** To the moon: Defining and detecting cryptocurrency pump-and-dumps. *Crime Science* 7, 18. https://doi.org/10.1186/s40163-018-0093-5 [V].
- **Xu, J. and Livshits, B. (2019).** The anatomy of a cryptocurrency pump-and-dump scheme. *28th USENIX Security Symposium*, 1609-1625. https://www.usenix.org/conference/usenixsecurity19/presentation/xu-jiahua [V].
- **La Morgia, M., Mei, A., Sassi, F. and Stefa, J. (2020).** Pump and dumps in the Bitcoin era. *ICCCN 2020*. https://doi.org/10.1109/ICCCN49398.2020.9209660 [V]; public dataset (MIT): 1,110 Telegram pumps 2017-07-05 to 2021-01-18, 520 on Binance, no memecoins.
- **La Morgia, M., Mei, A., Sassi, F. and Stefa, J. (2023).** The Doge of Wall Street. *ACM Transactions on Internet Technology* 23(1), 11. https://doi.org/10.1145/3561300 [V]. Rush-order detector, F1 94.5% in 25 seconds.
- **Hamrick, J. T., Rouhi, F., Mukherjee, A., Feder, A., Gandal, N., Moore, T. and Vasek, M. (2021).** An examination of the cryptocurrency pump-and-dump ecosystem. *Information Processing and Management* 58(4), 102506. https://doi.org/10.1016/j.ipm.2021.102506 [V]. Price effects modest and shrinking.
- **Dhawan, A. and Putnins, T. J. (2023).** A new wolf in town? Pump-and-dump manipulation in cryptocurrency markets. *Review of Finance* 27(3), 935-975. https://doi.org/10.1093/rof/rfac051 [V]. Participants knowingly join; gambling and overconfidence.
- **Li, T., Shin, D. and Wang, B. (2025).** Cryptocurrency pump-and-dump schemes. *JFQA*, published online 4 April 2025. https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/abs/cryptocurrency-pumpanddump-schemes/97149DCD519BAF838F269F98DC76D682 [V; DOI and volume to add]. Fast reversals; Bittrex ban as natural experiment.
- **Hu, S., Zhang, Z., Lu, S., He, B. and Li, Z. (2023).** Sequence-based target coin prediction for cryptocurrency pump-and-dump. SIGMOD 2023; arXiv 2204.12929 [V repo; DOI U]. 709 pumps 2019-2022; repository has no licence.
- **Gandal, N., Hamrick, J. T., Moore, T. and Oberman, T. (2018).** Price manipulation in the Bitcoin ecosystem. *Journal of Monetary Economics* 95, 86-96. https://doi.org/10.1016/j.jmoneco.2017.12.004 [V per citation checker].
- **Griffin, J. M. and Shams, A. (2020).** Is Bitcoin really untethered? *Journal of Finance* 75(4), 1913-1964. https://doi.org/10.1111/jofi.12903 [V per citation checker].
- **Mirtaheri, M., Abu-El-Haija, S., Morstatter, F., Ver Steeg, G. and Galstyan, A. (2021).** Identifying and analyzing cryptocurrency manipulations in social media. *IEEE Trans. Computational Social Systems* 8(3), 607-617 [U].
- **Felez-Vinas, E., Johnson, L. and Putnins, T. J. (2022, revised 2025).** Insider trading in cryptocurrency markets. SSRN 4184367. https://doi.org/10.2139/ssrn.4184367 [V]. Pre-listing insider trading in an estimated 28% to 48% of listings. *For us:* the prior for P5.

## 8. Memecoin market structure (launchpads, bots, listings, perps)

Launchpad and token-death evidence:
- **Cernera, F., La Morgia, M., Mei, A. and Sassi, F. (2023).** Token spammers, rug pulls, and sniper bots. *32nd USENIX Security Symposium*, 3349-3366. https://www.usenix.org/conference/usenixsecurity23/presentation/cernera [V]. About 60% of tokens live under a day; 1% of addresses create 20% to 25% of tokens; about $240M to 1-day rug-pull organisers.
- **Xia, P. et al. (2021).** Trade or trick? Detecting and characterizing scam tokens on Uniswap. *Proc. ACM Meas. Anal. Comput. Syst.* 5(3), 39. arXiv 2109.00229 [V].
- **Mazorra, B., Adan, V. and Daza, V. (2022).** Do not rug on me. *Mathematics* 10(6), 949. https://doi.org/10.3390/math10060949 [V]. Warning on extreme class imbalance.
- **Feder, A., Gandal, N., Hamrick, J. T., Moore, T. and Vasek, M. (2018).** The rise and fall of cryptocurrencies. WEIS 2018 [V per citation checker]. Standard coin-death definition, used in the repo's HIP-1 draft.
- **Mongardini, A. M. and Mei, A. (2025).** A midsummer meme's dream: Investigating market manipulations in the meme coin ecosystem. arXiv 2507.01963 [V as preprint; "to appear, USENIX Security 2026" U]. 34,988 tokens on 4 chains; about 82.6% to 82.9% of 100%+ return tokens show artificial growth; replication package on Zenodo 15697524.
- **Meme Coin Factories: Uncovering large-scale manipulations on pump.fun (2026).** arXiv 2609.10246 [U: authors and CCS 2026 venue unverified]. Full-history census of about 15M pump.fun coins; five manipulation classes.
- **Marino, G., Naviglio, M., Tarantelli, F. and Lillo, F. (2026).** Predicting the success of new crypto-tokens: The Pump.fun case. arXiv 2602.14860 [U: author order and SSRN 6543715]. Graduation conditioned on curve SOL; early top-trader uplift at most modest.
- **Mancino, D. (2025).** The memecoin phenomenon. arXiv 2512.11850 [U venue]. Pump.fun up to 71.1% of Solana token mints in Q4 2024; under 2% graduate.
- **Hu, S., Tekin, S. F., Xu, Y., Liu, L. et al. (2026).** MemeTrans. arXiv 2602.13480 [U]. About 41k migrated launches; bundled accounts hold 36.5% of supply.
- **Li, J. et al. (2026).** Catching the rug. arXiv 2608.20271 [U].
- **Chen, J., Li, Z. et al. (2026).** From hype to collapse: Investigating rug pull scams on Solana. arXiv 2603.24625 [U].
- **Kamat, A. U. (2026).** Coordinated sniper cohorts on Pump.fun. arXiv 2607.02795 [U; corrigenda and partial withdrawals]. Lift +6.3% [-0.5, +15.1], not distinguishable from zero. A cautionary example.
- **Gafarov, F. (2026).** Retrospective analysis of team-following trading profitability in Pump.fun meme coins. arXiv 2611.11436 [U]. Apparent edge is look-ahead; 3 of 40 nulls reject after Holm.
- **Ding, Lin, Luo and Xu (2025).** Decompose market manipulation strategies: Evidence from on-chain meme coin market. SSRN 5953738. https://papers.ssrn.com/abstract=5953738 [U: first names; repo ref [12] in `research/novelty/insider_trading_detection.md`].

Bots and MEV:
- **Gerzon et al. (2025).** Quantifying the threat of sandwiching MEV on Jito. ACM IMC '25. DOI 10.1145/3730567.3764493 [U: full author list and DOI]. More than 500K sandwiches, over $7.7M victim losses in four months.
- **No place to hide: An analysis on protected order flow sandwich attacks (2026).** arXiv 2609.28115 [U: authors].
- **Daian, P. et al. (2020).** Flash Boys 2.0. IEEE S&P 2020; **Qin, K., Zhou, L. and Gervais, A. (2022).** Quantifying blockchain extractable value. IEEE S&P 2022 [U, added by citation checker].

Listings and perpetuals:
- **Ante, L. (2019).** Market reaction to exchange listings of cryptocurrencies. Blockchain Research Lab WP 3; SSRN 3450301. https://doi.org/10.2139/ssrn.3450301 [V].
- **Ruan, Q. and Streltsov, A.** Perpetual futures contracts and cryptocurrency market quality. Working paper, SSRN 4218907 (the id already in the repo; a second id 5323703 is U). https://qihongruan.github.io/papers/perpetuals_revision_v3-27.pdf [V]. 95 staggered perp introductions: more spot volume, wider spreads, more wash trading. *For us:* design template for P2 and P5.
- **Galati, L. and Perdichizzi, S. (2025).** From zero to hero: Memecoins' spillover effects in cryptocurrency markets. *Economics Letters* 253, 112381. https://doi.org/10.1016/j.econlet.2025.112381 [V].
- **Nieweglowski, I., Yaish, A., Saleh, F. and Zhang, F. (2025).** PoliFi tokens and the Trump effect. arXiv 2512.06036 [V as preprint, work in progress]. $TRUMP and $MELANIA prices co-move with approval ratings.
- **Schmeling, M., Schrimpf, A. and Todorov, K. (2023).** Crypto carry. BIS Working Paper 1087 [U]. Funding driven by retail demand for leveraged longs; predicts crashes. *For us:* the closest prior for P3.
- **He, S., Manela, A., Ross, O. and von Wachter, V. (2022).** Fundamentals of perpetual futures. arXiv 2212.06888 [U].
- **Soska, K. et al. (2021).** Towards understanding cryptocurrency derivatives: A case study of BitMEX. WWW 2021 [U].
- **Sockin, M. and Xiong, W. (2023).** A model of cryptocurrencies. *Management Science* 69(11); **Cong, L. W., Li, Y. and Wang, N. (2021).** Tokenomics. *Review of Financial Studies* 34(3), 1105-1155 [U page ranges]. Theory of valuing tokens with no cash flows.
- **Makarov, I. and Schoar, A. (2020).** Trading and arbitrage in cryptocurrency markets. *Journal of Financial Economics* 135(2), 293-319. https://doi.org/10.1016/j.jfineco.2019.07.001 [V per citation checker].

Industry sources [I], cite only as estimates:
- CoinGecko research on pump.fun wallet profitability (profitable share under 50% in most months from April 2024; 30.1% in June 2025; 56.8% to 73.3% in February to April 2026 after active wallets fell from 5.2M to 1.8M). Realised PnL only, bots not filtered, survivorship.
- Nansen $TRUMP figures as reported by the press: about 989,000 of 1.48M buyer wallets at a loss, about $3.8B in realised plus unrealised losses.
- Galaxy Research coverage (Cointelegraph): https://cointelegraph.com/news/memecoins-attract-users-platforms-reap-profits-report. Pump.fun about $120M fees in 30 days; original report not read, author attribution U.
- The Block (2025-02-19) on LIBRA losses via Nansen, and (2025-02-18) on Bubblemaps' TRUMP early wallet; already referenced in the repo's novelty notes.

*What it means:* the launch layer (creators, snipers, MEV) is where most memecoin value is extracted, but free reproducible Solana data is not reachable here. The repo's realistic contribution is the exchange-listed layer (P2, P3, P5) and Hyperliquid wallets (P4), with the launch layer reached only through the existing HIP-1 census.

## Still to check once hosts are allowed

All [U] entries; the exact Gao-Lin and Dorn-Dorn-Sengmueller specifications; the Baker et al. journal version; Binance's official definition of "top trader" (developers.binance.com); whether any academic paper already uses Binance long/short ratio columns (none located, but no search was possible).
