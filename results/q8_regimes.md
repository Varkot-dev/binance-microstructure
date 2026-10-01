# Q8: regime comparison, stability of the cross-sectional laws over time

## Method

I load `q4_cross_section.json` (required) and `q6_endogeneity.json` (optional) from a baseline directory (`2023-06`) and one or more regime directories. Each cross-sectional regression (γ̂, p_flip, and α̂_median vs. log10(activity), the last when Q6 is present) is recomputed from the per-symbol records with this module's `np.polyfit` OLS. The stored regression blocks in the upstream jsons are only cross-checked, and a mismatch beyond 1e-06 is reported as a warning below.

**Survivorship**: baseline symbols absent from a regime's successful set are non-survivors. Each gets a reason from that regime's Q4 `skips` (below `min_events`) and `failures` (missing parquet / other exception) when available.

**Rank correlation**: Spearman's rho on the symbol overlap for p_flip, γ̂ (and α̂ when both sides have a Q6 run), as the Pearson correlation of average ranks.

**Law-stability verdicts**: a same-sign check on the flip-law slope across the baseline and every regime, plus each regime's slope ratio to the baseline. γ-invariance holds iff every regime's (baseline included) γ-vs-activity R² is below 0.05. The verdict text is generated from these values.

## Regime table

| regime | universe | n_success | flip slope | flip R² | γ slope | γ R² | γ median (IQR) | p_flip median | anti-persistent | α median (IQR) | α median, slow-mode fits | n̂_CV median | fast-mode share |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2023-06 | fixed | 121 | 0.1114 | 0.2632 | -0.0112 | 0.0003 | 0.3270 (0.0985) | 0.4543 | 20 | 0.7070 (0.2240) | 0.7526 | 0.9587 | 0.12 |
| 2023-07 | fixed | 117 | 0.0920 | 0.2328 | -0.0225 | 0.0086 | 0.3221 (0.0611) | 0.4483 | 15 | 0.6925 (0.2505) | 0.7223 | 0.9425 | 0.12 |
| 2024-07 | fixed | 95 | 0.0448 | 0.0520 | 0.0126 | 0.0013 | 0.2386 (0.1025) | 0.3840 | 4 | 0.3874 (0.4021) | 0.7024 | 0.9299 | 0.49 |
| 2025-07 | fixed | 94 | 0.0463 | 0.0608 | 0.1588 | 0.2505 | 0.1868 (0.1029) | 0.3738 | 6 | 0.4847 (0.2859) | 0.5849 | 0.9329 | 0.33 |
| 2026-07 | fixed | 46 | 0.0230 | 0.0113 | 0.1683 | 0.2441 | 0.1991 (0.1510) | 0.4154 | 4 | 0.5766 (0.4159) | 0.6595 | 0.8903 | 0.31 |
| 2026-07-native | native | 231 | 0.0006 | 0.0000 | 0.0612 | 0.0196 | 0.2071 (0.1321) | 0.3986 | 11 | n/a | n/a | n/a | n/a |

**Kernel-mode shift: do not read the α median as an endogeneity change for 2024-07 (0.49), 2025-07 (0.33).** The fast-mode share is the fraction of symbols whose single-exponential fit has β̂ > 10 (decay faster than 0.1 business-time seconds). In the baseline (2023-06) it is 0.12. A fast-mode fit captures only the fast component of a multi-timescale kernel, so its α̂ is lower by construction. Compare these regimes on the slow-mode α median (fits with β̂ ≤ 10 only) or on the count-variance n̂_CV column, which assumes no kernel shape.

## Law-stability verdicts

**Flip-law sign stability**: the flip-law slope has the **same sign** in every regime as in the baseline, so the direction of the p_flip-vs-activity relationship is stable across regimes.

The sign agreement is weaker than it looks. In 2026-07, 2026-07-native the slope is within 2 standard errors of zero, indistinguishable from zero, so its sign carries no information. The law is absent there, not confirmed.

Flip-law slope ratio vs. baseline, per regime:

- 2023-07: 0.8262x baseline slope
- 2024-07: 0.4027x baseline slope
- 2025-07: 0.4159x baseline slope
- 2026-07: 0.2069x baseline slope
- 2026-07-native: 0.0056x baseline slope

