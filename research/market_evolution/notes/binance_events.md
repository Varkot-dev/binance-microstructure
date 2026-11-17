# Binance USDT-M futures market-structure events, 2023 to 2026

Research date: 2026-11-17. Tags: **[V]** verified this session at the source (for this
session that mostly means checked directly in the data.binance.vision aggTrades archive,
because binance.com and developers.binance.com could not be reached from the sandbox);
**[S]** secondary: a search-engine snippet of a binance.com page or a news report, not
opened; **[I]** inference. Dates are UTC.

## Verification pass (2026-11-17, second session)

What was checked. For a short window www.binance.com was reachable, and 34 announcements
were read in full through Binance's own JSON endpoint behind each announcement page
(`https://www.binance.com/bapi/composite/v1/public/cms/article/detail/query?articleCode=<code>`,
where `<code>` is the 32-character id at the end of each announcement URL; the human page is
`https://www.binance.com/en/support/announcement/<code>`). The full title lists of the
"Latest Binance News" (catalogId 49, 4,000 most recent titles back to 2020-04) and
"Delisting" (catalogId 161, 446 titles) categories were also downloaded from
`https://www.binance.com/bapi/composite/v1/public/cms/article/list/query?type=1&catalogId=<id>&pageNo=<n>&pageSize=50`.
After that, www.binance.com, developers.binance.com, arxiv.org and export.arxiv.org were
refused again by the network proxy (HTTP 403 on CONNECT), so about 45 further notices whose
titles were found could not be opened. "[V title]" below means the title, code and
publication time were read in Binance's own list, but the body was not. The 2024-09-20 batch
was also re-checked in the data.binance.vision archive for the five contracts not checked
before.

What changed.
- **2024-09-20 batch has 12 USDT-M contracts, not 7** [V]: APT, ASTR, JOE, KEY, XVG,
  BIGTIME, ILV, GLM, ETHFI, TURBO, ZRO, RPL (all tick cut 10x at 06:30). All 12 now verified
  in the archive (old-grid share 1.000 on 2024-09-19, 0.12 to 0.34 on 2024-09-21 for APT,
  ASTR, XVG, BIGTIME, TURBO and KEY) [V]. APTUSDT is also in the opposite-direction
  2023-02-10 batch.
- **The Taker Program did not start on 2023-10-31** [V]. "Binance Futures Launches Taker
  Program" was published 2022-07-19 [V title], with upgrades effective 2023-02-07,
  2023-05-02, 2023-08-08, 2023-10-31, 2024-01-30, 2024-04-30, 2024-07-30, 2024-10-29,
  2025-01-28 and 2025-08-12 [V title for all; body V for 2023-10-31, 2024-07-30,
  2025-01-28, 2025-08-12]. 2023-10-31 is one quarterly renewal (up to 25% taker discount,
  validity 2023-10-31 to 2024-01-29), so it is not a clean break.
- **2023-10 funding batch list corrected** [V]: the 15 contracts are IMX, LPT, API3, HIFI,
  NMR, TRB, BLZ, DODO, STMX, CYBER, YGG, UNFI, FLM, PERP, AMB (8h to 4h at 2023-10-12
  08:00; +/-3% cap from 2023-10-09 08:30 for all contracts with max leverage 25x or below).
  BIGTIME, LOOM, STRAX, ORBS, STPT, WAXP and BSV are not in this notice.
- **2023-08-29 batch took effect at 2023-08-29 06:30**, one time, not "29 to 30" [V].
- **There are far more tick-size batches than the table lists** [V title]: 67 USDT-M
  futures tick notices from 2023-01 to 2026-11 (4 in 2023, 11 in 2024, 22 in 2025, 30 in
  2026). The full list is in the appendix at the end. Inside the Q10 window (2023-06 to
  2025-07) there are at least 12 batches whose contract lists were not read (2023-06-05,
  2024-02-05, 2024-03-19, 2024-04-11, 2024-05-08, 2024-06-20, 2024-07-25, 2024-11-04,
  2024-11-28, 2025-03-25, 2025-04-17, 2025-06-12). Any of them could hit a Q10 symbol or a
  planned control.
