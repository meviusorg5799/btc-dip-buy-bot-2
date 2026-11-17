# Strategy

## Idea

BTC on 1-minute bars is choppy: the dev window swung in a ~2.5% band
(63,874–65,467) while ending almost flat (+0.48% buy-and-hold). A full-size
round trip costs about 26 bps in fees, slippage and price impact, so a
trade must catch a move clearly larger than that. This bot is a
mean-reversion dip-buyer: it waits for a real washout below the recent
high, wants a bounce already underway, and then lets the snap-back pay
for the round trip.

## Rules

All prices are bar closes unless noted; all comparisons are exact
integer arithmetic except the two log returns.

- **Universe:** CBBTC/USDC, 1-minute bars. Long only, at most 1 open
  position. Buys spend all cash; sells sell the whole position.
- **Entry** (flat only, at most 3 entries per window):
  - close ≥ 0.9% below the trailing 60-bar high, **and**
  - 10-minute log return > +0.05% (bounce confirmation).
  - Re-entries (after the first) additionally need the 240-minute log
    return > 0 (uptrend only) **and** at least 60 bars since the last exit.
- **Exit** (while holding, checked on every bar's close):
  - take-profit: close ≥ 1.2% above the entry fill price (cost basis);
  - stop-loss: close ≤ 0.3% below the entry close;
  - trailing stop: close ≤ 0.8% below the highest close since entry.
- Orders carry `max_slippage_bps = 200` (fills run ~15 bps over the
  close; the largest 1-minute move in the dev window was ~45 bps, so
  200 bps never binds in practice and no order is lost to it).
- No new entries are placed after the window's last bar (orders there
  would be rejected `after_end` anyway).

## Why these parameters

The starting shape (0.5% dip, 0.8% take-profit) lost **−$20.82** on the
dev window: it bought every shallow dip and was stopped out three times
in a row. The tuned values were picked only where neighbouring values
give the same result — a plateau, not a point:

- DIP 80–100 bps × bounce 5–10 bps: identical +$6.43.
- Take-profit 120–150 bps: identical +$6.43 (90–110 bps still positive
  at +$0.89; 170–200 bps higher but a local peak, not taken).
- Stop-loss 25–50 bps: all positive (+$6.43 / +$5.01 / +$4.37).
- Trailing stop 80–150 bps: identical (it never binds before the
  take-profit / stop-loss on this window).
- Cooldown 30–60 bars, max entries 2–6, bounce window 5–20 bars:
  identical.

Deliberately **not** taken: stop-loss ≥ 55 bps scores +$24.31, but that
jump is a single trade surviving a −0.59% dip by 4 bps of margin — one
trade's luck, not a plateau. The chosen stop keeps the loss on a failed
dip bounded at ~$7 instead.

## Local verification (dev window, 2026-11-16 06:03 – 2026-11-17 06:03 UTC)

Graded with a local replay runner transcribed from the kit's harness
source (`sim/bars/engine.ts`: `BarsPool`, `barsBuyFill`,
`barsSellFill`, decision checks in order, flatten at the last close),
driving the real `main.py` as a subprocess over the wire protocol.
Fees 4 bps, slippage 2 bps, price impact against each bar's open depth.

| Metric | Value |
|---|---|
| Net PnL | **+$6.4333** |
| Final cash | $1,006.43 (from $1,000) |
| Trades | 2 round trips, 4 fills, 0 rejected |
| Fees paid | $1.61 |
| Max drawdown | 0.87% |
| Dev gate (net PnL > $0) | **PASS** |
| Race bar (≥1 trade, max DD ≤ 25%) | met |

Trades (fills at the next bar's open):

| # | Side | Decision bar (seq) | Fill price | Notional |
|---|---|---|---|---|
| 1 | buy | 380 | $64,111.32 | $1,000.00 |
| 1 | sell | 510 | $65,012.89 | $1,013.25 |
| 2 | buy | 582 | $64,626.52 | $1,013.25 |
| 2 | sell | 602 | $64,243.07 | $1,006.43 |

Trade 1 caught the block-1 low and rode the recovery to the
take-profit (+$13.25). Trade 2 re-entered on the next dip and was
stopped out (−$6.82).

6-hour sub-window PnLs: block 0 $0.00, block 1 **+$6.43**, block 2 $0.00,
block 3 $0.00, final $0.00. All of the profit comes from block 1; the
other blocks are flat because no entry fired there. The edge is thin and
concentrated in one round trip — the dev gate passes, but no prize is
likely on the race window unless a similar washout-and-recovery shows
up there.

## Determinism

Two runs of `main.py` on the dev window through the wire protocol
produce byte-identical reply logs (same orders, same client ids). The
bot reads no clock, no environment, no files outside the repository,
and uses no randomness.
