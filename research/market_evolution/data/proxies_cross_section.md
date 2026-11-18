# Order-flow proxies on the Q14 cross-sections (`proxies_cross_section.parquet`)

Built by `research/market_evolution/e2_proxies_cross_section.py`. One row per Q14 unit: `set`, `symbol`, `period`, `status` (ok or failed, with `reason`), Q14's status label (`q14_status`), the Q14 metrics (`q14_gbm_all`, `q14_linear`, `q14_persistence`, `q14_majority`, `q14_lift`, `q14_log10_events`, `q14_n_events`, from `results/q14_survivorship.json`), the lifecycle status of the life trading in that month (`lifecycle_*`, from `contract_lifecycle.csv`), and every proxy of `contract_month_proxies` (definitions in `microstructure.evolution.proxies.PROXY_DOCS`) plus `n_raw`. The near-circular proxies `sign_repeat_rate`, `sign_acf_lag1` are kept under those names; they are nearly the outcome and are descriptive only.

## Coverage

| set | units | ok | failed | local Q9 parquet | downloaded |
|---|---|---|---|---|---|
| cross_2023 | 181 | 5 | 176 | 1 | 4 |
| cross_2026 | 251 | 0 | 251 | 0 | 0 |

By Q14 status label:

| set | q14_status | ok | not ok |
|---|---|---|---|
| cross_2023 | delisted | 0 | 33 |
| cross_2023 | merged | 0 | 2 |
| cross_2023 | renamed | 0 | 10 |
| cross_2023 | survivor | 5 | 128 |
| cross_2023 | survivor_gap | 0 | 3 |
| cross_2026 | new_listing | 0 | 113 |
| cross_2026 | survivor | 0 | 135 |
| cross_2026 | survivor_gap | 0 | 3 |

### Failures

