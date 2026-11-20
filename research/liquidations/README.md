# Liquidation cascades: does the market warn you before it breaks?

Status: planning. Nothing has been run yet.

## The question

Crypto futures let traders borrow heavily. When the price moves against a heavily borrowed
position, the exchange closes it by force (a liquidation). That forced selling pushes the
price further, which liquidates the next trader, and so on: a cascade. On 10 October 2025 this
wiped out billions of dollars of positions within hours.

This project asks two things:

1. **Is there a warning?** In the hours before a cascade, does the market get visibly fragile,
   for example thinner order books, a one-sided build-up of leveraged positions, or order flow
   that keeps pushing the same way?
2. **Who gets hurt, and where?** Do crashes run deeper in contracts where traders were more
   heavily borrowed, and does the depth of the order book come back more slowly in markets
   where large orders are sliced into many small ones?

## Why it is worth doing

Several studies describe the October 2025 crash itself. What is missing is a panel across
2023 to 2026 and hundreds of contracts that ties fragility to things this repo has already
measured, such as order splitting and trade-direction memory
([research/novelty/SUMMARY.md](../novelty/SUMMARY.md)).

## Free data

All from data.binance.vision, the same source as the rest of the repo:

| Data | What it shows |
|---|---|
| Trades | Every trade, to the millisecond |
| Order book depth snapshots | How much is waiting to be bought or sold within 1%, 2%, ... of the price |
| Open interest and long/short ratios (5-minute metrics) | How much is borrowed and on which side |
| Funding rates | What it costs to hold a long or short position |
| Mark and index price candles | The prices that trigger liquidations |

## A known trap

Binance's depth data for BTCUSDT froze at exactly 17.654 BTC on the bid side from
2025-10-10 19:15 UTC for days. Read naively, it looks like buyers vanished before the crash.
Every series has to be screened for frozen values before it is used.

## Plan, in order

1. **Literature and data review:** what has been done on liquidation cascades and fragility,
   and exactly what each Binance file contains.
2. **Event list:** define a cascade with fixed rules (for example a large move with a jump in
   forced closures), written down and locked before looking at the warning signals.
3. **Data quality:** screen for frozen and missing values.
4. **Warning-sign test:** compare the hours before cascades with matched calm periods.
5. **Cross-section:** do more heavily borrowed contracts fall further?
6. **Machine learning:** an early-warning model, tested only on periods it never saw, against
   a simple baseline.
