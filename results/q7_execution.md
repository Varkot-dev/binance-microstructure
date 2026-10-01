# Q7: execution cost of TWAP, front-loaded and flow-reactive schedules

## Scope

This is a model-based cost comparison, not a trading recommendation or a backtest of a tradable strategy. Own-impact comes from each symbol's measured Q5 kernel, linearly scaled (see Caveats). Queueing, order-book depth, latency, and other participants' reaction are not modeled. Shortfall is in basis points of the arrival mid. Evaluation covers 4 calendar days (2023-06-04..07) of one symbol panel in one week, so the results describe how these schedules would have costed against this replayed flow under this cost model, and nothing broader.

## Method

I selected 6 panel symbols as ranks [1, 4, 7, 10, 13, 16] (1-indexed, by Q5 n_events, descending) from the kernels file, spanning the panel's activity range: **BTCUSDT, XRPUSDT, SOLUSDT, ARBUSDT, APTUSDT, BCHUSDT**. For each symbol x day x side ({+1, -1}) x parent size ([2.0, 10.0] typical-event-units), a parent order is executed over `horizon_events=2000` with `n_children=20` under TWAP, front-loaded (decay set from `kernel_half_life_lag(G)`), and flow-reactive schedules. All three use the same cost model (`execution/simulator.py`: drift + half-spread + linear own-impact from the symbol's kernel).

## Calibration vs. evaluation split

The flow-reactive schedule's (lookback, pause_threshold) come from a grid search over {50, 200} x {0.2, 0.4} that maximizes mean advantage vs. TWAP (mean(twap_shortfall - reactive_shortfall) in bps, pooled over symbols, sides, and parent sizes), using only days ['2023-06-01', '2023-06-02', '2023-06-03']. The chosen params are then frozen and evaluated on the disjoint window ['2023-06-04', '2023-06-05', '2023-06-06', '2023-06-07']. The summary tables below use only that window.

**Chosen params**: lookback=200, pause_threshold=0.4.

| lookback | pause_threshold | calibration-window mean advantage vs TWAP (bps) |
|---|---|---|
| 50 | 0.2 | 0.0664649 |
| 50 | 0.4 | -0.00690683 |
| 200 | 0.2 | -0.550855 |
| 200 | 0.4 | 0.0829256 **(chosen)** |

## Evaluation-window results (days 4-7)

| schedule | mean shortfall (bps) | sd (bps, across day/symbol/side/qty) | n |
|---|---|---|---|
| twap | 0.550809 | 29.333 | 96 |
| frontloaded | 2.11457 | 1.74845 | 96 |
| reactive | 0.507966 | 29.3675 | 96 |

## Per-symbol table (evaluation window)

| symbol | twap mean±sd (bps) | frontloaded mean±sd (bps) | reactive mean±sd (bps) |
|---|---|---|---|
| BTCUSDT | 0.03328±4.706 | 0.2816±0.1791 | 0.04159±4.692 |
| XRPUSDT | 1.016±12.66 | 1.686±0.8758 | 0.8874±12.77 |
| SOLUSDT | 0.3355±20.54 | 2.023±1.209 | 0.3386±20.54 |
| ARBUSDT | 0.6102±43.26 | 2.955±1.699 | 0.6102±43.26 |
| APTUSDT | 0.7707±43.39 | 3.819±2.207 | 0.6796±43.53 |
| BCHUSDT | 0.5394±28.34 | 1.923±1.061 | 0.4905±28.29 |

## Findings

Over the evaluation window, **reactive** has the lowest mean shortfall per unit (0.508 bps) and **frontloaded** the highest (2.115 bps) among the three schedules under this cost model, pooled across symbols, sides, and parent sizes. The per-symbol table shows whether the ranking holds across the panel or is driven by a subset of symbols.

Reactive minus twap: mean paired difference -0.04284 bps, paired SE 0.0191 bps, n = 96 cells. The difference is more than 2 paired SEs from zero, so reactive is cheaper than twap in this sample.

Front-loaded shortfall has sd 1.748 bps against 29.33 bps for twap (ratio 0.06) and mean 2.115 bps against 0.5508 bps. Per symbol, its sd is below twap's in 6 of 6 symbols and its mean is above twap's in 6 of 6. This is consistent with front-loading paying more own-impact cost, which the model charges deterministically, for less exposure to adverse drift. Which trade-off is better depends on a risk preference this analysis takes no position on.

## Caveats

- **Linear own-impact scaling**: `temp_impact(q) = G[1] * (q / typical_event_qty)` extrapolates the measured lag-1 kernel value linearly. The square-root law literature (Almgren et al. 2005; Bouchaud et al. 2018) finds temporary impact grows sublinearly at large child sizes. Here children stay at or below a few multiples of typical_event_qty (parent sizes [2.0, 10.0] split across 20 children), where the linear and sqrt curves are close, so the linearization is a reasonable local approximation. It is not validated against real large-child impact data and should not be extrapolated to larger orders.
- **Kernels are in-sample**: the G kernels come from Q5, estimated on 2023-06-01..2023-06-07, which includes 7 of the 7 replayed days (2023-06-01, 2023-06-02, 2023-06-03, 2023-06-04, 2023-06-05, 2023-06-06, 2023-06-07). The own-impact term is therefore fitted on the same days it is evaluated on. Only the reactive parameters are held out (calibrated on the first three days, evaluated on the rest).
- **No queueing or latency**: children execute instantaneously at the chosen event's prevailing mid + half-spread. Queue position, partial fills, and network or exchange latency are not modeled.
- **No market reaction to the schedule**: the replayed order flow (prices, other participants' signs) is fixed historical data and does not react to the simulated parent order beyond the own-impact term. Real execution would interact with real order flow, including other participants adapting to a visible schedule.
- **4 evaluation days**: 2023-06-04..07 is one short window in one market regime. Microstructure statistics are regime-dependent (see Q8), so these results may not carry over.
- **Front-loaded decay from `kernel_half_life_lag`**: the half-life is the lag where G first decays to half its post-peak maximum. If a symbol's kernel never decays within its recorded lags, a fallback (`len(G)//4`) is used (see the `simulator.kernel_half_life_lag` docstring).
- **Paired SE treats cells as independent**: the sides and parent sizes of one symbol-day share a replay, so the paired standard error of reactive minus twap understates the uncertainty.
