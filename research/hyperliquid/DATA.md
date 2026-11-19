# Hyperliquid data reference

Endpoint-by-endpoint notes for the skill-vs-luck and memecoin projects. Probed live from the
research machine on 2026-11-19 unless marked otherwise. Numbers (counts, sizes) change daily;
always snapshot and hash what you use.

Tags: **[V]** we called it and saw the result; **[S]** from docs or third-party docs seen in
search results (the official docs host hyperliquid.gitbook.io was blocked here); **[I]** our
estimate.

## 0. Basics

All info calls are a JSON `POST` to one URL:

```bash
curl -s https://api.hyperliquid.xyz/info \
  -H 'Content-Type: application/json' \
  -d '{"type":"meta"}'
```

- Timestamps are milliseconds since epoch and **must be integers** (a float gives HTTP 422) [V].
- Addresses are lowercase 0x hex strings.
- No API key, no account. Everything in sections 1 to 6 is free.

### Rate limits

- Documented: **1,200 weight per minute per IP** [S].
- Weight 2: `l2Book`, `allMids`, `clearinghouseState`, `orderStatus`, `spotClearinghouseState`,
  `exchangeStatus`. Weight 60: `userRole`. Weight 20: everything else [S].
- Extra weight `ceil(items/20)` on `recentTrades`, `historicalOrders`, `userFills`,
  `userFillsByTime`, `fundingHistory`, `userFunding`; `ceil(items/60)` on `candleSnapshot` [S].
  A full 2,000-fill page therefore costs about 120 weight, about 10 pages per minute on paper.
- Observed: enforcement looked looser. 34 full fill pages in 20 s and 80 more after gave no 429
  in one test; another test hit 429 after about 40 calls in 12 s, and another after about 70
  pages at 1.2 s spacing, while 6.5 s spacing ran clean [V]. **Measure, pace at about 70% of the
  documented budget, back off on 429, and never spread load over many IPs.**
- `tokenDetails` returns HTTP 500 for many tokens; that is not a rate-limit signal [V].

### Websocket limits

About 100 connections, 1,000 subscriptions and 2,000 messages sent per minute per IP [S, from
memory of docs; verify]. Send `{"method":"ping"}` every 30 s.

---

## 1. Universe and leaderboard files (stats-data host)

### `GET https://stats-data.hyperliquid.xyz/Mainnet/leaderboard`

```bash
curl -s -o leaderboard_$(date -u +%F).json https://stats-data.hyperliquid.xyz/Mainnet/leaderboard
sha256sum leaderboard_$(date -u +%F).json
```

- Size about 39.3 to 39.4 MB; rows 48,181 to 48,220 on 2026-11-19 depending on the hour [V].
- Top key `leaderboardRows`. Row fields: `ethAddress`, `accountValue`, `displayName` (non-null
  for 1,481), `prize` (0 everywhere), `windowPerformances` = list of
  `[window, {pnl, roi, vlm}]` for `day`, `week`, `month`, `allTime` [V].
- Distribution (2026-11-19): median accountValue about $381; 14,823 rows with accountValue 0;
  44.8% positive allTime PnL; 58.7% exactly zero monthly PnL [V].
- Refreshed roughly hourly (S3 Last-Modified about an hour old). **No history endpoint.** No
  public archive of old snapshots found on GitHub; Wayback untested [V].
- Inclusion rule undocumented. In one 90 s websocket sample only about 22% of trading addresses
  (46% of trade sides) were in the file [V, small sample].
- Values can disagree with per-wallet endpoints: top row 0xf5d81a13... shows accountValue
  $109.4M and allTime vlm $235B, while `clearinghouseState` shows $1.64M and `portfolio` vlm
  $84.0B [V]. Use as a universe list, not ground truth.

### `GET https://stats-data.hyperliquid.xyz/Mainnet/vaults`

- 14.2 MB, 9,478 vaults: 6,432 closed, 3,046 open [V].
- Row: `summary{name, vaultAddress, leader, tvl, isClosed, relationship{type}, createTimeMillis}`,
  `apr`, `pnls` per window (about 12 compressed points each) [V].
- HLP is `parent` with 7 `child` vaults; summing TVL double counts [V].
- Other guessed paths on this host (funding, liquidations, open_interest...) returned 403 [V].

