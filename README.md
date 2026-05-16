# MonkeyTrade

A full-stack stock and crypto analysis web app built on **Wyckoff Market Cycle Theory** and **institutional order flow analysis** — the frameworks professional traders use to identify where a market sits in its cycle and how big players are positioned.

---

## What It Does

### Forward Testing & Autonomous Learning Bot *(new)*
- **Forward Test** — paper-trade any signal in real-time; tracks live P&L, auto-closes when stop/target is hit, and records a daily lesson per trade so you build a personal edge log
- **Autonomous Bot** — scans ~550 tickers (S&P 500 + ETFs + crypto + popular non-index names) in two stages: fast pre-filter by price/volume, then full Wyckoff cycle detection. Scores setups with a Bayesian model, logs its own paper trades, runs a daily review, and updates its learned weights after every outcome (EMA update rule, α = 0.15)
- **Learning Model** — starts from Wyckoff-theory priors (markup 65%, accumulation 55%, distribution 40%, markdown 30%), drifts toward what actually works via each closed trade; score threshold auto-adapts to recent win rate
- **$10,000 Virtual Portfolio** — fully automated capital allocation. The bot sizes each trade via quarter-Kelly (capped at 20% of available cash, max 6 concurrent positions). Positions open and close automatically — no manual intervention needed. Tracks equity curve, win rate, P&L, and best/worst trades in real time

### Core Analysis (EOD data via Yahoo Finance)
- **Cycle Detector** — classifies any stock into one of the four Wyckoff stages with a confidence score
- **Trade Levels** — calculates stage-appropriate entry, stop loss, and target using ATR-scaled math
- **Buying Point** — shows the ideal entry zone, trigger condition, and what invalidates the setup
- **Volume & Whale Detector** — surfaces institutional accumulation/distribution using OBV and volume spike analysis
- **Institutional Intelligence** — options put/call ratio, short interest, 13F institutional holders, insider transactions
- **Stock Screener** — scans Top 100 or full S&P 500 with stage filters and sortable columns
- **Watchlist** — tracks saved tickers with a built-in R:R calculator
- **News Feed** — aggregates market news with strategy-relevance scoring
- **Education** — interactive guide to Wyckoff theory with the four-stage cycle diagram

### Order Flow Intelligence (real-time, Phase 1–3)
- **WebSocket Tick Pipeline** — ingests live Binance trade and order book data into SQLite
- **Footprint Chart** — per-candle buy/sell volume at every price level with imbalance flags
- **VPVR (Volume Profile)** — Point of Control, Value Area High/Low from tick data
- **Market Regime Filter** — K-Means clustering classifies market into Trending / Mean-Reverting / High Volatility
- **Institutional Flow Classifier** — SVM model distinguishes retail flow from institutional accumulation
- **Risk Manager & Kill Switch** — volatility-adjusted position sizing with a portfolio-level daily drawdown halt
- **Trigger Engine** — executes only when price, volume delta, and SVM signal all align simultaneously

### Whale Tracker — Institutional Intelligence (6 live data sources)
- **Smart Money Score** — composite 0–100 score aggregated from all six sources, weighted by signal conviction
- **SEC Form 4 (Insider Transactions)** — real-time cluster buy/sell detection from EDGAR API, zero lag from filing to signal
- **SEC 13D/G (Activist Filings)** — detects new >5% institutional holders and activist campaigns before price reacts
- **FINRA Dark Pool Metrics** — daily off-exchange short volume as an institutional accumulation proxy, with spike detection
- **CFTC COT Report** — futures positioning by Asset Managers vs Leveraged Funds; divergence = pre-squeeze setup
- **Congressional STOCK Act Disclosures** — House + Senate trade filings; cluster buying by 3+ members = policy-informed signal
- **Enhanced Options Flow** — unusual activity sweeps, IV skew (25-delta), deep ITM call detection, dollar-weighted premium flow, expected move from ATM straddle

---

## Tech Stack

### Backend

| Tool | Why |
|------|-----|
| **FastAPI** | Async Python API with automatic OpenAPI docs; handles concurrent stock data and WebSocket background tasks without blocking |
| **yfinance** | Free Yahoo Finance wrapper — covers price history, fundamentals, options chains, 13F holders, and insider transactions without a paid data subscription |
| **pandas** | Required for time-series indicator math; rolling windows, index manipulation, and OHLCV slicing are native operations |
| **ta (Technical Analysis library)** | Clean pandas wrappers for every indicator — avoids reimplementing rolling EMA, ATR, and Bollinger math by hand |
| **scikit-learn** | K-Means for market regime classification; SVM for institutional flow detection. Both are unsupervised or auto-labelled — no hand-labelled dataset required |
| **websockets** | Async WebSocket client for Binance real-time streams; supports auto-reconnect on drops |
| **aiosqlite** | Async SQLite writes for tick data batching — avoids blocking the FastAPI event loop while flushing high-throughput trade records |
| **feedparser** | RSS parsing for news aggregation from multiple financial sources |
| **uvicorn** | ASGI server for FastAPI; runs background pipeline tasks alongside HTTP request handling |
| **requests** | Synchronous HTTP client for all government API calls (SEC EDGAR, FINRA, CFTC, Congress S3 buckets) — these endpoints do not require async and the simpler sync interface is appropriate |

### Frontend

| Tool | Why |
|------|-----|
| **React + Vite** | Component-based UI with hot-module reload; Vite's dev server is significantly faster than Create React App |
| **Tailwind CSS v3** | Utility-first CSS — the design system (colors, shadows, radii) is centralized in `tailwind.config.js` and referenced everywhere; no per-component CSS files |
| **Recharts** | Declarative charting for React; used for candlestick price chart, VPVR bar chart, and regime history area chart |
| **Lucide React** | Lightweight icon set that tree-shakes cleanly with Vite |
| **React Router** | Client-side routing across all pages without full-page reloads |

---

## Trading Theory: Wyckoff Market Cycle

The core premise (from `strategy.txt`):

> *"For prices to rise, most of the shares must be in the hands of the owners."*

**Think of it like a warehouse sale.** A retailer (institution) buys thousands of units cheap when the store is empty (accumulation), marks them up and sells to the public at full price (markup → distribution), then the price collapses once they've sold out (markdown). The stock market is this loop, repeated endlessly.

Price is driven by supply vs demand. Institutions cannot buy or sell their full positions in one day without moving the price against themselves — a $1 billion fund trying to buy $100M of a stock in one session would push the price up before they finished. So they operate slowly across four stages:

```
Accumulation → Markup → Distribution → Markdown → (repeat)
```

### The Four Stages

#### 🔵 Accumulation
Institutions quietly buy over weeks or months while suppressing price to get cheaper fills. Price trades sideways at low levels. Retail investors are bored or scared — they sell to institutions.

**Think of it as:** A big buyer slowly sweeping up every cheap item on eBay without driving up the listing prices, one lot at a time.

**Best for:** Long-term investors. Low-risk entry before the crowd arrives.
**Action:** Buy / Accumulate

#### 🟢 Markup
Once enough shares are "in strong hands," institutions push price up. Momentum builds, news stories appear, breakout traders pile in. Volume and price both surge.

**Think of it as:** The same eBay seller relist everything at 3× the price, and now everyone wants it because they see the price rising.

**Best for:** Breakout and momentum traders. Trail stops as price rises.
**Action:** Ride / Add on pullbacks