- cross_2023 1INCHUSDT 2023-06: not_run: None
- cross_2023 AAVEUSDT 2023-06: not_run: None
- cross_2023 ACHUSDT 2023-06: not_run: None
- cross_2023 ADAUSDT 2023-06: not_run: None
- cross_2023 AGIXUSDT 2023-06: not_run: None
- cross_2023 ALGOUSDT 2023-06: not_run: None
- cross_2023 ALICEUSDT 2023-06: not_run: None
- cross_2023 ALPHAUSDT 2023-06: not_run: None
- cross_2023 AMBUSDT 2023-06: not_run: None
- cross_2023 ANKRUSDT 2023-06: not_run: None
- cross_2023 ANTUSDT 2023-06: not_run: None
- cross_2023 APEUSDT 2023-06: not_run: None
- cross_2023 API3USDT 2023-06: not_run: None
- cross_2023 APTUSDT 2023-06: not_run: None
- cross_2023 ARBUSDT 2023-06: not_run: None
- cross_2023 ARPAUSDT 2023-06: not_run: None
- cross_2023 ARUSDT 2023-06: not_run: None
- cross_2023 ASTRUSDT 2023-06: not_run: None
- cross_2023 ATAUSDT 2023-06: not_run: None
- cross_2023 ATOMUSDT 2023-06: not_run: None
- cross_2023 AUDIOUSDT 2023-06: not_run: None
- cross_2023 AVAXUSDT 2023-06: not_run: None
- cross_2023 AXSUSDT 2023-06: not_run: None
- cross_2023 BAKEUSDT 2023-06: not_run: None
- cross_2023 BALUSDT 2023-06: not_run: None
- cross_2023 BANDUSDT 2023-06: not_run: None
- cross_2023 BATUSDT 2023-06: not_run: None
- cross_2023 BCHUSDT 2023-06: not_run: None
- cross_2023 BELUSDT 2023-06: not_run: None
- cross_2023 BLURUSDT 2023-06: not_run: None
- cross_2023 BLZUSDT 2023-06: not_run: None
- cross_2023 BNBUSDT 2023-06: not_run: None
- cross_2023 BNXUSDT 2023-06: not_run: None
- cross_2023 BTCDOMUSDT 2023-06: not_run: None
- cross_2023 BTCUSDT 2023-06: not_run: None
- cross_2023 C98USDT 2023-06: not_run: None
- cross_2023 CELOUSDT 2023-06: not_run: None
- cross_2023 CELRUSDT 2023-06: not_run: None
- cross_2023 CFXUSDT 2023-06: not_run: None
- cross_2023 CHRUSDT 2023-06: not_run: None
- cross_2023 CHZUSDT 2023-06: not_run: None
- cross_2023 CKBUSDT 2023-06: not_run: None
- cross_2023 COMPUSDT 2023-06: not_run: None
- cross_2023 COTIUSDT 2023-06: not_run: None
- cross_2023 CRVUSDT 2023-06: not_run: None
- cross_2023 CTKUSDT 2023-06: not_run: None
- cross_2023 CTSIUSDT 2023-06: not_run: None
- cross_2023 CVXUSDT 2023-06: not_run: None
- cross_2023 DARUSDT 2023-06: not_run: None
- cross_2023 DASHUSDT 2023-06: not_run: None
- cross_2023 DENTUSDT 2023-06: not_run: None
- cross_2023 DGBUSDT 2023-06: not_run: None
- cross_2023 DOGEUSDT 2023-06: not_run: None
- cross_2023 DOTUSDT 2023-06: not_run: None
- cross_2023 DUSKUSDT 2023-06: not_run: None
- cross_2023 DYDXUSDT 2023-06: not_run: None
- cross_2023 EDUUSDT 2023-06: not_run: None
- cross_2023 EGLDUSDT 2023-06: not_run: None
- cross_2023 ENJUSDT 2023-06: not_run: None
- cross_2023 ENSUSDT 2023-06: not_run: None
- cross_2023 EOSUSDT 2023-06: not_run: None
- cross_2023 ETCUSDT 2023-06: not_run: None
- cross_2023 ETHUSDT 2023-06: not_run: None
- cross_2023 FETUSDT 2023-06: not_run: None
- cross_2023 FILUSDT 2023-06: not_run: None
- cross_2023 FLMUSDT 2023-06: not_run: None
- cross_2023 FLOWUSDT 2023-06: not_run: None
- cross_2023 FTMUSDT 2023-06: not_run: None
- cross_2023 FXSUSDT 2023-06: not_run: None
- cross_2023 GALAUSDT 2023-06: not_run: None
- cross_2023 GALUSDT 2023-06: not_run: None
- cross_2023 GMTUSDT 2023-06: not_run: None
- cross_2023 GMXUSDT 2023-06: not_run: None
- cross_2023 GRTUSDT 2023-06: not_run: None
- cross_2023 GTCUSDT 2023-06: not_run: None
- cross_2023 HBARUSDT 2023-06: not_run: None
- cross_2023 HFTUSDT 2023-06: not_run: None
- cross_2023 HIGHUSDT 2023-06: not_run: None
- cross_2023 HOOKUSDT 2023-06: not_run: None
- cross_2023 HOTUSDT 2023-06: not_run: None
- cross_2023 ICPUSDT 2023-06: not_run: None
- cross_2023 ICXUSDT 2023-06: not_run: None
- cross_2023 IDEXUSDT 2023-06: not_run: None
- cross_2023 IDUSDT 2023-06: not_run: None
- cross_2023 IMXUSDT 2023-06: not_run: None
- cross_2023 INJUSDT 2023-06: not_run: None
- cross_2023 IOSTUSDT 2023-06: not_run: None
- cross_2023 IOTAUSDT 2023-06: not_run: None
- cross_2023 IOTXUSDT 2023-06: not_run: None
- cross_2023 JASMYUSDT 2023-06: not_run: None
- cross_2023 JOEUSDT 2023-06: not_run: None
- cross_2023 KAVAUSDT 2023-06: not_run: None
- cross_2023 KEYUSDT 2023-06: not_run: None
- cross_2023 KLAYUSDT 2023-06: not_run: None
- cross_2023 KNCUSDT 2023-06: not_run: None
- cross_2023 KSMUSDT 2023-06: not_run: None
- cross_2023 LDOUSDT 2023-06: not_run: None
- cross_2023 LEVERUSDT 2023-06: not_run: None
- cross_2023 LINAUSDT 2023-06: not_run: None
- cross_2023 LINKUSDT 2023-06: not_run: None
- cross_2023 LITUSDT 2023-06: not_run: None
- cross_2023 LPTUSDT 2023-06: not_run: None
- cross_2023 LQTYUSDT 2023-06: not_run: None
- cross_2023 LRCUSDT 2023-06: not_run: None
- cross_2023 LTCUSDT 2023-06: not_run: None
- cross_2023 LUNA2USDT 2023-06: not_run: None
- cross_2023 MAGICUSDT 2023-06: not_run: None
- cross_2023 MANAUSDT 2023-06: not_run: None
- cross_2023 MASKUSDT 2023-06: not_run: None
- cross_2023 MATICUSDT 2023-06: not_run: None
- cross_2023 MINAUSDT 2023-06: not_run: None
- cross_2023 MKRUSDT 2023-06: not_run: None
- cross_2023 MTLUSDT 2023-06: not_run: None
- cross_2023 NEARUSDT 2023-06: not_run: None
- cross_2023 NEOUSDT 2023-06: not_run: None
- cross_2023 NKNUSDT 2023-06: not_run: None
- cross_2023 OCEANUSDT 2023-06: not_run: None
- cross_2023 OGNUSDT 2023-06: not_run: None
- cross_2023 OMGUSDT 2023-06: not_run: None
- cross_2023 ONEUSDT 2023-06: not_run: None
- cross_2023 ONTUSDT 2023-06: not_run: None
- cross_2023 OPUSDT 2023-06: not_run: None
- cross_2023 PEOPLEUSDT 2023-06: not_run: None
- cross_2023 PERPUSDT 2023-06: not_run: None
- cross_2023 PHBUSDT 2023-06: not_run: None
- cross_2023 QNTUSDT 2023-06: not_run: None
- cross_2023 QTUMUSDT 2023-06: not_run: None
- cross_2023 RADUSDT 2023-06: not_run: None
- cross_2023 RDNTUSDT 2023-06: not_run: None
- cross_2023 REEFUSDT 2023-06: not_run: None
- cross_2023 RENUSDT 2023-06: not_run: None
- cross_2023 RLCUSDT 2023-06: not_run: None
- cross_2023 RNDRUSDT 2023-06: not_run: None
- cross_2023 ROSEUSDT 2023-06: not_run: None
- cross_2023 RSRUSDT 2023-06: not_run: None
- cross_2023 RUNEUSDT 2023-06: not_run: None
- cross_2023 RVNUSDT 2023-06: not_run: None
- cross_2023 SANDUSDT 2023-06: not_run: None
- cross_2023 SFPUSDT 2023-06: not_run: None
- cross_2023 SKLUSDT 2023-06: not_run: None
- cross_2023 SNXUSDT 2023-06: not_run: None
- cross_2023 SOLUSDT 2023-06: not_run: None
- cross_2023 SPELLUSDT 2023-06: not_run: None
- cross_2023 SSVUSDT 2023-06: not_run: None
- cross_2023 STGUSDT 2023-06: not_run: None
- cross_2023 STMXUSDT 2023-06: not_run: None
- cross_2023 STORJUSDT 2023-06: not_run: None
- cross_2023 STXUSDT 2023-06: not_run: None
- cross_2023 SUIUSDT 2023-06: not_run: None
- cross_2023 SUSHIUSDT 2023-06: not_run: None
- cross_2023 SXPUSDT 2023-06: not_run: None
- cross_2023 THETAUSDT 2023-06: not_run: None
- cross_2023 TLMUSDT 2023-06: not_run: None
- cross_2023 TOMOUSDT 2023-06: not_run: None
- cross_2023 TRBUSDT 2023-06: not_run: None
- cross_2023 TRUUSDT 2023-06: not_run: None
- cross_2023 TRXUSDT 2023-06: not_run: None
- cross_2023 TUSDT 2023-06: not_run: None
- cross_2023 UMAUSDT 2023-06: not_run: None
- cross_2023 UNFIUSDT 2023-06: not_run: None
- cross_2023 UNIUSDT 2023-06: not_run: None
- cross_2023 USDCUSDT 2023-06: not_run: None
- cross_2023 VETUSDT 2023-06: not_run: None
- cross_2023 WAVESUSDT 2023-06: not_run: None
- cross_2023 WOOUSDT 2023-06: not_run: None
- cross_2023 XEMUSDT 2023-06: not_run: None
- cross_2023 XLMUSDT 2023-06: not_run: None
- cross_2023 XMRUSDT 2023-06: not_run: None
- cross_2023 XRPUSDT 2023-06: not_run: None
- cross_2023 XTZUSDT 2023-06: not_run: None
- cross_2023 XVSUSDT 2023-06: not_run: None
- cross_2023 YFIUSDT 2023-06: not_run: None
- cross_2023 ZECUSDT 2023-06: not_run: None
- cross_2023 ZENUSDT 2023-06: not_run: None
- cross_2023 ZILUSDT 2023-06: not_run: None
- cross_2023 ZRXUSDT 2023-06: not_run: None
- cross_2026 1000FLOKIUSDT 2026-07: not_run: None
- cross_2026 1000LUNCUSDT 2026-07: not_run: None
- cross_2026 1000PEPEUSDT 2026-07: not_run: None
- cross_2026 1000SHIBUSDT 2026-07: not_run: None
- cross_2026 1000XECUSDT 2026-07: not_run: None
- cross_2026 1INCHUSDT 2026-07: not_run: None
- cross_2026 AAVEUSDT 2026-07: not_run: None
- cross_2026 ACHUSDT 2026-07: not_run: None
- cross_2026 ADAUSDT 2026-07: not_run: None
- cross_2026 ALGOUSDT 2026-07: not_run: None
- cross_2026 ALICEUSDT 2026-07: not_run: None
- cross_2026 ANKRUSDT 2026-07: not_run: None
- cross_2026 APEUSDT 2026-07: not_run: None
- cross_2026 API3USDT 2026-07: not_run: None
- cross_2026 APTUSDT 2026-07: not_run: None
- cross_2026 ARBUSDT 2026-07: not_run: None
- cross_2026 ARPAUSDT 2026-07: not_run: None
- cross_2026 ARUSDT 2026-07: not_run: None
- cross_2026 ASTRUSDT 2026-07: not_run: None
- cross_2026 ATOMUSDT 2026-07: not_run: None
- cross_2026 AVAXUSDT 2026-07: not_run: None
- cross_2026 AXSUSDT 2026-07: not_run: None
- cross_2026 BANDUSDT 2026-07: not_run: None
- cross_2026 BATUSDT 2026-07: not_run: None
- cross_2026 BCHUSDT 2026-07: not_run: None
- cross_2026 BELUSDT 2026-07: not_run: None
- cross_2026 BLURUSDT 2026-07: not_run: None
- cross_2026 BNBUSDT 2026-07: not_run: None
- cross_2026 BTCDOMUSDT 2026-07: not_run: None
- cross_2026 BTCUSDT 2026-07: not_run: None
- cross_2026 C98USDT 2026-07: not_run: None
- cross_2026 CELOUSDT 2026-07: not_run: None
- cross_2026 CELRUSDT 2026-07: not_run: None
- cross_2026 CFXUSDT 2026-07: not_run: None
- cross_2026 CHRUSDT 2026-07: not_run: None
- cross_2026 CHZUSDT 2026-07: not_run: None
- cross_2026 CKBUSDT 2026-07: not_run: None
- cross_2026 COMPUSDT 2026-07: not_run: None
- cross_2026 COTIUSDT 2026-07: not_run: None
- cross_2026 CRVUSDT 2026-07: not_run: None
- cross_2026 CTKUSDT 2026-07: not_run: None
- cross_2026 CTSIUSDT 2026-07: not_run: None
- cross_2026 CVXUSDT 2026-07: not_run: None
- cross_2026 DASHUSDT 2026-07: not_run: None
- cross_2026 DOGEUSDT 2026-07: not_run: None
- cross_2026 DOTUSDT 2026-07: not_run: None
- cross_2026 DUSKUSDT 2026-07: not_run: None
- cross_2026 DYDXUSDT 2026-07: not_run: None
- cross_2026 EDUUSDT 2026-07: not_run: None
- cross_2026 EGLDUSDT 2026-07: not_run: None
- cross_2026 ENJUSDT 2026-07: not_run: None
- cross_2026 ENSUSDT 2026-07: not_run: None
- cross_2026 ETCUSDT 2026-07: not_run: None
- cross_2026 ETHUSDT 2026-07: not_run: None
- cross_2026 FETUSDT 2026-07: not_run: None
- cross_2026 FILUSDT 2026-07: not_run: None
- cross_2026 FLOWUSDT 2026-07: not_run: None
- cross_2026 GALAUSDT 2026-07: not_run: None
- cross_2026 GMTUSDT 2026-07: not_run: None
- cross_2026 GMXUSDT 2026-07: not_run: None
- cross_2026 GRTUSDT 2026-07: not_run: None
- cross_2026 GTCUSDT 2026-07: not_run: None
- cross_2026 HBARUSDT 2026-07: not_run: None
- cross_2026 HFTUSDT 2026-07: not_run: None
- cross_2026 HOTUSDT 2026-07: not_run: None
- cross_2026 ICPUSDT 2026-07: not_run: None
- cross_2026 ICXUSDT 2026-07: not_run: None
- cross_2026 IDUSDT 2026-07: not_run: None
- cross_2026 IMXUSDT 2026-07: not_run: None
- cross_2026 INJUSDT 2026-07: not_run: None
- cross_2026 IOSTUSDT 2026-07: not_run: None
- cross_2026 IOTAUSDT 2026-07: not_run: None
- cross_2026 IOTXUSDT 2026-07: not_run: None
- cross_2026 JASMYUSDT 2026-07: not_run: None
- cross_2026 JOEUSDT 2026-07: not_run: None
- cross_2026 KAVAUSDT 2026-07: not_run: None
- cross_2026 KNCUSDT 2026-07: not_run: None
- cross_2026 KSMUSDT 2026-07: not_run: None
- cross_2026 LDOUSDT 2026-07: not_run: None
- cross_2026 LINKUSDT 2026-07: not_run: None
- cross_2026 LITUSDT 2026-07: not_run: None
- cross_2026 LPTUSDT 2026-07: not_run: None
- cross_2026 LQTYUSDT 2026-07: not_run: None
- cross_2026 LTCUSDT 2026-07: not_run: None
- cross_2026 LUNA2USDT 2026-07: not_run: None
- cross_2026 MAGICUSDT 2026-07: not_run: None
- cross_2026 MANAUSDT 2026-07: not_run: None
- cross_2026 MASKUSDT 2026-07: not_run: None
- cross_2026 MAVUSDT 2026-07: not_run: None
- cross_2026 MINAUSDT 2026-07: not_run: None
- cross_2026 MTLUSDT 2026-07: not_run: None
- cross_2026 NEARUSDT 2026-07: not_run: None
- cross_2026 NEOUSDT 2026-07: not_run: None
- cross_2026 NMRUSDT 2026-07: not_run: None
- cross_2026 OGNUSDT 2026-07: not_run: None
- cross_2026 ONEUSDT 2026-07: not_run: None
- cross_2026 ONTUSDT 2026-07: not_run: None
- cross_2026 OPUSDT 2026-07: not_run: None
- cross_2026 PEOPLEUSDT 2026-07: not_run: None
- cross_2026 QNTUSDT 2026-07: not_run: None
- cross_2026 QTUMUSDT 2026-07: not_run: None
- cross_2026 RLCUSDT 2026-07: not_run: None
- cross_2026 ROSEUSDT 2026-07: not_run: None
- cross_2026 RSRUSDT 2026-07: not_run: None
- cross_2026 RUNEUSDT 2026-07: not_run: None
- cross_2026 RVNUSDT 2026-07: not_run: None
- cross_2026 SANDUSDT 2026-07: not_run: None
- cross_2026 SFPUSDT 2026-07: not_run: None
- cross_2026 SKLUSDT 2026-07: not_run: None
- cross_2026 SNXUSDT 2026-07: not_run: None
- cross_2026 SOLUSDT 2026-07: not_run: None
- cross_2026 SPELLUSDT 2026-07: not_run: None
- cross_2026 SSVUSDT 2026-07: not_run: None
- cross_2026 STGUSDT 2026-07: not_run: None
- cross_2026 STORJUSDT 2026-07: not_run: None
- cross_2026 STXUSDT 2026-07: not_run: None
- cross_2026 SUIUSDT 2026-07: not_run: None
- cross_2026 SUSHIUSDT 2026-07: not_run: None
- cross_2026 THETAUSDT 2026-07: not_run: None
- cross_2026 TLMUSDT 2026-07: not_run: None
- cross_2026 TRBUSDT 2026-07: not_run: None
- cross_2026 TRXUSDT 2026-07: not_run: None
- cross_2026 TUSDT 2026-07: not_run: None
- cross_2026 UMAUSDT 2026-07: not_run: None
- cross_2026 UNIUSDT 2026-07: not_run: None
- cross_2026 USDCUSDT 2026-07: not_run: None
- cross_2026 VETUSDT 2026-07: not_run: None
- cross_2026 WOOUSDT 2026-07: not_run: None
- cross_2026 XLMUSDT 2026-07: not_run: None
- cross_2026 XMRUSDT 2026-07: not_run: None
- cross_2026 XRPUSDT 2026-07: not_run: None
- cross_2026 XTZUSDT 2026-07: not_run: None
- cross_2026 XVSUSDT 2026-07: not_run: None
- cross_2026 YFIUSDT 2026-07: not_run: None
- cross_2026 ZECUSDT 2026-07: not_run: None
- cross_2026 ZENUSDT 2026-07: not_run: None
- cross_2026 ZILUSDT 2026-07: not_run: None
- cross_2026 ZRXUSDT 2026-07: not_run: None
- cross_2026 ALLUSDT 2026-07: not_run: None
- cross_2026 ARKUSDT 2026-07: not_run: None
- cross_2026 1000000MOGUSDT 2026-07: not_run: None
- cross_2026 STEEMUSDT 2026-07: not_run: None
- cross_2026 BSVUSDT 2026-07: not_run: None
- cross_2026 REDUSDT 2026-07: not_run: None
- cross_2026 METISUSDT 2026-07: not_run: None
- cross_2026 PROVEUSDT 2026-07: not_run: None
- cross_2026 AEVOUSDT 2026-07: not_run: None
- cross_2026 SPKUSDT 2026-07: not_run: None
- cross_2026 BEAMXUSDT 2026-07: not_run: None
- cross_2026 HIVEUSDT 2026-07: not_run: None
- cross_2026 AIXBTUSDT 2026-07: not_run: None
- cross_2026 KAIAUSDT 2026-07: not_run: None
- cross_2026 1000CATUSDT 2026-07: not_run: None
- cross_2026 GOATUSDT 2026-07: not_run: None
- cross_2026 DEEPUSDT 2026-07: not_run: None
- cross_2026 FORMUSDT 2026-07: not_run: None
- cross_2026 WCTUSDT 2026-07: not_run: None
- cross_2026 MERLUSDT 2026-07: not_run: None
- cross_2026 1000SATSUSDT 2026-07: not_run: None
- cross_2026 VELODROMEUSDT 2026-07: not_run: None
- cross_2026 CFGUSDT 2026-07: not_run: None
- cross_2026 AUCTIONUSDT 2026-07: not_run: None
- cross_2026 RONINUSDT 2026-07: not_run: None
- cross_2026 TOSHIUSDT 2026-07: not_run: None
- cross_2026 DRIFTUSDT 2026-07: not_run: None
- cross_2026 IRYSUSDT 2026-07: not_run: None
- cross_2026 SOPHUSDT 2026-07: not_run: None
- cross_2026 MUBARAKUSDT 2026-07: not_run: None
- cross_2026 NEWTUSDT 2026-07: not_run: None
- cross_2026 LSKUSDT 2026-07: not_run: None
- cross_2026 AKTUSDT 2026-07: not_run: None
- cross_2026 ACUUSDT 2026-07: not_run: None
- cross_2026 ACXUSDT 2026-07: not_run: None
- cross_2026 ORDERUSDT 2026-07: not_run: None
- cross_2026 ALPINEUSDT 2026-07: not_run: None
- cross_2026 BIGTIMEUSDT 2026-07: not_run: None
- cross_2026 BANUSDT 2026-07: not_run: None
- cross_2026 GLMUSDT 2026-07: not_run: None
- cross_2026 FHEUSDT 2026-07: not_run: None
- cross_2026 STRKUSDT 2026-07: not_run: None
- cross_2026 VICUSDT 2026-07: not_run: None
- cross_2026 MONUSDT 2026-07: not_run: None
- cross_2026 POPCATUSDT 2026-07: not_run: None
- cross_2026 SWARMSUSDT 2026-07: not_run: None
- cross_2026 CUSDT 2026-07: not_run: None
- cross_2026 REZUSDT 2026-07: not_run: None
- cross_2026 0GUSDT 2026-07: not_run: None
- cross_2026 PIXELUSDT 2026-07: not_run: None
- cross_2026 SAGAUSDT 2026-07: not_run: None
- cross_2026 METUSDT 2026-07: not_run: None
- cross_2026 PRLUSDT 2026-07: not_run: None
- cross_2026 BANANAUSDT 2026-07: not_run: None
- cross_2026 BRUSDT 2026-07: not_run: None
- cross_2026 HYPERUSDT 2026-07: not_run: None
- cross_2026 EDENUSDT 2026-07: not_run: None
- cross_2026 COAIUSDT 2026-07: not_run: None
- cross_2026 BIOUSDT 2026-07: not_run: None
- cross_2026 SAFEUSDT 2026-07: not_run: None
- cross_2026 STABLEUSDT 2026-07: not_run: None
- cross_2026 CAKEUSDT 2026-07: not_run: None
- cross_2026 POLUSDT 2026-07: not_run: None
- cross_2026 AIAUSDT 2026-07: not_run: None
- cross_2026 NEIROUSDT 2026-07: not_run: None
- cross_2026 SEIUSDT 2026-07: not_run: None
- cross_2026 SENTUSDT 2026-07: not_run: None
- cross_2026 TSTUSDT 2026-07: not_run: None
- cross_2026 ACTUSDT 2026-07: not_run: None
- cross_2026 TREEUSDT 2026-07: not_run: None
- cross_2026 CATIUSDT 2026-07: not_run: None
- cross_2026 RPLUSDT 2026-07: not_run: None
- cross_2026 DIAUSDT 2026-07: not_run: None
- cross_2026 FFUSDT 2026-07: not_run: None
- cross_2026 NIGHTUSDT 2026-07: not_run: None
- cross_2026 AIOTUSDT 2026-07: not_run: None
- cross_2026 MANTRAUSDT 2026-07: not_run: None
- cross_2026 HOLOUSDT 2026-07: not_run: None
- cross_2026 NOMUSDT 2026-07: not_run: None
- cross_2026 RIVERUSDT 2026-07: not_run: None
- cross_2026 TRADOORUSDT 2026-07: not_run: None
- cross_2026 SCRTUSDT 2026-07: not_run: None
- cross_2026 GIGGLEUSDT 2026-07: not_run: None
- cross_2026 TRUTHUSDT 2026-07: not_run: None
- cross_2026 B2USDT 2026-07: not_run: None
- cross_2026 AIOUSDT 2026-07: not_run: None
- cross_2026 ETHFIUSDT 2026-07: not_run: None
- cross_2026 PIEVERSEUSDT 2026-07: not_run: None
- cross_2026 AEROUSDT 2026-07: not_run: None
- cross_2026 XANUSDT 2026-07: not_run: None
- cross_2026 HUMAUSDT 2026-07: not_run: None
- cross_2026 ZROUSDT 2026-07: not_run: None
- cross_2026 PENGUUSDT 2026-07: not_run: None
- cross_2026 OPNUSDT 2026-07: not_run: None
- cross_2026 PUMPUSDT 2026-07: not_run: None
- cross_2026 GWEIUSDT 2026-07: not_run: None
- cross_2026 JTOUSDT 2026-07: not_run: None
- cross_2026 BLUAIUSDT 2026-07: not_run: None
- cross_2026 CAPUSDT 2026-07: not_run: None
- cross_2026 ENAUSDT 2026-07: not_run: None
- cross_2026 BUSDT 2026-07: not_run: None
- cross_2026 HUSDT 2026-07: not_run: None
- cross_2026 MORPHOUSDT 2026-07: not_run: None
- cross_2026 OUSDT 2026-07: not_run: None
- cross_2026 BASEDUSDT 2026-07: not_run: None
- cross_2026 REUSDT 2026-07: not_run: None
- cross_2026 EPICUSDT 2026-07: not_run: None
- cross_2026 VELVETUSDT 2026-07: not_run: None
- cross_2026 EULUSDT 2026-07: not_run: None
- cross_2026 ESPORTSUSDT 2026-07: not_run: None
- cross_2026 TACUSDT 2026-07: not_run: None
- cross_2026 AKEUSDT 2026-07: not_run: None
- cross_2026 BANKUSDT 2026-07: not_run: None

