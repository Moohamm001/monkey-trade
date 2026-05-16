# MonkeyTrade

A full-stack stock and crypto analysis web app built on **Wyckoff Market Cycle Theory** and **institutional order flow analysis** — the frameworks professional traders use to identify where a market sits in its cycle and how big players are positioned.

---

## What It Does

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

Stock prices are driven by supply vs demand. Institutions cannot buy or sell their full positions in one day without moving the market against themselves — they operate across four stages:

```
Accumulation → Markup → Distribution → Markdown → (repeat)
```

### The Four Stages

#### 🔵 Accumulation
Institutions quietly buy over weeks or months while suppressing price to get cheaper fills. Price trades sideways at low levels. Retail investors are bored or scared — they sell to institutions.

**Best for:** Long-term investors. Low-risk entry before the crowd arrives.
**Action:** Buy / Accumulate

#### 🟢 Markup
Once enough shares are "in strong hands," institutions push price up. Momentum builds, news stories appear, breakout traders pile in. Volume and price both surge.

**Best for:** Breakout and momentum traders. Trail stops as price rises.
**Action:** Ride / Add on pullbacks

#### 🟡 Distribution
Institutions begin selling into the retail FOMO they created during Markup. Price moves sideways at high levels — institutions absorb every buyer. This can last months.

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

The detector scores each of four stage hypotheses using **eight independent signal categories**. The stage with the highest weighted score wins. Confidence is `winner_score / total_score × 100`.

### Signal 1 — 60-Day Price Trend
**Why:** Three months of price action filters out short-term noise and reveals the dominant institutional trend. A 15%+ gain over 60 days is not retail driven — it requires institutional size. A 15%+ loss without recovery means institutions are not buying the dip.

### Signal 2 — Moving Average Alignment (SMA20 / SMA50 / SMA200)
**Why:** Moving averages represent the average cost basis of buyers over different time horizons. SMA20 > SMA50 > SMA200 (Golden Order) means every timeframe agrees on uptrend — institutions are long across all horizons. The reverse (Death Order) confirms markdown.

### Signal 3 — RSI (14-period)
**Why:** RSI measures the speed of price moves, not just direction. RSI 60–70 during an uptrend is the "institutional sweet spot" — strong buying without FOMO exhaustion. RSI <30 while price is stable (not falling further) signals selling exhaustion and early accumulation.

### Signal 4 — MACD (12/26/9 EMA)
**Why:** MACD captures the *rate of change* of institutional interest. Rising histogram in positive territory = institutions actively adding. The histogram crossing zero is the earliest momentum shift signal — often appears before price confirms the move.

### Signal 5 — MACD Divergence
**Why:** Divergence is a leading indicator. Bearish divergence (price higher high, MACD lower high) means the last rally had fewer buyers — institutions stepping back before a breakdown. Bullish divergence (price lower low, MACD higher low) means sellers are exhausting — the earliest accumulation signal available.

### Signal 6 — Bollinger Bands (20-period, 2σ)
**Why:** Bollinger Bands represent statistical normality. Three uses: squeeze at lows (coiled spring before breakout), squeeze at highs (distribution before breakdown), price below lower band in a stable range (accumulation bounce trigger). Only 5% of closes occur outside the bands — sustained breaks confirm the trend is extreme.

### Signal 7 — OBV (On-Balance Volume)
**Why:** OBV rising while price is flat is stealth accumulation — institutions spreading purchases across many sessions to avoid moving the price. This is invisible to observers watching single-day volume. A steadily rising 20-day OBV is the most reliable institutional signature in daily bar data.

### Signal 8 — Stochastic Oscillator (14,3)
**Why:** Stochastic K/D crossover in overbought (>80) or oversold (<20) territory is a short-term momentum flip signal used as confirmation only. The same signal in Markup stage is noise; in Distribution it is actionable — context from other signals determines weight.

---

## Trade Level Calculation

All stop losses and targets use **ATR (Average True Range)** as the base unit. ATR scales automatically with the stock's actual daily movement — a volatile stock gets a wider stop, a calm stock gets a tighter one. A fixed-percentage stop ignores this and gets hit by noise.