- The "2024-06-21 06:30" batch has no notice under that date; the only notice nearby is
  titled (2024-06-20), published 2024-06-20 04:00 [V title]. Date corrected to 2024-06-20,
  time unconfirmed.
- 2025-10-17 batch is BASUSDT and CLOUSDT only, both tick increases, at 07:00 [V].
- Renames: futures settlement times confirmed for MATIC (2024-09-04 09:00), RNDR
  (2024-07-16 09:00), FTM (2025-01-06 09:00) and EOS (2025-05-21 09:00) [V]. The new
  futures listing times (POL, RENDER, S, A) are in separate notices that were not opened.
  No MKR to SKY notice exists in either downloaded title list [unverified].
- RPI: "Binance Futures Launches Retail Price Improvement (RPI) Orders" was published
  2025-11-18 09:00 [V title]; body (start time, symbol list) not opened.
- STP mandatory from 2024-12-10 06:00 with default EXPIRE_MAKER [V]; optional API STP by
  2023-09-06 10:00 [V]. 2025-05-02 08:00 rule (1h funding after a cap/floor settlement)
  [V]. 2025-09-18 08:01 funding formula change [V]. 2025-04-02 06:00 price cap change (6
  contracts: SIREN, BROCCOLIF3B, PLUME, WAL, VIRTUAL, 1000WHY) [V].

Still unverified: the regular USDT-M fee 0.02%/0.05% (FAQ 360033544231 not reachable); the
2026-03-05 contract list (title V, body not opened; the archive check of all 12 still holds);
the RPI symbol list and start time; MKR to SKY; AGIX/OCEAN merger time; the initial USDC-M
symbol list; XAU/XAG funding change; the 2026-08-13 REST lookback change; and every
developers.binance.com claim (aggTrade definition, RPI fields).

## Summary

The most useful exchange-side events for a natural experiment are **tick-size (price
filter) changes**. Binance announces them in batches of 2 to 12 contracts
("Updates on Tick Size for Multiple USDⓈ-M Perpetual Futures Contracts (date)"), they take
effect at a stated minute (06:30 UTC up to late 2024, 07:00 UTC in 2025 and 2026, with
06:30 again in some 2026 notices), and they are directly visible in aggTrades prices. Five
batches were checked in the archive this session and all match: a 10x change in the price
grid appears within the stated half hour. Resting orders keep the old tick, so about
10% of trades still print on the old grid for a day or more after an increase. Funding
interval changes (8h to 4h, or 1h after cap hits) also affect named subsets, but they do not
show up in aggTrades directly. Fee changes in 2023 to 2026 were nearly all promotions
(USDC-M zero maker, Taker Program, LP program) that apply to the whole market or to whole
margin assets, so they make poor treated/control splits. Data format: futures aggTrades
archives are still in **milliseconds** (checked on 2026-10-01); only spot moved to
microseconds (from 2025-01-01). Fees: the regular USDT-M fee is **0.02% maker, 0.05% taker**
[S] (Binance FAQ 360033544231 worked examples), which matches the repo's assumption;
paying in BNB gives 10% off [S].

**Answer to the SOLUSDT lead.** SOLUSDT (and SOLUSDC) went from tick 0.001 to 0.01 on
**2024-10-14 at 06:30 UTC** ("Updates on Tick Size for SOL USDⓈ-M and COIN-M Futures
Contracts (2024-10-14)", https://www.binance.com/en/support/announcement/8bfe2e9b86734cd08f3cbcdb82b79f51) [V for the announcement, V for the date and minute in the data:
share of SOLUSDT trades on the 0.01 grid is 0.11 in every half hour up to 06:00 and 0.86 from
06:30]. The announcement title names only SOL (USDⓈ-M SOLUSDT, SOLUSDC plus COIN-M), so
there is no wider treated group in that announcement [V]. The doubling of trades per
aggTrade record for SOL is a **step at exactly this date** [V]: trades per record were 2.5
to 2.7 on 2024-10-08 to 2024-10-12 and 5.2 to 5.3 on 2024-10-16 to 2024-10-20 (computed from
first_trade_id and agg_trade_id differences between consecutive daily files). That is
mechanical [I]: aggTrades merge fills of one taker order at one price, so a 10x coarser grid
puts more maker orders at each level, and a sweep crosses fewer levels (hence also fewer
records sharing one millisecond). For **DOGEUSDT** there is no step: trades per record drift
from about 4 (2023) to about 6 (2025 to 2026) with no tick change [V], so DOGE's rise is a
gradual behavioural change (more, smaller resting orders per level), not an aggregation rule
change. No Binance change to aggTrade aggregation rules was found for 2023 to 2026; the
documented rule is still "fills of the same taker order at the same price, market trades
only (insurance fund and ADL trades excluded)" [S]. One caveat [S]: since RPI orders
(2025-11) the docs say RPI fills are included in aggTrades without a tag (the REST response
has an extra quantity field excluding RPI; the archive CSV still has the same 7 columns [V]).

