# Q7: execution cost of TWAP, front-loaded and flow-reactive schedules

## Scope

This is a model-based cost comparison, not a trading recommendation or a backtest of a tradable strategy. Own-impact comes from each symbol's measured Q5 kernel, linearly scaled (see Caveats). Queueing, order-book depth, latency, and other participants' reaction are not modeled. Evaluation covers 4 calendar days (2023-06-04..07) of one symbol panel in one week, so the results describe how these schedules would have costed against this replayed flow under this cost model, and nothing broader.

## Method

I selected 6 panel symbols as ranks [1, 4, 7, 10, 13, 16] (1-indexed, by Q5 n_events, descending) from the kernels file, spanning the panel's activity range: **BTCUSDT, XRPUSDT, SOLUSDT, ARBUSDT, APTUSDT, BCHUSDT**. For each symbol x day x side ({+1, -1}) x parent size ([2.0, 10.0] typical-event-units), a parent order is executed over `horizon_events=2000` with `n_children=20` under TWAP, front-loaded (decay set from `kernel_half_life_lag(G)`), and flow-reactive schedules. All three use the same cost model (`execution/simulator.py`: drift + half-spread + linear own-impact from the symbol's kernel).

## Calibration vs. evaluation split

The flow-reactive schedule's (lookback, pause_threshold) come from a grid search over {50, 200} x {0.2, 0.4} that maximizes mean advantage vs. TWAP (mean(twap_shortfall - reactive_shortfall), pooled over symbols, sides, and parent sizes), using only days ['2023-06-01', '2023-06-02', '2023-06-03']. The chosen params are then frozen and evaluated on the disjoint window ['2023-06-04', '2023-06-05', '2023-06-06', '2023-06-07']. The summary tables below use only that window.

**Chosen params**: lookback=50, pause_threshold=0.2.

| lookback | pause_threshold | calibration-window mean advantage vs TWAP |
|---|---|---|
| 50 | 0.2 | 0.0200506 **(chosen)** |
| 50 | 0.4 | 0.0173062 |
| 200 | 0.2 | -0.0119261 |
| 200 | 0.4 | -0.000562778 |

## Evaluation-window results (days 4-7)

| schedule | mean shortfall | sd (across day/symbol/side/qty) | n |
|---|---|---|---|
| twap | 0.016099 | 5.20875 | 96 |
| frontloaded | 0.130551 | 0.340422 | 96 |
| reactive | -0.0111392 | 5.27081 | 96 |

## Per-symbol table (evaluation window)

| symbol | twap mean±sd | frontloaded mean±sd | reactive mean±sd |
|---|---|---|---|
| BTCUSDT | 0.08899±12.75 | 0.7536±0.4786 | -0.07288±12.91 |
| XRPUSDT | 5.311e-05±0.0006719 | 8.816e-05±4.553e-05 | 4.561e-05±0.0006733 |
| SOLUSDT | 0.0006987±0.04242 | 0.004211±0.00251 | -0.0001638±0.04288 |
| ARBUSDT | 7.245e-05±0.005202 | 0.0003503±0.0002012 | 8.182e-05±0.005203 |
| APTUSDT | 0.0006631±0.03671 | 0.003283±0.001884 | 0.0005318±0.03677 |
| BCHUSDT | 0.006115±0.3224 | 0.0218±0.01202 | 0.005553±0.3256 |

## Findings

Over the evaluation window, **reactive** has the lowest mean shortfall per unit (-0.0111392) and **frontloaded** the highest (0.130551) among the three schedules under this cost model, pooled across symbols, sides, and parent sizes. The per-symbol table shows whether the ranking holds across the panel or is driven by a subset of symbols.

Read the reactive-vs-twap ranking cautiously. The mean gap (0.02724) is small relative to their shared across-cell dispersion (sd ≈ 5.24 for both), so this sample does not statistically distinguish the two, and the apparent edge is consistent with noise. Only frontloaded's variance reduction (below) is clearly resolved in this data.

A second pattern, independent of the means, shows in both the summary table and the per-symbol plot. **Frontloaded** pays a small but consistently positive mean shortfall with a much smaller standard deviation (0.3404) than twap or reactive (5.24 on average), for every symbol in the panel and not just in the pooled numbers. This fits front-loading paying more own-impact cost (which the model always charges, deterministically) for less exposure to adverse drift (the dominant, noisy term for twap and reactive, which spread execution over the full horizon). Which trade-off is better depends on a risk preference this analysis takes no position on.

## Caveats

- **Linear own-impact scaling**: `temp_impact(q) = G[1] * (q / typical_event_qty)` extrapolates the measured lag-1 kernel value linearly. The square-root law literature (Almgren et al. 2005; Bouchaud et al. 2018) finds temporary impact grows sublinearly at large child sizes. Here children stay at or below a few multiples of typical_event_qty (parent sizes [2.0, 10.0] split across 20 children), where the linear and sqrt curves are close, so the linearization is a reasonable local approximation. It is not validated against real large-child impact data and should not be extrapolated to larger orders.
- **No queueing or latency**: children execute instantaneously at the chosen event's prevailing mid + half-spread. Queue position, partial fills, and network or exchange latency are not modeled.
- **No market reaction to the schedule**: the replayed order flow (prices, other participants' signs) is fixed historical data and does not react to the simulated parent order beyond the own-impact term. Real execution would interact with real order flow, including other participants adapting to a visible schedule.
- **4 evaluation days**: 2023-06-04..07 is one short window in one market regime. Microstructure statistics are regime-dependent (see Q8), so these results may not carry over.
- **Front-loaded decay from `kernel_half_life_lag`**: the half-life is the lag where G first decays to half its post-peak maximum. If a symbol's kernel never decays within its recorded lags, a fallback (`len(G)//4`) is used (see the `simulator.kernel_half_life_lag` docstring).