| Stage | Stop Logic | Target Logic |
|-------|-----------|-------------|
| **Accumulation** | Below 20-day range low and lower BB − 0.5 ATR | 15%+ above SMA50 or 4 ATR above entry |
| **Markup** | 1 ATR below SMA20 (first dynamic support in uptrend) | 50% of the 52-week measured move, capped at 6 ATR |
| **Distribution** | Below 20-day low − 0.5 ATR buffer | Top of the 20-day range |
| **Markdown** | Above 20-day high + 0.75 ATR (short entry) | 52-week low or 5 ATR below entry |

Trades with R:R < 1.5 are flagged as poor setups.

---

## Whale / Institutional Detection (EOD)

### Volume Spike Analysis
Current volume vs 20-day average. `>5×` = extreme spike, `3–5×` = major institutional event, `1.8–3×` = elevated interest. Up-day vs down-day volume over 10 sessions produces buy/sell pressure. Extreme volume with 65%+ buy pressure = accumulation signature.

### OBV Slope (Stealth Detection)
OBV slope normalized over 5 and 20 days. A rising 20-day OBV with normal daily volume = institutions spreading purchases across many sessions. Invisible to observers watching single-day volume. The most reliable EOD smart-money signal.

### Options Flow (Put/Call Ratio)
Nearest expiry options chain from Yahoo Finance. P/C ratio >1.5 = heavy put buying — someone is paying a lot to protect against downside, which is smart money, not retail.

### Short Interest
Short % of float and days-to-cover. >20% = institutions actively betting against the stock. High short interest + accumulation signals = potential short squeeze setup.

### 13F Institutional Holders
Top 10 holders from quarterly 13F filings. Shows which funds own the stock. Vanguard or BlackRock with large stakes = institutional support. They signal exits through OBV and volume changes before price reacts.

### Insider Transactions
Isolated sales are noise (taxes, diversification). Cluster buying by multiple insiders = the signal. Insiders only buy for one reason.

---

## Order Flow Intelligence (Phase 1–3)

### Phase 1 — Data Infrastructure

#### WebSocket Tick Pipeline (`data_pipeline.py`)
Opens two concurrent Binance WebSocket streams per symbol:
- `aggTrade` — every matched trade with price, quantity, and aggressor side (buyer vs seller)
- `depth5@100ms` — top-5 bid/ask ladder snapshots every 100ms

Trades are batched in memory (100 ticks) before flushing to SQLite, amortizing write overhead without losing data. Order-book snapshots are written individually. Auto-reconnects on connection drops with 3-second backoff.

**Why batch instead of write every tick?** Individual SQLite writes at 10–100 ticks/second create thousands of fsync calls per minute. Batching reduces disk I/O by 100× with no data loss — ticks accumulate in memory and flush atomically.

#### Footprint Chart (`footprint.py`)
Groups ticks into N-minute candles. For each candle, bins trades by price level and computes:
- `buy_qty` (taker buys) vs `sell_qty` (taker sells) at every level
- Volume delta = total aggressive buys − sells for the candle
- **Imbalance flag** — when one side is ≥3× the other at a price level, institutions are hitting one side of the book hard

**Why footprint over regular OHLCV?** A green candle can form from one large institution buying OR from thousands of retail limit orders. The footprint shows *which* — by separating aggressive (market order) from passive (limit order) volume at every price level.

#### VPVR — Volume Profile Visible Range (`footprint.py`)
Algorithm:
1. Bin all traded quantity by price level
2. POC (Point of Control) = price level with highest total volume = fair value consensus
3. Expand outward from POC (always adding the higher-volume adjacent bin) until 70% of total volume is covered
4. Boundary bins = Value Area High (VAH) and Value Area Low (VAL)

**Why POC matters:** Institutions accumulate around POC because it offers the best average fill. Price returning to POC after a deviation tends to find support or resistance — it is the most defended level on the chart.

---

### Phase 2 — Machine Learning Models

#### Market Regime Filter (`regime_detector.py`)
K-Means clustering (k=3) on five features derived from historical daily bars:

