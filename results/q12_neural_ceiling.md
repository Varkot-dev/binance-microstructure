# Q12: how much held-out timing likelihood does the linear Hawkes family leave unexplained?

## Question

Q6 and Q6b fit exponential-kernel Hawkes models to trade arrivals; the branching ratio depends on the kernel family. A neural point process cannot settle that, but it can answer a well-posed question: on identical held-out events, how many nats per event better is a flexible neural model than Poisson and than the K = 1, 2, 3 exponential Hawkes fits? If the neural model barely beats the best Hawkes, the parametric family is close to adequate for one-step-ahead timing. If it wins clearly, there is structure the linear self-exciting form misses.

## Method

**Data and split.** Aggressor-level events (`load_events`) of one symbol-month, split on whole UTC days: 20 training days, 2 validation days, 1 embargo day, the remaining days are the test block (`microstructure.ml.dataset.split_masks`).

**Business time.** As in Q6 and Q6b (`intraday_rate_profile`, 48 bins, then `rescale_to_business_time`), except that the profile is estimated on the training days only and applied unchanged to validation and test, so intraday seasonality is counted neither as self-excitation nor as neural skill.

**Score: interval-censored likelihood, the same for every model.** Timestamps are integer milliseconds and gaps of 0 and 1 ms are common, so a continuous density is not a usable score: a log-normal density at a gap of 0 is zero, and a narrow mixture component or a Hawkes kernel with a very large beta can push the density on lattice values arbitrarily high. I read the stamps as floors of the true times. If the previous event truly happened u ms after its stamp, an event recorded d ms later has a true gap in [d - u, d + 1 - u). Averaging over u uniform on [0, 1), the probability of the recorded gap is P(d) = integral of F(d + 1 - u) - F(d - u) du, with F the model's conditional gap CDF and F = 0 below 0, and the score is log P(d). This is the interval [max(d - 1, 0), d + 1) with the weighting inside it that makes the masses sum to 1; unweighted, those overlapping intervals would sum to about 2. The integral uses a 4-node Gauss-Legendre rule, and for each node the cells tile the half-line, so the rule is an exactly normalized probability mass function over the recorded gap for any F. The log score is therefore proper, at most zero, finite at d = 0, and cannot be improved by spiking. The millisecond is mapped to business time exactly by pushing the times ts and ts + 1 ms through the time change (its business-time width is the local rate times 1 ms). F is closed form for the log-normal mixture (mixture of normal CDFs in log time) and for an exponential-sum Hawkes (survival exp(-Lambda(x)) with Lambda(x) = mu x + sum_k alpha_k A_k (1 - exp(-beta_k x)) and A_k the recursive state after the previous event). Validation by simulation is in tests/ml/test_tpp.py.

**Tie truncation.** Same-millisecond same-side prints are one event, so a millisecond holds at most a sell and a buy. After such a pair the next recorded gap is at least 1 ms by construction of the data. Every model is conditioned on that known support (after a tied event the score is log(P(d) / (1 - P(0)))), so that learning this artifact is not credited to the network.