### Excluded (Q14 labels them stock, ETF or commodity; not measured)

37 cross_2026 units: EWZUSDT (ETF (Brazil); Q14 skipped), COSTUSDT (stock (Costco); Q14 skipped), UBERUSDT (stock (Uber); Q14 skipped), SONYUSDT (stock (Sony); Q14 skipped), IWMUSDT (ETF (Russell 2000); Q14 skipped), URNMUSDT (ETF (uranium miners); Q14 skipped), VUSDT (stock (Visa); Q14 skipped), CIENUSDT (stock (Ciena); Q14 skipped), BRKBUSDT (stock (Berkshire Hathaway B); Q14 skipped), HPEUSDT (stock (Hewlett Packard Enterprise); Q14 ok), JPMUSDT (stock (JPMorgan Chase); Q14 skipped), FLNCUSDT (stock (Fluence Energy); Q14 ok), ALABUSDT (stock (Astera Labs); Q14 ok), ASMLUSDT (stock (ASML); Q14 ok), CRDOUSDT (stock (Credo Technology); Q14 ok), SQQQUSDT (ETF (inverse Nasdaq-100); Q14 ok), ASTSUSDT (stock (AST SpaceMobile); Q14 ok), XPTUSDT (commodity (platinum); Q14 ok), CRWVUSDT (stock (CoreWeave); Q14 ok), AVGOUSDT (stock (Broadcom); Q14 ok), AMATUSDT (stock (Applied Materials); Q14 ok), QCOMUSDT (stock (Qualcomm); Q14 ok), MVLLUSDT (timing screen (US-equity trading hours); Q14 ok), GOOGLUSDT (stock (Alphabet); Q14 ok), PAXGUSDT (gold-backed token; Q14 ok), METAUSDT (stock (Meta Platforms); Q14 ok), QQQUSDT (ETF (Nasdaq-100); Q14 ok), BEUSDT (timing screen (US-equity trading hours); Q14 ok), TSLAUSDT (stock (Tesla); Q14 ok), CRCLUSDT (stock (Circle); Q14 ok), ARMUSDT (stock (Arm Holdings); Q14 ok), DRAMUSDT (timing screen (US-equity trading hours); Q14 ok), AMDUSDT (stock (AMD); Q14 ok), EWYUSDT (ETF (South Korea); Q14 ok), XAUUSDT (commodity (gold); Q14 ok), SKHYNIXUSDT (stock (SK hynix); Q14 ok), SNDKUSDT (stock (SanDisk); Q14 ok).

