# Forward Test Guide

How to use MonkeyTrade as a daily learning system — paper-trade signals in real-time, review every outcome, and let the model update itself from what actually worked.

---

## What Forward Testing Is

A forward test is a paper trade logged at the moment a signal appears, tracked as price moves, and reviewed when the trade closes. No real money. The point is to find out whether your read of the market is accurate *before* committing capital.

The difference from backtesting: backtests are written with the answer already known. Forward tests force you to commit to a direction *before* you know how it resolves. That discipline is what makes the learning real.

---

## The Daily Habit (5 minutes a day)

```
Morning  → Run Scan (Auto Bot) or manually log 1 setup you see
Midday   → Optional: check open trades on Forward Test page
Evening  → Run Daily Review; fill in lessons for any closed trades
```

Over weeks, the performance stats show you which stage you read correctly and which signals actually predicted direction. The autonomous bot does the same thing in parallel, building its own learned model that adapts daily.

---

## Part 1 — Manual Forward Testing

### Step 1: Find a setup

Use any page to identify a setup before logging a trade:

- **Dashboard** → enter a ticker → look at the stage banner, signals, and trade levels
- **Cycle Detector** → enter a ticker and period → read the stage confidence
- **Screener** → scan Top 100 or S&P 500 → filter by stage → find accumulation or markup stocks

A good setup has:
- Stage confidence ≥ 60%
- At least 2 confirming signals
- R:R ratio ≥ 2.0 (shown in Trade Levels panel)
- Volume ratio > 1.5× (volume above average)

### Step 2: Log the trade

1. Click **Forward Test** in the sidebar
2. Click **Log Trade**
3. Fill in the form:

| Field | What to enter | Where to find it |
|-------|--------------|-----------------|
| **Ticker** | Stock symbol | Dashboard search |
| **Direction** | Long (bullish) or Short (bearish) | Stage → accumulation/markup = long; markdown = short |
| **Entry Price** | Current market price | Dashboard indicator strip or any finance site |
| **Shares** | How many units (use 10 or 100 for paper) | Your choice |
| **Stop Loss** | Price where thesis is wrong | Dashboard → Trade Levels → Stop Loss |
| **Target** | Price target | Dashboard → Trade Levels → Target |
| **Stage** | Current Wyckoff stage | Dashboard → stage banner |
| **Confidence %** | Stage confidence score | Dashboard → stage badge |
| **Signals** | List signals that triggered this trade | Dashboard → Signals panel (tap to expand) |
| **Technique** | Setup name | e.g. "Wyckoff Spring", "MACD cross", "RSI bounce" |
| **Notes / Thesis** | Why you're taking this trade | Write 1–2 sentences |

**Example entry:**
```
Ticker:     NVDA
Direction:  Long
Entry:      $875.00
Stop Loss:  $840.00  (from Trade Levels — below SMA20 - 1×ATR)
Target:     $950.00  (from Trade Levels)
Stage:      Markup
Confidence: 78%
Signals:    MACD cross bullish, Price above SMA50, Volume surge
Technique:  Markup continuation pullback
Notes:      Pulled back to SMA20 with volume drying up. MACD just crossed. R:R = 2.1.
```

### Step 3: Monitor the trade

The **Open Trades** tab refreshes live prices every time you load the page. For each open trade you see:

- **Current price** and **unrealized P&L %**
- **P&L bar** showing where the current price sits between stop and target
- **Max gain / Max drawdown** — how far price went in your favor vs against you
- **Days held** — how long the position has been open

The trade auto-closes when:
- Price hits the **stop loss** → closes as a loss
- Price hits the **target** → closes as a win

You can also close manually: expand the trade card → click **Close Trade** → enter your exit price.

### Step 4: Write the daily lesson

After a trade closes, open the **Closed Trades** tab and expand the trade. Click **Edit** next to "Daily Lesson" and write:

**The three questions to answer:**
1. Was my stage read correct? Did the price behave as that stage predicted?
2. Did the signals I listed actually confirm direction, or were they noise?
3. Did I follow the plan? Or did I second-guess the entry/exit rules?

**Rate the trade 1–5 stars** — not based on outcome, but on quality of execution:
- ⭐⭐⭐⭐⭐ = Perfect execution, followed the plan, good thesis
- ⭐⭐⭐ = Followed the plan but thesis had a flaw
- ⭐ = Lost, AND I deviated from the plan

A loss with 5 stars means you did everything right and the market was random. A win with 1 star means you got lucky with bad process. Both lessons matter.

**Example lesson:**
```
Stage was correct — markup stage held and continued higher.
MACD cross and volume surge were both accurate signals.
I exited 3 days early when it hit $930 instead of waiting for $950.
That's $0.50 left on the table per share. Need to trust the target.
Rating: 3/5 — right thesis, wrong exit discipline.
```

---

## Part 2 — Autonomous Bot