| Feature | Why |
|---------|-----|
| ATR / price | Absolute volatility normalized to price level |
| ADX / 100 | Directional strength — high ADX = trending, low = oscillating |
| (SMA20 − SMA50) / price | Moving average spread — positive and growing = trending up |
| 20-day return std dev | Realized volatility |
| 10-day momentum | Short-term directional bias |

Cluster centroids are mapped semantically each run: highest ADX centroid = Trending, highest ATR+vol centroid = High Volatility, remaining = Mean-Reverting.

**Why K-Means instead of a labelled classifier?** A regime is a latent state — you cannot directly observe it, only infer it from indicator behaviour. K-Means lets the historical data itself define what "trending" looks like for each instrument, without requiring hand-labelled training data. The mapping from cluster → regime uses centroid characteristics, not fixed labels.

**Why three regimes?**
- **Trending** → follow the trend, use breakout and momentum strategies
- **Mean-Reverting** → fade the extremes, buy range lows / sell range highs
- **High Volatility** → reduce size, widen stops, or stay flat until regime settles

The same indicator (e.g., an RSI >70 reading) means something different in each regime. Knowing the regime first prevents applying the wrong strategy.

#### Institutional Flow Classifier (`flow_classifier.py`)
RBF-SVM trained on 1-minute bar features aggregated from tick data:

| Feature | What it captures |
|---------|-----------------|
| `vol_delta_norm` | Normalised aggressive buy − sell (directional conviction) |
| `avg_trade_size` | Mean quantity per trade — institutions trade large |
| `n_trades` | Trade count — institutions are infrequent but sized |
| `close_vs_vwap` | Where price closed relative to VWAP — directional intent |
| `buy_ratio` | Fraction of volume from aggressive buyers |

**Auto-labelling strategy:** Bars in the top quartile of both `avg_trade_size` AND `|vol_delta_norm|` are labelled Institutional (label=1). This heuristic reflects that institutions trade large and with directional conviction — no hand-labelled dataset required.

**Architecture path to Deep Learning:** The (T × 5) feature matrix per session can be fed directly into a 1-D CNN over a rolling 30-bar window to capture sequential order-book dynamics without hand-crafted features. An LSTM layer after the CNN adds memory of prior bars for drift detection. The sklearn Pipeline interface is preserved — swap the `svm` step for a scikeras Keras wrapper to maintain the `predict` / `predict_proba` API.

---

### Phase 3 — Risk Management & Execution

#### InstitutionalRiskManager (`risk_manager.py`)
**Position sizing formula:**
```
Size = (Account_Balance × Risk_Percentage) / (ATR × Multiplier)
```
This ensures the dollar risk per trade is constant regardless of asset volatility — a volatile asset gets a smaller position. Default: 1% account risk, 2× ATR stop distance, max 20% of account in any single symbol.

**Portfolio Kill Switch:**
Tracks daily unrealized PnL across all open positions. If total equity drops more than 5% below the daily opening balance, the system:
1. Sets `_halted = True` — blocks all new order entry
2. Liquidates every open position immediately at current price
3. Logs the reason and requires an explicit `reset_daily()` call to resume

**Why a kill switch?** A single bad trade can be absorbed. A correlated drawdown across multiple positions in a volatile session (e.g., a flash crash, surprise macro event) can wipe an account before the human can react. The kill switch is the circuit breaker that acts faster than emotion.

#### Trigger Engine (`trigger_engine.py`)
Executes a BUY only when **all three conditions align simultaneously**:

| Condition | Threshold | Why |
|-----------|-----------|-----|
| Price near POC | Within 1% | Entry at fair-value consensus = best average fill, institutions defend this level |
| Volume delta > 0 | Any positive value | Aggressive buyers outnumber sellers — demand is real |
| SVM signal = 1 | Institutional classification | Confirms order flow is institutional, not retail momentum |

Stop loss is placed **0.5% below POC** — if the POC breaks, the thesis is wrong. This creates asymmetric risk/reward by construction: entry at POC, stop just below it (small), target at VAH or beyond (large).

**Why require all three?**
- Price near POC alone: institutions may already be selling at this level
- Positive delta alone: could be retail FOMO, not sustained institutional flow
- SVM alone: model confidence varies; false positives exist

All three together = multi-confirmation institutional entry where the risk is physically defined by the POC boundary.

---