## Event table

| date (UTC) | contracts | change | measurable in aggTrades? | source | tag |
|---|---|---|---|---|---|
| 2023-02-10 06:30 | APTUSDT, OCEANUSDT (plus APTBUSD; COIN-M APTUSD, DOGEUSD, ADAUSD, BNBUSD) | tick increased 10x (APT 0.0001 to 0.001, OCEAN 0.00001 to 0.0001); trades on new grid 0.12 to 0.97 (APT), 0.11 to 0.98 (OCEAN), day before vs day after | yes, price grid | binance.com/en/support/announcement/updates-on-tick-size-for-multiple-usd%E2%93%A2-m-and-coin-m-perpetual-futures-contracts-2023-02-03-98315efae83841a2bb71046d4bbae204 (notice dated 2023-02-03, effective 2023-02-10 06:30) | [V] list and time, [V] data |
| 2023-08-29 06:30 | AMBUSDT, HOOKUSDT, API3USDT, TRBUSDT, DODOXUSDT | tick cut 10x (e.g. TRB 0.01 to 0.001, API3 0.001 to 0.0001); distinct prices per day up 3x to 15x | yes | binance.com/en/support/announcement/updates-on-tick-size-for-multiple-usd%E2%93%A2-m-perpetual-futures-contracts-2023-08-29-8764f0d84e6b4c7abc97f036bb6f9ebc | [V] list and time (published 2023-08-23), [V] data for 4 of 5 (DODOX not checked) |
| 2023-08-13 10:30 | LPTUSDT | funding every 8h to every 4h | no (funding only) | binance.com/en/support/announcement/detail/ed3c7b7e35b546aeab635cb4a5b3ee80 | [V] (also cap multiplier 0.75 to 1, cap +/-2.5%) |
| 2023-09-06 10:00 | all USDT-M (API orders) | Self-Trade Prevention launched for USDⓈ-M via API (optional modes incl. EXPIRE_TAKER) | weakly (fewer self-matches) | binance.com/en-AE/support/announcement/binance-futures-launches-self-trade-prevention-stp-function-for-usd%E2%93%A2-margined-futures-on-api-32916877372243d69154c345200e34b8 | [V] (optional, API only, by 2023-09-06 10:00) |
| 2023-10-09 08:30 (cap) and 2023-10-12 08:00 (interval) | 15 contracts: IMX, LPT, API3, HIFI, NMR, TRB, BLZ, DODO, STMX, CYBER, YGG, UNFI, FLM, PERP, AMB (corrected; earlier snippet lists added BIGTIME, LOOM, STRAX, ORBS, STPT, WAXP, BSV, which are not in this notice) | funding 8h to 4h; funding cap raised to +/-3% for all contracts with max leverage 25x or below | no | binance.com/en/support/announcement/98d6b24d3e5c4f84a8ed04087997d8d0 (published 2023-09-28) | [V] list and times; still check against fundingRate archive |
| 2023-12-11 | last 4 BUSD-M perps (BTCBUSD, ETHBUSD, BNBBUSD, XRPBUSD) | BUSD-margined perps closed (last archive day 2023-12-11); BUSD removed from Multi-Assets at 2023-12-11 10:00 | indirectly (flow to USDT twins) | binance.com/en/support/announcement/d980d81501594f80b2903cdfe29f1166 | [V] archive last day; [V] notice: margin tiers cut 2023-11-24 14:00, BTCBUSD and ETHBUSD settled 2023-12-11 (05:30 close-only, 06:00 settlement); Multi-Assets time [S] |
| 2024-01-03 12:30 | BTC, ETH, BNB, SOL, XRP USDC-M perps | USDC-M perpetuals launched with promotional fees (0% maker); later extended to many symbols | indirectly (competing venue) | coingape report of Binance 2023-12-28 notice; the LP notice https://www.binance.com/en/support/announcement/f5d3200b65104308b8349cee59a2296e confirms USDC-margined contracts from 2024-01-03 12:30 | [V] date and time, [S] symbol list |
| 2024-01-03 | all USDT-M | USDⓈ-M Liquidity Provider Program upgraded | no | binance.com/en/support/announcement/detail/f5d3200b65104308b8349cee59a2296e | [V] (maker rebates -0.003% to -0.005% USDT-M by tier) |
| 2024-04-03 12:30 | USDC-M perps | limited-time USDC-M fee discount (0% maker, 0.017% taker in the first round), renewed repeatedly; the 2025-12-10 08:00 update runs "until further notice" (regular user 0% maker, 0.04% taker) | no | binance.com/en/support/announcement/fc7732cf48cd49cf95e53aa479ed4deb ; .../03180947641b414ebcb9a6c407fe80e2 | [V] |
| 2024-06-20 (corrected from 06-21; time not confirmed) | several USDT-M perps (list not read) | tick size update | yes | https://www.binance.com/en/support/announcement/50df6c9af8f14d09937a01956779d2a3 (published 2024-06-20 04:00) | [V title], list [unverified]: body not opened |
| 2024-06-25 | AGIXUSDT, OCEANUSDT (FETUSDT kept, became ASI) | ASI merger: AGIX and OCEAN settled and delisted (last archive day 2024-06-25) | contract ends | blockchain.news, beincrypto; Binance page not reached | [V] archive dates, [S] time (09:00 vs 12:00 disputed) |
| 2024-07-16 09:00 / 2024-07-26 10:00 | RNDRUSDT to RENDERUSDT | rename: RNDR settled 07-16, RENDER listed 07-26 (4h funding, +/-2% cap) | new symbol, 10-day gap | binance.com/en/support/announcement/d1f2ae8d99b24439a7a900caa9bb6b3b | [V] archive dates; [V] RNDRUSDT settlement 2024-07-16 09:00; RENDERUSDT listing time [S] (separate notice) |
| 2024-07-30 00:00 | USDT-M and USDC-M | Taker Program update (taker discounts up to 20%, tiers 10/15/20%); further updates 2025-01-28 00:00 (up to 20%) and 2025-08-12 07:00 (tiers 10/14/18%, lower thresholds). The program itself launched 2022-07-19 and is renewed roughly quarterly | no | binance.com/en/support/announcement/detail/612bf21438b34bdb825cf56d2c9c7554 ; https://www.binance.com/en/support/announcement/1d115917f1e24f83b93c8adfc41708ef ; https://www.binance.com/en/support/announcement/bec831262e4b4a49b021e6f4030921be | [V] |
| 2024-09-04 09:00 / 2024-09-13 | MATICUSDT to POLUSDT | rename: MATIC settled 09-04, POL listed (Binance tweet 2024-09-12 or 13 at 12:15; first archive day 2024-09-13) | new symbol, 9-day gap | binance.com/en/support/articles/6a6de383727f4659a3050f7982e1620f | [V] archive dates; [V] MATICUSDT and MATICUSDC settlement 2024-09-04 09:00 (new positions blocked from 08:30); POLUSDT listing time [S] |
| 2024-09-20 06:30 | 12 contracts (corrected from 7): APTUSDT, ASTRUSDT, JOEUSDT, KEYUSDT, XVGUSDT, BIGTIMEUSDT, ILVUSDT, GLMUSDT, ETHFIUSDT, TURBOUSDT, ZROUSDT, RPLUSDT | tick cut 10x; JOE switch at 06:30 [V]; distinct prices up 6x to 26x (first 7), 3x to 16x (APT, ASTR, XVG, BIGTIME, TURBO) | yes | binance.com/en-AE/support/announcement/detail/fa192e78242d4d96be9562ab7d76a10a (published 2024-09-19 02:00; APT row amended same day) | [V] list and time, [V] data for all 12 |
| 2024-10-14 06:30 | SOLUSDT, SOLUSDC (+ COIN-M) | tick increased 0.001 to 0.01; trades per aggTrade 2.6 to 5.2 | yes, strongly | binance.com/en/support/announcement/8bfe2e9b86734cd08f3cbcdb82b79f51 (published 2024-10-01) | [V] announcement, [V] data |
| 2024-11-04 and 2024-11-28 | several USDT-M perps (lists not read) | tick size updates | yes | https://www.binance.com/en/support/announcement/f9baa987cd944e75b3e06c297bca05f7 ; https://www.binance.com/en/support/announcement/8a4a0a76026a472b841162860d10d8cd | [V title], lists [unverified]: bodies not opened |
| 2024-11-29 | 1000WHYUSDT, 1000CHEEMSUSDT | tick 0.00001 to 0.000001 (snippet says 0.000001 to 0.0000001; the data show the former) | yes | https://www.binance.com/en/support/announcement/0d330d9e556e44c68dacbc902306c907 (published 2024-11-29 05:00) | [V title], [V] data; tick values in notice not read |
| 2024-12-10 | all futures | STP mandatory for all users from 06:00 (rollout about 24h), default EXPIRE_MAKER; STP NONE rejected; self-trades can still occur between pre- and post-change orders | yes, self-trades vanish (market-wide, no control group) | binance.com/en/support/announcement/detail/7803d494fa654f749fbc0a22a17372e3 | [V] |
| 2025-01-01 | spot only | spot archive timestamps in microseconds; futures stay in ms | futures unaffected (checked 2026-10-01 file: 13-digit ms) | github.com/binance/binance-public-data README | [V] |
| 2025-01-06 09:00 / 2025-01-16 | FTMUSDT to SUSDT | rename: FTM settled 01-06; SUSDT first archive day 2025-01-16 (SONICUSDT, listed 2025-01-08, is a different project) | new symbol, 10-day gap | binance.com/en/support/announcement/aec6fcbc84b749eeab6690e6bcac2f3d | [V] archive dates; [V] FTMUSDT settlement 2025-01-06 09:00 |
| 2025 (various) | contracts hitting the funding cap | rule: funding interval auto-shortened to 1h after a cap/floor settlement, without announcement; e.g. 2025-05-02 batch, 2025-07-22 five contracts back to 4h | no | binance.com/en/support/announcement/3243c81a35bd4f0c86a37315c3dc96cc | [V] rule (effective 2025-05-02 08:00: after a settlement at the cap/floor, 8h or 4h becomes 1h); 2025-07-22 example [S] |
| 2025-04-02 06:00 | SIRENUSDT, BROCCOLIF3BUSDT, PLUMEUSDT, WALUSDT, VIRTUALUSDT, 1000WHYUSDT | order price cap/floor ratio 15% to 50% (limit and market) | weakly (extreme prints) | binance.com/en/support/announcement/7bc0d0e0625a46e2995181ef8408d765 | [V] |
| 2025-05-21 09:00 / 2025-05-28 08:00 | EOSUSDT to AUSDT (Vaulta) | rename: EOS settled 05-21, A listed 05-28 (4h funding) | new symbol, 7-day gap | binance.com/en/support/announcement/1e89a9ca957c4b0ca7502e60b993e201 | [V] archive dates; [V] EOSUSDT settlement 2025-05-21 09:00; AUSDT futures listing time [S] |
| 2025-09-08 / 2025-09-09 | MKRUSDT to SKYUSDT | rename (1 MKR = 24,000 SKY): last MKR archive day 09-08, first SKY 09-09; Binance notice not found (no MKR or SKY swap title in the 4,000 latest "Latest Binance News" titles or the Delisting list) | new symbol, also a price-scale change | archive only | [V] archive dates; announcement [unverified]: not found |
| 2025-09-19 07:00 | AVNTUSDT, SUIUSDC and others | tick increased (AVNT 0.00001 to 0.0001) | yes | binance.com/en/square/post/09-17-2025-binance-to-adjust-tick-size-for-usd-m-perpetual-futures-contracts-29789849203537 ; official notice https://www.binance.com/en/support/announcement/01535c3f5c7842189883d4108efdd055 (published 2025-09-17 02:00) | [V title], list [S] |
| 2025-09-18 08:01 | all perps | funding formula rescaled by funding interval (F = [P + clamp(0.01% - P, 0.05%, -0.05%)] / (8/N)) and mark price calculation update | no | binance.com/en-AE/support/announcement/detail/c00588a7e8504b3eb28d02a2da00530b | [V] |
| 2025-10-17, 2025-10-27, 2025-12-08, 2025-12-15, 2025-12-22 (07:00) | 10-17: BASUSDT, CLOUSDT only (both increases) [V]; 10-27: EVAAUSDT, XPINUSDT, TACUSDT [S]; 12-15: KERNEL, LINEA, BERA, SONIC, WCT, ZETA, MANTA (all cuts) [V]; 12-22: USELESS, NOM, EVAA, SLP, WAXP, POWR, SCR, AT, VTHO, VANRY, STABLE (all cuts) [V]; 12-08 list not read | tick changes | yes | binance.com/en-AE/support/announcement/detail/fd11627dc39046b791b7504a2f08e3fc ; .../baee5eb8aa8447c0810512b9da108f0a ; .../1cd08ee9bafd40a2a94e8dfc58408f82 ; 10-27: https://www.binance.com/en/support/announcement/f9dd6ab751f3499cb88f236549c8ef23 ; 12-08: https://www.binance.com/en/support/announcement/d9d73edb19864da1b1b25393f8263513 | [V] for 10-17, 12-15, 12-22 (all 07:00); [V title] for 10-27 and 12-08 |
| 2025-11-18 (API) / 2025-11-20 (launch) | selected USDT-M symbols (permissionSets contains RPI; list not found) | RPI (Retail Price Improvement) orders: post-only, match only against web/app (non-API) takers, filled after non-RPI at same price, hidden from standard depth; separate rpiDepth (2025-11-25); own RPI fee | partly: RPI fills are in aggTrades untagged | official notice "Binance Futures Launches Retail Price Improvement (RPI) Orders", https://www.binance.com/en/support/announcement/d0ed1c8add7848c8b3e5a87bbabf6300 (published 2025-11-18 09:00); developers.binance.com change log (via GitHub issue nautechsystems/nautilus_trader#4805); chaincatcher report | [V title, publication 2025-11-18]; start date 2025-11-20, mechanics and symbol list [S]: body not opened |
| 2026-01 | XAUUSDT, XAGUSDT | funding 4h to 8h | no | search snippet | [S] |
| 2026-03-05 07:00 | MYXUSDT, GRIFFAINUSDT, 4USDT, AUSDT, MIRAUSDT, SCRTUSDT, HEIUSDT, DRIFTUSDT, ZKCUSDT, A2ZUSDT, LAYERUSDT, LISTAUSDT | tick cut 10x on 12 cheap contracts (relative tick before about 10 to 13 bps); MYX switch at 07:00 [V]; distinct prices up 5x to 12x | yes, strongly | official notice "Updates on Tick Size for Multiple USDⓈ-M Perpetual Futures Contracts (2026-03-05)", https://www.binance.com/en/support/announcement/f0e08ccaf57d4cc8a719b67337706763 (published 2026-03-02 06:00); bloomingbit report | [V title and date], list [S] (body not opened), [V] data for all 12 |
| 2026-04-28 | BOBUSDT | last archive day (1000000BOBUSDT trades from 2025-06) | contract ends | archive | [V] |
| 2026-06-04, 2026-06-08 06:30; 2026-08-06 06:30; 2026-10-15 06:30; 2026-10-22 06:30 | 08-06: MOVE, COOKIE, AVNT, ZK, MAV, CKB, VANA, AXS (all cuts) [V]; 10-15: APR, XPIN, ROBO, BEAT, RUM, FLNC, CSOPSAMSUNG2L (all cuts) [V]; 10-22: BILL, IDOL, ESPORTS (cuts), BR, AGT (increases) [V]; 06-04/06-08 list not read | tick changes | yes | https://www.binance.com/en/support/announcement/be5c80d75197412b86d0faa1c5efd146 ; https://www.binance.com/en/support/announcement/7157d432816e455dbf9fe7f3e452b0cf ; https://www.binance.com/en/support/announcement/84b9812b7a88404baedec318c5d60b37 ; https://www.binance.com/en/support/announcement/fcf3698a42104ba2b52e5c475d155321 | [V] for 08-06, 10-15, 10-22; [V title] for 06-04/06-08 |
| 2026-08-13 | all | REST /fapi/v1/aggTrades lookback 24h to 48h | no (API only) | developers.binance.com change log | [S] |

