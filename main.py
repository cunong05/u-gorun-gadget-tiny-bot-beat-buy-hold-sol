"""Tiny trend-following bot for make.fun "Tiny Bot, Easy $2: Beat Buy-and-Hold on Solana".

Strategy (simple, robust, no tuning to any one window):
  - Per symbol, EMA(8) vs EMA(21) on hourly closes, seeded as the mean of
    the first span of closes (the standard EMA warm-up).
  - Enter long when EMA(8) crosses above EMA(21) AND the close is above
    EMA(21) AND the 24h momentum is positive (close above the close 24 bars
    ago). A trend that is already up when the window opens is entered once,
    on the first tradable bar, under the same filters.
  - Exit the whole position when EMA(8) crosses back below EMA(21), or the
    close falls below EMA(8) (the trend has lost its short-term momentum),
    or a stop-loss / take-profit trips: -8% vs cost, +25% vs cost. After an
    exit the symbol needs a fresh cross up before it can re-enter, so a
    stopped-out position is not re-bought immediately into the same move.
  - Sizing: equal weight, equity / number of symbols, capped at the
    25% max-weight cap; never more than the cash on hand. Sells go first
    in every reply (their proceeds never fund a buy in the same reply).
  - Deterministic: pure float arithmetic on the bars, no clock, no env,
    no randomness. Slippage cap 100 bps (1%) per order.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

FAST_SPAN = 8
SLOW_SPAN = 21
MOMENTUM_BARS = 24
STOP_LOSS = 0.92   # exit when position value <= 92% of cost
TAKE_PROFIT = 1.25  # exit when position value >= 125% of cost
# Bars to wait after an exit before the symbol may re-enter on a still-up
# trend without a fresh cross (0 = no such re-entry: a fresh cross is needed).
REENTRY_BARS = 0
MAX_SLIPPAGE_BPS = 100


class Ema:
    """One EMA: mean of the first span closes, then 2/(span+1) towards each close."""

    def __init__(self, span):
        self.span = span
        self.warm = []
        self.value = None

    def step(self, close):
        if self.value is not None:
            self.value += (2.0 / (self.span + 1)) * (close - self.value)
            return
        self.warm.append(close)
        if len(self.warm) == self.span:
            self.value = sum(self.warm) / self.span


class Series:
    """Per-symbol indicator state."""

    def __init__(self):
        self.fast = Ema(FAST_SPAN)
        self.slow = Ema(SLOW_SPAN)
        self.closes = []
        self.prev_gap = None  # fast - slow after the previous bar
        self.gap = None       # fast - slow after this bar
        self.armed = True     # may enter on a cross up (False after an exit until trend resets)
        self.seen_trend = False  # have we seen fast/slow defined on a tradable bar yet
        self.exit_seq = None  # seq of the last exit (for cooldown re-entry)


def on_batch(state, batch):
    series = on_batch.series
    fresh = set()
    cross_up = set()
    cross_down = set()
    for bar in batch["bars"]:
        sym = bar["symbol"]
        s = series.setdefault(sym, Series())
        close = float(int(bar["c"]))
        s.closes.append(close)
        s.fast.step(close)
        s.slow.step(close)
        s.prev_gap = s.gap
        if s.fast.value is not None and s.slow.value is not None:
            s.gap = s.fast.value - s.slow.value
        else:
            s.gap = None
        fresh.add(sym)
        if s.prev_gap is not None and s.gap is not None:
            if s.gap > 0 and s.prev_gap <= 0:
                cross_up.add(sym)
            elif s.gap < 0 and s.prev_gap >= 0:
                cross_down.add(sym)
        # A trend that ends below its slow EMA re-arms the symbol for a fresh entry.
        if s.gap is not None and s.gap <= 0:
            s.armed = True

    if state.warming_up:
        return []

    orders = []
    sells = []
    entries = []
    for info in state.hello["symbols"]:
        sym = info["symbol"]
        if sym not in fresh:
            continue
        s = series.get(sym)
        if s is None or s.gap is None:
            continue
        held = state.positions.get(sym)
        close = float(state.close(sym))
        if held is not None:
            value = state.value(sym, held.qty)
            cost = held.cost
            if (sym in cross_down or close < s.fast.value
                    or value <= STOP_LOSS * cost or value >= TAKE_PROFIT * cost):
                sells.append({"side": "sell", "symbol": sym, "qty": held.qty,
                              "max_slippage_bps": MAX_SLIPPAGE_BPS})
                s.armed = False
                s.exit_seq = state.seq
            continue
        # Entry: fresh cross up, or an already-up trend on the first tradable bar.
        momentum_ok = True
        if len(s.closes) > MOMENTUM_BARS:
            momentum_ok = close > s.closes[-1 - MOMENTUM_BARS]
        if not momentum_ok or close <= s.slow.value or s.gap <= 0:
            continue
        if sym in cross_up and s.armed:
            entries.append(sym)
        elif not s.seen_trend:
            # First tradable bar where the trend is already up: enter once.
            entries.append(sym)
        elif (REENTRY_BARS and s.exit_seq is not None
                and state.seq - s.exit_seq >= REENTRY_BARS):
            # Trend still up some bars after an exit: re-enter without a
            # fresh cross (the exit was a stop / take-profit, not a reversal).
            entries.append(sym)
        s.seen_trend = True

    orders.extend(sells)
    max_orders = state.hello["caps"]["max_orders_per_bar"]
    n_symbols = len(state.hello["symbols"])
    slots = min(n_symbols, state.hello["caps"]["max_open_positions"])
    stake = state.equity // slots
    by_weight = state.hello["caps"]["max_weight_bps"] * state.equity // 10000
    slice_size = min(stake, by_weight)
    min_notional = int(state.hello["fees"]["min_notional_quote_units"])
    cash = state.cash
    room = slots - len(state.positions)
    for sym in entries:
        if room <= 0 or len(orders) >= max_orders:
            break
        amount = min(slice_size, cash)
        if amount < min_notional:
            break
        orders.append({"side": "buy", "symbol": sym,
                       "notional_quote_units": int(amount),
                       "max_slippage_bps": MAX_SLIPPAGE_BPS})
        cash -= amount
        room -= 1
    return orders


on_batch.series = {}

makefun_bars.run(on_batch)
