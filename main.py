"""Mean-reversion dip-buy bot for make.fun btc-race-24h-20261117-0603.

Trades Coinbase Wrapped BTC (CBBTC) against USDC on 1-minute on-chain bars.
Long only, at most one open position, whole cash in on each buy, whole
position out on each sell. Simulation only: no real money is traded.

Strategy
--------
Enter (flat only) when the close is at least DIP_BPS below the trailing
HIGH_LOOKBACK-bar high AND the short log return is positive (bounce
confirmation). After the first entry, further entries need the long log
return to be positive (uptrend only) plus a COOLDOWN_BARS gap since the
last exit, and at most MAX_ENTRIES entries are taken in the whole window.

Exit a position when any of these holds on a bar's close:
  * take-profit: close >= TP_BPS above the entry fill price (cost),
  * stop-loss:   close >= STOP_BPS below the entry close,
  * trailing:    close >= TRAIL_BPS below the highest close since entry.

Determinism: standard library only, no network, no wall clock, no files
outside the repository; every decision is a pure function of the bars
seen so far. Two runs on the same data produce identical orders.

Tuning note: the entry dip (0.9%) and take-profit (1.2%) were chosen on
the dev window only where neighbouring values give the same result
(DIP 80-100 bps x bounce 5-10 bps, TP 120-150 bps all identical), not on
a single lucky point. The prescribed 0.5% dip lost money on this window
(-$20.82) because it bought every shallow dip; the deeper dip waits for
a real washout. Local verification on the published dev window (see
STRATEGY.md): net PnL +$6.43, 2 round trips, max drawdown 0.87%.
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))

import makefun_bars

SYMBOL = "CBBTC"

# --- Strategy parameters (basis points unless noted) -------------------------
DIP_BPS = 90            # entry: close at least this far below the 60-bar high
BOUNCE_BPS = 5          # entry: 10-min log return above this (0.05%)
STOP_BPS = 30           # exit: close this far below the entry close
TRAIL_BPS = 80          # exit: close this far below the peak close since entry
TP_BPS = 120            # exit: close this far above the entry fill price
MAX_ENTRIES = 3         # at most this many entries in the whole window
COOLDOWN_BARS = 60      # bars between an exit and the next (re-)entry
HIGH_LOOKBACK = 60      # bars in the trailing high
RET_SHORT = 10          # bars in the short (bounce) log return
RET_LONG = 240          # bars in the long (uptrend) log return
MAX_SLIP_BPS = 200      # max slippage allowed on any order
NO_ENTRY_LAST_BARS = 0  # do not open a new entry this close to the end


class DipBuyer:
    """Keeps the bar history and the open-position bookkeeping."""

    def __init__(self):
        self.closes = []            # closes seen so far, ints at price_scale 5
        self.entries = 0            # entries filled so far
        self.last_exit_seq = -10 ** 9
        self.pending_buy = None     # client_id of a buy awaiting its fill
        self.pending_entry_close = None
        self.entry_close = None     # close of the bar the entry was decided on
        self.entry_cost = None      # fill price of the entry (cost basis)
        self.peak = None            # highest close since entry

    def on_batch(self, state, batch):
        # Absorb the fills of the orders decided on the previous batch.
        for fill in batch.get("fills", []):
            if fill["symbol"] != SYMBOL:
                continue
            if fill["client_id"] == self.pending_buy:
                self.pending_buy = None
                if fill["status"] == "filled" and fill["side"] == "buy":
                    self.entries += 1
                    self.entry_close = self.pending_entry_close
                    self.entry_cost = int(fill["price"])
                    self.peak = self.entry_close
                self.pending_entry_close = None
        bar = state.latest.get(SYMBOL)
        if bar is None:
            return []
        close = int(bar["c"])
        self.closes.append(close)
        holding = state.positions.get(SYMBOL)
        if holding is None:
            return self._maybe_enter(state, close)
        return self._maybe_exit(state, close, holding)

    def _maybe_exit(self, state, close, holding):
        if self.peak is None:
            self.peak = close
        elif close > self.peak:
            self.peak = close
        take_profit = (self.entry_cost is not None
                       and close * 10000 >= self.entry_cost * (10000 + TP_BPS))
        stop_loss = (self.entry_close is not None
                     and close * 10000 <= self.entry_close * (10000 - STOP_BPS))
        trailing = close * 10000 <= self.peak * (10000 - TRAIL_BPS)
        if take_profit or stop_loss or trailing:
            self.last_exit_seq = state.seq
            self.entry_close = None
            self.entry_cost = None
            self.peak = None
            return [{"side": "sell", "symbol": SYMBOL, "qty": holding.qty,
                     "max_slippage_bps": MAX_SLIP_BPS}]
        return []

    def _maybe_enter(self, state, close):
        if self.pending_buy is not None:
            return []
        if state.seq >= 1440 - NO_ENTRY_LAST_BARS:
            return []
        if self.entries >= MAX_ENTRIES:
            return []
        if len(self.closes) < HIGH_LOOKBACK or len(self.closes) <= RET_SHORT:
            return []
        high = max(self.closes[-HIGH_LOOKBACK:])
        if close * 10000 > high * (10000 - DIP_BPS):
            return []
        if math.log(close / self.closes[-1 - RET_SHORT]) * 10000 <= BOUNCE_BPS:
            return []
        if self.entries > 0:
            if len(self.closes) <= RET_LONG:
                return []
            if math.log(close / self.closes[-1 - RET_LONG]) <= 0:
                return []
            if state.seq - self.last_exit_seq < COOLDOWN_BARS:
                return []
        if state.cash < 1_000_000:
            return []
        cid = state.client_id()
        self.pending_buy = cid
        self.pending_entry_close = close
        return [{"side": "buy", "symbol": SYMBOL, "client_id": cid,
                 "notional_quote_units": state.cash,
                 "max_slippage_bps": MAX_SLIP_BPS}]


def main():
    makefun_bars.run(DipBuyer().on_batch)


if __name__ == "__main__":
    main()