Notes on the table:
- "Distinct prices" and grid shares come from scripts run on daily archive files the day
  before and after; the method (share of trades whose price is a multiple of each power of
  ten, and the gcd of all prices) is reusable for any symbol.
- No change of contract multiplier on an existing symbol (for example PEPEUSDT to
  1000PEPEUSDT) was found in 2023 to 2026: 1000x and 1000000x contracts (1000PEPEUSDT from
  2023-05-05, 1000BONKUSDT 2023-11, 1MBABYDOGEUSDT 2024-09, 1000000MOGUSDT 2024-11,
  1000000BOBUSDT 2025-06) were new listings [V archive dates]. The one rescaling found was
  BITOUSDT (contract size change after a 1:2 reverse split, date and year unclear) [S].
- No reduction of the default order rate limit (300 orders per 10 s, 1,200 per minute) was
  found for 2023 to 2026 [S].
- Minimum order size (lot) changes were not found as separate announcements; they are
  usually bundled into tick notices or listings [I].

## Best natural experiments (ranked)

1. **2026-03-05 07:00 tick cut on 12 contracts.** Largest verified treated group in one
   minute, all with the same 10x cut, all cheap coins with relative tick of about 10 to 13
   bps, so the treatment is big. Controls: other low-price USDT perps with similar relative
   tick and volume that were not in the list. Clean prediction from Q4b/Q8: sign
   predictability and trades per aggTrade should fall for treated coins. Caveat: these are
   weak coins (selection on price decline), so match controls on price trend.