The bot does the same loop automatically — it finds setups, logs its own paper trades, reviews them daily, and learns from each outcome.

### Running the bot

1. Go to **Auto Bot** in the sidebar
2. Click **Run Scan**

The terminal panel (Scan Log tab) shows live output as the bot scans each ticker:

```
🔍 Starting autonomous scan — threshold=0.52, universe=70 tickers
SCAN AAPL…
✓ AAPL [markup] score=0.614
SCAN MSFT…
✗ MSFT [distribution] score=0.431   ← below threshold, skipped
SCAN NVDA…
✓ NVDA [markup] score=0.672
...
🎯 SCAN COMPLETE — 3 trades logged
  → AAPL [markup] entry=$195.20 score=0.614
  → NVDA [markup] entry=$875.40 score=0.672
  → AMD  [accumulation] entry=$142.30 score=0.558
```

The logged trades appear immediately in **Forward Test → Open Trades**.

### How the bot scores setups

```
Score = stage_win_rate × 35%
      + signal_weight  × 30%
      + confidence     × 25%
      + volume_ratio   × 10%
```

A setup only gets logged if `score ≥ threshold` (default 0.52). Only 3 trades are logged per scan (the highest-scoring candidates).

**Direction rules:**
- Accumulation → Long
- Markup → Long
- Distribution → Skipped (no reliable edge in choppy ranges)
- Markdown → Short

### Running the daily review

Click **Daily Review** on the Auto Bot page. The bot:

1. Fetches the live price for every open bot trade
2. Checks if stop loss or target was hit
3. Auto-closes any that were hit (win or loss)
4. Writes an automatic lesson to each closed trade
5. Updates the learned model via the EMA update rule

Run this once a day, ideally after market close.

### Reading the learning model

**Model Brain tab** shows:

| Panel | What it means |
|-------|--------------|
| Stage win-rate bars | Bot's current belief about win probability in each Wyckoff stage. Starts at theory priors, drifts toward observed reality. |
| Score threshold | The minimum score a setup must reach to be logged. Auto-adjusts: rises when losing streak, falls when winning streak. |
| Recent win rate | Win rate across last 20 closed bot trades |
| Performance log | Every closed trade with ticker, stage, outcome, and P&L — the raw training data |

**Signal Weights tab** ranks every signal by its observed win rate. After each closed trade, the signals that were active during that trade are updated:

```
if trade won:  signal_weight = signal_weight × 0.85 + 1.0 × 0.15
if trade lost: signal_weight = signal_weight × 0.85 + 0.0 × 0.15
```

Over time, signals with real predictive power (RSI oversold, Volume surge, Wyckoff spring) will rise toward the top. Signals that generate false positives will drift lower.

**Activity Log tab** shows every bot action — scans, auto-closes, model updates — with expandable detail explaining each decision.

---

## Part 3 — $10,000 Virtual Portfolio (Fully Automated)

The bot manages a virtual $10,000 portfolio automatically. Every time the bot logs a trade, it allocates real dollars to it — no manual steps required.

### How capital allocation works

```
Step 1: Bot finds a candidate (score ≥ threshold)
Step 2: Calculates kelly_fraction from the stage win-rate prior
        accumulation ≈ 0.10,  markup ≈ 0.30,  markdown ≈ 0.10
Step 3: position_dollar = cash × min(kelly_fraction, 0.20)
        → Never more than 20% of available cash per trade
        → Minimum $100, maximum 6 open positions
Step 4: shares = position_dollar / entry_price   (fractional shares)
Step 5: Cash is deducted immediately; position recorded
```

**Example allocation at $10,000 starting cash:**

| Stage | Kelly fraction | Cash used | Shares at $500 stock |
|-------|---------------|-----------|---------------------|
| Markup | 0.30 → capped at 0.20 | $2,000 | 4.0 shares |
| Accumulation | 0.10 | $1,000 | 2.0 shares |
| Markdown (short) | 0.10 | $1,000 | 2.0 shares |

### How positions close

Positions close **automatically** during **Daily Review**:

1. Bot fetches live price for every open trade
2. If price ≥ target → closes as **WIN**, returns cash + profit
3. If price ≤ stop loss → closes as **LOSS**, returns cash − loss
4. Lesson is written, learning model updates, portfolio equity snapshotted

You never need to manually close bot positions.

### Viewing the portfolio

1. Go to **Portfolio** in the sidebar
2. **Overview tab** — total equity, total return %, cash available, win rate across all closed positions
3. **Equity Curve** — shows $10,000 growing (or shrinking) as trades close, one data point per daily-review run
4. **Open tab** — all positions with cost basis, share count, stage, direction
5. **History tab** — closed trades with entry, exit, P&L dollar and %, outcome

### Resetting the portfolio