---

## 2. Market metadata

| Body | Returns | Notes |
|---|---|---|
| `{"type":"meta"}` | Perp universe: `name`, `szDecimals`, `maxLeverage`, `marginTableId`, `isDelisted`, `onlyIsolated` | 235 perps, 56 `isDelisted` [V]. No delisting time. |
| `{"type":"meta","dex":"xyz"}` | Same for a HIP-3 builder dex | xyz has 147 markets, 24 delisted [V]. |
| `{"type":"perpDexs"}` | HIP-3 dexes | 10: xyz, flx, vntl, hyna, km, abcd, cash, para, mkts, io [V]. |
| `{"type":"metaAndAssetCtxs"}` | Meta plus **current** `openInterest`, `funding`, `premium`, `oraclePx`, `markPx`, `dayNtlVlm` | Current only. Historical contexts are in paid S3. **Record every 5 min from now.** |
| `{"type":"spotMeta"}` | `tokens` (518) and `universe` (353 pairs) | Token fields: `name`, `index`, `tokenId`, `isCanonical`, `evmContract`, `fullName`, `deployerTradingFeeShare` [V]. Indices run 0 to 1337, about 820 missing [V]. |
| `{"type":"spotMetaAndAssetCtxs"}` | Spot pairs plus `prevDayPx`, `dayNtlVlm`, `markPx`, `midPx`, `circulatingSupply`, `totalSupply` | 207 of 353 pairs had zero 24h volume [V]. |

Spot pairs are named `@<index>` (e.g. HYPE is `@107`), except `PURR/USDC`. HIP-3 coins are
`dex:COIN` (e.g. `xyz:XYZ100`).

---

## 3. HIP-1 token launch data

### `tokenDetails`

```bash
curl -s https://api.hyperliquid.xyz/info -H 'Content-Type: application/json' \
  -d '{"type":"tokenDetails","tokenId":"<tokenId hex string from spotMeta>"}'
```

- Fields: `name`, `maxSupply`, `totalSupply`, `circulatingSupply`, `szDecimals`, `weiDecimals`,
  `midPx`, `markPx`, `prevDayPx`, `genesis{userBalances, existingTokenBalances, blacklistUsers}`,
  `deployer`, `deployGas`, `deployTime`, `seededUsdc`, `nonCirculatingUserBalances`,
  `futureEmissions` [V].
- Coverage: a full crawl got data for 359 of 518 tokens; samples saw HTTP 500 for 9 of 21
  (clustered at indices 175 to 375, mid-2025) and `null` for others (e.g. WCLP) [V]. Retry with
  backoff; log failures as data.
- `0xffff...ffff` in genesis balances is the HIP-2 Hyperliquidity reserve, not a person [V].
- HYPE's own `tokenDetails` is 5.2 MB with 94,023 genesis addresses (the airdrop) [V].
- `deployGas`: USDC until 2025-05-22, HYPE after. Early tokens show 0 [V/S]. Peak: GOD 975,747
  USDC on 2024-12-16 [V].

### Deploy auctions

| Body | Returns |
|---|---|
| `{"type":"spotDeployState","user":"0x0000000000000000000000000000000000000000"}` | `states` plus live `gasAuction{startTimeSeconds, durationSeconds:111600, startGas, currentGas}`. Without `user` it errors [V]. |
| `{"type":"spotPairDeployAuctionStatus"}` | Pair auction (500 HYPE floor at probe) [V] |
| `{"type":"perpDeployAuctionStatus"}` | HIP-3 auction (startGas 1168.8, endGas 664.2 HYPE at probe) [V] |

The auction is a 31-hour Dutch auction; start price is 2x the last clearing price [S].

---

## 4. Prices and funding

### `candleSnapshot`

```bash
curl -s https://api.hyperliquid.xyz/info -H 'Content-Type: application/json' \
  -d '{"type":"candleSnapshot","req":{"coin":"BTC","interval":"1d","startTime":0,"endTime":1795000000000}}'
```