#### 🟡 Distribution
Institutions begin selling into the retail FOMO they created during Markup. Price moves sideways at high levels — institutions absorb every buyer. This can last months.

**Think of it as:** The seller quietly unloads inventory onto eager buyers while price stays flat. They're done when their warehouse is empty.

**Best for:** Swing traders who can buy range lows and sell range highs with discipline.
**Action:** Range trade / Reduce position

#### 🔴 Markdown
Price declines persistently. Every bounce is a short-covering trap, not a reversal. "Cheap valuation" narratives appear — they are wrong. Institutions are gone.

**Best for:** Short sellers only. Everyone else stays out.
**Action:** Avoid / Short only

---

## Fundamental Filter

Stocks with growing profits will always have an uptrend chart. Before technical analysis, the screener applies a profit-quality filter based on three tiers:

| Tier | Pattern | Meaning |
|------|---------|---------|
| ⭐⭐⭐ Best | Revenue ↑, Cost ↓ | Sales growing + Economies of Scale emerging |
| ⭐⭐ Good | Revenue ↑ faster than Cost ↑ | Growth stage — expansion costs expected to normalize |
| ⭐ Neutral | Revenue flat, Cost ↓ | Cost cutting — only acceptable for cyclical/seasonal businesses |

A stock failing all three tiers is unlikely to enter a sustained Markup.

---

## Cycle Detection: How It Works

The detector scores each of four stage hypotheses using **eight independent signal categories**. The stage with the highest weighted score wins.

```
Confidence = (winning_stage_score / total_score_all_stages) × 100
```

**Example:** If Markup scores 42, Accumulation scores 18, Distribution scores 12, and Markdown scores 8 — Markup wins with `42 / 80 = 52.5%` confidence.

---

### Signal 1 — 60-Day Price Trend

```
trend_return = (price_today - price_60_days_ago) / price_60_days_ago × 100
```

**Why 60 days?** Three months of price action filters out single-event noise. A 15%+ gain over 60 days cannot come from retail traders alone — moving a stock 15% requires institutional-size buying sustained over months. A 15%+ loss without recovery means institutions are not buying the dip; they are selling into every bounce.

**Plain English:** If a stock is up 20% over 3 months, someone very large has been buying. Individual investors buying in dribs and drabs cannot produce that.

---

### Signal 2 — Moving Average Alignment (SMA20 / SMA50 / SMA200)

```
SMA_n = (sum of closing prices over last n days) / n
```

**Golden Order (Markup signal):**
```
SMA20 > SMA50 > SMA200
```
**Death Order (Markdown signal):**
```
SMA20 < SMA50 < SMA200
```

**Why:** A moving average is the average price paid by buyers over that time window — it is their average cost basis. If SMA20 > SMA50 > SMA200, buyers at every horizon (short, medium, long-term) are profitable. Nobody is panic-selling. The reverse means buyers at every horizon are underwater and looking for an exit.

**Plain English:** Imagine three groups of investors: those who bought in the last month (SMA20), last 2.5 months (SMA50), and last 10 months (SMA200). If all three groups are profitable, the stock has strong support. If all three are losing money, every rally gets sold by someone trying to "get back to even."

---

### Signal 3 — RSI (14-period Relative Strength Index)

```
RS  = average_gain_over_14_days / average_loss_over_14_days
RSI = 100 - (100 / (1 + RS))
```

**Range:** 0 to 100. Above 70 = "overbought." Below 30 = "oversold."

**Example:** If a stock gains an average of $0.80 on up-days and loses $0.40 on down-days over 14 sessions:
```
RS  = 0.80 / 0.40 = 2.0
RSI = 100 - (100 / (1 + 2)) = 100 - 33.3 = 66.7
```
RSI 66.7 = buyers are winning 2:1 but not yet at exhaustion.

**Why RSI 60–70 is the "institutional sweet spot" during Markup:** RSI above 70 means the stock has moved too fast — retail FOMO is driving it, not sustained institutional buying. RSI 60–70 means the uptrend is strong and orderly. RSI below 30 in a sideways base = sellers are exhausted and accumulation may be underway.

---

### Signal 4 — MACD (12/26/9 Exponential Moving Averages)

```
MACD_line      = EMA(12) - EMA(26)
Signal_line    = EMA(9) of MACD_line
Histogram      = MACD_line - Signal_line
```

EMA gives more weight to recent prices. A 12-day EMA reacts faster than a 26-day EMA. When the fast EMA crosses above the slow EMA, short-term momentum just turned upward — early signal that buyers are taking control.

**Why the histogram matters:** The histogram shows the *rate of change* of the trend, not the trend itself. A shrinking histogram while price still rises means momentum is fading — buyers are tiring. This often appears 2–5 days before price peaks.