**Models.** Poisson: constant rate from the training block. Hawkes K = 1, 2, 3: `fit_hawkes_exp` and `fit_hawkes_multiexp` on 2 contiguous training chunk(s) of at most 250,000 events (Q6b's cap). Those fits maximize a continuous likelihood on the recorded times, while the network is trained on the censored score itself. To keep the comparison fair each K also gets a Nelder-Mead polish of the censored training score (300 iterations on 100,000 events, started from its MLE). For each K the candidate with the best validation score is used; validation plays the same role for the network (early stopping and seed choice). Neural: a GRU with 48 hidden units and a 8-component log-normal mixture for the next gap (Shchur, Bilos and Gunnemann 2020). Inputs per event: the log gap and log exponentially weighted event rates at horizons 1, 10, 100, 1000 business-time seconds, standardized with training statistics. No trade sign is used: within a tied millisecond the order of signs is fixed by the sort and would leak a timing artifact. Training: truncated backpropagation on random contiguous windows of 256 events (the first 64 warm the state and are not scored), at most 8,192 windows per epoch, up to 10 epochs, batch 64, Adam at 0.002, 2 seed(s).

**Same events, same warm-up.** At the first event of the test block every model starts from an empty state. The first 20,000 events are fed and not scored. All models are scored on the same remaining events. The network reads between 64 and 255 past events through its recurrent state (the same window layout as in training) and the slow rate inputs beyond that.

**Reported.** Mean score minus the Poisson score, in nats per event. Intervals are 95% percentile intervals from resampling whole UTC test days (2,000 resamples) of per-event differences, paired across models. Residuals: by the time-rescaling theorem the compensator increments of a correct model are independent Exp(1). Because a gap is only known up to its cell I use the randomized probability integral transform (a uniform draw between the model's survival at the two cell edges), which is exactly Exp(1) under a correct model and has no atom from ties. I report the KS distance to Exp(1) and lag-1 autocorrelations, not p-values: at these sample sizes every model is rejected.

## Run summary

Symbol-months scored: 10. Failed: 0.

## Held-out nats per event over Poisson (test block, 95% day-block CI)

| symbol-month | scored events | test days | tied (0 ms) | gap <= 1 ms | Hawkes K=1 | Hawkes K=2 | Hawkes K=3 | neural |
|---|---|---|---|---|---|---|---|---|
| BTCUSDT 2023-06 | 5,130,776 | 7 | 1.0% | 6.3% | +0.2631 [+0.1820, +0.3640] | +0.2771 [+0.1890, +0.3836] | +0.2860 [+0.2008, +0.3909] | +0.3748 [+0.2984, +0.4684] |
| ETHUSDT 2023-06 | 3,492,988 | 7 | 0.7% | 5.9% | +0.2673 [+0.1861, +0.3539] | +0.3272 [+0.2503, +0.4083] | +0.3342 [+0.2579, +0.4150] | +0.4354 [+0.3731, +0.4981] |
| 1000PEPEUSDT 2023-06 | 3,462,210 | 7 | 1.4% | 6.9% | +0.5511 [+0.4746, +0.6215] | +0.6384 [+0.5593, +0.7109] | +0.6535 [+0.5735, +0.7258] | +0.7039 [+0.6237, +0.7741] |
| XRPUSDT 2023-06 | 964,756 | 7 | 0.6% | 1.5% | -0.1278 [-0.1733, -0.0846] | +0.2718 [+0.2173, +0.3410] | -0.8432 [-1.0210, -0.6612] | +0.5359 [+0.4711, +0.6106] |
| SOLUSDT 2023-06 | 1,784,882 | 7 | 0.8% | 4.7% | +0.5526 [+0.3760, +0.6487] | +0.6655 [+0.5057, +0.7563] | +0.6724 [+0.5138, +0.7624] | +0.7063 [+0.5460, +0.7958] |
| BNBUSDT 2023-06 | 1,141,278 | 7 | 0.5% | 3.3% | +0.3488 [+0.2902, +0.4171] | +0.4231 [+0.3637, +0.4911] | +0.4293 [+0.3696, +0.4972] | +0.4693 [+0.4045, +0.5405] |
| LTCUSDT 2023-06 | 1,616,864 | 7 | 1.3% | 5.2% | +0.8560 [+0.2955, +1.1495] | +0.8810 [+0.3261, +1.1709] | +0.8836 [+0.3400, +1.1684] | +0.9455 [+0.3891, +1.2369] |
| DOGEUSDT 2023-06 | 730,233 | 7 | 0.6% | 1.9% | +0.5365 [+0.4208, +0.6528] | +0.5588 [+0.4470, +0.6725] | +0.5652 [+0.4551, +0.6760] | +0.6200 [+0.5106, +0.7362] |
| LINKUSDT 2023-06 | 692,417 | 7 | 0.5% | 1.8% | +0.4172 [+0.2887, +0.5453] | +0.4380 [+0.3128, +0.5647] | +0.4468 [+0.3230, +0.5726] | +0.4903 [+0.3701, +0.6103] |
| AVAXUSDT 2023-06 | 619,971 | 7 | 0.4% | 2.2% | +0.4235 [+0.3234, +0.5029] | +0.5651 [+0.4819, +0.6288] | +0.5763 [+0.4944, +0.6391] | +0.6170 [+0.5349, +0.6839] |

## Neural minus Hawkes

The best Hawkes is chosen on the validation block, never on the test block. Seed spread is the range of the neural test gain across seeds.

| symbol-month | share of neural gain: K=1 / K=2 / K=3 | best Hawkes (validation) | neural minus best Hawkes | interval | seed spread |
|---|---|---|---|---|---|
| BTCUSDT 2023-06 | 70% / 74% / 76% | Hawkes K=3 | +0.0888 [+0.0774, +0.0996] | above zero | 0.0004 |
| ETHUSDT 2023-06 | 61% / 75% / 77% | Hawkes K=3 | +0.1012 [+0.0833, +0.1167] | above zero | 0.0013 |
| 1000PEPEUSDT 2023-06 | 78% / 91% / 93% | Hawkes K=3 | +0.0504 [+0.0461, +0.0551] | above zero | 0.0008 |
| XRPUSDT 2023-06 | -24% / 51% / -157% | Hawkes K=2 | +0.2642 [+0.2487, +0.2788] | above zero | 0.0026 |
| SOLUSDT 2023-06 | 78% / 94% / 95% | Hawkes K=3 | +0.0340 [+0.0317, +0.0365] | above zero | 0.0030 |
| BNBUSDT 2023-06 | 74% / 90% / 91% | Hawkes K=3 | +0.0400 [+0.0344, +0.0467] | above zero | 0.0025 |
| LTCUSDT 2023-06 | 91% / 93% / 93% | Hawkes K=3 | +0.0619 [+0.0432, +0.0698] | above zero | 0.0011 |
| DOGEUSDT 2023-06 | 87% / 90% / 91% | Hawkes K=3 | +0.0547 [+0.0441, +0.0658] | above zero | 0.0014 |
| LINKUSDT 2023-06 | 85% / 89% / 91% | Hawkes K=3 | +0.0435 [+0.0368, +0.0527] | above zero | 0.0003 |
| AVAXUSDT 2023-06 | 69% / 92% / 93% | Hawkes K=3 | +0.0406 [+0.0335, +0.0497] | above zero | 0.0003 |

## Hawkes fits used

`MLE` is the repo's continuous-likelihood fit (best training chunk by validation score); `used` is the validation-selected candidate, which is the MLE itself or its censored-score polish. n is the branching ratio, shown for reference only.

| symbol-month | K | used | n (used) | 1/beta (used, business s) | test gain, MLE | test gain, used |
|---|---|---|---|---|---|---|
| BTCUSDT 2023-06 | 1 | polished | 0.8401 | 0.576 | +0.2637 | +0.2631 |
| BTCUSDT 2023-06 | 2 | polished | 0.8632 | 0.0164, 1.98 | +0.2788 | +0.2771 |
| BTCUSDT 2023-06 | 3 | mle | 0.8637 | 0.00989, 0.367, 5.37 | +0.2860 | +0.2860 |
| ETHUSDT 2023-06 | 1 | mle | 0.6645 | 0.191 | +0.2673 | +0.2673 |
| ETHUSDT 2023-06 | 2 | mle | 0.8257 | 0.0163, 1.45 | +0.3272 | +0.3272 |
| ETHUSDT 2023-06 | 3 | mle | 0.8735 | 0.0122, 0.293, 7.12 | +0.3342 | +0.3342 |
| 1000PEPEUSDT 2023-06 | 1 | mle | 0.7439 | 0.61 | +0.5511 | +0.5511 |
| 1000PEPEUSDT 2023-06 | 2 | mle | 0.8515 | 0.0346, 3.26 | +0.6384 | +0.6384 |
| 1000PEPEUSDT 2023-06 | 3 | polished | 0.8357 | 0.0168, 0.767, 21.9 | +0.6494 | +0.6535 |
| XRPUSDT 2023-06 | 1 | mle | 0.4533 | 0.0229 | -0.1278 | -0.1278 |
| XRPUSDT 2023-06 | 2 | mle | 0.8401 | 0.0109, 1.34 | +0.2718 | +0.2718 |
| XRPUSDT 2023-06 | 3 | mle | 0.0253 | 6.15e-309, 0.0378, 2.71e+16 | -0.8432 | -0.8432 |
| SOLUSDT 2023-06 | 1 | mle | 0.6675 | 0.564 | +0.5526 | +0.5526 |
| SOLUSDT 2023-06 | 2 | mle | 0.8612 | 0.0175, 4.56 | +0.6655 | +0.6655 |
| SOLUSDT 2023-06 | 3 | mle | 0.8815 | 0.0139, 0.365, 8.58 | +0.6724 | +0.6724 |
| BNBUSDT 2023-06 | 1 | mle | 0.7483 | 1.48 | +0.3488 | +0.3488 |
| BNBUSDT 2023-06 | 2 | mle | 0.8529 | 0.0135, 5.27 | +0.4231 | +0.4231 |
| BNBUSDT 2023-06 | 3 | mle | 0.8922 | 0.0113, 0.773, 16.1 | +0.4293 | +0.4293 |
| LTCUSDT 2023-06 | 1 | mle | 0.8766 | 3.16 | +0.8560 | +0.8560 |
| LTCUSDT 2023-06 | 2 | mle | 0.8891 | 0.00564, 4.31 | +0.8810 | +0.8810 |
| LTCUSDT 2023-06 | 3 | mle | 0.8895 | 0.00487, 1.56, 20.8 | +0.8836 | +0.8836 |
| DOGEUSDT 2023-06 | 1 | mle | 0.7631 | 4.37 | +0.5365 | +0.5365 |
| DOGEUSDT 2023-06 | 2 | mle | 0.8506 | 0.647, 18 | +0.5588 | +0.5588 |
| DOGEUSDT 2023-06 | 3 | mle | 0.8572 | 0.00124, 0.93, 22 | +0.5652 | +0.5652 |
| LINKUSDT 2023-06 | 1 | mle | 0.7936 | 4.12 | +0.4172 | +0.4172 |
| LINKUSDT 2023-06 | 2 | mle | 0.8570 | 0.503, 11.7 | +0.4380 | +0.4380 |
| LINKUSDT 2023-06 | 3 | mle | 0.8789 | 0.00821, 1.57, 24.7 | +0.4468 | +0.4468 |
| AVAXUSDT 2023-06 | 1 | polished | 0.7718 | 2.76 | +0.4217 | +0.4235 |
| AVAXUSDT 2023-06 | 2 | mle | 0.8316 | 0.0478, 7.44 | +0.5651 | +0.5651 |
| AVAXUSDT 2023-06 | 3 | mle | 0.8657 | 0.0213, 0.477, 15.9 | +0.5763 | +0.5763 |

## Time-rescaling residuals (test block)

KS distance of the randomized residuals to Exp(1) (0 is a perfect fit; the 5% critical value for independent draws at these sizes is about 0.001 to 0.003, so read the distances as effect sizes) and lag-1 autocorrelation of the residuals z and of u = 1 - exp(-z).

| symbol-month | model | KS distance | lag-1 autocorr (z) | lag-1 autocorr (u) |
|---|---|---|---|---|
| BTCUSDT 2023-06 | Poisson | 0.1445 | +0.3357 | +0.4738 |
| BTCUSDT 2023-06 | Hawkes K=1 | 0.0578 | +0.1036 | +0.1986 |
| BTCUSDT 2023-06 | Hawkes K=2 | 0.1038 | +0.1312 | +0.1900 |
| BTCUSDT 2023-06 | Hawkes K=3 | 0.0956 | +0.1107 | +0.1872 |
| BTCUSDT 2023-06 | Neural (GRU + log-normal mixture) | 0.0108 | +0.0226 | +0.0143 |
| ETHUSDT 2023-06 | Poisson | 0.1754 | +0.3103 | +0.4867 |
| ETHUSDT 2023-06 | Hawkes K=1 | 0.0964 | +0.1214 | +0.2348 |
| ETHUSDT 2023-06 | Hawkes K=2 | 0.0847 | +0.1332 | +0.2275 |
| ETHUSDT 2023-06 | Hawkes K=3 | 0.0810 | +0.1131 | +0.2104 |
| ETHUSDT 2023-06 | Neural (GRU + log-normal mixture) | 0.0091 | -0.0035 | -0.0038 |
| 1000PEPEUSDT 2023-06 | Poisson | 0.3263 | +0.2926 | +0.4130 |
| 1000PEPEUSDT 2023-06 | Hawkes K=1 | 0.1154 | +0.0838 | +0.1591 |
| 1000PEPEUSDT 2023-06 | Hawkes K=2 | 0.0457 | +0.1066 | +0.1579 |
| 1000PEPEUSDT 2023-06 | Hawkes K=3 | 0.0264 | +0.0818 | +0.1424 |
| 1000PEPEUSDT 2023-06 | Neural (GRU + log-normal mixture) | 0.0170 | +0.0080 | +0.0185 |
| XRPUSDT 2023-06 | Poisson | 0.1719 | +0.2470 | +0.3681 |
| XRPUSDT 2023-06 | Hawkes K=1 | 0.3387 | +0.2393 | +0.2761 |
| XRPUSDT 2023-06 | Hawkes K=2 | 0.2608 | +0.0438 | +0.0522 |
| XRPUSDT 2023-06 | Hawkes K=3 | 0.3382 | +0.2471 | +0.3912 |
| XRPUSDT 2023-06 | Neural (GRU + log-normal mixture) | 0.0051 | +0.0012 | -0.0020 |
| SOLUSDT 2023-06 | Poisson | 0.2821 | +0.2825 | +0.4046 |
| SOLUSDT 2023-06 | Hawkes K=1 | 0.1058 | +0.0443 | +0.1010 |
| SOLUSDT 2023-06 | Hawkes K=2 | 0.0186 | +0.0665 | +0.1115 |
| SOLUSDT 2023-06 | Hawkes K=3 | 0.0141 | +0.0531 | +0.0989 |
| SOLUSDT 2023-06 | Neural (GRU + log-normal mixture) | 0.0152 | -0.0102 | -0.0092 |
| BNBUSDT 2023-06 | Poisson | 0.1271 | +0.2491 | +0.3816 |
| BNBUSDT 2023-06 | Hawkes K=1 | 0.0689 | +0.0230 | +0.1158 |
| BNBUSDT 2023-06 | Hawkes K=2 | 0.0171 | +0.0643 | +0.1378 |
| BNBUSDT 2023-06 | Hawkes K=3 | 0.0218 | +0.0474 | +0.1175 |
| BNBUSDT 2023-06 | Neural (GRU + log-normal mixture) | 0.0060 | -0.0120 | -0.0195 |
| LTCUSDT 2023-06 | Poisson | 0.3411 | +0.3643 | +0.5679 |
| LTCUSDT 2023-06 | Hawkes K=1 | 0.0453 | +0.0847 | +0.1643 |
| LTCUSDT 2023-06 | Hawkes K=2 | 0.0211 | +0.0917 | +0.1658 |
| LTCUSDT 2023-06 | Hawkes K=3 | 0.0360 | +0.0896 | +0.1547 |
| LTCUSDT 2023-06 | Neural (GRU + log-normal mixture) | 0.0087 | +0.0182 | +0.0225 |
| DOGEUSDT 2023-06 | Poisson | 0.1978 | +0.2960 | +0.4616 |
| DOGEUSDT 2023-06 | Hawkes K=1 | 0.0564 | +0.0347 | +0.0806 |
| DOGEUSDT 2023-06 | Hawkes K=2 | 0.0343 | +0.0495 | +0.0711 |
| DOGEUSDT 2023-06 | Hawkes K=3 | 0.0270 | +0.0492 | +0.0738 |
| DOGEUSDT 2023-06 | Neural (GRU + log-normal mixture) | 0.0094 | +0.0082 | -0.0025 |
| LINKUSDT 2023-06 | Poisson | 0.2417 | +0.2753 | +0.3910 |
| LINKUSDT 2023-06 | Hawkes K=1 | 0.0381 | +0.0287 | +0.0897 |
| LINKUSDT 2023-06 | Hawkes K=2 | 0.0238 | +0.0343 | +0.0772 |
| LINKUSDT 2023-06 | Hawkes K=3 | 0.0127 | +0.0289 | +0.0809 |
| LINKUSDT 2023-06 | Neural (GRU + log-normal mixture) | 0.0140 | +0.0150 | +0.0193 |
| AVAXUSDT 2023-06 | Poisson | 0.2777 | +0.2323 | +0.3121 |
| AVAXUSDT 2023-06 | Hawkes K=1 | 0.1275 | +0.0038 | +0.0767 |
| AVAXUSDT 2023-06 | Hawkes K=2 | 0.0358 | +0.0266 | +0.0681 |
| AVAXUSDT 2023-06 | Hawkes K=3 | 0.0243 | +0.0210 | +0.0581 |
| AVAXUSDT 2023-06 | Neural (GRU + log-normal mixture) | 0.0201 | -0.0125 | -0.0184 |

## Where the neural-minus-best-Hawkes difference comes from

Per recorded gap of the scored event: share of events, mean difference in nats, and contribution (share times mean; the gap rows sum to the overall difference). The last row is a separate cut: events whose predecessor was tied.

| symbol-month | bucket | share | mean difference | contribution |
|---|---|---|---|---|
| BTCUSDT 2023-06 | 0 ms | 1.0% | -0.2892 | -0.0029 |
| BTCUSDT 2023-06 | 1 ms | 5.3% | +0.5815 | +0.0309 |
| BTCUSDT 2023-06 | 2 to 9 ms | 12.8% | -0.1689 | -0.0216 |
| BTCUSDT 2023-06 | 10 to 99 ms | 37.9% | -0.1247 | -0.0473 |
| BTCUSDT 2023-06 | 100 to 999 ms | 42.6% | +0.3058 | +0.1303 |
| BTCUSDT 2023-06 | 1 s or more | 0.4% | -0.1906 | -0.0007 |
| BTCUSDT 2023-06 | previous event tied | 1.0% | +0.0422 | +0.0004 |
| ETHUSDT 2023-06 | 0 ms | 0.7% | -0.1898 | -0.0014 |
| ETHUSDT 2023-06 | 1 ms | 5.2% | +0.7192 | +0.0372 |
| ETHUSDT 2023-06 | 2 to 9 ms | 12.2% | -0.1011 | -0.0123 |
| ETHUSDT 2023-06 | 10 to 99 ms | 31.6% | -0.1906 | -0.0603 |
| ETHUSDT 2023-06 | 100 to 999 ms | 48.6% | +0.2821 | +0.1372 |
| ETHUSDT 2023-06 | 1 s or more | 1.6% | +0.0482 | +0.0008 |
| ETHUSDT 2023-06 | previous event tied | 0.7% | +0.0292 | +0.0002 |
| 1000PEPEUSDT 2023-06 | 0 ms | 1.4% | +0.4117 | +0.0056 |
| 1000PEPEUSDT 2023-06 | 1 ms | 5.5% | +0.5200 | +0.0286 |
| 1000PEPEUSDT 2023-06 | 2 to 9 ms | 15.4% | +0.0271 | +0.0042 |
| 1000PEPEUSDT 2023-06 | 10 to 99 ms | 37.5% | +0.0064 | +0.0024 |
| 1000PEPEUSDT 2023-06 | 100 to 999 ms | 37.5% | +0.0321 | +0.0120 |
| 1000PEPEUSDT 2023-06 | 1 s or more | 2.7% | -0.0914 | -0.0025 |
| 1000PEPEUSDT 2023-06 | previous event tied | 1.4% | +0.2450 | +0.0033 |
| XRPUSDT 2023-06 | 0 ms | 0.6% | -0.5601 | -0.0031 |
| XRPUSDT 2023-06 | 1 ms | 1.0% | -0.8158 | -0.0081 |
| XRPUSDT 2023-06 | 2 to 9 ms | 3.0% | -0.8459 | -0.0251 |
| XRPUSDT 2023-06 | 10 to 99 ms | 14.4% | -0.2683 | -0.0387 |
| XRPUSDT 2023-06 | 100 to 999 ms | 62.2% | +0.3617 | +0.2251 |
| XRPUSDT 2023-06 | 1 s or more | 18.8% | +0.6053 | +0.1140 |
| XRPUSDT 2023-06 | previous event tied | 0.6% | +0.1505 | +0.0008 |
| SOLUSDT 2023-06 | 0 ms | 0.8% | +0.0642 | +0.0005 |
| SOLUSDT 2023-06 | 1 ms | 3.9% | +0.4836 | +0.0191 |
| SOLUSDT 2023-06 | 2 to 9 ms | 12.8% | +0.0145 | +0.0019 |
| SOLUSDT 2023-06 | 10 to 99 ms | 32.2% | -0.0358 | -0.0115 |
| SOLUSDT 2023-06 | 100 to 999 ms | 41.4% | +0.0296 | +0.0123 |
| SOLUSDT 2023-06 | 1 s or more | 8.8% | +0.1337 | +0.0118 |
| SOLUSDT 2023-06 | previous event tied | 0.8% | +0.1532 | +0.0012 |
| BNBUSDT 2023-06 | 0 ms | 0.5% | +0.1932 | +0.0010 |
| BNBUSDT 2023-06 | 1 ms | 2.8% | +0.5635 | +0.0155 |
| BNBUSDT 2023-06 | 2 to 9 ms | 7.4% | +0.0135 | +0.0010 |
| BNBUSDT 2023-06 | 10 to 99 ms | 21.5% | -0.0671 | -0.0145 |
| BNBUSDT 2023-06 | 100 to 999 ms | 52.3% | +0.0400 | +0.0209 |
| BNBUSDT 2023-06 | 1 s or more | 15.5% | +0.1035 | +0.0161 |
| BNBUSDT 2023-06 | previous event tied | 0.5% | +0.1063 | +0.0005 |
| LTCUSDT 2023-06 | 0 ms | 1.3% | +0.4577 | +0.0059 |
| LTCUSDT 2023-06 | 1 ms | 3.9% | +0.5986 | +0.0232 |
| LTCUSDT 2023-06 | 2 to 9 ms | 12.3% | +0.2351 | +0.0290 |
| LTCUSDT 2023-06 | 10 to 99 ms | 31.9% | -0.0496 | -0.0158 |
| LTCUSDT 2023-06 | 100 to 999 ms | 40.7% | +0.0390 | +0.0159 |
| LTCUSDT 2023-06 | 1 s or more | 9.9% | +0.0381 | +0.0038 |
| LTCUSDT 2023-06 | previous event tied | 1.3% | +0.3023 | +0.0039 |
| DOGEUSDT 2023-06 | 0 ms | 0.6% | +0.5874 | +0.0032 |
| DOGEUSDT 2023-06 | 1 ms | 1.3% | +0.4668 | +0.0063 |
| DOGEUSDT 2023-06 | 2 to 9 ms | 5.1% | +0.6090 | +0.0312 |
| DOGEUSDT 2023-06 | 10 to 99 ms | 22.4% | +0.0748 | +0.0168 |
| DOGEUSDT 2023-06 | 100 to 999 ms | 47.7% | -0.0092 | -0.0044 |
| DOGEUSDT 2023-06 | 1 s or more | 22.9% | +0.0074 | +0.0017 |
| DOGEUSDT 2023-06 | previous event tied | 0.6% | +0.3337 | +0.0018 |
| LINKUSDT 2023-06 | 0 ms | 0.5% | +0.7983 | +0.0042 |
| LINKUSDT 2023-06 | 1 ms | 1.3% | +0.5751 | +0.0072 |
| LINKUSDT 2023-06 | 2 to 9 ms | 3.7% | +0.0957 | +0.0035 |
| LINKUSDT 2023-06 | 10 to 99 ms | 18.3% | -0.0316 | -0.0058 |
| LINKUSDT 2023-06 | 100 to 999 ms | 52.0% | +0.0620 | +0.0322 |
| LINKUSDT 2023-06 | 1 s or more | 24.3% | +0.0090 | +0.0022 |
| LINKUSDT 2023-06 | previous event tied | 0.5% | +0.3465 | +0.0018 |
| AVAXUSDT 2023-06 | 0 ms | 0.4% | +0.2414 | +0.0008 |
| AVAXUSDT 2023-06 | 1 ms | 1.9% | +0.5527 | +0.0103 |
| AVAXUSDT 2023-06 | 2 to 9 ms | 6.9% | +0.1220 | +0.0084 |
| AVAXUSDT 2023-06 | 10 to 99 ms | 23.2% | -0.0027 | -0.0006 |
| AVAXUSDT 2023-06 | 100 to 999 ms | 42.0% | +0.0091 | +0.0038 |
| AVAXUSDT 2023-06 | 1 s or more | 25.6% | +0.0695 | +0.0178 |
| AVAXUSDT 2023-06 | previous event tied | 0.4% | +0.1678 | +0.0006 |

## Training log

| symbol-month | parameters | seed | epochs run | best validation gain | test gain | seconds (Hawkes / neural) |
|---|---|---|---|---|---|---|
| BTCUSDT 2023-06 | 11,688 | 0 | 8 | +0.5703 | +0.3744 | 394 / 532 |
| BTCUSDT 2023-06 | 11,688 | 1 (used) | 10 | +0.5720 | +0.3748 | 394 / 532 |
| ETHUSDT 2023-06 | 11,688 | 0 (used) | 10 | +0.5267 | +0.4354 | 421 / 443 |
| ETHUSDT 2023-06 | 11,688 | 1 | 10 | +0.5257 | +0.4340 | 421 / 443 |
| 1000PEPEUSDT 2023-06 | 11,688 | 0 (used) | 10 | +1.2955 | +0.7039 | 451 / 567 |
| 1000PEPEUSDT 2023-06 | 11,688 | 1 | 9 | +1.2945 | +0.7031 | 451 / 567 |
| XRPUSDT 2023-06 | 11,688 | 0 | 10 | +0.8971 | +0.5334 | 416 / 411 |
| XRPUSDT 2023-06 | 11,688 | 1 (used) | 10 | +0.9070 | +0.5359 | 416 / 411 |
| SOLUSDT 2023-06 | 11,688 | 0 | 5 | +0.4689 | +0.7033 | 364 / 280 |
| SOLUSDT 2023-06 | 11,688 | 1 (used) | 10 | +0.4710 | +0.7063 | 364 / 280 |
| BNBUSDT 2023-06 | 11,688 | 0 (used) | 10 | +0.3385 | +0.4693 | 365 / 300 |
| BNBUSDT 2023-06 | 11,688 | 1 | 7 | +0.3370 | +0.4667 | 365 / 300 |
| LTCUSDT 2023-06 | 11,688 | 0 (used) | 10 | +0.3996 | +0.9455 | 343 / 359 |
| LTCUSDT 2023-06 | 11,688 | 1 | 9 | +0.3979 | +0.9445 | 343 / 359 |
| DOGEUSDT 2023-06 | 11,688 | 0 | 5 | +0.5005 | +0.6186 | 346 / 185 |
| DOGEUSDT 2023-06 | 11,688 | 1 (used) | 6 | +0.5019 | +0.6200 | 346 / 185 |
| LINKUSDT 2023-06 | 11,688 | 0 (used) | 10 | +0.4063 | +0.4903 | 295 / 337 |
| LINKUSDT 2023-06 | 11,688 | 1 | 10 | +0.4056 | +0.4900 | 295 / 337 |
| AVAXUSDT 2023-06 | 11,688 | 0 (used) | 10 | +0.5820 | +0.6170 | 341 / 312 |
| AVAXUSDT 2023-06 | 11,688 | 1 | 9 | +0.5816 | +0.6166 | 341 / 312 |

## Verdict

Across 10 symbol-month(s), the neural model's held-out timing likelihood is +0.5765 nats per event over Poisson (median), and +0.0525 over the validation-selected Hawkes (median, range +0.0340 to +0.2642). The day-block 95% interval for neural minus best Hawkes lies above zero on 10 of 10, below zero on 0, and contains zero on 0. Median share of the Poisson-to-neural gain already captured by each Hawkes: K=1 76%, K=2 90%, K=3 91%.

On 10 of 10 the gap is both resolved and at least 0.01 nats per event, so on this sample the linear self-exciting form leaves one-step-ahead timing structure unexplained.

Hawkes fits that did not behave: XRPUSDT 2023-06: K=1 scores below Poisson on test, K=3 fit is degenerate. A degenerate fit has a timescale outside 1e-06 to 1e+06 business seconds. Where the fits of one symbol disagree this much, the training chunks probably differ in regime, and the neural-minus-best-Hawkes gap there measures a poor linear fit as much as missing structure; read the median, not that symbol.

## Caveats

- **One-step-ahead timing only.** The score is the likelihood of the next recorded gap given the past. It says nothing about multi-step simulation, about marks (side, size), or about prices, and it is not a trading result.
- **Nothing here bears on the branching ratio.** A likelihood gap between a network and a Hawkes fit does not move the 0.71 / 0.85 / 0.96 dispute of Q6 and Q6b. That dispute is about long memory versus baseline non-stationarity, which a one-step score on a few test days barely weighs, and there is no accepted way to read a branching ratio out of a recurrent network.
- **The network is a lower bound on flexible models, not an upper bound.** It is a small, short-memory model (a few hundred events of recurrent state plus exponentially weighted rates), trained briefly on CPU on a capped number of windows. A larger or longer-memory model could score higher. A small gap therefore means the Hawkes family is close to what this network finds, not that nothing better exists; a gap in favour of Hawkes means the network is not a ceiling at all.
- **The Hawkes side is also not the best possible linear model.** Constant baseline, at most three exponentials, fitted on at most 250,000 events per chunk with Nelder-Mead. A flexible baseline or more components would likely narrow any gap (the research notes cite evidence that it usually does).
- **Cold start.** All models start empty at the test block and are warmed on the burn-in only, so kernel components slower than the burn-in are under-used by every model equally.
- **Few day blocks.** The test block has 7 day(s), so the day-block intervals rest on that many resampling units and are coarse.
- **Discretization convention.** The score assumes floor stamps with a uniform, independent sub-millisecond offset, and takes the recorded times as exact when updating the history state of every model. Stamps that are not floors, or batching in the matching engine, would shift probability between the 0 and 1 ms gaps for all models. The bucket table shows how much of any gap between models sits there.
- **Residual lattice structure.** Even with the tie truncation, a gap of 0 ms can only occur as a sell followed by a buy, which roughly halves its frequency relative to a continuous process. A flexible gap distribution can match that and an exponential kernel cannot, so part of any neural advantage in the 0 ms bucket is recording structure, not market dynamics.
- **Business-time profile** is estimated on 20 training days; drift in the intraday pattern between training and test is left in the data for every model.
