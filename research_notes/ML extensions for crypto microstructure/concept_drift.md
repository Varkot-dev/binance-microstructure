# Concept drift and distribution shift across market regimes: measurement and attribution

Verification legend used throughout:
- **[V]** = confirmed in this session from search results quoting the primary source or its abstract.
- **[R]** = recalled from the researcher's own knowledge of the paper; the URL/identifier is believed correct but the specific number or formula was NOT re-read this session (arxiv.org and ar5iv were unreachable from the sandbox, so no full texts could be fetched). Check before quoting in a final report.
- **[2nd]** = from a secondary summary, not checked against the primary.

Notation: source period A with joint P(x, y), target period B with joint Q(x, y); model f trained on A; loss l(f(x), y); R_P(f) = E_P[l], R_Q(f) = E_Q[l]. Project periods: 2023-06, 2023-07, 2024-07, 2025-07, 2026-07.

---

## 1. Taxonomy: covariate shift, label (prior) shift, concept shift, and the diagnostics that separate them

### Takeaway
All three shift types are different ways the factorisation P(x, y) = P(y|x) P(x) = P(x|y) P(y) can change; they are separated in practice by (a) label-free two-sample tests on X (covariate), (b) comparing class priors (label shift), and (c) testing whether P(y|x) differs after controlling for X, which needs labels in both periods (concept). Since the project has labels in every period, concept shift is directly testable, which is the fortunate case.