**γ invariance**: at least one regime's γ-vs-activity R² is at or above 0.05 (2025-07, 2026-07), so γ's liquidity-invariance does **not** hold in every regime examined.

### Survivorship-free test: 2026-07-native (native universe)

**2026-07-native** was run on the market's own universe for that period, not the baseline's fixed list, so the verdicts below are not confounded by survivorship.

- Flip-law slope for 2026-07-native (0.0006) is within 2 standard errors of zero, indistinguishable from zero. The flip law is **absent** in this survivorship-free test, so its direction is neither confirmed nor reversed.
- γ-vs-activity R² for 2026-07-native (0.0196) is below 0.05, but the slope (0.0612, 2.1 standard errors) is distinguishable from zero. That is a weak but nonzero activity dependence, not strict flatness.

### γ-break outlier sensitivity (drop-one-out)

For **2025-07** (n=94, full-sample slope=0.1588, R²=0.2505), refitting γ vs. log10(activity) with each symbol removed in turn gives an **R² range of [0.1937 (dropping ETHUSDT), 0.4666 (dropping BTCDOMUSDT)]** and a **slope range of [0.1373 (dropping ETHUSDT), 0.1823 (dropping BTCDOMUSDT)]**. The highest-influence points by Cook's distance are BTCDOMUSDT (Cook's D=0.589, leverage=0.025); ETHUSDT (Cook's D=0.313, leverage=0.105); 1000PEPEUSDT (Cook's D=0.096, leverage=0.072). The slope **stays positive under every single-symbol removal**, so the direction of the break does not depend on any one symbol. R² swings by a large relative amount depending on which point is dropped, so the strength of the break is outlier-sensitive.

For **2026-07** (n=46, full-sample slope=0.1683, R²=0.2441), refitting γ vs. log10(activity) with each symbol removed in turn gives an **R² range of [0.1738 (dropping BTCUSDT), 0.2959 (dropping LTCUSDT)]** and a **slope range of [0.1442 (dropping BTCUSDT), 0.1867 (dropping YFIUSDT)]**. The highest-influence points by Cook's distance are BTCUSDT (Cook's D=0.168, leverage=0.165); YFIUSDT (Cook's D=0.130, leverage=0.062); LTCUSDT (Cook's D=0.112, leverage=0.045). The slope **stays positive under every single-symbol removal**, so the direction of the break does not depend on any one symbol. R² swings by a large relative amount depending on which point is dropped, so the strength of the break is outlier-sensitive.

## Survivorship

Fixed-universe regimes only. A native-universe regime was run on its own requested universe, not the baseline's, so survivorship does not apply to it (see Overlap).

**2023-07**: 101/121 baseline symbols survive into this regime's successful set (117 symbols total in this regime). 20 non-survivor(s).

| symbol | reason |
|---|---|
| 1000FLOKIUSDT | skipped below min_events (n_events=747701) |
| ACHUSDT | skipped below min_events (n_events=748120) |
| AMBUSDT | skipped below min_events (n_events=556865) |
| BNXUSDT | skipped below min_events (n_events=653211) |
| COMBOUSDT | skipped below min_events (n_events=880918) |
| COTIUSDT | skipped below min_events (n_events=962970) |
| DASHUSDT | skipped below min_events (n_events=823758) |
| FLMUSDT | skipped below min_events (n_events=684050) |
| GALABUSD | skipped below min_events (n_events=713883) |
| GALUSDT | skipped below min_events (n_events=936924) |
| HIGHUSDT | skipped below min_events (n_events=619327) |
| JOEUSDT | skipped below min_events (n_events=877303) |
| LDOBUSD | skipped below min_events (n_events=752586) |
| LPTUSDT | skipped below min_events (n_events=782640) |
| QNTUSDT | skipped below min_events (n_events=941058) |
| RADUSDT | skipped below min_events (n_events=497135) |
| SFPUSDT | skipped below min_events (n_events=831726) |
| TRUUSDT | skipped below min_events (n_events=737950) |
| TUSDT | skipped below min_events (n_events=959631) |
| VETUSDT | skipped below min_events (n_events=796364) |

