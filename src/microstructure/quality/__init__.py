"""Data-quality screens for Binance public archive files (liquidation-cascades project P1).

`bookdepth` implements research/liquidations/bookdepth_mask_v2.txt (primary) and
bookdepth_mask_v1_DRAFT.txt; `metrics` implements research/liquidations/metrics_screen_v1.txt.
The research scripts check the sha256 of those texts before calling anything here.
"""