## Whale Tracker — Institutional Intelligence

### Why Track Institutional Flow?

Retail traders react to price. Institutions move price. By the time a move is visible on a chart, the smart money has already built its position. Every data source in this system is designed to detect *positioning before price*, not confirmation after.

The six data sources were selected because they are:
1. **Legally mandated disclosures** — institutions cannot avoid filing (SEC Form 4 within 2 days of trade; 13D/G within 10 days of crossing 5%; STOCK Act within 45 days)
2. **Free and public** — no paid API key required for any source
3. **Independent signals** — each captures a different footprint of the same institutional activity

---

### Data Sources

| Source | URL / API | Update Lag | What It Reveals |
|--------|-----------|-----------|-----------------|
| **SEC Form 4** | `efts.sec.gov` + `yfinance` | ≤2 business days after trade | Corporate insiders (executives, directors, 10%+ owners) buying or selling their own stock. They cannot legally trade on undisclosed material information — but they can buy ahead of organic catalysts they observe. A cluster (≥3 insiders buying in 30 days) is the highest-conviction signal available. |
| **SEC 13D/G** | `efts.sec.gov` EDGAR full-text search | ≤10 days after crossing 5% | Any entity acquiring >5% of a public company must file. Schedule 13D = activist intent (they want to change something). Schedule 13G = passive large holder. A new 13D is an activist campaign catalyst before the press release exists. |
| **FINRA Short Volume** | `cdn.finra.org/equity/regsho/daily/` | Next business day | FINRA's Regulation SHO short volume data (pipe-delimited daily files). Short volume includes all off-exchange / dark pool transactions. `dark_pct = ShortVolume / TotalVolume` is the institutional accumulation proxy: when institutions buy large through dark pools, it registers as elevated "short" volume (technical designation) while not being public retail flow. Spike = >1.5× 10-day average AND >40% total. |
| **CFTC COT Report** | `publicreporting.cftc.gov` (Socrata API) | Every Friday for prior week | Commitment of Traders: how futures market participants are net positioned. **Asset Managers** = real money (pension funds, mutual funds) — they are the smart money. **Leveraged Funds** = hedge funds — they are directional traders. Divergence (Asset Mgr net long, Lev Funds net short) is a classic pre-squeeze setup. Applies to index futures (SP500, NASDAQ), commodities (gold, oil), and volatility (VIX). |
| **Congress STOCK Act** | House S3 bucket + Senate S3 bucket | ≤45 days after trade | Members of Congress must disclose stock trades within 45 days. Academic research (Ziobrowski et al., 2004; 2011) found senators outperform the market by 12% annually — above random. A cluster of 3+ members buying the same ticker within 90 days signals policy-informed positioning. Source is public JSON on AWS S3 — no API key required. |
| **Options Flow (yfinance)** | Yahoo Finance options chains | Real-time (20-min delayed) | Multi-expiry scan across 8 nearest expirations. Four sub-signals: (1) dollar-weighted premium flow (call vs put dollars); (2) unusual activity sweeps (vol/OI ≥ 2.0 + premium ≥ $50K); (3) IV skew — 25-delta put IV minus call IV (negative = fear; positive = call bid); (4) deep ITM calls (strike ≤ 0.85× spot + volume ≥ 500) — institutions disguise large equity purchases as deep-in-the-money calls to avoid showing in 13F until next quarter. |

---

### Smart Money Score Model

**Base score: 50 (neutral). All sources add or subtract. Final score clamped to [0, 100].**