**2024-07**: 73/121 baseline symbols survive into this regime's successful set (95 symbols total in this regime). 48 non-survivor(s).

| symbol | reason |
|---|---|
| 1000XECUSDT | skipped below min_events (n_events=876001) |
| AGIXUSDT | failed/missing (parquet not found: data/parquet/aggTrades/AGIXUSDT/2024-07.parquet) |
| ALPHAUSDT | skipped below min_events (n_events=721547) |
| ANKRUSDT | skipped below min_events (n_events=711127) |
| ANTUSDT | failed/missing (parquet not found: data/parquet/aggTrades/ANTUSDT/2024-07.parquet) |
| ARPAUSDT | skipped below min_events (n_events=700331) |
| BELUSDT | skipped below min_events (n_events=692307) |
| BLURUSDT | skipped below min_events (n_events=998191) |
| BTCBUSD | failed/missing (parquet not found: data/parquet/aggTrades/BTCBUSD/2024-07.parquet) |
| COMBOUSDT | skipped below min_events (n_events=569402) |
| CTSIUSDT | skipped below min_events (n_events=459433) |
| DASHUSDT | skipped below min_events (n_events=549604) |
| ETHBUSD | failed/missing (parquet not found: data/parquet/aggTrades/ETHBUSD/2024-07.parquet) |
| FLMUSDT | skipped below min_events (n_events=994612) |
| FXSUSDT | skipped below min_events (n_events=901620) |
| GALABUSD | failed/missing (parquet not found: data/parquet/aggTrades/GALABUSD/2024-07.parquet) |
| GALUSDT | skipped below min_events (n_events=728492) |
| JOEUSDT | skipped below min_events (n_events=649055) |
| KAVAUSDT | skipped below min_events (n_events=627946) |
| KEYUSDT | skipped below min_events (n_events=641600) |
| KNCUSDT | skipped below min_events (n_events=646659) |
| LDOBUSD | failed/missing (parquet not found: data/parquet/aggTrades/LDOBUSD/2024-07.parquet) |
| LINAUSDT | skipped below min_events (n_events=467389) |
| LQTYUSDT | skipped below min_events (n_events=854451) |
| LUNA2USDT | skipped below min_events (n_events=799836) |
| MAGICUSDT | skipped below min_events (n_events=845442) |
| MANAUSDT | skipped below min_events (n_events=901355) |
| MASKUSDT | skipped below min_events (n_events=907354) |
| MINAUSDT | skipped below min_events (n_events=977396) |
| NKNUSDT | skipped below min_events (n_events=673877) |
| OCEANUSDT | failed/missing (parquet not found: data/parquet/aggTrades/OCEANUSDT/2024-07.parquet) |
| OMGUSDT | skipped below min_events (n_events=595144) |
| QNTUSDT | skipped below min_events (n_events=671580) |
| RADUSDT | failed/missing (parquet not found: data/parquet/aggTrades/RADUSDT/2024-07.parquet) |
| RENUSDT | skipped below min_events (n_events=720502) |
| RLCUSDT | skipped below min_events (n_events=831637) |
| SFPUSDT | skipped below min_events (n_events=810036) |
| SNXUSDT | skipped below min_events (n_events=579750) |
| SOLBUSD | failed/missing (parquet not found: data/parquet/aggTrades/SOLBUSD/2024-07.parquet) |
| STGUSDT | skipped below min_events (n_events=692043) |
| SXPUSDT | skipped below min_events (n_events=539925) |
| TOMOUSDT | failed/missing (parquet not found: data/parquet/aggTrades/TOMOUSDT/2024-07.parquet) |
| TUSDT | skipped below min_events (n_events=529551) |
| WAVESUSDT | failed/missing (parquet not found: data/parquet/aggTrades/WAVESUSDT/2024-07.parquet) |
| WOOUSDT | skipped below min_events (n_events=989604) |
| XMRUSDT | skipped below min_events (n_events=990189) |
| XRPBUSD | failed/missing (parquet not found: data/parquet/aggTrades/XRPBUSD/2024-07.parquet) |
| YFIUSDT | skipped below min_events (n_events=784627) |