Click **Reset to $10k** on the Portfolio page to wipe all positions and history and start fresh with $10,000. This does **not** affect the forward test trades list or the learning model — only the dollar accounting.

---

## Part 5 — Performance Statistics

The **Performance tab** on the Forward Test page shows what your (and the bot's) combined trading record looks like.

### Key metrics

**Win Rate** — % of closed trades that were profitable. Target: ≥ 50%. Note: a 45% win rate with 3:1 R:R is more profitable than a 65% win rate with 1:1 R:R. Win rate alone is meaningless without R:R.

**Expectancy** — average P&L per trade, accounting for win rate and average size of wins/losses:
```
Expectancy = (Win Rate × Avg Win%) + (Loss Rate × Avg Loss%)
```
Positive expectancy means the strategy makes money over time. The goal is to push expectancy above +0.5% per trade.

**Win Rate by Stage** — the most important panel. After 20+ trades, this tells you which Wyckoff stage you (or the bot) reads most accurately. If markup trades win 70% of the time but accumulation trades only win 40%, the system learns to weight markup signals more heavily and require a higher score threshold for accumulation entries.

**Equity Curve** — cumulative P&L over time. A healthy curve slopes upward with small drawdowns. A jagged curve with large down-spikes means position sizing or stop placement needs adjustment.

**Streak** — current consecutive wins or losses. A 4-loss streak is normal variance; a 7-loss streak suggests the market regime changed and the model needs to adapt (or the score threshold is too low).

---

## Part 6 — What to Do After 30 Days

After 30 closed trades, you have enough data to draw real conclusions.

### Questions to answer

**Which stage do I read correctly?**
Look at Win Rate by Stage. Pick the 1–2 stages where your win rate is above 55%. Focus exclusively on those. Ignore the others until the model improves.

**Which signals are real?**
Look at Signal Weights on the Auto Bot page. Signals still near their starting weight (50–65%) after 30 trades mean the bot hasn't seen them enough to update. Signals significantly above or below their starting weight have real data behind them.

**Am I sizing correctly?**
A healthy paper trade result with 30 trades should show no single loss larger than 5–7% of the assumed account. If individual losses are larger, the stop placement or position size is wrong.

**Is the bot's threshold right?**
If the bot is logging 0–1 trades per scan, the threshold is too high — lower it. If it's logging 5+ trades per scan, the threshold is too low — raise it. 2–3 trades per scan is the target.

### Adjusting the model

The model adjusts automatically via the EMA rule. But you can also reset it to initial priors if you want a clean start (Reset Model button on Auto Bot → Model Brain tab).

After 30+ days of data, the model's learned weights reflect the current market regime. If the market regime changes significantly (e.g., high-volatility bear market after a quiet bull market), the old weights may become misleading. A reset followed by a new 30-day learning period is the correct response.

---

## Common Mistakes to Avoid

**Logging too many trades.** More is not better. 2–3 high-conviction trades per week produce cleaner learnings than 10 mediocre ones. The bot enforces this with a max-3-per-scan limit. Do the same manually.

**Skipping the lesson.** The lesson is the entire point. A closed trade without a lesson is wasted data. Write at minimum one sentence. Over 30 days these become a personal trading journal with real analytical value.

**Ignoring R:R.** A trade with R:R < 1.5 is not worth logging. Even at 60% win rate, a 1:1 R:R trade barely breaks even after fees and slippage. Only log trades with R:R ≥ 2.0.

**Moving the stop.** When you log a stop, it represents your thesis invalidation point. Moving it lower after the trade goes against you converts a disciplined stop into emotional holding. The paper trade system enforces the original stop automatically — use that as a model for real trading.

**Changing the target early.** Closing a trade at +2% when the target was +8% "to lock in profit" is a common mistake that collapses expectancy. Let the target hit or the stop hit. The lesson after is always more valuable than the early exit.

---

## Quick Reference

| Action | Where |
|--------|-------|
| Log a manual paper trade | Forward Test → Log Trade button |
| See open trades + live P&L | Forward Test → Open Trades tab |
| Close a trade manually | Forward Test → expand trade → Close Trade |
| Write a lesson | Forward Test → Closed Trades → expand → Edit |
| See your stats | Forward Test → Performance tab |
| Run the autonomous scanner | Auto Bot → Run Scan button |
| Run daily review (bot learns + portfolio updates) | Auto Bot → Daily Review button |
| See what the bot learned | Auto Bot → Model Brain tab |
| See which signals work | Auto Bot → Signal Weights tab |
| See all bot decisions | Auto Bot → Activity Log tab |
| Reset bot to factory priors | Auto Bot → Model Brain → Reset Model |
| View $10k portfolio + equity curve | Portfolio page (sidebar) |
| See open positions + capital allocated | Portfolio → Open tab |
| See closed trades with P&L | Portfolio → History tab |
| Reset portfolio to $10,000 | Portfolio → Reset to $10k button |