**Plain English:** Think of MACD as a speedometer vs an odometer. Price is the odometer (where you are). MACD is the speedometer (how fast you're getting there). A car can still be moving forward while decelerating — that deceleration is the signal.

---

### Signal 5 — MACD Divergence

```
Bearish divergence: price makes Higher High  →  MACD makes Lower High
Bullish divergence: price makes Lower Low    →  MACD makes Higher Low
```

**Why divergence is a leading indicator:** If price reaches a new high but the MACD histogram does not confirm it, the new price high was achieved with less buying momentum than the previous high. Fewer buyers showed up. Institutions are quietly stepping back — a breakdown is coming.

**Plain English:** Imagine two runners. The first lap, both finish at the same time. On the second lap, one "wins" but their time is actually slower. They're still ahead, but they're tiring faster. That's bearish divergence.

---

### Signal 6 — Bollinger Bands (20-period, 2 standard deviations)

```
Middle Band = SMA20
Upper Band  = SMA20 + (2 × std_dev_of_closes_over_20_days)
Lower Band  = SMA20 - (2 × std_dev_of_closes_over_20_days)
Band Width  = (Upper - Lower) / Middle
```

**Statistical property:** Under a normal distribution, ~95% of all data points fall within ±2 standard deviations. Applied to prices: 95% of closes should land inside the bands. A sustained close outside = statistically extreme move, confirming a strong trend.

**Squeeze signal:** When `Band Width` shrinks to multi-month lows, the stock has been calm too long. Volatility clusters — calm periods are followed by explosive moves. A squeeze at a stage low → breakout incoming.

**Plain English:** Bollinger Bands are like a rubber band. The more you stretch it (wide bands during a trend), the more it snaps back. The tighter it is (squeeze = narrow bands), the bigger the next move.

---

### Signal 7 — OBV (On-Balance Volume)

```
If close > previous_close:  OBV = previous_OBV + today_volume
If close < previous_close:  OBV = previous_OBV - today_volume
If close = previous_close:  OBV = previous_OBV
```

**Why OBV slope is more powerful than single-day volume:**

Consider a fund that wants to buy 10 million shares. If they buy 500,000 shares per day for 20 trading days, each day looks like "normal" volume. But OBV quietly accumulates +500K × 20 = +10M in net buying. A rising OBV with stable price is the mathematical fingerprint of stealth accumulation.

**Plain English:** OBV is a running tally of "did more people buy or sell today?" If the score keeps going up even while price stays flat, someone is steadily buying without anyone noticing. That's a whale hiding its footprint.

---

### Signal 8 — Stochastic Oscillator (14,3)

```
%K = (current_close - lowest_low_14) / (highest_high_14 - lowest_low_14) × 100
%D = 3-day SMA of %K
```

**Range:** 0 to 100. Above 80 = overbought territory. Below 20 = oversold territory.

**Why it's used as confirmation only:** Stochastic measures where price is within its recent range. In a Markup stage, the stock can stay "overbought" (above 80) for months — that's strength, not a sell signal. In a Distribution stage, a cross below 80 from overbought territory signals the range is starting to break down.

---

## Trade Level Calculation

All stop losses and targets use **ATR (Average True Range)** as the base unit.

```
True Range (each day) = max(high - low,  |high - prev_close|,  |low - prev_close|)
ATR = 14-day average of True Range
```

**Why ATR and not a fixed percentage?**

Stock A moves $0.50 per day on average (ATR = $0.50). Stock B moves $8 per day (ATR = $8.00).

A fixed 2% stop on a $100 stock = $2.00 stop for both. For Stock A this is 4× its normal daily move — safe. For Stock B this is 0.25× its daily move — it will be hit by random noise, not by the thesis being wrong.

ATR-based stop example: ATR = $3.00, entry = $100.
```
Stop (Markup stage) = $100 - (1 × $3.00) = $97.00
Target             = $100 + (3 × $3.00) = $109.00
R:R ratio          = $9.00 risk-reward / $3.00 risk = 3:1
```

| Stage | Stop Formula | Target Formula |
|-------|-------------|---------------|
| **Accumulation** | `min(range_low_20d, lower_BB) - 0.5 × ATR` | `SMA50 × 1.15` or `entry + 4 × ATR` |
| **Markup** | `SMA20 - 1 × ATR` | `entry + 0.5 × (52wk_high - 52wk_low)`, max `entry + 6 × ATR` |
| **Distribution** | `range_low_20d - 0.5 × ATR` | top of 20-day range |
| **Markdown** | `range_high_20d + 0.75 × ATR` (short entry) | `52wk_low` or `entry - 5 × ATR` |

Trades with `R:R < 1.5` are flagged as poor setups.

---

## Whale / Institutional Detection (EOD)

### Volume Spike Analysis

```
volume_ratio = today_volume / avg_volume_20_days
buy_pressure = up_day_volume_sum_10d / (up_day_volume_sum_10d + down_day_volume_sum_10d)
```

| Ratio | Signal |
|-------|--------|
| > 5.0× | Extreme event — earnings, M&A, institutional block print |
| 3–5× | Major institutional activity |
| 1.8–3× | Elevated interest, worth noting |

`buy_pressure > 0.65` combined with `volume_ratio > 3` = accumulation signature.

**Plain English:** If the average daily volume of a stock is 1 million shares and today traded 5 million, somebody very large showed up. The buy_pressure ratio then tells you whether they were buying or selling.

---

### OBV Slope (Stealth Detection)

```
obv_slope_5d  = (OBV_today - OBV_5d_ago) / 5
obv_slope_20d = (OBV_today - OBV_20d_ago) / 20
stealth_signal = obv_slope_20d > 0  AND  volume_ratio < 1.5
```

Rising 20-day OBV with normal daily volume = institutions are spreading purchases across sessions. This signature cannot be faked by a single event and is invisible to traders watching single-day volume.

---

### Options Flow (Put/Call Ratio)

```
PC_ratio = total_put_volume / total_call_volume
```

`PC_ratio > 1.5` = put-heavy. Someone is paying significant premium to be protected against a large downside move. That level of hedging cost is only rational for institutions with large equity exposure.

---

### Short Interest

```
days_to_cover = shares_sold_short / avg_daily_volume
short_pct_float = shares_sold_short / shares_available_to_trade × 100
```

`short_pct_float > 20%` = a meaningful portion of all available shares is borrowed and sold, betting on a decline. If the stock then rises, all those short-sellers must buy to cover — creating additional upward pressure (short squeeze).

---

### 13F Institutional Holders

Quarterly SEC filings show which funds own what. Vanguard or BlackRock with large stakes = institutional support floor. They signal exits through OBV and volume changes before price reacts — their 13F only updates quarterly, but their trades register in OBV the day they happen.

---

### Insider Transactions

Isolated sales are noise (taxes, diversification). Cluster buying by multiple insiders = the signal. Insiders only buy for one reason: they believe the stock will go up.

---

## Order Flow Intelligence (Phase 1–3)

### Phase 1 — Data Infrastructure

#### WebSocket Tick Pipeline (`data_pipeline.py`)
Opens two concurrent Binance WebSocket streams per symbol:
- `aggTrade` — every matched trade with price, quantity, and aggressor side (buyer vs seller)
- `depth5@100ms` — top-5 bid/ask ladder snapshots every 100ms

Trades are batched in memory (100 ticks) before flushing to SQLite, amortizing write overhead without losing data. Auto-reconnects on connection drops with 3-second backoff.

**Why batch instead of write every tick?** At 50–200 ticks/second, individual writes create hundreds of fsync calls per second. Batching 100 ticks into one atomic write reduces disk I/O by ~100× with zero data loss.

---

#### Footprint Chart (`footprint.py`)

Groups ticks into N-minute candles. For each candle, bins trades by price level and computes:

```
buy_qty[price]   = sum of qty where aggressor = buyer
sell_qty[price]  = sum of qty where aggressor = seller
delta[candle]    = total_buy_qty - total_sell_qty
imbalance_flag   = True  when  buy_qty[p] / sell_qty[p] >= 3.0
                        OR  sell_qty[p] / buy_qty[p] >= 3.0
```

**Why 3:1 for imbalance?** A 3:1 ratio means one side is absorbing 75% of all volume at that exact price. That is not random. At $150.00 if 900 contracts are hitting the ask (aggressive buys) versus 300 hitting the bid (aggressive sells), institutions are specifically targeting that level.

**Why footprint over regular OHLCV?** A green candle can form from one large institution buying OR from thousands of small retail limit orders. The footprint shows *which*, by separating aggressive (market order — they want in NOW) from passive (limit order — they're willing to wait) volume at every price level.

---

#### VPVR — Volume Profile Visible Range (`footprint.py`)

```
Step 1: bin_volume[p] = total volume traded at price level p (rounded to tick_size)
Step 2: POC = argmax(bin_volume)           # price with highest traded volume
Step 3: expand outward from POC, always picking the adjacent bin with more volume,
        until cumulative_volume >= 0.70 × total_volume
Step 4: VAH = upper boundary bin, VAL = lower boundary bin
```

**Why 70%?** The Chicago Board of Trade originally defined the Value Area as the price range covering 70% of day's volume — where "fair value" was agreed upon by the market. Price outside the VA is considered "too cheap" or "too expensive" by participants; it tends to return to the VA.

**Why POC matters for entries:**
```
distance_to_poc = |current_price - POC| / POC × 100
```
Entries within 1% of POC have a natural institutional defense — funds accumulating near POC will buy every dip back to it, providing a natural stop floor.

---

### Phase 2 — Machine Learning Models

#### Market Regime Filter (`regime_detector.py`)

K-Means clustering (k=3) on five normalized features:

```
f1 = ATR / close                           # volatility as % of price
f2 = ADX / 100                             # trend strength (0=oscillating, 1=strong trend)
f3 = (SMA20 - SMA50) / close              # moving average spread
f4 = std_dev(returns_20d)                  # realized volatility
f5 = (close - close_10d_ago) / close_10d_ago   # 10-day momentum
```

K-Means finds cluster centroids by minimizing:
```
J = Σ ||x_i - μ_k||²       (sum of squared distances from each point to its cluster center)
```

Each day's feature vector is assigned to the nearest centroid. The centroid with highest ADX (f2) = Trending regime. Remaining centroids are ranked by combined f1+f4 (volatility) — highest = High Volatility, lowest = Mean-Reverting.

**Why K-Means instead of a labelled classifier?** You cannot observe a "regime" directly — you can only measure it from indicator behaviour. K-Means lets the historical data itself define what "trending" looks like for each instrument, adapting to each stock's personality without hand-labelled training data.

**Why three regimes and why it matters:**

The same RSI=72 reading means completely different things:
- **Trending regime (ADX > 25):** RSI 72 = healthy trend continuation, do not fade it
- **Mean-Reverting regime (ADX < 20):** RSI 72 = near the range top, expect a reversal
- **High Volatility regime:** RSI 72 = unreliable; reduce position size or stand aside

Using the wrong strategy in the wrong regime is the most common cause of profitable setups failing.

---

#### Institutional Flow Classifier (`flow_classifier.py`)

RBF-SVM trained on 1-minute bar features aggregated from tick data:

```
vol_delta_norm = (buy_qty - sell_qty) / total_qty        # directional conviction [-1, +1]
avg_trade_size = total_qty / n_trades                     # mean qty per trade
n_trades       = count of trades in the bar               # frequency
close_vs_vwap  = (close - VWAP) / VWAP                   # where price settled vs average
buy_ratio      = buy_qty / total_qty                      # fraction of aggressive buying
```

**Auto-labelling strategy:**
```
institutional_label = 1  if  avg_trade_size > Q75(avg_trade_size)
                             AND |vol_delta_norm| > Q75(|vol_delta_norm|)
                      0  otherwise
```
Top quartile on *both* size and directional conviction = institution. Large AND opinionated = not retail.

**RBF-SVM decision boundary:**
```
K(x_i, x_j) = exp(-γ ||x_i - x_j||²)
```
The SVM finds the maximum-margin hyperplane separating institutional from retail bars in feature space. The RBF kernel allows the boundary to be non-linear — institutional flow does not separate cleanly in a straight line from retail flow, but it does in curved high-dimensional space.

**Plain English:** The SVM is trained to recognize what institutional trading "feels like" across 5 measurements. Once trained, it looks at a new 1-minute bar and answers: does this pattern of size, speed, and direction match the institutional pattern, or the retail pattern?

---

### Phase 3 — Risk Management & Execution

#### InstitutionalRiskManager (`risk_manager.py`)

**Position sizing formula:**
```
dollar_risk   = account_balance × risk_pct          # e.g. $100,000 × 1% = $1,000
stop_distance = ATR × atr_multiplier                # e.g. $3.50 × 2.0  = $7.00
shares        = dollar_risk / stop_distance         # e.g. $1,000 / $7.00 = 142 shares
position_value = shares × current_price             # e.g. 142 × $100 = $14,200
```

**Worked example with numbers:**
- Account: $100,000
- Risk per trade: 1% → $1,000 max loss
- Stock price: $100, ATR (14-day): $3.50
- Stop distance: 2.0 × $3.50 = $7.00
- Position size: $1,000 / $7.00 = **142 shares** ($14,200 position, 14.2% of account)
- If stop is hit: loss = 142 × $7.00 = **$994** ≈ exactly 1% of account ✓

This math ensures that no matter how volatile the stock is, the dollar loss if wrong is always the same.

**Portfolio Kill Switch:**
```
daily_drawdown = (current_equity - opening_equity) / opening_equity
HALT if daily_drawdown <= -0.05
```
If the portfolio drops 5% in a single day across all open positions, the system halts all new orders and liquidates everything at current price. A 5% daily drawdown means something macro is wrong — not a normal trading day.

---

#### Trigger Engine (`trigger_engine.py`)

Executes a BUY only when **all three conditions align simultaneously**:

```
C1: |current_price - POC| / POC <= 0.01       # within 1% of POC
C2: volume_delta > 0                           # aggressive buys > aggressive sells
C3: svm_signal == 1                            # SVM classifies flow as institutional

fire = C1 AND C2 AND C3
stop_loss = POC × (1 - 0.005)                 # 0.5% below POC
```

**Why require all three — probability math:**

Assume each condition has a 60% true-positive rate independently:
- Probability all three are correct together: `0.60 × 0.60 × 0.60 = 21.6%` of all bars trigger
- But given a true institutional setup, all three align ~85% of the time
- False positive rate drops from 40% per signal to `0.40³ = 6.4%` for all three together

The three-condition gate is a logical AND that dramatically reduces false positives at the cost of missing some valid setups — the right tradeoff for a system that also sizes positions.

---

## Whale Tracker — Institutional Intelligence

### Why Track Institutional Flow?

Retail traders **react** to price. Institutions **move** price. By the time a breakout appears on a chart, the institutional buyer has already spent weeks accumulating. Every source here is designed to detect positioning *before* price, not confirmation after.

**The information asymmetry in numbers:**

A retail investor sees a stock at $100 and decides to buy 100 shares = $10,000 order. This cannot move price.

A pension fund managing $10 billion decides to add 1% to a $50 stock = $100 million position = 2,000,000 shares. At 500,000 shares per day (institutional limit to avoid moving price), this takes **4 full trading weeks** to build. During those 4 weeks, the position is invisible on any single day's chart — but shows up in OBV, dark pool volume, and Form 4 filings.

The six data sources are legally mandated disclosures (institutions cannot avoid them) and completely free (no API key required for any source).

---

### Data Sources

| Source | URL / API | Update Lag | What It Reveals |
|--------|-----------|-----------|-----------------|
| **SEC Form 4** | `efts.sec.gov` + `yfinance` | ≤2 business days after trade | Corporate insiders (executives, directors, 10%+ owners) buying or selling their own stock. A cluster (≥3 insiders buying in 30 days) is the highest-conviction signal. |
| **SEC 13D/G** | `efts.sec.gov` EDGAR full-text search | ≤10 days after crossing 5% | Any entity acquiring >5% of a public company must file. 13D = activist intent. 13G = passive large holder. A new 13D is a catalyst before the press release exists. |
| **FINRA Short Volume** | `cdn.finra.org/equity/regsho/daily/` | Next business day | Daily off-exchange volume data. `dark_pct = ShortVolume / TotalVolume` proxies institutional accumulation through dark pools. Spike = >1.5× 10-day avg AND >40% total. |
| **CFTC COT Report** | `publicreporting.cftc.gov` (Socrata API) | Every Friday for prior week | Futures positioning by trader type. Asset Managers = real money (pension funds). Leveraged Funds = hedge funds. Divergence = pre-squeeze. |
| **Congress STOCK Act** | House S3 bucket + Senate S3 bucket | ≤45 days after trade | Members of Congress must disclose trades. Academic research found senators outperform the market by ~12%/year. Cluster buying by 3+ members = policy-informed signal. |
| **Options Flow (yfinance)** | Yahoo Finance options chains | Real-time (20-min delayed) | Multi-expiry scan: dollar-weighted flow, unusual sweeps (vol/OI ≥ 2.0), IV skew, deep ITM calls, ATM expected move. |

---

### Formulas Behind Each Data Source

#### FINRA Dark Pool Percentage

```
dark_pct = (ShortVolume / TotalVolume) × 100
```

FINRA requires all off-exchange trades to be reported as "short volume" under Regulation SHO (this is a technical reporting designation, not actual short-selling). When a bank's dark pool fills a 500,000-share institutional buy order, it appears in FINRA data as ShortVolume.

**Spike detection:**
```
avg_dark_pct_10d = mean(dark_pct over last 10 days)
spike = True  if  dark_pct_today > 1.5 × avg_dark_pct_10d  AND  dark_pct_today > 40
```

**Plain English:** If a stock normally has 30% of its volume off-exchange and today it suddenly shows 55%, a large institution just executed a block order through a dark pool. They didn't want everyone to see the order on the public exchange — but FINRA still captures it the next day.

---

#### CFTC COT — Net Positioning

```
net_position = long_contracts - short_contracts
net_change   = net_position_this_week - net_position_last_week
```

Three trader categories:
- **Asset Managers** (pension funds, mutual funds, sovereign wealth) — the "smart money" with 3–10 year time horizons
- **Leveraged Funds** (hedge funds) — short-term directional traders
- **Dealers** (banks) — primarily hedging, not directional

**Pre-squeeze formula:**
```
pre_squeeze = True  if  asset_mgr_net > 0          # real money is net long
                        AND asset_mgr_net_change > 0  # and adding to longs
                        AND lev_fund_net < 0           # while hedge funds are short
```

When this condition is true, the patient money (asset managers) is accumulating while the impatient money (hedge funds) is betting against them. Historically this resolves with a short squeeze — hedge funds are forced to cover, adding additional buying pressure on top of the asset manager's existing demand.

**Plain English:** Think of two groups arm-wrestling — one representing pension funds (very strong, very patient) and the other representing hedge funds (aggressive but have to cover their bets eventually). When pension funds are clearly winning but hedge funds refuse to give up, the moment hedge funds finally snap = a violent price surge as they all cover at once.

---

#### Options Premium Dollar Flow

```
call_premium_total = sum(last_price × volume × 100)  for all call contracts scanned
put_premium_total  = sum(last_price × volume × 100)  for all put contracts scanned
call_pct = call_premium_total / (call_premium_total + put_premium_total) × 100
```

Thresholds:
```
bullish  if  call_pct > 65%    (65¢ of every options dollar is going into calls)
bearish  if  call_pct < 35%    (65¢ of every options dollar is going into puts)
neutral  otherwise
```

**Why dollar-weighted instead of contract count?** A retail trader buying 1 call contract at $0.50 premium = $50 cost. An institution buying 500 contracts at $8.00 = $400,000 cost. Counting contracts equally would make the retail trade look as significant. Dollar weighting reveals who is actually committing capital.

---

#### IV Skew (25-Delta)

```
skew = IV_of_25delta_put - IV_of_25delta_call
```

A 25-delta option is roughly "25% chance of expiring in-the-money" — it represents the wings of the distribution. If put wings cost more than call wings, the market is paying a premium for downside protection.

```
bearish signal  if  skew > threshold    (puts cost significantly more than calls)
bullish signal  if  skew < -threshold   (calls cost more than puts — rare, means call demand)
neutral         otherwise
```

**Plain English:** Imagine car insurance. Normal car insurance (put protection) costs more than "gap insurance that pays if your car doubles in value" (call insurance). If suddenly the protection-from-collapse insurance skyrockets in price, someone is scared of a crash. That fear shows in the IV skew number.

---

#### Unusual Activity Detection

```
vol_oi_ratio = volume_traded_today / open_interest

unusual = True  if  vol_oi_ratio >= 2.0
                    AND premium_usd >= 50,000

sweep   = True  if  vol_oi_ratio >= 5.0       # volume is 5× open interest
```

`Open interest` is the number of existing contracts. If today's volume exceeds existing open interest by 2×, it means this is almost entirely **new positioning** — someone is opening a brand-new bet, not closing an existing one. At 5× it's called a "sweep" because the order was likely routed aggressively across multiple exchanges simultaneously.

**Plain English:** If a stock's call options have 1,000 existing contracts and today 3,000 contracts traded (vol/OI = 3.0), 2,000 of those had to be brand new. Someone just opened a fresh $X million bet that the stock will rise. That's not hedging — that's directional conviction.

---

#### Expected Move from ATM Straddle

```
expected_move_pct = (ATM_call_price + ATM_put_price) / current_stock_price × 100
```

The ATM (at-the-money) straddle price is the sum of what you'd pay to own both the call and the put at the current price. If you own both, you profit if the stock moves more than the total cost in either direction. This is therefore the market's implied expectation of how much the stock will move by expiry.

**Example:** Stock at $100. ATM call = $4.50, ATM put = $4.00.
```
expected_move = ($4.50 + $4.00) / $100 × 100 = 8.5%
```
The options market is saying the stock is expected to move ±8.5% by expiry. If you think it'll move more, you buy the straddle. If less, you sell it.

---

#### Deep ITM Call Detection

```
moneyness     = strike / current_price
deep_itm_call = True  if  moneyness <= 0.85   # strike ≤ 85% of current price
                           AND volume >= 500
```

A call with strike 15% below the current stock price has near-zero optionality — it moves almost identically to owning the stock. Its delta ≈ 0.98 (moves 98 cents for every $1 the stock moves). So why buy it instead of stock?

**The quarterly reporting game:**
- Equity shares: appear in 13F filings every quarter
- Options contracts: appear as derivatives, not equity, in 13F until exercised

An institution buying 500 deep ITM calls on $100 stock at $85 strike controls 50,000 shares × ~$98 delta = $4.9M of effective equity exposure — without the position appearing in equity 13F filings until the next quarter. It buys them an extra 90 days of stealth.

---

### Smart Money Score Model

**Base score: 50 (neutral). All sources add or subtract. Final score clamped to [0, 100].**

```
score = 50 + Σ(source_deltas)
score = max(0, min(100, score))
```

| Source | Max Bullish | Max Bearish | Trigger Condition |
|--------|------------|------------|------------------|
| SEC Form 4 — Cluster Buy | +20 | — | ≥3 executives buying in 30 days |
| SEC Form 4 — Solo Buy | +10 | — | 1–2 insiders buying |
| SEC Form 4 — Cluster Sell | — | −15 | ≥3 executives selling in 30 days |
| SEC Form 4 — Isolated Sell | — | −5 | 1–2 insiders selling (often just diversification) |
| SEC 13D — Activist Filing | +20 | — | New 13D from known activist or intent language |
| SEC 13G — Passive Large Holder | +5 | — | New >5% passive institutional holder |
| FINRA Dark Pool — Spike | +15 | — | dark_pct > 1.5× avg AND dark_pct > 40 |
| FINRA Dark Pool — Elevated | +10 | — | Bullish trend without spike threshold |
| FINRA Dark Pool — Bearish | — | −12 | Declining dark pool participation (distribution) |
| Options Premium Flow — Bullish | +12 | — | call_pct > 65% |
| Options Premium Flow — Bearish | — | −12 | call_pct < 35% |
| IV Skew — Bearish | — | −10 | 25-delta put IV substantially above call IV |
| IV Skew — Bullish | +8 | — | 25-delta call IV above put IV |
| Unusual Options — Bullish | +10 | — | ≥3 call sweeps: vol/OI ≥ 2.0 + premium ≥ $50K |
| Unusual Options — Bearish | — | −10 | ≥3 put sweeps meeting same threshold |
| Congress — Cluster Buy | +15 | — | ≥3 members buying same ticker within 90 days |
| Congress — Solo Buy | +7 | — | 1–2 members buying |
| Congress — Bearish | — | −8 | Net selling by members |
| COT — Asset Mgr Bullish | +12 | — | asset_mgr_net > 0 AND increasing week-over-week |
| COT — Bearish | — | −12 | Asset Manager net short or Leveraged Funds heavily short |
| Short Interest — Squeeze Setup | +8 | — | short_pct_float > 5% AND short_change_mom < −10% |
| Short Interest — Bearish | — | −8 | short_pct_float > 20% AND increasing |

**Worked Score Example:**

Suppose AAPL shows: insider cluster buy (+20), dark pool spike (+15), unusual call sweeps (+10), COT bullish (+12), congressional solo buy (+7).

```
score = 50 + 20 + 15 + 10 + 12 + 7 = 114  →  clamped to 100
rating = EXTREME BULLISH
```

Now suppose the same stock also has: high short interest (-8) and bearish IV skew (-10).

```
score = 50 + 20 + 15 + 10 + 12 + 7 - 8 - 10 = 96  →  clamped to 100
```

Still extreme bullish, but the bearish signals reduce conviction. The signal feed shows all individual signals ranked by |delta| so the user sees what is driving the score.

**Score Interpretation:**

| Score | Rating | Meaning |
|-------|--------|---------|
| 80–100 | EXTREME BULLISH | Multiple institutional signals converging. Rare. Historically precedes significant upside. |
| 65–79 | BULLISH | Smart money is positioning long. Risk/reward skewed upside. |
| 45–64 | NEUTRAL | Mixed or absent signals. No directional edge from institutional data. |
| 30–44 | BEARISH | Institutional indicators suggest selling pressure or distribution. |
| 0–29 | EXTREME BEARISH | Multiple signals warn of institutional exit or active shorting. |

---

### Why Each Signal Was Weighted This Way

**Insider cluster buy (+20, highest weight):** Executives know the internal financials, pipeline, and strategy before the market does. They face legal penalties for trading on material non-public information — but they can buy based on what they observe that is *not yet material*. Three executives buying simultaneously is mathematical coordination: the probability that three insiders independently decide to buy on the same stock in the same month by coincidence is very low. For a stock where insiders each trade 5–10 times per year, three simultaneous buys in a 30-day window is approximately a 1-in-500 event by chance alone.

**Activist 13D (+20, tied highest):** A 13D filer has crossed 5% ownership ($5M+ in a $100M company) and filed public confrontational intent. They have skin in the game and a legal obligation to follow through. Academic studies show stocks receiving 13D filings outperform by an average of 5–15% in the 30 days following the filing.

**Dark pool spike (+15):** Institutions cannot execute block orders on public exchanges without the bid/ask spread widening against them (market impact). A 500,000-share order hitting the NASDAQ would be obvious and cause price to spike before the order is filled. Dark pools exist to prevent this. When dark pool volume spikes 1.5× above baseline, a block order just executed — and price has not yet reflected it.

**Options premium flow (+12 / −12):** Dollar-weighted flow reveals commitment. A 70/30 call/put dollar split means for every $1 spent hedging downside, someone spent $2.33 betting on upside. At that ratio, the premium outlay is in the millions for large strikes — not retail behavior.

**COT (+12 / −12):** Asset Managers represent pension funds, sovereign wealth funds, and endowments — the largest pools of capital in the world. When they shift their futures positioning, equities must follow because they are the same underlying exposure. The weekly COT report is one of the most reliable leading indicators in professional macro trading.

**Congressional trades (+15 cluster / +7 solo):** The Ziobrowski (2004) Senate study found senators' stock picks beat the market by 12.3% per year over 6 years. The 2011 follow-up found House members outperformed by 6%. The STOCK Act (2012) mandated disclosure within 45 days — but the market still underreacts to this information because nobody aggregates it. Three members buying the same ticker in 90 days is not diversification — it is coordination around a shared information set (upcoming legislation, regulatory decisions, government contracts).

**Short interest squeeze (+8):** The mechanics: short-sellers borrow shares and sell them, hoping to buy them back cheaper. If the stock rises instead, they are losing money on every share they owe. When short interest drops more than 10% month-over-month while the float is still 5%+ short, thousands of short-sellers are buying to close positions. That buying creates more buying pressure on top of the fundamental demand. The mathematical inevitability: someone who is short *must* buy to close the position eventually.

**Asymmetric buy/sell weights (buys > sells):** Insider purchases are unambiguous — executives buy stock because they believe it will rise. There is only one reason to buy. Insider sales, however, have dozens of explanations: planned selling schedules (10b5-1 plans), estate taxes, diversification, exercising expiring options. Because the signal-to-noise ratio for sells is lower, a single sell is weighted only −5 versus +10 for a single buy. Three coordinated sells still get −15 because coordination is harder to explain away.

---

### How the Frontend Renders It

The **WhaleTracker** page (`/whale`) loads in three async stages to minimize perceived wait time:

```
Stage 1 (fast, ~200ms):  GET /api/whale/{ticker}/score   → show score card immediately
Stage 2 (parallel, ~3s): Promise.all([
                            GET /api/whale/{ticker}/insider,
                            GET /api/whale/{ticker}/options-flow,
                            GET /api/whale/{ticker}/congress
                          ])
Stage 3 (independent):   DarkPool component's own useEffect
                          GET /api/whale/{ticker}/darkpool
```

**Signal Feed** — all signals sorted descending by |delta|, highest conviction first. Each signal is an expandable accordion showing source, direction badge, score contribution, and full interpretation text.

**COT Panel** — bar chart of Asset Manager net positioning by week (green = net long, red = net short) with interpretation of current positioning vs leveraged fund divergence.

**Options Panel** — premium flow bar showing call vs put dollar split, expected move from ATM straddle price, IV skew percentage, unusual activity table with sweep flags, and deep ITM call warning when applicable.

---

## Project Structure

```
monkey-trade3/
├── backend/
│   ├── main.py                      # FastAPI app, CORS, router registration
│   ├── requirements.txt
│   ├── routers/
│   │   ├── stock.py                 # /api/stock/{ticker}/* endpoints
│   │   ├── screener.py              # /api/screener/run, /universes
│   │   ├── watchlist.py             # /api/watchlist CRUD
│   │   ├── news.py                  # /api/news
│   │   ├── orderflow.py             # /api/orderflow/* (Phase 1–3)
│   │   ├── whale.py                 # /api/whale/* (institutional intelligence)
│   │   ├── quant.py                 # /api/quant/* (HMM, Kalman, Kelly, IC)
│   │   ├── forwardtest.py           # /api/forwardtest CRUD + lesson endpoint
│   │   ├── bot.py                   # /api/bot/* (scan, daily-review, model, activity)
│   │   └── portfolio.py             # /api/portfolio/* (equity, positions, history, reset)
│   ├── services/
│   │   ├── cycle_detector.py        # Wyckoff scoring engine + 8 signals
│   │   ├── institutional.py         # Options, short interest, 13F, insiders (EOD)
│   │   ├── stock_data.py            # yfinance wrappers for price + fundamentals
│   │   ├── screener.py              # S&P 500 / Top 100 scanning
│   │   ├── news.py                  # RSS aggregation + relevance scoring
│   │   ├── data_pipeline.py         # WebSocket tick ingestion → SQLite
│   │   ├── footprint.py             # Footprint chart + VPVR from tick data
│   │   ├── regime_detector.py       # K-Means market regime classification
│   │   ├── flow_classifier.py       # SVM institutional flow detection
│   │   ├── risk_manager.py          # Position sizing + kill switch
│   │   ├── trigger_engine.py        # Three-condition execution gate
│   │   ├── sec_edgar.py             # SEC Form 4 + 13D/G filings
│   │   ├── dark_pool.py             # FINRA dark pool metrics
│   │   ├── cot_report.py            # CFTC COT futures positioning
│   │   ├── congress_trades.py       # House + Senate STOCK Act disclosures
│   │   ├── options_flow.py          # Enhanced multi-expiry options flow
│   │   ├── smart_money.py           # Smart Money Score aggregator (0–100)
│   │   ├── hidden_markov.py         # HMM regime detection (Baum-Welch / Viterbi)
│   │   ├── kalman_filter.py         # Kalman Filter price smoothing + signal
│   │   ├── mean_reversion.py        # Ornstein-Uhlenbeck mean-reversion model
│   │   ├── signal_quality.py        # IC, IR, Ljung-Box, Hurst exponent
│   │   ├── kelly.py                 # Kelly Criterion position sizing
│   │   ├── autonomous_bot.py        # Autonomous scanner + learner + daily reviewer
│   │   ├── bot_model.py             # Bayesian EMA learning model (load/save/update/score)
│   │   └── portfolio.py             # $10k virtual portfolio — open/close positions, equity curve
│   └── data/
│       ├── bot_model.json           # Persisted learned weights (stage priors, signal weights)
│       ├── bot_activity.json        # Bot decision log (last 200 entries)
│       ├── portfolio.json           # Virtual portfolio state (cash, positions, equity curve)
│       └── scan_logs/               # Per-scan JSON logs with full ticker decisions
└── frontend/
    ├── public/
    │   └── monkey_pic.jpg           # App logo/avatar served as static asset
    └── src/
        ├── App.jsx                  # Layout, collapsible sidebar, monkey logo, top bar
        ├── pages/
        │   ├── Dashboard.jsx        # Main analysis view
        │   ├── Screener.jsx         # Stock scanner
        │   ├── CycleDetector.jsx    # Wyckoff stage detector
        │   ├── OrderFlow.jsx        # Phase 1–3 order flow page
        │   ├── WhaleTracker.jsx     # Institutional intelligence — 7-panel view
        │   ├── QuantEngine.jsx      # HMM + Kalman + Kelly + IC dashboard
        │   ├── ForwardTest.jsx      # Paper trading — open/closed trades + stats
        │   ├── BotControl.jsx       # Autonomous bot command center + learning model
        │   ├── Portfolio.jsx        # $10k virtual portfolio — equity curve, positions, history
        │   ├── Watchlist.jsx        # Saved tickers + R:R calculator
        │   ├── Education.jsx        # Wyckoff theory guide
        │   └── News.jsx             # News feed
        └── components/
            ├── StageBadge.jsx
            ├── CandlestickChart.jsx
            └── StageScoreBar.jsx
```

---

## Forward Testing

See **[FORWARD_TEST_GUIDE.md](FORWARD_TEST_GUIDE.md)** for the full step-by-step guide on how to:
- Log manual paper trades from any signal in the app
- Use the Autonomous Bot to find and log setups automatically
- Run the daily review so the model learns from every outcome
- Read the performance stats and what to do after 30 days

---

## Running Locally

**Requirements:** Python 3.11+, Node.js 18+

```bash
# 1. Install backend dependencies
pip install -r backend/requirements.txt

# 2. Start the backend (from project root)
python -m uvicorn backend.main:app --reload
# API available at http://localhost:8000

# 3. Install and start frontend (separate terminal)
cd frontend
npm install
npm run dev
# App available at http://localhost:5173
```

Or use the included batch scripts on Windows:
```
start_backend.bat
start_frontend.bat
```

### Using the Order Flow page
The Footprint, VPVR, and SVM features require live tick data:
1. Navigate to **Order Flow** in the sidebar
2. Enter a Binance symbol (e.g. `BTCUSDT`) and click **Start** to open the WebSocket pipeline
3. Wait a few minutes for tick data to accumulate in SQLite
4. Click **Load** on the Footprint panel to visualize volume profile and candle delta
5. Click **Train** on the SVM panel to train the classifier on the collected data
6. Use the **Trigger Engine** panel to evaluate a live entry signal

---

## API Endpoints

### Stock Analysis
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/stock/{ticker}/cycle?period=1y` | Full Wyckoff analysis — stage, signals, indicators, trade levels |
| `GET` | `/api/stock/{ticker}/info` | Basic stock info and fundamentals |
| `GET` | `/api/stock/{ticker}/financials` | Income statement and balance sheet |
| `GET` | `/api/stock/{ticker}/institutional` | Options flow, short interest, 13F holders, insiders |
| `GET` | `/api/stock/{ticker}/news?limit=10` | Stock-specific news |
| `POST` | `/api/screener/run` | Run screener with filters and universe selection |
| `GET` | `/api/screener/universes` | Available universes with ticker counts |
| `GET/POST/DELETE` | `/api/watchlist` | Watchlist management |
| `GET` | `/api/news?limit=20` | General market news feed |

### Order Flow (Phase 1–3)
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/orderflow/pipeline/start/{symbol}` | Start WebSocket tick pipeline for a symbol |
| `POST` | `/api/orderflow/pipeline/stop` | Stop the running pipeline |
| `GET` | `/api/orderflow/pipeline/status` | Pipeline status, DB path, SVM/risk state |
| `GET` | `/api/orderflow/footprint/{symbol}` | Footprint candles + VPVR from SQLite tick data |
| `GET` | `/api/orderflow/vpvr/{symbol}` | VPVR only (POC, VAH, VAL, full profile) |
| `GET` | `/api/orderflow/regime/{ticker}` | K-Means regime classification with 60-bar history |
| `POST` | `/api/orderflow/train-classifier/{symbol}` | Train SVM on collected tick data |
| `POST` | `/api/orderflow/predict-flow` | Predict institutional vs retail for a given bar |
| `POST` | `/api/orderflow/risk/init` | Initialize risk manager with account balance |
| `GET` | `/api/orderflow/risk/status` | Portfolio equity, drawdown, open positions |
| `POST` | `/api/orderflow/risk/position-size` | Calculate volatility-adjusted position size |
| `POST` | `/api/orderflow/risk/add-position` | Add an open position to risk tracking |
| `POST` | `/api/orderflow/risk/update-price` | Update price (triggers stop-loss + kill-switch check) |
| `POST` | `/api/orderflow/risk/reset-daily` | Reset daily drawdown baseline and kill switch |
| `POST` | `/api/orderflow/trigger/evaluate` | Evaluate all three trigger conditions for a buy signal |

### Forward Test
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/forwardtest` | List all trades (open ones enriched with live price + P&L) |
| `POST` | `/api/forwardtest` | Log a new paper trade |
| `PATCH` | `/api/forwardtest/{id}/close` | Manually close a trade at a given exit price |
| `PATCH` | `/api/forwardtest/{id}/lesson` | Add a daily lesson + 1–5 star rating to a closed trade |
| `DELETE` | `/api/forwardtest/{id}` | Delete a trade record |
| `GET` | `/api/forwardtest/stats` | Performance stats: win rate, expectancy, equity curve, stage breakdown |

### Autonomous Bot
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/bot/run-stream` | SSE stream: live scanner progress + logged trades |
| `POST` | `/api/bot/run` | Trigger a background scan (non-streaming) |
| `POST` | `/api/bot/daily-review` | Refresh all open trades, auto-close hits, update model, snapshot equity |
| `GET` | `/api/bot/model` | Current learned model state (stage win rates, signal weights, threshold) |
| `POST` | `/api/bot/model/reset` | Reset model back to initial Wyckoff-theory priors |
| `GET` | `/api/bot/activity?limit=50` | Bot decision log (scans, learns, reviews) |
| `GET` | `/api/bot/scanlogs` | List scan log filenames (most recent first) |
| `GET` | `/api/bot/scanlogs/{filename}` | Full detail for a specific scan log |
| `GET` | `/api/bot/scanlogs/latest/summary` | Quick summary of the most recent scan |

### Virtual Portfolio
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/portfolio/` | Full portfolio summary — equity, cash, positions, stats, equity curve |
| `GET` | `/api/portfolio/equity-curve` | Equity curve snapshots (one per day daily-review runs) |
| `GET` | `/api/portfolio/positions` | Current open positions with cost basis and share counts |
| `GET` | `/api/portfolio/history?limit=50` | Closed trade history |
| `POST` | `/api/portfolio/reset` | Reset portfolio to a clean balance (default $10,000) |

### Whale Tracker — Institutional Intelligence
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/whale/{ticker}` | Full intelligence package — all 6 sources + Smart Money Score |
| `GET` | `/api/whale/{ticker}/score` | Smart Money Score only (fast, loads first in UI) |
| `GET` | `/api/whale/{ticker}/insider` | SEC Form 4 insider transactions + 13D/G activist filings |
| `GET` | `/api/whale/{ticker}/darkpool?days=10` | FINRA dark pool metrics, 3–30 day lookback |
| `GET` | `/api/whale/{ticker}/options-flow` | Full options analysis: flow, skew, unusual, deep ITM, expected move |
| `GET` | `/api/whale/{ticker}/congress?days=365` | Congressional trade disclosures, 30–730 day window |
| `GET` | `/api/whale/cot/{instrument}` | CFTC COT for a futures instrument (SP500, NASDAQ, GOLD, OIL, BONDS, VIX) |

---

## Design Decisions

**Why not a dark theme?** A light theme with high-contrast stage colors (blue/green/amber/red) is easier to read at a glance. These colors carry immediate stage meaning — dark themes wash out the distinction.

**Why separate institutional API call on Dashboard?** Fetching options chains and 13F data takes 2–5 seconds. Splitting it from the main cycle analysis means the chart and signals appear immediately while institutional data loads in the background.

**Why ATR for all trade levels?** A fixed-percentage stop (e.g., always −5%) ignores that Stock A moves 1%/day and Stock B moves 8%/day. ATR-based stops are proportional to each stock's actual volatility. A stop too tight relative to daily ATR gets hit by noise before the thesis can prove itself.

**Why OBV for EOD institutional detection rather than just volume?** A single high-volume day could be an index rebalance, expiration, or news event. OBV accumulated over 20 days filters that noise. A steadily rising 20-day OBV means sustained net buying across many sessions — the only way to produce it is consistent institutional demand.

**Why K-Means for regime and SVM for flow, not a single deep learning model?** Both tasks lack labelled training data. K-Means requires no labels and defines regimes from the data's own structure. The SVM uses auto-labelled data (top-quartile bars by size + conviction) as a bootstrap. A deep learning model would require thousands of hand-labelled examples. For an unsupervised problem, simpler models that explain their decisions are more trustworthy than black-box networks — especially when a wrong prediction costs real money.

**Why batch tick writes to SQLite instead of writing every tick?** At 50–200 Binance aggTrades per second, individual writes create hundreds of fsync calls per second. Batching 100 ticks into one atomic write reduces disk I/O by ~100× with no data loss, since ticks accumulate in memory and flush atomically.

**Why use FINRA short volume as a dark pool proxy rather than a paid feed?** True dark pool data disaggregated by venue requires expensive institutional feeds. FINRA's Regulation SHO data is the best free proxy: all FINRA-member firms must report off-exchange volume as short volume. It captures the same institutional block-order flow. Not identical to a paid feed, but the correlation with real dark pool accumulation is strong enough for a directional signal.

**Why does the dark pool spike use a relative threshold (1.5× avg) rather than an absolute level?** A large-cap stock may consistently run 45% off-exchange volume — seeing 46% tells you nothing. The spike is the signal: `dark_pct / avg_dark_pct_10d >= 1.5`. A sudden increase from baseline means a block order just executed that wasn't there yesterday.

**Why track Congressional trades despite the 45-day disclosure lag?** The Ziobrowski studies (Senate 2004, House 2011) found that outperformance persists *after* public disclosure because the market underreacts to buried STOCK Act filings. Our cluster detection surfaces coordinated trades that individual filing browsers miss. Three members buying the same ticker in 90 days is the signal; individual filings are noise.

**Why asymmetric insider buy/sell weights?** Executives buy for one reason: they think the stock will rise. They sell for dozens of reasons: scheduled 10b5-1 plans, tax diversification, option exercise, estate planning, home purchase. The signal quality is fundamentally asymmetric — a buy is more informative than a sell of equal dollar value. Cluster sells (≥3 executives) get a meaningful −15 penalty because coordination is harder to explain away by diversification.

**Why scan 8 options expiries instead of just the nearest one?** Retail concentrates in the nearest weekly (0–7 DTE). Institutions build positions across calendars: 30-day for near-term positioning, 90–180 day for structural bets. Unusual activity in a 3-month expiry is far more likely institutional than the same activity in 0-DTE options. Scanning 8 expiries catches the signal regardless of where on the curve it appears.

**Why detect deep ITM calls separately?** A call with strike ≤ 85% of spot has delta ≈ 0.95–0.99. It moves nearly identically to owning the stock. Institutions buy deep ITM calls instead of shares to delay the equity position from appearing in their quarterly 13F filings — options are disclosed separately from equity holdings. Volume ≥ 500 contracts = 50,000 share equivalent = multi-million dollar position. On a stock with no catalyst, that is almost certainly an institution deferring its disclosure footprint by one quarter.

**Why use COT for individual stock analysis when it covers futures?** COT tracks index futures (S&P 500, NASDAQ-100), commodities (gold, oil), and volatility (VIX). For correlated stocks (large-cap tech tracks NASDAQ futures, energy tracks oil futures, gold miners track gold futures), institutional futures positioning is a leading indicator of equity flow. When Asset Managers aggressively go net long NASDAQ futures, the equity money follows — they are the same underlying exposure through different instruments.

**Why load the Smart Money Score first before other panels?** The score endpoint uses yfinance insider data (cached) and computes in ~200ms. The dark pool, options, and congress endpoints each make external API calls taking 2–5 seconds. A user searching for a quick directional read gets the answer in 200ms, then drills into detail panels as they load. This perceived performance gap matters in a trading context.