| Source | Max Bullish | Max Bearish | Trigger |
|--------|------------|------------|---------|
| SEC Form 4 — Cluster Buy | +20 | — | ≥3 executives buying in 30 days |
| SEC Form 4 — Solo Buy | +10 | — | 1–2 insiders buying |
| SEC Form 4 — Cluster Sell | — | −15 | ≥3 executives selling in 30 days |
| SEC Form 4 — Isolated Sell | — | −5 | 1–2 insiders selling (low weight — often diversification) |
| SEC 13D — Activist Filing | +20 | — | New 13D from known activist or intent language |
| SEC 13G — Passive Large Holder | +5 | — | New >5% passive institutional holder |
| FINRA Dark Pool — Spike | +15 | — | Volume >1.5× avg AND dark_pct >40% |
| FINRA Dark Pool — Elevated | +10 | — | Bullish trend signal without spike threshold |
| FINRA Dark Pool — Bearish | — | −12 | Declining dark pool participation (distribution) |
| Options Premium Flow — Bullish | +12 | — | Call premium >65% of total call+put dollars |
| Options Premium Flow — Bearish | — | −12 | Put premium >65% of total dollars |
| IV Skew — Bearish | — | −10 | 25-delta put IV substantially above call IV |
| IV Skew — Bullish | +8 | — | 25-delta call IV above put IV |
| Unusual Options — Bullish | +10 | — | ≥3 sweeps: calls with vol/OI ≥ 2.0 + premium ≥ $50K |
| Unusual Options — Bearish | — | −10 | ≥3 sweeps: puts meeting same threshold |
| Congress — Cluster Buy | +15 | — | ≥3 members buying same ticker within 90 days |
| Congress — Solo Buy | +7 | — | 1–2 members buying |
| Congress — Bearish | — | −8 | Net selling by members |
| COT — Asset Mgr Bullish | +12 | — | Asset Manager net long and increasing WoW |
| COT — Bearish | — | −12 | Asset Manager net short or Leveraged Funds heavily short |
| Short Interest — Squeeze Setup | +8 | — | Float shorted >5% AND short interest falling >10% MoM |
| Short Interest — Bearish | — | −8 | Float shorted >20% AND increasing |

**Score Interpretation:**

| Score | Rating | Meaning |
|-------|--------|---------|
| 80–100 | EXTREME BULLISH | Multiple institutional signals converging. Rare. Historically precedes significant upside. |
| 65–79 | BULLISH | Smart money is positioning long. Risk/reward skewed upside. |
| 45–64 | NEUTRAL | Mixed or absent signals. No directional edge from institutional data. |
| 30–44 | BEARISH | Institutional indicators suggest selling pressure or distribution. |
| 0–29 | EXTREME BEARISH | Multiple signals warn of institutional exit or active shorting. High-risk long environment. |

---

### Why Each Signal Was Weighted This Way

**Insider cluster buy (+20, highest weight):** Executives have legal access to internal financials, pipeline, and strategic plans. They take personal legal risk to buy — and they can only buy for one reason. A single insider buy might be routine. Three buying simultaneously is coordination. No other public signal has higher insider knowledge content.

**Activist 13D (+20, tied highest):** A 13D filing means someone bought >5% and filed with confrontational intent. This is a public commitment to drive price — they have skin in the game and a legal obligation to follow through. The market typically re-rates the stock 5–15% within 30 days of a 13D becoming public.

**Dark pool (+15 spike):** Institutions cannot execute large orders on-exchange without moving the price against themselves. Dark pools exist specifically to hide block-size order flow from the market. Elevated dark pool volume on an up-trending stock = stealth accumulation that hasn't appeared in price yet.

**Options premium flow (+12 / −12):** The total dollar commitment reveals conviction level. Retail trades 1 contract. Institutions spend millions in premium. A 70/30 call/put dollar split means someone is paying serious money to be long. Dollar flow outweighs contract count.

**COT (+12 / −12):** Asset Managers represent the largest pools of capital on earth. When pension funds and sovereign wealth funds shift their futures positioning, price follows — it has to. The weekly COT report is one of the most reliable leading indicators in professional macro trading.

**Congressional trades (+10 / −8):** The academic evidence (Ziobrowski 2004, 2011) is unambiguous: members of Congress consistently outperform random stock selection. The STOCK Act disclosure requirement is the only window into this flow. Cluster buying by multiple members on the same stock in the same 90-day window is the strongest signal — diversification doesn't explain it.

**Short interest / squeeze setup (+8):** High short interest alone is not bullish — it can mean the stock deserves to be shorted. But a rapid decline in short interest (>10% cover in one month) while the float is still meaningfully shorted suggests shorts are being squeezed or capitulating. This creates upside pressure as covering shorts are forced to buy.

---

### How the Frontend Renders It