2. **2024-09-20 06:30 tick cut on 7 contracts** (JOE, KEY, ILV, GLM, ETHFI, ZRO, RPL), 6
   verified in data. Mid-sized coins, a year before the March 2026 batch, so it gives an
   independent replication in a different market regime.
3. **2024-10-14 06:30 SOLUSDT tick increase.** Only one treated contract, but a large liquid
   one, inside the Q10 panel, with an opposite-sign treatment (coarser grid). It already
   explains SOL's jump in trades per aggTrade (2.6 to 5.2) and must be controlled for in the
   Q10 panel; as an event study use the other 9 Q10 symbols, whose ticks did not change, as
   controls (single treated unit, so use synthetic control or permutation inference).
4. **2023-08-29 tick cut (5 contracts) and 2023-02-10 tick increase (APT, OCEAN).** Small
   groups but early in the sample, giving opposite-direction treatments before the 2025
   rise; pooling all verified batches (about 30 contracts, both directions) into one stacked
   event study is the strongest design.
5. **Funding interval switches (2023-10 batches, 8h to 4h).** Clear dates and a named subset
   of about 15 to 20 small caps, but the treatment acts on funding, not on the trading
   mechanism, so it is a placebo-style test: predictability should not change. Verify the
   lists from the archive's fundingRate files before use.

Not recommended: fee promotions (market-wide or USDC-only), STP default (market-wide, no
controls), RPI (symbol list not found; untagged in aggTrades, but worth a second look if the
eligible list can be recovered from exchangeInfo permissionSets), and renames (a new symbol
after a 7 to 10 day gap is a different market, not a treatment).

Sources that could not be opened this session: www.binance.com and developers.binance.com
(blocked by the sandbox network); allowing them would turn most [S] rows into [V].