Q14's other non-fitted units (incomplete months in 2023-06, too-thin units) have no Q14 metrics and are outside this table, as in Q14.

## Runtime and disk

- 1 run(s), 0.01 h wall in total; per-unit time (download wait, ingest and proxies) median 7 s, max 23 s.
- Peak temporary disk (zips plus parquet under data/proxies_cs/tmp, sampled every 0.5 s): 0.21 GB (budget 3 GB).
- Ingest: `ingest_agg_trades` for CSVs up to 1.5 GB; above that, chunked parsing straight from the zip (same casts and schema as Q14's streaming ingest, which would have extracted a 4 to 5 GB CSV and broken the disk budget): none.

## First descriptive table: proxies against Q14 gbm_all accuracy

**Descriptive only.** Within each period, the Spearman correlation across contracts of each non-circular proxy with Q14's `gbm_all` accuracy, and the same after partialling out `log10_events` (ranks of both regressed on the rank of log10 events, residuals correlated). 95% intervals from 2000 bootstrap resamples of contracts. One cross-section per period, many proxies, no correction for multiple comparisons, no causal reading: these are leads for weeks 3 to 4. `lot` and `tick` are in coin and USDT units and are not comparable across contracts; they are shown for completeness.

| proxy | 2023-06 rho | 2023-06 partial |
|---|---|---|
| events_per_day | +0.20 [-1.00, +1.00] | +0.02 [-1.00, +1.00] |
| run_mean | -0.10 [-1.00, +1.00] | -0.00 [-1.00, +1.00] |
| run_share_ge10 | -0.20 [-1.00, +0.83] | +0.00 [-1.00, +0.99] |
| run_mean_sweeps_merged | -0.30 [-1.00, +1.00] | -0.24 [-1.00, +1.00] |
| run_share_ge10_sweeps_merged | -0.20 [-1.00, +0.97] | +0.00 [-1.00, +1.00] |
| sweep_share | +0.30 [-0.67, +1.00] | +0.23 [-1.00, +1.00] |
| equal_size_repeat_share | -0.50 [-1.00, +0.67] | -0.75 [-1.00, +0.97] |
| lot | n/a | -0.29 [-1.00, +0.98] |
| round_size_share | +0.40 [-0.65, +1.00] | +0.52 [-0.57, +1.00] |
| round10_share | +0.20 [-1.00, +1.00] | +0.02 [-0.89, +1.00] |
| share_gap_le_1ms | -0.30 [-1.00, +0.67] | -0.63 [-1.00, +1.00] |
| fano_1s | -0.30 [-1.00, +0.83] | -0.63 [-1.00, +0.84] |
| minute_open_ratio | +0.50 [-0.92, +1.00] | +0.65 [-0.95, +1.00] |
| quarter_open_ratio | +0.30 [-0.97, +1.00] | +0.63 [-0.03, +1.00] |
| median_notional_usd | -0.10 [-1.00, +1.00] | -0.66 [-1.00, +1.00] |
| share_under_1k_usd | +0.10 [-1.00, +0.88] | +0.66 [-0.79, +1.00] |
| tick | +0.22 [-1.00, +0.87] | +0.49 [-1.00, +1.00] |
| tick_changes | +0.71 [+0.71, +1.00] | +0.69 [-0.57, +1.00] |
| rel_tick_bps | +0.10 [-1.00, +1.00] | +0.66 [-0.96, +1.00] |
| unchanged_price_share | -0.10 [-1.00, +1.00] | +0.19 [-1.00, +1.00] |
| prints_per_event | +0.30 [-1.00, +1.00] | +0.23 [-0.41, +1.00] |
| fills_per_record | -0.80 [-1.00, -0.11] | -0.87 [-1.00, +0.38] |

n per period: 2023-06: 5 (rows with a missing value for a proxy are dropped for that proxy).