The **WhaleTracker** page (`/whale`) loads in three async stages:
1. **Score card** (fast) — hits `/api/whale/{ticker}/score` first, shows the composite score while other panels load
2. **Parallel data panels** — insider, options-flow, and congress data fetch simultaneously via `Promise.all`
3. **Independent panels** — dark pool loads in its own `useEffect` (independent component lifecycle)

**Signal Feed** — all signals sorted descending by |delta|, highest conviction first. Each signal is an expandable accordion showing source, direction badge, score contribution, and full interpretation text.

**COT Panel** — bar chart of Asset Manager net positioning by week (green bars = net long, red = net short) with interpretation of the current positioning vs leveraged fund divergence.

**Options Panel** — premium flow bar showing call vs put dollar split, expected move from ATM straddle, IV skew with percentage, unusual activity table, and deep ITM call warning when applicable.

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
│   │   └── whale.py                 # /api/whale/* (institutional intelligence)
│   └── services/
│       ├── cycle_detector.py        # Wyckoff scoring engine + 8 signals
│       ├── institutional.py         # Options, short interest, 13F, insiders (EOD)
│       ├── stock_data.py            # yfinance wrappers for price + fundamentals
│       ├── screener.py              # S&P 500 / Top 100 scanning
│       ├── news.py                  # RSS aggregation + relevance scoring
│       ├── data_pipeline.py         # WebSocket tick ingestion → SQLite
│       ├── footprint.py             # Footprint chart + VPVR from tick data
│       ├── regime_detector.py       # K-Means market regime classification
│       ├── flow_classifier.py       # SVM institutional flow detection
│       ├── risk_manager.py          # Position sizing + kill switch
│       ├── trigger_engine.py        # Three-condition execution gate
│       ├── sec_edgar.py             # SEC Form 4 insider transactions + 13D/G activist filings
│       ├── dark_pool.py             # FINRA daily short volume → dark pool metrics
│       ├── cot_report.py            # CFTC COT futures positioning (Socrata API)
│       ├── congress_trades.py       # House + Senate STOCK Act trade disclosures
│       ├── options_flow.py          # Enhanced multi-expiry options flow analysis
│       └── smart_money.py           # Smart Money Score aggregator (all 6 sources → 0-100)
└── frontend/
    ├── src/
    │   ├── App.jsx                  # Layout, sidebar nav
    │   ├── pages/
    │   │   ├── Dashboard.jsx        # Main analysis view
    │   │   ├── Screener.jsx         # Stock scanner
    │   │   ├── OrderFlow.jsx        # Phase 1–3 order flow page
    │   │   ├── WhaleTracker.jsx     # Institutional intelligence — 7-panel whale view
    │   │   ├── Watchlist.jsx        # Saved tickers + R:R calculator
    │   │   ├── Education.jsx        # Wyckoff theory guide
    │   │   └── News.jsx             # News feed
    │   └── components/
    │       ├── StageBadge.jsx       # Colored cycle stage pill
    │       ├── CandlestickChart.jsx
    │       └── StageScoreBar.jsx
    ├── tailwind.config.js           # Design system (colors, shadows)
    └── package.json