**2025-07**: 70/121 baseline symbols survive into this regime's successful set (94 symbols total in this regime). 51 non-survivor(s).

| symbol | reason |
|---|---|
| 1000LUNCUSDT | skipped below min_events (n_events=950125) |
| 1000XECUSDT | skipped below min_events (n_events=473102) |
| AGIXUSDT | failed/missing (parquet not found: data/parquet/aggTrades/AGIXUSDT/2025-07.parquet) |
| AMBUSDT | failed/missing (parquet not found: data/parquet/aggTrades/AMBUSDT/2025-07.parquet) |
| ANKRUSDT | skipped below min_events (n_events=564241) |
| ANTUSDT | failed/missing (parquet not found: data/parquet/aggTrades/ANTUSDT/2025-07.parquet) |
| ARPAUSDT | skipped below min_events (n_events=998723) |
| BANDUSDT | skipped below min_events (n_events=879850) |
| BNXUSDT | failed/missing (parquet not found: data/parquet/aggTrades/BNXUSDT/2025-07.parquet) |
| BTCBUSD | failed/missing (parquet not found: data/parquet/aggTrades/BTCBUSD/2025-07.parquet) |
| CHZUSDT | skipped below min_events (n_events=993679) |
| COMBOUSDT | failed/missing (parquet not found: data/parquet/aggTrades/COMBOUSDT/2025-07.parquet) |
| COTIUSDT | skipped below min_events (n_events=926791) |
| CTSIUSDT | skipped below min_events (n_events=545975) |
| DASHUSDT | skipped below min_events (n_events=506118) |
| EDUUSDT | skipped below min_events (n_events=528579) |
| EOSUSDT | failed/missing (parquet not found: data/parquet/aggTrades/EOSUSDT/2025-07.parquet) |
| ETHBUSD | failed/missing (parquet not found: data/parquet/aggTrades/ETHBUSD/2025-07.parquet) |
| FLMUSDT | skipped below min_events (n_events=546758) |
| FTMUSDT | failed/missing (parquet not found: data/parquet/aggTrades/FTMUSDT/2025-07.parquet) |
| GALABUSD | failed/missing (parquet not found: data/parquet/aggTrades/GALABUSD/2025-07.parquet) |
| GALUSDT | failed/missing (parquet not found: data/parquet/aggTrades/GALUSDT/2025-07.parquet) |
| HIGHUSDT | skipped below min_events (n_events=739147) |
| KAVAUSDT | skipped below min_events (n_events=914392) |
| KEYUSDT | failed/missing (parquet not found: data/parquet/aggTrades/KEYUSDT/2025-07.parquet) |
| LDOBUSD | failed/missing (parquet not found: data/parquet/aggTrades/LDOBUSD/2025-07.parquet) |
| LINAUSDT | failed/missing (parquet not found: data/parquet/aggTrades/LINAUSDT/2025-07.parquet) |
| LUNA2USDT | skipped below min_events (n_events=519850) |
| MATICUSDT | failed/missing (parquet not found: data/parquet/aggTrades/MATICUSDT/2025-07.parquet) |
| MINAUSDT | skipped below min_events (n_events=821373) |
| MTLUSDT | skipped below min_events (n_events=784129) |
| NKNUSDT | skipped below min_events (n_events=770668) |
| OCEANUSDT | failed/missing (parquet not found: data/parquet/aggTrades/OCEANUSDT/2025-07.parquet) |
| OMGUSDT | failed/missing (parquet not found: data/parquet/aggTrades/OMGUSDT/2025-07.parquet) |
| RADUSDT | failed/missing (parquet not found: data/parquet/aggTrades/RADUSDT/2025-07.parquet) |
| RDNTUSDT | skipped below min_events (n_events=838543) |
| RENUSDT | failed/missing (parquet not found: data/parquet/aggTrades/RENUSDT/2025-07.parquet) |
| RLCUSDT | skipped below min_events (n_events=906571) |
| RNDRUSDT | failed/missing (parquet not found: data/parquet/aggTrades/RNDRUSDT/2025-07.parquet) |
| ROSEUSDT | skipped below min_events (n_events=961562) |
| SFPUSDT | skipped below min_events (n_events=587051) |
| SNXUSDT | skipped below min_events (n_events=569246) |
| SOLBUSD | failed/missing (parquet not found: data/parquet/aggTrades/SOLBUSD/2025-07.parquet) |
| STGUSDT | skipped below min_events (n_events=421781) |
| STORJUSDT | skipped below min_events (n_events=758352) |
| SXPUSDT | skipped below min_events (n_events=625145) |
| TOMOUSDT | failed/missing (parquet not found: data/parquet/aggTrades/TOMOUSDT/2025-07.parquet) |
| TUSDT | skipped below min_events (n_events=681859) |
| WAVESUSDT | failed/missing (parquet not found: data/parquet/aggTrades/WAVESUSDT/2025-07.parquet) |
| XRPBUSD | failed/missing (parquet not found: data/parquet/aggTrades/XRPBUSD/2025-07.parquet) |
| YFIUSDT | skipped below min_events (n_events=734925) |

