# Which project ideas are new? (summary of the novelty research)

Four reports in this folder check academic papers, products and open-source work for each
idea. Most outside claims come from search excerpts (arXiv, SSRN and several vendor sites
were blocked from the research machine), so read the cited source before relying on any
claim in writing.

## Licensing constraint (applies to every idea)

data.binance.vision data is licensed **CC BY-NC-SA 4.0** (verified): research, coursework,
open datasets and free public tools are fine if released under the same licence; anything
sold or built into a paid product needs a commercial licence from Binance or other data.

## Ratings

| idea | verdict | closest prior work | what makes ours new |
|---|---|---|---|
| Part A findings: rising sign predictability 2023 to 2025; tick size causes sign persistence | **open** | order-splitting theory; tick-size studies measure spreads and depth, not sign persistence | the trend itself, and 35 natural experiments on sign persistence |
| Trading before Binance **delisting** announcements (tick data) | **open** | none found | first test; shorting before delistings; pre-registered |
| Trading before Binance **listing** announcements | partly done | Felez-Vinas, Johnson and Putnins (hourly, Coinbase listings) | Binance futures tick data, pre-registration, public-warning controls |
| Collusion test after tick changes (price clustering on the old tick) | **open, but hard** | simulations only (Calvano; Dou, Goldstein and Ji; Cartea, Chang and Penalva) | first empirical crypto test; quotes cover 2023-05 to 2024-04 only |
| Hyperliquid skill versus luck | partly done | Zhai 2026 (rank persistence, no luck adjustment); Polymarket skill studies | bootstrap with common shocks, false discovery rate, value added, out of sample, systematic event test |
| Open survivorship-free Binance futures dataset | partly done | paid vendors; free availability packages | real trading dates, rename and reuse map, ghost files flagged |
| Delisting-risk ranking | open as a product | coin-death papers, not Binance futures | first public forecast; edge over the volume rule is thin |
| Live "leak score" monitor for announcements | partly done | private surveillance vendors | public, calibrated, per announcement, false-positive rates, no naming |
| Fragility and liquidation cascades | partly done | several 2025-10-10 event studies | a 2023 to 2026 panel linking order slicing to depth recovery |
| Crypto 0DTE options | not feasible for free | Deribit expiry-day study | none on free data |
| Macro (FOMC, CPI) events | done for prices | many | depth and order-sign memory around events may be open |

## Data warning found during the research

Binance's depth snapshots for BTCUSDT show the bid side frozen at exactly 17.654 BTC in the
-1% to -3% bands from 2025-10-10 19:15 UTC through at least 2025-10-15. Used naively, it
looks like a bid-depth collapse before the crash. Any fragility work must screen for
frozen values first.

## Startup view

Only ideas with a clear buyer: delisting alerts (market makers, token projects), leak
forensics for exchanges and issuers, fragility or liquidity-risk monitoring. All need a
data source licensed for commercial use, or a Binance licence. A free public track record
(published, hashed lists) is the right first step before charging anyone.