```

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

**Why not a dark theme?** A light theme with high-contrast stage colors is easier to read at a glance when scanning multiple stocks. The stage colors (blue/green/amber/red) carry immediate meaning — dark themes tend to wash out these distinctions.

**Why separate institutional API call on Dashboard?** Fetching options chains and 13F data is slow (2–5 seconds). Splitting it from the main cycle analysis means the chart and signals appear immediately while institutional data loads in the background.

**Why ATR for all trade levels?** A fixed-percentage stop (e.g., always −5%) ignores that some stocks move 1% per day and others move 8%. ATR-based stops are proportional to the stock's actual volatility. A stop too tight relative to normal daily movement gets hit by noise, not by the thesis being wrong.

**Why OBV for EOD institutional detection rather than just volume?** A single high-volume day could be an index rebalance, an expiration, or a news event. OBV accumulated over 20 days filters that noise. A steadily rising 20-day OBV means sustained buying pressure across many sessions — the signature of a large fund building a position.

**Why K-Means for regime and SVM for flow, not a single deep learning model?** Both tasks lack labelled training data. K-Means requires no labels and defines regimes from the data's own structure. The SVM uses auto-labelled data (top-quartile bars by size + conviction) as a bootstrap. A deep learning model would require thousands of hand-labelled examples. For an unsupervised problem, simpler models that explain their decisions are more trustworthy than black-box networks — especially when the cost of a wrong prediction is a real trade.

**Why batch tick writes to SQLite instead of writing every tick?** Binance aggTrade streams can produce 50–200 messages per second for liquid pairs. Writing each tick individually creates hundreds of fsync calls per second — SQLite is not designed for this. Batching 100 ticks and flushing atomically reduces disk I/O by ~100× with no data loss, since ticks are held in memory between flushes.

**Why use FINRA short volume as a dark pool proxy rather than a paid dark pool feed?** True dark pool data (lit vs. off-exchange disaggregated by venue) requires expensive institutional feeds. FINRA ATS short volume is the best free proxy: FINRA's Regulation SHO requires all FINRA-member firms to report their off-exchange volume as short volume. This captures the same institutional block-order flow that dark pools are designed to hide from the open market. It's not identical, but the correlation with real dark pool accumulation is strong enough for a directional signal.

**Why does the dark pool signal use a spike threshold (1.5× avg AND >40%) rather than a raw level?** A stock with consistently high dark pool participation (e.g., a large-cap with 45% average off-exchange volume) provides no new information when it shows 46%. The spike threshold detects *change from baseline* — a sudden increase in institutional participation that wasn't there before is the signal, not the absolute level.

**Why track Congressional trades if the disclosure lag is up to 45 days?** The Ziobrowski academic studies (Senate 2004, House 2011) found members outperformed by 12% and 6% annually respectively. The edge persists even *after* public disclosure because the market underreacts to this information — individual member trades are buried in STOCK Act filings that nobody aggregates. Our cluster-buy detection (≥3 members, same ticker, 90-day window) surfaces the coordinated signal that the market has not yet fully priced in.

**Why does the Smart Money Score apply asymmetric weights (buys score higher than sells)?** Isolated insider selling is genuinely noisy — executives sell for taxes, liquidity needs, estate planning, and diversification. There are many reasons to sell that have nothing to do with bearish conviction. But executives only buy for one reason: they believe the stock will go up. This asymmetry matches the empirical literature on insider trading signal quality. Cluster sells (3+ execs) get a meaningful penalty because coordinated selling is harder to explain away.

**Why scan 8 options expiries instead of just the nearest one?** Retail traders concentrate in the nearest weekly expiry. Institutions use calendars across multiple expirations to hedge, structure synthetic equity positions, or build directional exposure without showing it in a single chain. Unusual activity in a 3-month or 6-month expiry is more likely institutional than the same activity in 0-DTE. Scanning all 8 nearest expiries ensures we catch the institutional flow regardless of where on the curve it occurs.

**Why detect deep ITM calls as a separate signal?** A call with a strike 15%+ below the current stock price has near-zero optionality — it trades almost identically to owning the stock. Institutions sometimes buy deep ITM calls instead of shares to delay the equity ownership from appearing in their quarterly 13F filings. By buying options rather than stock, they defer the public disclosure by one full quarter. Deep ITM calls with high volume (≥500 contracts) on a stock with no obvious catalyst are a textbook institutional equity-disguise pattern.

**Why use the COT report for individual stock analysis when it covers futures?** COT covers index futures (S&P 500, NASDAQ-100), commodities (gold, oil), and volatility (VIX). For index-correlated stocks (large-cap tech in QQQ, energy in XOM, gold miners), institutional futures positioning is a leading indicator of equity flow. When Asset Managers aggressively net long NASDAQ futures and Leveraged Funds are short, the next equity flow tends to follow the Asset Managers. The `INSTRUMENT_RELEVANCE` mapping connects each futures instrument to the equity tickers it most directly affects.

**Why load the Smart Money Score first before the other panels?** The score endpoint is fast (uses only yfinance insider data which is cached). The dark pool, options, and congress endpoints each make external API calls that can take 2–5 seconds individually. Loading the score card immediately gives the user a directional read while the detailed panels load in parallel. This perceived performance difference is significant in a trading context where the user wants a fast answer and then inspects the detail.