**2026-07**: 40/121 baseline symbols survive into this regime's successful set (46 symbols total in this regime). 81 non-survivor(s).

| symbol | reason |
|---|---|
| 1000FLOKIUSDT | skipped below min_events (n_events=589155) |
| 1000LUNCUSDT | skipped below min_events (n_events=919921) |
| ACHUSDT | skipped below min_events (n_events=920286) |
| AGIXUSDT | failed/missing (parquet not found: data/parquet/aggTrades/AGIXUSDT/2026-07.parquet) |
| ALPHAUSDT | failed/missing (parquet not found: data/parquet/aggTrades/ALPHAUSDT/2026-07.parquet) |
| AMBUSDT | failed/missing (parquet not found: data/parquet/aggTrades/AMBUSDT/2026-07.parquet) |
| ANKRUSDT | skipped below min_events (n_events=533868) |
| ANTUSDT | failed/missing (parquet not found: data/parquet/aggTrades/ANTUSDT/2026-07.parquet) |
| APEUSDT | skipped below min_events (n_events=667991) |
| ATOMUSDT | skipped below min_events (n_events=837588) |
| AXSUSDT | skipped below min_events (n_events=487196) |
| BANDUSDT | skipped below min_events (n_events=258105) |
| BNXUSDT | failed/missing (parquet not found: data/parquet/aggTrades/BNXUSDT/2026-07.parquet) |
| BTCBUSD | failed/missing (parquet not found: data/parquet/aggTrades/BTCBUSD/2026-07.parquet) |
| CFXUSDT | skipped below min_events (n_events=642676) |
| CHZUSDT | skipped below min_events (n_events=763155) |
| COMBOUSDT | failed/missing (parquet not found: data/parquet/aggTrades/COMBOUSDT/2026-07.parquet) |
| COMPUSDT | skipped below min_events (n_events=252556) |
| CRVUSDT | skipped below min_events (n_events=718109) |
| CTSIUSDT | skipped below min_events (n_events=286784) |
| DUSKUSDT | skipped below min_events (n_events=457845) |
| EDUUSDT | skipped below min_events (n_events=438257) |
| EOSUSDT | failed/missing (parquet not found: data/parquet/aggTrades/EOSUSDT/2026-07.parquet) |
| ETHBUSD | failed/missing (parquet not found: data/parquet/aggTrades/ETHBUSD/2026-07.parquet) |
| FLMUSDT | failed/missing (parquet not found: data/parquet/aggTrades/FLMUSDT/2026-07.parquet) |
| FTMUSDT | failed/missing (parquet not found: data/parquet/aggTrades/FTMUSDT/2026-07.parquet) |
| FXSUSDT | failed/missing (parquet not found: data/parquet/aggTrades/FXSUSDT/2026-07.parquet) |
| GALABUSD | failed/missing (parquet not found: data/parquet/aggTrades/GALABUSD/2026-07.parquet) |
| GALAUSDT | skipped below min_events (n_events=849002) |
| GALUSDT | failed/missing (parquet not found: data/parquet/aggTrades/GALUSDT/2026-07.parquet) |
| GMTUSDT | skipped below min_events (n_events=360680) |
| GRTUSDT | skipped below min_events (n_events=293204) |
| HIGHUSDT | failed/missing (parquet not found: data/parquet/aggTrades/HIGHUSDT/2026-07.parquet) |
| ICPUSDT | skipped below min_events (n_events=994228) |
| IMXUSDT | skipped below min_events (n_events=345265) |
| JASMYUSDT | skipped below min_events (n_events=546964) |
| JOEUSDT | skipped below min_events (n_events=261908) |
| KAVAUSDT | skipped below min_events (n_events=271865) |
| KEYUSDT | failed/missing (parquet not found: data/parquet/aggTrades/KEYUSDT/2026-07.parquet) |
| KNCUSDT | skipped below min_events (n_events=175561) |
| LDOBUSD | failed/missing (parquet not found: data/parquet/aggTrades/LDOBUSD/2026-07.parquet) |
| LINAUSDT | failed/missing (parquet not found: data/parquet/aggTrades/LINAUSDT/2026-07.parquet) |
| LPTUSDT | skipped below min_events (n_events=410648) |
| LQTYUSDT | skipped below min_events (n_events=301348) |
| LUNA2USDT | skipped below min_events (n_events=369214) |
| MAGICUSDT | skipped below min_events (n_events=406652) |
| MANAUSDT | skipped below min_events (n_events=719991) |
| MASKUSDT | skipped below min_events (n_events=360294) |
| MATICUSDT | failed/missing (parquet not found: data/parquet/aggTrades/MATICUSDT/2026-07.parquet) |
| MINAUSDT | skipped below min_events (n_events=489846) |
| MKRUSDT | failed/missing (parquet not found: data/parquet/aggTrades/MKRUSDT/2026-07.parquet) |
| MTLUSDT | skipped below min_events (n_events=178253) |
| NEOUSDT | skipped below min_events (n_events=342698) |
| NKNUSDT | failed/missing (parquet not found: data/parquet/aggTrades/NKNUSDT/2026-07.parquet) |
| OCEANUSDT | failed/missing (parquet not found: data/parquet/aggTrades/OCEANUSDT/2026-07.parquet) |
| OMGUSDT | failed/missing (parquet not found: data/parquet/aggTrades/OMGUSDT/2026-07.parquet) |
| PHBUSDT | failed/missing (parquet not found: data/parquet/aggTrades/PHBUSDT/2026-07.parquet) |
| QNTUSDT | skipped below min_events (n_events=400838) |
| RADUSDT | failed/missing (parquet not found: data/parquet/aggTrades/RADUSDT/2026-07.parquet) |
| RDNTUSDT | failed/missing (parquet not found: data/parquet/aggTrades/RDNTUSDT/2026-07.parquet) |
| RENUSDT | failed/missing (parquet not found: data/parquet/aggTrades/RENUSDT/2026-07.parquet) |
| RLCUSDT | skipped below min_events (n_events=358385) |
| RNDRUSDT | failed/missing (parquet not found: data/parquet/aggTrades/RNDRUSDT/2026-07.parquet) |
| ROSEUSDT | skipped below min_events (n_events=531017) |
| SANDUSDT | skipped below min_events (n_events=727999) |
| SFPUSDT | skipped below min_events (n_events=231105) |
| SNXUSDT | skipped below min_events (n_events=602240) |
| SOLBUSD | failed/missing (parquet not found: data/parquet/aggTrades/SOLBUSD/2026-07.parquet) |
| STGUSDT | skipped below min_events (n_events=830723) |
| STORJUSDT | skipped below min_events (n_events=697656) |
| STXUSDT | skipped below min_events (n_events=756215) |
| SUSHIUSDT | skipped below min_events (n_events=281617) |
| SXPUSDT | failed/missing (parquet not found: data/parquet/aggTrades/SXPUSDT/2026-07.parquet) |
| THETAUSDT | skipped below min_events (n_events=423345) |
| TOMOUSDT | failed/missing (parquet not found: data/parquet/aggTrades/TOMOUSDT/2026-07.parquet) |
| TRUUSDT | failed/missing (parquet not found: data/parquet/aggTrades/TRUUSDT/2026-07.parquet) |
| VETUSDT | skipped below min_events (n_events=497001) |
| WAVESUSDT | failed/missing (parquet not found: data/parquet/aggTrades/WAVESUSDT/2026-07.parquet) |
| WOOUSDT | skipped below min_events (n_events=246613) |
| XRPBUSD | failed/missing (parquet not found: data/parquet/aggTrades/XRPBUSD/2026-07.parquet) |
| ZENUSDT | skipped below min_events (n_events=587443) |

