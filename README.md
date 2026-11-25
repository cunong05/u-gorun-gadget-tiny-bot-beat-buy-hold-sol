[![make.fun · u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1](https://make.fun/badge/u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1.svg)](https://make.fun/bounty/u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1?utm_source=github&utm_medium=readme&utm_campaign=u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1)
[![rank](https://make.fun/badge/u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1/cunong05/u-gorun-gadget-tiny-bot-beat-buy-hold-sol/rank.svg)](https://make.fun/bounty/u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1)
[![reward](https://make.fun/badge/u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1/cunong05/u-gorun-gadget-tiny-bot-beat-buy-hold-sol/reward.svg)](https://make.fun/bounty/u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1)

# Tiny Bot: EMA Trend-Following on Solana

A tiny paper-trading bot for make.fun's **"Tiny Bot, Easy $2: Beat Buy-and-Hold on Solana"** bounty. It trades hourly bars of FARTCOIN, JITOSOL, POPCAT, RAY, SOL, WETH and WIF on $10,000 USDC of paper capital, long only, no leverage, no shorts.

## Strategy

Simple, robust trend-following — no fitted parameters, just round standard ones:

- **Entry:** EMA(8) crosses above EMA(21), the close is above EMA(21), and 24-hour momentum is positive (close above the close 24 bars ago). A trend already up when the window opens is entered once on the first tradable bar under the same filters.
- **Exit:** the whole position when EMA(8) crosses back below EMA(21), when the close falls below EMA(8), or when a stop-loss (−8% vs cost) or take-profit (+25% vs cost) trips. After an exit a symbol needs a fresh cross up to re-enter.
- **Sizing:** equal weight — equity / 7 per position, capped at the 25% max-weight cap; sells are sent before buys in every reply.
- **Deterministic:** pure float arithmetic on the bars; no clock, no environment, no randomness. Slippage cap 100 bps per order.

The idea: in a falling market the bot mostly sits in cash (beating buy-and-hold by not holding the drawdown), and in a rising market it rides the symbols whose trend is actually up.

## Local grade (dev window, `grade-local`, process driver)

| Metric | This bot | Buy-and-hold baseline |
|---|---|---|
| Net PnL (USDC) | **−43.40** | −869.34 |
| Trades | 16 over 6 symbols | 7 |
| Max drawdown | 1.16% | 10.92% |
| Fees | 22.83 USDC | 19.14 USDC |

Guardrails met (≥8 trades, drawdown ≪ 25%). Two independent executions reproduced the action log byte for byte. The dev window was a broad downtrend (all 7 symbols down 3–14%), so the bot's edge there is staying out; the rules are deliberately generic so they also apply to the unseen final window (3 days, 27–30 Nov 2026).

## Run it

Python 3.13, standard library only:

```sh
python3 -P -s main.py
```

The bot speaks `agent-fun/bars-replay/v1` on stdin/stdout (JSON lines) via the vendored `vendor/makefun_bars.py`, a copy of the kit's SDK. To grade it against the dev window with the kit:

```sh
node cli/makefun.mjs grade-local --kit <kit-dir> --bot <this-repo> --driver process
```

## Files

- `main.py` — the bot (entrypoint)
- `vendor/makefun_bars.py` — the bars-replay protocol shim from the competition kit
- `owner.json`, `.makefun/owner.json` — payout wallet claim
- `LICENSE` — MIT
