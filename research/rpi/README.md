# Who is retail in crypto futures? (RPI project)

Status on 2026-11-22: research done, plan drafted, nothing locked, no analysis run.

| File | What it is |
|---|---|
| `README.md` | This page: the plan in plain language and the open decisions |
| `RESEARCH.md` | What we found about Binance's rules, prior work and methods, with verification status |
| `PREREGISTRATION.md` | The draft analysis plan, to be reviewed and then sha256-locked |
| `DATA_QUALITY.md` | Gap and data-quality checks on the recorder's output |

Code: `src/microstructure/rpi/quality.py` (data-quality checks) and
`src/microstructure/rpi/books.py` (order-book snapshots), tested in `tests/rpi/`. The
recorder is `src/microstructure/rpi/recorder.py`, on `main` since 2026-11-22.

## The plan in plain language

**The problem.** People who study crypto markets want to know which trades come from ordinary
people and which from trading firms' programs. Trades are anonymous, so everyone guesses, and the
usual guess is "small trades are retail". Nobody has checked that guess.

**The opportunity.** Since November 2025 Binance lets market makers post a special kind of order
(RPI) that can only be hit by someone trading in the Binance app or website, never by a program
using the API. Binance marks those trades publicly. A marked trade is a confirmed app user.

**The catch.** An unmarked trade tells us nothing: it could be a program, or an app user who
happened to trade against ordinary orders. So we have confirmed "yes" examples and no confirmed
"no" examples. Statisticians call this positive-unlabelled learning.

**The second catch.** The marks are not handed out at random. Binance's rules put RPI orders at
the back of the queue at each price. An app user gets marked either because an RPI order was
offering the best price alone (then any order gets marked), or because their order was big enough
to eat through the ordinary orders at that price first (then only big orders get marked). The
second route makes marked trades look large for a mechanical reason. This probably explains part
of what the early probes showed, and the plan is designed around it: for questions about size we
use only the first kind of mark.

**What we will do.**
1. Record every trade on 15 contracts for 8 weeks, with the marks.
2. Rebuild orders from fills (fills in the same millisecond on the same side).
3. Test the common retail rules: small size, round dollar amounts, round quantities, time of day,
   sweeps, and a "split pattern" rule that looks for a large order cut into equal small pieces. For each rule, ask how much more often its trades are confirmed app trades than
   average (lift), and what share of confirmed app trades it catches.
4. Train a model on weeks 1 to 4, tune it on week 5, and test it once on weeks 6 to 8, including
   three contracts it never saw. Ask whether it beats the best simple rule.
5. Report uncertainty by resampling whole contract-days, because trades within a day are related.

**What we can honestly claim.** "At least X% of trades picked by this rule are app users", and
"this rule or model concentrates app users by a factor of Y". What we cannot claim is the true
share of all trading that is retail. The data cannot reveal that, and the plan says so.

## What needs your decision

1. **Check that the recorder runs on time.** Pull request 19 was merged on 2026-11-22 and the
   first run was started by hand, but it was still waiting in GitHub's queue behind the
   Hyperliquid crawl ten minutes later. Flags that are not recorded are lost for good.
2. **Merge the order-book recording.** It is built and tested on this branch
   (`src/microstructure/rpi/books.py`, plus a change to the recorder workflow) and starts only
   once merged to `main`. It takes both books every 30 seconds, which tells us when RPI orders
   are at the front.
3. **D2: free API key for gap repair (recommended, low priority).**
4. **The plan itself**, especially: the rule thresholds (section 5), the two label definitions
   (section 4.2), the 56-day window and split (section 7), the three held-out contracts, and the
   hypotheses (section 8.3).