## Overlap (native-universe regimes)

Survivorship does not apply to a native-universe regime, since a symbol absent from it may not have existed yet. I report the overlap between the baseline's successful symbols and the regime's own, with Spearman rank correlation on that overlap.

| regime | n baseline | n regime | n overlap | baseline-only | regime-only | p_flip Spearman ρ | γ Spearman ρ |
|---|---|---|---|---|---|---|---|
| 2026-07-native | 121 | 231 | 39 | 82 | 192 | 0.3599 | 0.0172 |

### Cohort split (native-universe regimes)

I refit both laws on three cohorts: the baseline's data restricted to symbols present in both periods, this regime's data on the same symbols, and this regime's newly listed symbols alone. A law that changes between the first two rows changed within the same contracts. A law that differs only in the third row is a composition effect. t = slope / OLS stderr.

| regime | cohort | n | flip slope (t) | flip R² | γ slope (t) | γ R² |
|---|---|---|---|---|---|---|
| 2026-07-native | 2023-06 data, shared symbols | 39 | +0.0999 (t +4.04) | 0.306 | +0.0335 (t +0.98) | 0.025 |
| 2026-07-native | this regime, shared symbols | 39 | +0.0307 (t +1.12) | 0.033 | +0.1896 (t +3.56) | 0.256 |
| 2026-07-native | this regime, new listings | 192 | -0.0023 (t -0.17) | 0.000 | +0.0422 (t +1.32) | 0.009 |