- Bar fields: `t`, `T`, `s`, `i`, `o`, `h`, `l`, `c`, `v`, `n` (trade count) [V].
- **Only the most recent 5,000 bars per interval** [V]. On 2026-11-19: BTC 1m from 2026-11-15
  (about 3.5 days), 1h from 2026-04-24 (about 7 months), 1d from 2020-08-19.
- Pre-listing bars are back-filled with `v = 0` (BTC's first real bar is 2023-02-26). Filter
  `v > 0` [V].
- Delisted coins keep their last 5,000 bars, so 1h goes back to listing for short-lived coins
  (JELLY 1h: 1,332 bars 2025-01-30 to 2025-03-26) but 1m only covers about 3.5 days before
  delisting [V]. Some very old coins return null (LUNA) [V].
- Spot: use `@N`. HIP-3: use `dex:COIN`.
- Sum of daily `n` across perps gives trades per day (median about 3.0M in Oct to Nov 2026, peak
  8.76M on 2025-10-10) and is the completeness check for a trade recorder [V].

### `fundingHistory`

```bash
curl -s https://api.hyperliquid.xyz/info -H 'Content-Type: application/json' \
  -d '{"type":"fundingHistory","coin":"BTC","startTime":0}'
```

- 500 hourly rows per call: `coin`, `fundingRate`, `premium`, `time`. BTC from 2023-05-12 [V].
- About 60 pages per coin for full history; about 14k calls (several hours) for all perps [I].

### Other

- `{"type":"predictedFundings"}`: current Hyperliquid, Binance, Bybit rates (snapshot only) [V].
- `{"type":"recentTrades","coin":"BTC"}`: last ~10 trades only, each with `users` [V].

---

## 5. Per-wallet endpoints

All take `"user":"0x..."`.

### `portfolio` (main return source)

```bash
curl -s https://api.hyperliquid.xyz/info -H 'Content-Type: application/json' \
  -d '{"type":"portfolio","user":"0xYOURWALLET"}'
```

- Windows: `day`, `week`, `month`, `allTime`, `perpDay`, `perpWeek`, `perpMonth`,
  `perpAllTime`. Each has `accountValueHistory` and `pnlHistory` as `[ms, value]` pairs, plus
  `vlm` [V].
- `pnlHistory` is cumulative trading PnL, excluding deposits; flow over an interval = change in
  accountValue minus change in PnL [V].
- **Spacing is irregular.** Typical: allTime median 168 h (sometimes 336 h), month about 9 to 15 h,
  week about 2.3 h, day 1 to 2 h. But one wallet had 100 allTime points with a 1 h first gap [V].
- About 25 KB per wallet, about 1.2 GB raw for 48k wallets, 5 to 13 h of crawling [V/I].

### `userNonFundingLedgerUpdates` (flows and liquidations)

```bash
curl -s https://api.hyperliquid.xyz/info -H 'Content-Type: application/json' \
  -d '{"type":"userNonFundingLedgerUpdates","user":"0x...","startTime":0}'
```

- Up to 2,000 rows per call; page with `startTime` [V].
- Delta types seen: `deposit`, `withdraw`, `send`, `internalTransfer`, `subAccountTransfer`,
  `spotTransfer`, `accountClassTransfer`, `cStakingTransfer`, `rewardsClaim`, `spotGenesis`,
  `vaultCreate`, `vaultDeposit`, `vaultWithdraw`, `liquidation`, `gossipPriorityGasAuction` [V].
- `withdraw` carries a `nonce` equal to signing time in ms (proved JELLY margin was withdrawn
  2.7 min before liquidation) [V].
- `liquidation` gives `liquidatedNtlPos`, `accountValue`, leverage type and positions [V].
- On a **vault address** it returns every deposit and withdrawal; withdrawals include `user`,
  `basis`, `commission`, `requestedUsd`, `netWithdrawnUsd`. Deposits have no `user` [V].
- History goes back to at least March 2025 for every account tested; one wallet back to
  2024-04-22 [V]. One earlier report of `null` at startTime 0 was wallet-specific.

### `userFills` and `userFillsByTime`

```bash
curl -s https://api.hyperliquid.xyz/info -H 'Content-Type: application/json' \
  -d '{"type":"userFillsByTime","user":"0x...","startTime":0,"aggregateByTime":false}'
```

- `userFills`: the 2,000 most recent fills only [V].
- `userFillsByTime`: 2,000 per call, **oldest first** from `startTime`. Page forward with
  `startTime = last time` (inclusive) and dedupe on `(tid, oid)`. Paging backward with `endTime`
  returns `[]` [V].
- Fields: `coin`, `px`, `sz`, `side`, `time`, `startPosition`, `dir`, `closedPnl`, `hash`, `oid`,
  `crossed` (true = taker), `fee` (negative = rebate), `tid`, `feeToken`, `twapId`, optional
  `cloid`, `builderFee`, `liquidation{liquidatedUser, markPx, method}` [V]. No counterparty.
- About 367 bytes per fill as JSON [V].
- **Retention.** Docs say "10,000 most recent fills" [S]. Measured: 13.8k to 160k+ fills
  depending on wallet. Best hypothesis: about 10,000 distinct orders are kept, so a wallet
  with 132,129 fills from 3,884 orders was complete back to first deposit, while cut-off wallets
  had 10.6k to 11.4k orders and heavy market makers keep only hours [V/I]. In a random 30 active
  wallets, 22 were complete back to first deposit [V]. HLP Liquidator history starts
  2025-10-10; HLP Strategy B has about 2.5 hours [V].
- **Rule:** record each wallet's earliest retrievable fill and first ledger event; mark wallets
  as complete or left-censored.

### Others (all free, all returned 200)

| Body | Use |
|---|---|
| `clearinghouseState` | Current perp positions and margin (weight 2) |
| `spotClearinghouseState` | Current spot balances (weight 2) |
| `userFunding` (`startTime`) | Hourly funding paid/received: `coin`, `usdc`, `szi`, `fundingRate`, `nSamples`; 500 per call |
| `historicalOrders` | 2,000 most recent orders incl. cancelled, with `tif` (Alo, Ioc, Gtc): maker vs taker style |
| `subAccounts` | Master to sub-accounts; `null` for non-masters (positive-only labels) |
| `userRole` | `user`, `vault`, `subAccount`, ... (weight 60) |
| `userVaultEquities` | Wallet's vault stakes |
| `userFees` | Fee tier and rebates |
| `userTwapSliceFills` | 2,000 most recent TWAP slices |
| `referral`, `delegatorHistory`, `frontendOpenOrders`, `userRateLimit` | Context |

### `vaultDetails`

```bash
curl -s https://api.hyperliquid.xyz/info -H 'Content-Type: application/json' \
  -d '{"type":"vaultDetails","vaultAddress":"0xdfc24b077bc1425ad1dea75bcb6f8158e10df303"}'
```

- Fields: `name`, `leader`, `description`, `portfolio`, `apr`, `followerState`,
  `leaderFraction`, `leaderCommission`, `followers`, `maxDistributable`, `maxWithdrawable`,
  `isClosed`, `relationship`, `allowDeposits`, `alwaysCloseOnWithdraw` [V].
- Works for closed vaults (survivorship-free) [V]. `followers` capped at 100 [V].
- HLP address above: allTime series from 2023-05-10, 103 points, about 336 h spacing [V].
- 300 sequential calls in 259 s without 429 [V].

### `validatorL1Votes`

Only open votes. Historical validator vote times are **not** available free from any endpoint
we tested; `rpc.hyperliquid.xyz/explorer` was blocked here (untested) [V].

---

## 6. Websocket trade tape (forward only)

```text
wss://api.hyperliquid.xyz/ws
-> {"method":"subscribe","subscription":{"type":"trades","coin":"BTC"}}
```

- Each trade: `coin`, `side` (taker side), `px`, `sz`, `time`, `hash`, `tid`, `users` =
  `[buyer, seller]`. Verified against `userFillsByTime`: buyer was maker with `crossed=false`,
  seller taker with `crossed=true` when side was `A` [V].
- `tid` unique in 7,176 live trades; key on `(coin, time, tid)` to be safe [V].
- Subscribing returns a snapshot of about 29 recent trades per coin (use it to fill short gaps
  after reconnects) [V].
- Coins to cover: 179 live main perps + 353 spot pairs + 332 HIP-3 perps = 864 subscriptions,
  under the ~1,000 limit [V/S].
- Volume: about 3M main-perp trades/day (peak 8.8M). Storage measured: raw JSONL 274 B/trade,
  gzip ratio 4.5, Parquet zstd 50.5 B/trade. About 150 MB/day typical, 440 MB peak day,
  55 to 70 GB/year with spot and HIP-3 adding 10 to 30% [V/I].
- Daily completeness check: unique tids per coin vs the 1d candle `n`.
- Poll `meta`, `spotMeta`, `perpDexs` every 5 minutes to subscribe to new listings quickly.

---

## 7. Sources that cost money (say so if ever used)

| Source | What | Cost | Status |
|---|---|---|---|
| S3 `hl-mainnet-node-data` | `node_trades` (2025-03-22 to 05-25), `node_fills` (2025-05-25 to 07-27), `node_fills_by_block` (from 2025-07-27, hourly `.lz4`) | Requester-pays. About 295 GB for fills by block, roughly $27 at ~$0.09/GB egress | Confirmed requester-pays (anonymous list denied) [V] |
| S3 `hyperliquid-archive` | Historical asset contexts, L2 snapshots | Requester-pays | [V] |
| Dune Hyperliquid tables | Decoded fills, perp trades from 2025-07-27 | Enterprise or trial | [S] |
| Allium | Fills back to 2023-11 | Enterprise | [S] |
| Hydromancer | Raw fills by block | About $300/month | [S] |
| GoldRush | Fills older than retention | Paid credits | [S] |
| Nansen | Leaderboard history from 2025-05 | Paid | [S] |
| Etherscan HyperEVM API | HyperEVM only, not HyperCore | Free until 2026-11-30, then Lite plan | [S] |
| Baselight | `node_fills` to 2025-12-01 | Pricing unknown | [S] |

## 8. Possibly free, not verified: SQD portal

- `POST https://portal.sqd.dev/datasets/hyperliquid-fills/stream` with
  `{"type":"hyperliquidFills","fromBlock":750000000,"toBlock":...,"fields":{...},"fills":[{"user":["0x..."]}]}`.
  Also `GET /head`, `/finalized-head`, `/metadata`. Response is JSON lines, one block per line [S, from SQD source code].
- Fields: `fillIndex`, `user`, `coin`, `px`, `sz`, `side`, `time`, `startPosition`, `dir`,
  `closedPnl`, `hash`, `oid`, `crossed`, `fee`, `builderFee`, `tid`, `cloid`, `feeToken`,
  `builder`, `twapId`. **No `liquidation` field.** Each trade appears twice (one row per side) [S].
- Built from the requester-pays `node_fills_by_block`; SQD pays the egress [S].
- Starts at block 750,000,000, about 2025-10-01 by extrapolation (about 12 blocks/s; SQD's own
  guide wrongly says 1 block/s) [I]. Misses JELLY.
- Limits: query body max 256 KiB (about 5,800 addresses), max 100 filter objects; public tier
  about 20 requests per 10 s; free Testing plan about 1 GB/month; Starter $99/month, Growth
  $499/month [S]. No terms found for bulk research use; do not republish raw dumps.
- Full pull from block 750M: roughly 0.8 to 2.5 billion rows, 170 GB to 1 TB uncompressed [I,
  low confidence].
- **Pilot:** from a machine that can reach it, pull one hour and block 750,000,000, record MB/s
  and `x-sqd-usage-*` headers, and match tids for 20 wallets against `userFillsByTime`.

## 9. Planned free collection budget (one IP)

| Step | Calls | Time | Size |
|---|---|---|---|
| Daily leaderboard + vaults snapshot | 2/day | seconds | ~2 GB/year gzip |
| Metadata, all tokenDetails, 1d candles all markets | ~1,500 | < 1 h | < 200 MB |
| fundingHistory all perps | ~14k | ~9 h | ~300 MB raw |
| `portfolio` all ~48k wallets | ~48k | 5 to 13 h | ~1.2 GB raw |
| Ledger updates same wallets | ~50k+ | similar | small |
| Fills, stratified 5k wallets | ~20k pages | ~1.5 to 2 days | ~14 GB raw, 1 to 2 GB Parquet |
| Websocket recorder | continuous | always on | ~150 MB/day |

Figures are estimates from probes [I].