### Cited Findings
- Moreno-Torres et al. define dataset shift as P_train(x, y) != P_test(x, y) and split it into: **covariate shift** (P(x) changes, P(y|x) fixed; defined for X->Y problems), **prior probability shift** (P(y) changes, P(x|y) fixed; defined for Y->X problems), and **concept shift** (P(y|x) changes with P(x) fixed in X->Y problems, or P(x|y) changes with P(y) fixed in Y->X problems). The paper was written to unify inconsistent terminology across the literature. [R] — [Moreno-Torres, Raeder, Alaiz-Rodriguez, Chawla, Herrera 2012, "A unifying view on dataset shift in classification", Pattern Recognition 45(1):521-530](https://doi.org/10.1016/j.patcog.2011.06.019)
- Gama et al. distinguish **real concept drift** (change in p(y|X), with or without change in p(X)) from **virtual drift** (change in p(X) that does not affect p(y|X)), and classify drift by temporal pattern: sudden/abrupt, incremental, gradual, and reoccurring concepts; they also organise adaptive learners into memory, change-detection, learning, and loss-estimation modules. [R] — [Gama, Zliobaite, Bifet, Pechenizkiy, Bouchachia 2014, "A survey on concept drift adaptation", ACM Computing Surveys 46(4), Article 44](https://doi.org/10.1145/2523813)
- The Quinonero-Candela et al. edited volume is the standard book-length reference; it contains the Storkey chapter ("When training and test sets are different") that lists covariate shift, prior probability shift, sample selection bias, imbalanced data, domain shift, and source component shift as distinct mechanisms. [R] — [Quinonero-Candela, Sugiyama, Schwaighofer, Lawrence (eds.) 2009, "Dataset Shift in Machine Learning", MIT Press](https://mitpress.mit.edu/9780262170055/dataset-shift-in-machine-learning/)
- Label shift can be detected and corrected without target labels through the classifier's confusion matrix (Black Box Shift Estimation): solve C w = mu, where C is the source confusion matrix of predicted vs true class and mu is the target distribution of predictions; w estimates q(y)/p(y). [R] — [Lipton, Wang, Smola 2018, "Detecting and Correcting for Label Shift with Black Box Predictors", ICML 2018, arXiv:1802.03916](https://arxiv.org/abs/1802.03916)
- Zhang et al. list "changes in data quality, differences in specific covariate distributions, or changes in the relationship between label and features" as simultaneous candidate causes that must be attributed jointly rather than tested one at a time. [V] — [Zhang, Singh, Ghassemi, Joshi 2023, ICML, PMLR 202:41550-41578](https://proceedings.mlr.press/v202/zhang23ai.html)
- Empirical work on tabular benchmarks from the same group as DISDE argues that Y|X shifts, not X shifts, account for most real-world tabular degradation, and that methods built for covariate shift therefore help little. [R] (title confirmed [V]) — [Liu, Wang, Cui, Namkoong 2023, "On the Need for a Language Describing Distribution Shifts: Illustrations on Tabular Datasets" / "Rethinking Distribution Shifts", NeurIPS 2023 D&B, arXiv:2307.05284](https://arxiv.org/html/2307.05284v6)

### Inferences
- Diagnostic map for the project (labels available in every period):

| Shift | What changes | Label-free diagnostic | Labelled diagnostic |
|---|---|---|---|
| Covariate | P(x) | per-feature PSI / KS / W1; domain-classifier AUC between months | importance-reweighted source loss moves toward target loss |
| Label / prior | P(y) | BBSE on predictions | compare class frequencies directly, per symbol |
| Concept | P(y given x) | not identifiable without labels | residual gap after reweighting; refit-per-period coefficient tests; DISDE Y given X term; period x feature interaction terms |

- Next-trade sign has P(y) near 0.5 in every period by construction, so pure label shift is negligible for that target. The relevant "prior" quantity is instead the **sign-persistence rate** P(y_t = y_{t-1}), which the project already knows moved strongly between 2023 and 2026. Because lagged sign is a feature, that movement is a change in P(y | x) for the lagged-sign feature, i.e. concept shift, not label shift.
- For mid-direction with a three-class label (up / flat / down) and a fixed threshold, class balance will swing with tick size in basis points and volatility. That is label shift manufactured by the label definition. Either define the label in a scale-free way (e.g. move of at least one tick over a horizon measured in events) and report class frequencies per period, or use a binary label conditional on a move and report the "move rate" separately.
- "Concept shift" is always relative to the chosen feature set. A change in P(y|x) can be a covariate shift in an omitted variable z (relative tick size, spread in ticks, participant mix, fee tier). A useful test: add regime descriptors z to x and see whether the concept-shift component shrinks. If it does, the mechanism is "same physics, different operating point"; if not, the relationship itself changed.
- The existing project result (cross-sectional slope of sign-flip probability on trading activity, strong in 2023, absent in 2026) is a symbol-level concept shift statement. It can be formalised as flip_{s,t} = a_t + b_t log(activity_{s,t}) + e_{s,t} with a Wald test of b_2023 = b_2026 using symbol-clustered standard errors, and it predicts that any model leaning on activity-type features will show a large Y|X term.

### Gaps
- No full text of Moreno-Torres or Gama was re-read; the definitions above are standard but the wording is paraphrased from memory.
- The taxonomy assumes i.i.d. draws within a period. Trade-level data are strongly dependent, and none of the taxonomy papers address what "P(x)" means for a non-stationary process within a month.

---

## 2. Measurement tools: transfer matrices, per-feature divergences, classifier two-sample tests, WILDS / Wild-Time reporting

### Takeaway
The core artefact should be a period-by-period train/test performance matrix with a genuinely held-out diagonal, reported in the WILDS style (in-distribution vs out-of-distribution on the same footing), supplemented by per-feature divergences and one multivariate summary, the domain-classifier AUC. With millions of rows every significance test rejects, so all shift measures should be reported as effect sizes with symbol/day-clustered uncertainty, not p-values.

### Cited Findings
- **WILDS**: 10 datasets of real-world shifts; the benchmark's reporting convention is to give both in-distribution (ID) and out-of-distribution (OOD) performance, where the ID number comes from held-out data drawn from the training distribution, and to show that standard ERM models have large ID-OOD gaps that existing robustness methods do not close. [R] — [Koh, Sagawa, Marklund, et al. 2021, "WILDS: A Benchmark of in-the-Wild Distribution Shifts", ICML 2021, arXiv:2012.07421](https://arxiv.org/abs/2012.07421)
- **Wild-Time**: 5 datasets with gradual temporal shift (portraits, healthcare, news, paper categorisation among them); two protocols, **Eval-Fix** (train on everything before a fixed split time, test on everything after) and **Eval-Stream** (continual, test on the next K periods after each timestamp); 13 methods from domain generalisation, continual learning, self-supervised and ensemble learning benchmarked. Headline: "an average performance drop of 20% from in-distribution to out-of-distribution data", and "existing methods are unable to close this gap"; invariant-learning methods (CORAL-T, GroupDRO-T, IRM-T, LISA, mixup) did not clearly beat ERM. [V] for headline numbers and protocol names; method-level claim [2nd] — [Yao, Choi, Cao, Lee, Koh, Finn 2022, "Wild-Time: A Benchmark of in-the-Wild Distribution Shift over Time", NeurIPS 2022 Datasets and Benchmarks, arXiv:2211.14238](https://arxiv.org/abs/2211.14238); [NeurIPS proceedings page](https://papers.neurips.cc/paper_files/paper/2022/hash/43119db5d59f07cc08fca7ba6820179a-Abstract-Datasets_and_Benchmarks.html)
- **Classifier two-sample test (C2ST)**: pool samples from P and Q, label them 0/1, train a binary classifier on a train split and compute accuracy on a held-out split of size n_te. Under H0: P = Q the accuracy is approximately N(1/2, 1/(4 n_te)); the classifier's accuracy is an interpretable effect size and its feature importances show where the distributions differ. [R] — [Lopez-Paz and Oquab 2017, "Revisiting Classifier Two-Sample Tests", ICLR 2017, arXiv:1610.06545](https://arxiv.org/abs/1610.06545)
- **MMD**: MMD^2(P, Q) = E[k(x, x')] + E[k(y, y')] - 2 E[k(x, y)] for a characteristic kernel k; equals zero iff P = Q; the unbiased estimator is quadratic in sample size, and a linear-time variant exists. [R] — [Gretton, Borgwardt, Rasch, Scholkopf, Smola 2012, "A Kernel Two-Sample Test", JMLR 13:723-773](https://www.jmlr.org/papers/v13/gretton12a.html)
- **Shift detection in practice**: an empirical comparison of shift detectors found that two-sample testing on a dimensionality-reduced representation, in particular on the outputs of a trained classifier ("black-box shift detection") with univariate tests and Bonferroni correction, worked best, and that domain classifiers are useful for characterising which examples shifted. [R] — [Rabanser, Gunnemann, Lipton 2019, "Failing Loudly: An Empirical Study of Methods for Detecting Dataset Shift", NeurIPS 2019, arXiv:1810.11953](https://arxiv.org/abs/1810.11953)
- A discriminative (logistic) model that separates train from test directly yields importance weights, linking the domain classifier used for detection to the weights used for correction. [R] — [Bickel, Bruckner, Scheffer 2009, "Discriminative Learning Under Covariate Shift", JMLR 10:2137-2155](https://www.jmlr.org/papers/v10/bickel09a.html)

### Inferences
Formulas (standard definitions, written out for the report writer; not tied to a single citation):

- **Transfer matrix** M[i, j] = metric of model trained on period i evaluated on held-out data of period j. Derived quantities:
  - forward decay curve: M[2023, j] for j = 2023-07, 2024, 2025, 2026;
  - **staleness gap** at j: G_j = M[j, j] - M[2023, j] (how much a fresh model beats the old one on the same data);
  - **predictability change** at j: D_j = M[j, j] - M[2023, 2023] (how much the task itself got easier/harder);
  - identity: M[2023, 2023] - M[2023, j] = G_j - D_j. A raw drop of the 2023 model mixes "model is stale" with "market is less predictable for everyone"; only G_j measures staleness.
  - backward transfer M[2026, 2023] is not a deployable number but is diagnostic: if both off-diagonals are bad the relationship changed; if only the forward one is bad, 2023 contained patterns that later disappeared (consistent with a relationship "gone by 2026").
- **PSI** over B bins with source shares e_b and target shares a_b: PSI = sum_b (a_b - e_b) ln(a_b / e_b). This equals the symmetrised KL (Jeffreys) divergence of the binned distributions. The conventional thresholds (below 0.1 stable, 0.1 to 0.25 moderate, above 0.25 major) are industry rules of thumb from credit scoring with no sampling theory behind them; under no shift PSI is approximately (1/N + 1/M) times a chi-square with B - 1 degrees of freedom, so at N, M in the millions any real change clears a significance bar and the value must be read as an effect size. [R, Yurdakul and Naranjo 2020, Journal of Risk Model Validation; no URL verified]
- **KL**: KL(Q || P) = sum q ln(q / p); asymmetric, infinite when supports differ. **Jensen-Shannon**: JSD = 0.5 KL(P || M) + 0.5 KL(Q || M), M = (P + Q)/2; symmetric, bounded by ln 2, sqrt(JSD) is a metric. Prefer JSD over KL for binned microstructure features with empty bins.
- **Wasserstein-1 (1-D)**: W1 = integral |F_P(t) - F_Q(t)| dt = integral_0^1 |F_P^{-1}(u) - F_Q^{-1}(u)| du. It is in feature units, so standardise by the source IQR or compute on rank-transformed features to compare across features.
- **KS**: sup_t |F_P(t) - F_Q(t)|, bounded in [0, 1], scale-free; a good default per-feature effect size.
- **Domain-classifier AUC**: train LightGBM/logistic to predict period from x; AUC 0.5 = indistinguishable, 1.0 = disjoint support. Convert to density ratio with w(x) = (n_A / n_B) * pi(x) / (1 - pi(x)), pi(x) = P(period = B | x). This single model gives the detection statistic, the per-feature blame (its importances), and the weights for Section 3.
- Practical cautions specific to this dataset:
  - Features in raw units (price, quantity, spread in quote currency, symbol id) make the domain AUC trivially about 1 and weights degenerate. Use scale-free features (spread in ticks, imbalance ratios, signed-flow z-scores, inter-trade times relative to the symbol's median).
  - Run every divergence three ways: pooled, within-symbol (then summarise the distribution across the 100+ symbols), and on symbol-level aggregates. Pooled divergences mostly measure change in symbol mix.
  - Use the **June 2023 vs July 2023 pair as the null-ish reference**: it gives the size of "ordinary" one-month drift for every statistic. Report later-year divergences as multiples of it. The three July-to-July gaps hold calendar month fixed, which controls coarse seasonality.
  - Uncertainty: block bootstrap over (symbol, day) cells, or leave-one-day-out; never treat trades as i.i.d.
  - CPU budget: PSI/KS/W1 from quantile sketches are O(n); domain classifier on about 100k to 500k subsampled rows per period; MMD only on 2k to 5k subsamples or with random Fourier features, and it adds little beyond the domain classifier.
- WILDS-style table to adopt: rows = model (logit, GBDT), columns = ID held-out 2023, OOD 2024, OOD 2025, OOD 2026, each with mean and worst-decile symbol, plus the in-period "oracle" M[j, j].

### Gaps
- Exact per-dataset Eval-Fix / Eval-Stream tables from Wild-Time were not retrieved.
- No source found that validates PSI thresholds for high-frequency financial features; treat thresholds as uncalibrated here.
- None of the cited two-sample tests has a null distribution valid for serially dependent tick data; block-bootstrap calibration is my recommendation, not a cited result.

---

## 3. Attribution: reweighting, performance decompositions, Shapley-based methods, importance comparisons, per-period refits

### Takeaway
The cleanest attribution for a small project is a two-layer approach: (1) a domain-classifier-based decomposition of the performance drop into X-shift and Y|X-shift components (simple importance reweighting, or better the DISDE three-term version that avoids exploding weights), and (2) an interpretable per-period refit of a low-dimensional logistic model with coefficient-equality tests to say which feature-label relationships moved. SHAP of a fixed model compared across periods cannot detect concept shift by itself and should be presented only as a covariate-shift view.

### Cited Findings
- **Importance weighting under covariate shift**: if P(y|x) is unchanged, the target risk equals the weighted source risk, R_Q(f) = E_P[w(x) l(f(x), y)] with w(x) = q(x)/p(x); weighted maximum likelihood is consistent for the target-optimal parameter under misspecification, and a flattened weight w^lambda (0 <= lambda <= 1) trades bias for variance. [R] — [Shimodaira 2000, "Improving predictive inference under covariate shift by weighting the log-likelihood function", Journal of Statistical Planning and Inference 90(2):227-244](https://doi.org/10.1016/S0378-3758(00)00115-4)
- **Importance-weighted cross-validation** gives an unbiased estimate of target risk under covariate shift and is the standard way to do model selection for the target period using source labels only. [R] — [Sugiyama, Krauledat, Muller 2007, "Covariate Shift Adaptation by Importance Weighted Cross Validation", JMLR 8:985-1005](https://www.jmlr.org/papers/v8/sugiyama07a.html)
- **DISDE (Cai, Namkoong, Yadlowsky)**: decomposes the performance drop into three terms: "harder but frequently seen training examples" (X shift from P_X to a shared distribution S_X), "changes in the relationship between features and outcomes" (Y|X shift evaluated on S_X), and "poor performance on examples infrequent or unseen during training" (X shift from S_X to Q_X). Y|X is compared only on covariate values common to both periods because "comparing the relationship Y|X is only meaningful in regions of shared support"; the terms are estimated "by reweighting data from P and Q to approximate samples from the shared distribution". Demonstrated on census employment prediction and satellite imagery. Code: github.com/namkoong-lab/disde. [V] for structure and quotes — [Cai, Namkoong, Yadlowsky 2023, "Diagnosing Model Performance Under Distribution Shift", arXiv:2303.02011; published in Operations Research 2025](https://arxiv.org/abs/2303.02011); [INFORMS page](https://pubsonline.informs.org/doi/10.1287/opre.2023.0217)
- A later paper adapting DISDE writes the shared distribution as p_S(x) proportional to p(x) q(x) / (p(x) + q(x)). [2nd; the exact equation should be checked against Section 2 of the original] — [third-party adaptation, arXiv:2609.13148](https://arxiv.org/html/2609.13148v1)
- **Zhang et al.**: treat the candidate shifting distributions (marginals and conditionals in a causal graph) as players in a cooperative game; "the value of a set of distributions [is] the change in model performance when only this set of distributions has changed between environments", computed by an importance-weighting estimator, and each distribution's contribution is its Shapley value. Validated on synthetic, semi-synthetic and real case studies. [V] — [Zhang, Singh, Ghassemi, Joshi 2023, "'Why did the Model Fail?': Attributing Model Performance Changes to Distribution Shifts", ICML 2023, PMLR 202:41550-41578, arXiv:2210.10769](https://proceedings.mlr.press/v202/zhang23ai.html)
- **Budhathoki et al.**: factorise the joint into causal mechanisms P(X_j | parents_j), measure the change in the joint (KL divergence in the arXiv version) and attribute it to changed mechanisms with Shapley values; case study on the male/female income distribution gap. Attributes change in a *distribution or its summary*, not specifically a model's loss, and needs a causal graph. [V] — [Budhathoki, Janzing, Bloebaum, Ng 2021, "Why did the distribution change?", AISTATS 2021, PMLR 130:1666-1674, arXiv:2102.13384](https://proceedings.mlr.press/v130/budhathoki21a.html)

### Inferences
**(a) Two-term reweighting decomposition (cheapest).** With weights from the domain classifier normalised to mean 1 on the 2023 held-out set:

- total drop: Delta = R_Q(f) - R_P(f)
- covariate component: Delta_X = E_P[w l] - E_P[l]
- residual / concept component: Delta_{Y|X} = E_Q[l] - E_P[w l]

Report the effective sample size ESS = (sum w)^2 / sum w^2 and clip weights (e.g. at the 99th percentile), because Delta_X is only trustworthy where 2023 covers the later period's feature space. If the domain AUC is above roughly 0.9, the weighted estimate is dominated by a handful of rows and this decomposition should not be reported without the DISDE variant.

**(b) DISDE three-term decomposition (recommended).** Let mu_P(x) = E_P[l | X = x], mu_Q(x) = E_Q[l | X = x], and pi(x) = P(sample from Q | x) from a class-balanced domain classifier. With S_X proportional to p q / (p + q), the density ratios are s/p proportional to pi(x) and s/q proportional to 1 - pi(x) (my derivation from the shared-distribution form above; verify against the paper). Then:

- R_Q - R_P = [E_S(mu_P) - E_P(mu_P)] + [E_S(mu_Q) - E_S(mu_P)] + [E_Q(mu_Q) - E_S(mu_Q)]
- term 1, "X shift P to S": estimated as sum_P pi_i l_i / sum_P pi_i minus mean_P l;
- term 2, "Y|X shift on shared support": sum_Q (1 - pi_i) l_i / sum_Q (1 - pi_i) minus sum_P pi_i l_i / sum_P pi_i;
- term 3, "X shift S to Q": mean_Q l minus sum_Q (1 - pi_i) l_i / sum_Q (1 - pi_i).

Weights are bounded in [0, 1] so nothing explodes; cost is one LightGBM domain classifier per period pair plus the per-row losses already computed. Interpretation for this project: term 2 large = the feature-to-label map changed (concept); term 1 large = later data sit in regions that were already hard in 2023; term 3 large = later data sit in regions 2023 never saw (new symbols, new tick regimes). Cross-fit the domain classifier (fit on folds split by symbol-day) and bootstrap over symbol-days for intervals.

**(c) Shapley-style attribution (optional, coarse-grained).** A full Zhang et al. analysis needs a causal graph over features. A tractable approximation is a three- or four-player game over feature *blocks* (e.g. order-flow history block, book-state block, activity/volatility block, label mechanism Y|X), where the value of a coalition is the loss change when only those blocks' distributions are swapped via reweighting. With 4 players this is 16 coalition evaluations. Budhathoki et al. is available off the shelf in DoWhy's `gcm.distribution_change` [R] but targets the distribution of a variable rather than model loss; lower priority.

**(d) Importance comparisons across periods; what each one can and cannot show.**
- SHAP of the *fixed 2023 model* on 2023 vs 2026 inputs: the model function is unchanged, so differences in mean |SHAP| reflect only that inputs moved (covariate shift). It is label-free and cannot reveal concept shift.
- Permutation importance of the fixed 2023 model measured in *loss on period j*: uses labels of j, so a feature whose importance collapses (or turns negative, meaning shuffling it helps) is a feature whose relationship to the label broke. This is the cheap concept-shift detector per feature.
- SHAP or gain importance of *separately refit* models per period: shows what a fresh learner finds useful; compare rank correlation (Spearman) of importances across periods and the partial-dependence shapes for the top features.
- Loss-SHAP (attributing loss rather than output) on the fixed model across periods is the principled version of the second bullet but is expensive on CPU; permutation on a subsample suffices.

**(e) Per-period refit with standard errors (the interpretable anchor).** Fit the same low-dimensional logistic model per period (standardise features within period-symbol so coefficients are comparable), or equivalently one pooled model with period x feature interactions:

- logit P(y = 1) = sum_k beta_{k,t} x_k; test H0: beta_{k,2023} = beta_{k,j} with z = (b_j - b_2023) / sqrt(se_j^2 + se_2023^2), standard errors clustered by symbol and day (or a symbol-day block bootstrap). Joint Wald/Chow-type test across all k. Apply a multiplicity correction across features.
- **Oaxaca-Blinder style split** of the change in the mean linear predictor (or of the change in fitted probability): (xbar_j - xbar_2023)' beta_2023 ["endowment" = covariate part] + xbar_j' (beta_j - beta_2023) ["coefficient" = concept part]. This is the regression analogue of (a) and gives a per-feature attribution for free. [classic econometrics, Oaxaca 1973 / Blinder 1973 / Chow 1960; no URL verified]
- Do the same at symbol level: fit per symbol per period and study the cross-section of coefficient changes against symbol traits (relative tick size, spread in ticks, volume rank). That directly ties ML degradation to the project's existing cross-sectional result.

**(f) Omitted-regime-variable test.** Re-run (b) after appending symbol-period descriptors (tick size in bps, median spread in ticks, trades per second, share of single-tick-spread time). If term 2 shrinks materially, the "concept shift" is better described as a shift in operating regime that a richer model could have conditioned on.

### Gaps
- The exact estimator equations and asymptotic variance formulas of DISDE were not re-read; the weight forms in (b) are derived, not quoted.
- No paper was found applying DISDE, Zhang et al., or Budhathoki et al. to limit-order-book or trade-sign prediction; the application here would be novel but unvalidated.
- All reweighting methods assume the feature set captures everything that changed in X; with dependent tick data the nominal standard errors from these papers do not apply.

---

## 4. Finance-specific evidence: alpha decay, non-stationary microstructure, LOB model degradation, crypto regime change

### Takeaway
The literature is split: Sirignano and Cont claim a universal, temporally stable price-formation map in US equities, while LOBCAST documents large drops on newer data and Briola et al. show predictability is conditional on microstructure (tick-size regime); the only crypto-specific evidence found (Bieganowski and Slepaczuk 2026) reports cross-asset stability of feature effects on Binance perpetuals. I found no study that measures year-over-year decay of trade-sign or mid-direction models on Binance perpetuals, so the project's question is open.

### Cited Findings
- **Alpha decay after publication**: McLean and Pontiff study "the out-of-sample and post-publication return predictability of 97 variables" and interpret the decline as investors learning about mispricing from publications [V]. The published abstract's figures, as I recall them, are that portfolio returns are 26% lower out-of-sample and 58% lower post-publication, implying about 32% attributable to publication-informed trading [R; the search could not confirm these, and secondary coverage of earlier drafts cites about 35% decay for 82 to 95 characteristics, so quote only after checking the JF version]. — [McLean and Pontiff 2016, "Does Academic Research Destroy Stock Return Predictability?", Journal of Finance 71(1):5-32, DOI 10.1111/jofi.12365](https://www.gwern.net/doc/economics/2016-mclean.pdf)
- **Universality and stability claim**: a deep model trained on pooled US equity quotes and trades to predict price-move direction "exhibit[s] a remarkably stable out-of-sample prediction accuracy across time, for a wide range of stocks from different sectors", outperforms asset-specific linear and nonlinear models, and the results "also hold for stocks which are not part of the training sample". [V, abstract] The details I recall (about 500 Nasdaq stocks, 2014 to early 2017, accuracy holding for test periods many months after training) are [R] and were not confirmed. — [Sirignano and Cont 2019, "Universal features of price formation in financial markets: perspectives from deep learning", Quantitative Finance 19(9):1449-1459, arXiv:1803.06917](https://arxiv.org/abs/1803.06917v1)
- **LOBCAST**: fifteen deep-learning LOB models re-implemented; best model BiN-CTABL reaches 92.1% F1 on FI-2010 at horizon k = 10 (87.7% at k = 5); on newer LOBSTER-derived datasets (LOB-2021 / LOB-2022) it "experiences an average decrease of approximately 19.6% in F1-Score", giving a "generalizability score of 73.5%"; "all models exhibit a significant performance drop when exposed to new data". [V via search snippets of the paper] A secondary summary says F1 fell to 48 to 61% [2nd, unreconciled with the 19.6% figure]. Authors are Prata, Masi, Berti, Arrigoni, Coletta, Cannistraci, Vyetrenko, Velardi, Bartolini (one search summary misattributed it to Briola). — [Prata et al. 2023/2024, "LOB-Based Deep Learning Models for Stock Price Trend Prediction: A Benchmark Study", arXiv:2308.01915; Artificial Intelligence Review 57:116](https://link.springer.com/article/10.1007/s10462-024-10715-4)
- **Microstructure-conditional predictability**: DeepLOB applied to 15 NASDAQ stocks over a three-year window; stocks grouped as small-, medium- and large-tick; large-tick stocks are the most predictable and tick size is proposed as a proxy for predictability; high forecasting power does not necessarily yield actionable signals; standard ML metrics are inadequate, and the authors propose a metric based on the probability of correctly forecasting complete transactions; LOBFrame code released. [V] Reported MCC of about 0.29 (large-tick) vs 0.11 (small-tick) at H = 10, with small-tick near zero at H = 100 [2nd]. — [Briola, Bartolucci, Aste 2024/2025, "Deep Limit Order Book Forecasting: A microstructural guide", Quantitative Finance 25(7):1101-1131, arXiv:2403.09267](https://pmc.ncbi.nlm.nih.gov/articles/PMC12315853/)
- **Crypto, cross-asset stability**: CatBoost with a direction-aware GMADL objective on Binance Futures perpetual order books and trades at 1-second frequency, 2022-01-01 to 2025-10-12, for BTC, LTC, ETC, ENJ, ROSE; feature rankings and SHAP partial effects are reported as similar across assets despite different liquidity; taker and maker backtests diverged sharply during a major flash crash. [V, abstract level] — [Bieganowski and Slepaczuk 2026, "Explainable Patterns in Cryptocurrency Microstructure", arXiv:2602.00776](https://arxiv.org/abs/2602.00776)
- **Order-flow features in equities**: the standard reference for deep models on multi-level order-flow imbalance uses 115 Nasdaq stocks. [V for dataset size] — [Kolm, Turiel, Westray 2023, "Deep order flow imbalance: Extracting alpha at multiple horizons from the limit order book", Mathematical Finance](https://www.researchgate.net/publication/372568099_Deep_order_flow_imbalance_Extracting_alpha_at_multiple_horizons_from_the_limit_order_book)
- **Binance tick-size changes are frequent and symbol-specific**: batches of USD-M perpetual tick-size updates are documented for 2023-08-29, 2024-09-20 (seven contracts incl. JOE, KEY, ILV), 2024-11-04, 2024-11-28, 2025-09-19 (AVNTUSDT, SUIUSDC from 0.00001 to 0.0001), 2025-10-17, 2025-12-08, 2025-12-15, 2025-12-22, and 2026-03-05 (twelve contracts incl. MYX). The latest tick size is exposed through GET /fapi/v1/exchangeInfo. [V] — [Binance announcement 2023-08-29](https://www.binance.com/en/support/announcement/updates-on-tick-size-for-multiple-usd%E2%93%A2-m-perpetual-futures-contracts-2023-08-29-8764f0d84e6b4c7abc97f036bb6f9ebc); [2024-09-20](https://www.binance.com/en-AE/support/announcement/detail/fa192e78242d4d96be9562ab7d76a10a); [2025-10-17](https://www.binance.com/en-AE/support/announcement/detail/fd11627dc39046b791b7504a2f08e3fc); [2025-12-22](https://www.binance.com/en/support/announcement/1cd08ee9bafd40a2a94e8dfc58408f82); [2026-03 report](https://en.bloomingbit.io/feed/news/107025)
- **Venue share and participant mix**: Kaiko reported Binance's share of BTC and ETH perpetual volume falling from 64% to 55% during 2023; a 2025-era Kaiko-sourced article puts perpetuals at more than 60% of BTC trading activity and Hyperliquid at roughly 10 to 15% of perpetual volume. [V via snippets; the second is 2nd] — [Kaiko Research, "summer trends" (2023)](https://research.kaiko.com/insights/summer-trends); [TokenPost citing Kaiko](https://tokenpost.com/news/insights/19074); [Kaiko, "Liquidity Flywheel Drives Binance to 300 Million Users" (Dec 2025; commissioned by Binance)](https://research.kaiko.com/reports/liquidity-flywheel-drives-binance-to-300-million-users)

### Inferences
- The three equity papers are not actually in contradiction once conditioning is considered: Sirignano-Cont pool hundreds of stocks (so the model sees many operating regimes) and test within a few years; LOBCAST trains on five Finnish stocks from 2010 and tests on US stocks a decade later (extreme covariate and concept shift at once); Briola et al. show the map depends on tick regime. A reasonable prior for this project: a pooled 100+ symbol model with scale-free features should transfer better than per-symbol models, and residual degradation should concentrate in symbols whose tick regime (spread in ticks) changed.
- The Bieganowski-Slepaczuk result is cross-asset, not cross-time; stability of SHAP shapes across five coins does not establish stability across 2023 to 2026. The project's transfer matrix would fill that gap.
- Tick-size changes give a quasi-experimental handle: symbols whose tick changed between two sampled months vs symbols whose tick did not. If the degradation of the 2023 model is concentrated in the changed-tick group (after measuring features in ticks), that is direct evidence for a mechanism. Even without an exchange-initiated change, a large price move changes tick size in bps; compute relative tick = tick / price per symbol-month and use the change in it as a continuous treatment.
- The alpha-decay literature suggests a second mechanism besides mechanical regime change: predictable patterns get arbitraged away as participants professionalise. That predicts D_j < 0 (even a freshly trained model finds less signal later), which is distinguishable from staleness (G_j > 0 with D_j near 0) using the Section 2 identity. The project's "flip probability vs activity relationship vanished" finding is suggestive of the former.
- 2023-06 and 2023-07 sit shortly after the US regulatory actions against Binance (June 2023) and after the end of zero-fee BTC spot trading (March 2023) [R; dates not verified this session]; the 2023 baseline may itself be an unusual liquidity regime, so "2023 vs later" should not be read as "normal vs changed".

### Gaps
- No study found that quantifies temporal decay of next-trade-sign or short-horizon direction models on Binance USDT-M perpetuals, or any crypto venue, over multi-year gaps.
- No quantitative source retrieved on changes in Binance perpetual market-maker composition, depth, or fee/VIP programme changes for 2024 to 2026; Kaiko depth figures are in charts not text, and one key report is exchange-commissioned.
- My knowledge and the searches do not cover market-structure events between mid-2026 and the July 2026 sample; any July 2026 specific regime facts (fee changes, matching-engine changes, new order types) must be checked against Binance announcements.
- McLean-Pontiff headline percentages and Sirignano-Cont sample details remain unverified against full texts. Exact LOBCAST per-horizon tables and LOBSTER stock/period lists were not retrieved.

---

## 5. Mitigations worth testing and how to report the benefit of retraining honestly

### Takeaway
Benchmarks suggest that sophisticated shift-robust methods rarely beat plain ERM under temporal shift, so the credible mitigation experiments are simple ones: retrain on recent data, recency-weight, pool, and importance-weight, each compared at matched training size against both the stale model and an in-period oracle. With only five disjoint months, "rolling vs expanding" reduces to "latest month only vs all months so far vs weighted pool", and this limitation should be stated.

### Cited Findings
- On Wild-Time, none of 13 methods (domain generalisation, continual learning, self-supervised, ensembles) closes the roughly 20% average ID-to-OOD gap, and invariant-learning methods do not clearly beat ERM. [V / 2nd as in Section 2] — [Yao et al. 2022, arXiv:2211.14238](https://arxiv.org/abs/2211.14238)
- WILDS finds the same pattern for domain and subpopulation shift: ERM baselines are hard to beat with existing robustness algorithms. [R] — [Koh et al. 2021, arXiv:2012.07421](https://arxiv.org/abs/2012.07421)
- Importance weighting is the textbook correction when only P(x) shifts, with a bias-variance trade-off controlled by flattening the weights; importance-weighted CV is the matching model-selection tool. [R] — [Shimodaira 2000](https://doi.org/10.1016/S0378-3758(00)00115-4); [Sugiyama et al. 2007](https://www.jmlr.org/papers/v8/sugiyama07a.html)
- A widely cited empirical-asset-pricing protocol refits models once a year on an expanding training window with a rolling validation window, rather than continuously, citing computational cost. [R] — [Gu, Kelly, Xiu 2020, "Empirical Asset Pricing via Machine Learning", Review of Financial Studies 33(5):2223-2273](https://doi.org/10.1093/rfs/hhaa009)
- Adaptive learners in the drift literature are categorised by how they forget (sliding windows, fading factors / instance weighting) and whether adaptation is blind (periodic) or informed (triggered by a detector). [R] — [Gama et al. 2014](https://doi.org/10.1145/2523813)

### Inferences
Candidate arms for evaluation on each later month j (all evaluated on the same held-out slice of j, with any "fresh" training data taken from strictly earlier time):

1. **Stale**: train on 2023 only (June + July), never updated.
2. **Latest-only ("rolling")**: train on the most recent available earlier month.
3. **Expanding / pooled**: train on all earlier months, equal weight.
4. **Recency-weighted pool**: sample weight proportional to exp(-age_years / tau), tau in {0.5, 1, 2}; chosen on validation from the latest earlier month only.
5. **Importance-weighted stale**: 2023 model refit with domain-classifier weights toward j's feature distribution (label-free adaptation; tests whether fixing covariate shift alone helps). If this recovers little while arm 2 recovers a lot, that is independent evidence of concept shift, consistent with Section 3.
6. **Within-month online update**: warm-start from the stale model and update on the first k days of month j (SGD logistic or LightGBM continued training), test on the remaining days; sweep k to get an adaptation-speed curve ("how many days of fresh data buy back the gap").
7. **In-period oracle**: train on the first part of month j, test on the last part. Upper bound, not deployable for a cross-year claim, but it defines the recoverable gap.

Honest-reporting checklist:
- **Held-out diagonal.** Every cell, including same-month cells, uses a chronological split inside the month (e.g. first about 21 days train, embargo of at least one day, last about 7 days test) so ID and OOD numbers are comparable. Never compare in-sample 2023 fit against out-of-sample 2026.
- **Match training size.** A pooled model has more rows than a single-month model. Subsample so arms 1 to 4 see equal row counts, and separately report the full-data version; otherwise "retraining helps" is confounded with "more data helps".
- **Separate staleness from lost predictability.** Report M[2023, 2023], M[2023, j], M[j, j] and the two derived quantities G_j and D_j from Section 2. State the benefit of retraining as the fraction of G_j recovered by a deployable arm: (M[arm, j] - M[stale, j]) / (M[oracle, j] - M[stale, j]).
- **Skill over a period-specific naive baseline.** For next-trade sign the naive rule "repeat the last sign" has accuracy 1 - flip probability, which itself moved between 2023 and 2026. Report skill relative to that baseline evaluated in the same period (and relative to the class prior for mid direction), preferably in log-loss or Brier terms plus AUC and MCC; raw accuracy changes will otherwise mostly restate the known descriptive result.
- **Fixed symbol panel plus separate new-listing analysis.** Main results on the intersection of symbols present in all five months; new symbols as a separate out-of-universe test, to keep temporal shift apart from composition shift.
- **Uncertainty at the right level.** Compute metrics per symbol-day, then bootstrap symbol-days (or cluster by symbol) for confidence intervals; show the distribution of per-symbol degradation, not only the pooled number; paired comparisons of arms on identical test rows.
- **No peeking.** Hyperparameters, feature choices and tau fixed using data strictly before the test month; one pre-specified primary metric and horizon; report all horizons tried.
- **Calibration drift.** Report calibration slope/intercept of the stale model per period; a model can keep its ranking ability (AUC) while its probabilities drift, and recalibration alone (two parameters on a few days of data) is the cheapest mitigation and a useful baseline arm.
- **Economic caveat.** Following Briola et al., classification metrics do not establish tradability; if any economic claim is made, state fees and that no execution simulation was run.

With five snapshot months the design cannot distinguish gradual from abrupt change between snapshots, cannot estimate an optimal retraining cadence finer than one year, and cannot study recurring regimes; say so explicitly.

### Gaps
- No finance-specific source found with a controlled comparison of rolling vs expanding vs recency-weighted training for tick-level direction models; the arms above are a design proposal, not replication of a published protocol.
- Whether Gu-Kelly-Xiu-style annual refits are adequate at microstructure frequencies is not addressed by any source found.

---

## 6. Adaptive drift detectors (ADWIN, DDM, Page-Hinkley) and their fit for a month-level regime comparison

### Takeaway
ADWIN, DDM and Page-Hinkley are sequential change-point detectors for continuous streams where the change time is unknown; for comparing disjoint months separated by a year, the change point is fixed by the sampling design, so batch two-sample and transfer analyses (Sections 2 and 3) are the right primary tools. The detectors have a legitimate secondary role only as a within-month stability check on daily aggregated error series.

### Cited Findings
- **ADWIN** keeps a variable-length window of recent values and, whenever two sub-windows have means that differ by more than a threshold, drops the older part; it comes with false-positive and false-negative guarantees based on a Hoeffding-type bound and takes a numeric stream. delta is a confidence parameter with common default 0.002 (smaller delta = more conservative; one library's docs state the opposite, which is wrong for the cut rule). [V via CapyMOA, datadriftR, menelaus docs; these are other libraries implementing the same algorithm] — [CapyMOA drift detection notebook](https://capymoa.org/notebooks/drift_detection.html); [menelaus change-detection examples](https://menelaus.readthedocs.io/en/dev/examples/change_detection/change_detection_examples.html); original: [Bifet and Gavalda 2007, "Learning from Time-Changing Data with Adaptive Windowing", SIAM SDM](https://doi.org/10.1137/1.9781611972771.42) [R]
- **DDM** monitors the error rate of an online classifier on a binary 0/1 error stream; common defaults are a 30-instance warm-up, warning level 2 and out-of-control level 3 (standard deviations above the running minimum). [V via datadriftR] — [datadriftR reference manual](https://cran.nics.utk.edu/cran/web/packages/datadriftR/refman/datadriftR.html); original: Gama, Medas, Castillo, Rodrigues 2004, "Learning with Drift Detection", SBIA [R, no URL verified]
- **Page-Hinkley** takes a numeric stream and has two jointly tuned parameters, a tolerance delta and an alarm threshold (example settings in other libraries: delta 0.01 with threshold 15; delta 0.05 with threshold 50), plus a minimum number of instances before testing. [V via menelaus and datadriftR] — [menelaus examples](https://menelaus.readthedocs.io/en/dev/examples/change_detection/change_detection_examples.html); [datadriftR vignette](https://archive.linux.duke.edu/cran/web/packages/datadriftR/vignettes/datadriftR-intro.html)
- River exposes these as `river.drift.ADWIN`, `river.drift.PageHinkley`, and `river.drift.binary.DDM` / `EDDM` / `HDDM_A` / `HDDM_W`, plus `river.drift.KSWIN`. [R; River's own documentation could not be retrieved by search this session, so parameter names and defaults should be read from the docs directly] — [River API reference, drift module](https://riverml.xyz/latest/api/drift/ADWIN/)
- The drift-adaptation survey treats detectors as the "informed adaptation" trigger inside an online learner, i.e. their purpose is to decide *when* to retrain or forget, not to quantify or explain a known difference between two batches. [R] — [Gama et al. 2014](https://doi.org/10.1145/2523813)

### Inferences
Decision rules (standard forms, from memory [R]):
- ADWIN: for a split of window W (length n) into W0, W1 with lengths n0, n1 and means m0, m1, cut if |m0 - m1| > eps_cut, where eps_cut = sqrt( (1 / (2 m)) ln(4 / delta') ), m = harmonic mean of n0 and n1, delta' = delta / n.
- DDM: with running error rate p_i and s_i = sqrt(p_i (1 - p_i) / i), track the minimum of p + s; warning when p_i + s_i >= p_min + 2 s_min, drift when p_i + s_i >= p_min + 3 s_min.
- Page-Hinkley: m_T = sum_{t<=T} (x_t - xbar_t - delta), M_T = min_{t<=T} m_t; alarm when m_T - M_T > lambda.

Why they are a poor primary tool here:
- **Known change point.** The data are five disjoint months with gaps of one month to one year. Concatenating them and running a detector will fire at the seams, which says nothing a two-sample comparison does not say better and with an effect size.
- **Sample size.** With 10^6 to 10^8 trades per symbol-month, ADWIN's bound shrinks so far that economically negligible changes in error rate (and ordinary intraday seasonality, funding-time effects, news bursts) trigger continual detections. Detection counts then measure stream length and volatility clustering, not regime change.
- **Dependence.** All three assume independent (DDM: Bernoulli) observations. Prediction errors on consecutive trades are strongly autocorrelated (order splitting, bursts), inflating false alarms.
- **No attribution.** A detector on the error stream cannot say whether X or Y|X moved.

Where they are reasonable (optional appendix-level analysis):
- Aggregate to one value per symbol per hour or per day (error rate or log-loss of the fixed 2023 model) and run Page-Hinkley or ADWIN on that coarse series within each month. A month with zero within-month alarms on daily data supports treating it as a single regime; a month with alarms flags a heterogeneous snapshot (e.g. a crash day) that should be reported with and without the affected days.
- As the trigger in mitigation arm 6 of Section 5 ("retrain when the detector fires" vs "retrain on a fixed schedule"), run within a month. This is the use the detectors were designed for, but one month gives few events, so expect low power.
- A simpler and more transparent alternative with the same purpose: plot daily metric of the stale model with block-bootstrap bands and a CUSUM chart; or apply the Section 2 two-sample tools to week 1 vs week 4 of the same month as a within-month drift reference.

### Gaps
- River's actual parameter names and defaults were not verified (search returned other libraries only; riverml.xyz was not fetched).
- No source found evaluating ADWIN / DDM / Page-Hinkley on tick-level financial prediction errors; the false-alarm argument above is reasoning from the detectors' assumptions, not a cited empirical result.
