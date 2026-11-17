# btc-dip-buy-bot-2

A mean-reversion dip-buy bot for the make.fun competition
**btc-race-24h-20261117-0603** — "Race a BTC trading bot live for 24 hours"
($250 USDC, top 10 paid).

The bot trades Coinbase Wrapped BTC (CBBTC) against USDC on 1-minute
on-chain bars, starting with 1,000 USDC of paper money. Simulation only:
no real money is traded anywhere.

## Run

```sh
python3 -P -s main.py
```

Python 3.13, standard library only. The bot speaks
`agent-fun/bars-replay/v1`: one JSON line per minute on stdin, one reply
line per batch on stdout. `vendor/makefun_bars.py` is the kit's Python
shim, copied byte for byte.

## Strategy

Long only, at most one open position. Buy the whole cash balance when the
close is at least 0.9% below the trailing 60-bar high and the 10-minute
log return is positive (bounce confirmation). Re-entries (max 3 total)
additionally need the 240-minute return to be positive and a 60-bar
cooldown after the last exit. Sell everything on take-profit (+1.2%
above the entry fill price), stop-loss (−0.3% below the entry close), or
a trailing stop (−0.8% below the peak close since entry). See
[STRATEGY.md](STRATEGY.md) for the full description and local
verification numbers.

## Local verification (dev window)

Graded locally on the kit's published dev window through the exact wire
protocol and fill model (4 bps fee, 2 bps slippage, constant-product
price impact against each bar's open depth):

- Net PnL: **+$6.43** (dev gate: > $0 — passes)
- Trades: 2 round trips (4 fills), 0 rejected orders
- Max drawdown: 0.87% (race bar: ≤ 25%)
- Two runs on the dev window produce byte-identical action logs
  (deterministic).

## License

MIT — see [LICENSE](LICENSE).