### Universe accounting (own requested universe, per regime)

Each regime's full requested universe (the baseline's list for a fixed-universe regime, its own native universe otherwise) splits into successful (passed `min_events`), skipped (downloaded but below `min_events`), and failed (no data for that period). The three sum to that regime's requested universe size by construction of the Q4 run.

| regime | requested | successful | skipped (below floor) | failed (no data) | reconciles |
|---|---|---|---|---|---|
| 2023-07 | 207 | 117 | 87 | 3 | yes |
| 2024-07 | 207 | 95 | 80 | 32 | yes |
| 2025-07 | 207 | 94 | 62 | 51 | yes |
| 2026-07 | 207 | 46 | 93 | 68 | yes |
| 2026-07-native | 371 | 231 | 138 | 2 | yes |

- **2026-07** download-missing cross-check: matches: 68 symbols in both the q4 `failures` list and the external download-missing file

## Symbol-level rank correlation

| regime | n overlap | p_flip Spearman ρ | γ Spearman ρ | α overlap n | α Spearman ρ |
|---|---|---|---|---|---|
| 2023-07 | 101 | 0.7576 | 0.1759 | 41 | 0.8723 |
| 2024-07 | 73 | 0.5704 | 0.0589 | 37 | 0.4203 |
| 2025-07 | 70 | 0.3172 | 0.1439 | 33 | -0.0351 |
| 2026-07 | 40 | 0.2925 | 0.0538 | 32 | 0.2144 |
| 2026-07-native | 39 | 0.3599 | 0.0172 | 0 | n/a |

## Caveats

- **The `min_events` filter shifts membership across regimes**, so the successful set is not a fixed panel. Some non-survivors are below the activity bar in that regime, not delisted. The skip/failure reasons above say which.
- **Fixed and native universes answer different questions**: fixed-universe regimes re-run the baseline's symbol list (`results/universe_2023-06.txt`) and track the original panel. Native-universe regimes (2026-07-native) include later listings, which differ in composition (new contract types as well as new coins). The cohort split above separates the two. Both apply the same min_events floor.
- **Regression stderr and R² inherit the heteroskedasticity caveat** in `q4_cross_section.md` and `q6_endogeneity.md` and are descriptive, not confidence intervals.
- **Spearman rho on a possibly small overlap**: rank correlation is only as informative as the overlap allows. Weight a small `n_overlap` accordingly.
