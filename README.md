# MonkeyTrade

A full-stack stock analysis web app built on **Wyckoff Market Cycle Theory** — the framework professional traders use to identify where a stock sits in its cycle (Accumulation → Markup → Distribution → Markdown) and trade accordingly.

---

## What It Does

- **Cycle Detector** — classifies any stock into one of the four Wyckoff stages with a confidence score
- **Trade Levels** — calculates stage-appropriate entry, stop loss, and target using ATR-scaled math
- **Buying Point** — shows the ideal entry zone, trigger, and what to avoid for the detected stage
- **Volume & Whale Detector** — surfaces institutional accumulation/distribution using OBV and volume spike analysis
- **Institutional Intelligence** — options put/call ratio, short interest, 13F institutional holders, insider transactions
- **Stock Screener** — scans Top 100 or full S&P 500 with stage filters and sortable columns
- **Watchlist** — tracks saved tickers with a built-in R:R calculator
- **News Feed** — aggregates market news with strategy-relevance scoring
- **Education** — interactive guide to Wyckoff theory with the four-stage cycle diagram

---

## Tech Stack

### Backend

| Tool | Why |
|------|-----|
| **FastAPI** | Async Python API with automatic OpenAPI docs; minimal boilerplate compared to Flask, handles concurrent stock data requests well |
| **yfinance** | Free Yahoo Finance wrapper — covers price history, fundamentals, options chains, institutional holders, and insider transactions without a paid data subscription |
| **pandas** | Required for time-series indicator math; rolling windows, index manipulation, and OHLCV slicing are native operations |
| **ta (Technical Analysis library)** | Clean Python wrappers over pandas for every indicator used — avoids reimplementing rolling math by hand |
| **feedparser** | RSS parsing for news aggregation from multiple financial sources |
| **uvicorn** | ASGI server for FastAPI; fast enough for local dev with `--reload` |

### Frontend

| Tool | Why |
|------|-----|
| **React + Vite** | Component-based UI with hot-module reload; Vite's dev server is significantly faster than Create React App |
| **Tailwind CSS v3** | Utility-first CSS — the design system is encoded in `tailwind.config.js` (colors, shadows, radii) and referenced everywhere; no separate `.css` files per component |
| **Recharts** | Declarative charting library for React; used for the OHLCV candlestick chart |
| **Lucide React** | Lightweight icon set that tree-shakes cleanly with Vite |
| **React Router** | Client-side routing for the multi-page app (Dashboard, Screener, Watchlist, Education, News) |

---

## Trading Theory: Wyckoff Market Cycle

The core premise of the strategy (from `strategy.txt`):

> *"For prices to rise, most of the shares must be in the hands of the owners."*

Stock prices are driven by supply vs demand. Big players (institutions, funds) cannot buy or sell their full positions in one day without moving the market against themselves. Instead they operate across four stages:

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

The detector scores each of four stage hypotheses (accumulation / markup / distribution / markdown) using **eight independent signal categories**. The stage with the highest weighted score wins. Confidence is `winner_score / total_score × 100`.

### Signal 1 — 60-Day Price Trend
**Why:** Three months of price action filters out short-term noise and reveals the dominant institutional trend. A 15%+ gain over 60 days is not retail driven — it requires institutional size. A 15%+ loss over 60 days without recovery means institutions are not buying the dip.

### Signal 2 — Moving Average Alignment (SMA20 / SMA50 / SMA200)
**Why:** Moving averages represent the average cost basis of buyers over different time horizons. When SMA20 > SMA50 > SMA200 (Golden Order), every time frame agrees on uptrend — institutions are long across all horizons. The reverse (Death Order) means they are not. MA alignment is the simplest X-ray of institutional trend bias.

### Signal 3 — RSI (14-period Relative Strength Index)
**Why:** RSI measures the speed of price moves, not just direction. RSI 60–70 during an uptrend is the "institutional sweet spot" — strong buying without the FOMO exhaustion of >75. RSI <30 while price is stable (not falling further) signals selling exhaustion — institutions absorbing the last panic sellers. RSI <30 in a downtrend just means Markdown is accelerating.

### Signal 4 — MACD (12/26/9 EMA)
**Why:** MACD measures momentum by comparing two EMAs. The histogram (MACD line minus signal line) shows acceleration or deceleration of that momentum. Rising histogram in positive territory = institutions actively adding; declining histogram in negative territory = sellers dominant. MACD captures the *rate of change* of institutional interest.

### Signal 5 — MACD Divergence (Bearish / Bullish)
**Why:** Divergence is a leading indicator — it warns *before* price reverses. Bearish divergence (price makes new high, MACD does not) means the last rally had fewer buyers behind it — institutions stepped back. Bullish divergence (price makes new low, MACD does not) means sellers are exhausting — fewer shares hit the market at each new low, which is how accumulation begins. This is one of the earliest and most reliable cycle-turn signals.

### Signal 6 — Bollinger Bands (20-period, 2σ)
**Why:** Bollinger Bands represent statistical normality (±2 standard deviations). Three uses:
- **Squeeze** (bands narrow to historical lows): volatility has compressed — an explosive move is coming. Direction is determined by where the squeeze occurs relative to SMA50.
- **Price above upper band**: statistically overextended; 95% of closes occur inside the bands. Distribution signal.
- **Price below lower band in stable market**: oversold at range lows — classic accumulation bounce trigger.

### Signal 7 — OBV (On-Balance Volume)
**Why:** OBV adds volume on up-days and subtracts on down-days, creating a running total. When OBV rises while price is flat or sideways, it means more shares are being bought on up-days than sold on down-days — even though price hasn't moved yet. This is **stealth accumulation**: institutions spreading purchases across many sessions to avoid alerting the market. OBV rising before price is the single most reliable institutional signature in the dataset.

### Signal 8 — Stochastic Oscillator (14,3)
**Why:** Stochastic measures where price closed relative to its recent high-low range. The K/D crossover in overbought (>80) or oversold (<20) territory is used as a short-term momentum flip signal. It is used as a confirmation signal, not standalone — a Stochastic sell signal in a Markup stage is noise; the same signal in Distribution is actionable.

---

## Trade Level Calculation

All stop losses and targets are calculated using **ATR (Average True Range)** as the base unit. ATR automatically scales with the stock's volatility — a $500 stock and a $10 stock get stops that are proportional to how much each stock actually moves day-to-day, not a fixed dollar amount.

| Stage | Stop Logic | Target Logic |
|-------|-----------|-------------|
| **Accumulation** | Below 20-day range low and lower BB − 0.5 ATR | 15%+ above SMA50 or 4 ATR above entry |
| **Markup** | 1 ATR below SMA20 (first dynamic support) | 50% of the 52-week measured move, capped at 6 ATR |
| **Distribution** | Below 20-day low − 0.5 ATR buffer | Top of the 20-day range |
| **Markdown** | Above 20-day high + 0.75 ATR (for shorts) | 52-week low or 5 ATR below entry |

Risk:Reward is calculated from these levels. Trades with R:R < 1.5 are flagged as poor setups.

---

## Whale / Institutional Detection

### Volume Spike Analysis
Current volume is compared to the 20-day average. Ratios:
- `>5×` — Extreme spike (whale-level event)
- `3–5×` — Major spike (strong institutional activity)
- `1.8–3×` — Elevated (possible accumulation or momentum)

Up-day vs down-day volume over the last 10 sessions produces a buy/sell pressure percentage. Extreme volume with 65%+ buy pressure = institutional accumulation signature. Same volume with 65%+ sell pressure = institutional distribution.

### OBV Slope (Stealth Detection)
The more sophisticated detection: OBV slope over 5 and 20 days, normalized by OBV magnitude. A rising 20-day OBV slope with normal daily volume means institutions are spreading purchases across many sessions — the most reliable smart-money signal because it's invisible to casual observers watching single-day volume.

### Options Flow (Put/Call Ratio)
The nearest expiry options chain is fetched from Yahoo Finance. Put/Call volume ratio:
- `< 0.5` — Aggressive call buying; bullish speculative flow
- `0.5–1.1` — Bullish bias; call-heavy market
- `1.1–1.5` — Slightly elevated puts; some defensive hedging
- `> 1.5` — Heavy put buying; institutions are hedging or shorting

Options are expensive. A P/C ratio >1.5 means someone is paying a lot to protect against downside — that is smart money, not retail.

### Short Interest
Short % of float and days-to-cover from Yahoo Finance fundamentals data:
- `> 20%` of float shorted: institutions are actively betting against the stock
- `10–20%`: moderate bearish positioning
- `< 10%`: low — few sophisticated sellers

A high short interest in the presence of accumulation signals (OBV rising, price stable) sets up a **short squeeze** — rising price forces short sellers to buy back, accelerating the move.

### 13F Institutional Holders
The top 10 holders from quarterly 13F filings (via `yfinance.institutional_holders`). Shows which funds own the stock and what percentage they hold. If Vanguard, BlackRock, or major hedge funds have large stakes, the stock has institutional support — they will not abandon a position without signaling first (via OBV and volume changes).

### Insider Transactions
Recent buy and sell transactions by company insiders (executives, directors). Key insight:
- Insiders sell for many reasons (taxes, diversification) — isolated sales are noise
- **Cluster buying** by multiple insiders is the signal: insiders only buy for one reason — they expect the price to go higher

---

## Project Structure

```
monkey-trade3/
├── backend/
│   ├── main.py                    # FastAPI app, CORS, router registration
│   ├── requirements.txt
│   ├── routers/
│   │   ├── stock.py               # /api/stock/{ticker}/* endpoints
│   │   ├── screener.py            # /api/screener/run, /universes
│   │   ├── watchlist.py           # /api/watchlist CRUD
│   │   └── news.py                # /api/news
│   └── services/
│       ├── cycle_detector.py      # Wyckoff scoring engine + all indicators
│       ├── institutional.py       # Options, short interest, 13F, insiders
│       ├── stock_data.py          # yfinance wrappers for price + fundamentals
│       ├── screener.py            # S&P 500 / Top 100 scanning
│       └── news.py                # RSS aggregation + relevance scoring
└── frontend/
    ├── src/
    │   ├── App.jsx                # Layout, sidebar nav
    │   ├── pages/
    │   │   ├── Dashboard.jsx      # Main analysis view
    │   │   ├── Screener.jsx       # Stock scanner
    │   │   ├── Watchlist.jsx      # Saved tickers + R:R calculator
    │   │   ├── Education.jsx      # Wyckoff theory guide
    │   │   └── News.jsx           # News feed
    │   └── components/
    │       ├── StageBadge.jsx     # Colored cycle stage pill
    │       ├── CandlestickChart.jsx
    │       └── StageScoreBar.jsx
    ├── tailwind.config.js         # Design system (colors, shadows)
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

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/stock/{ticker}/cycle?period=1y` | Full cycle analysis with signals, indicators, trade levels |
| `GET` | `/api/stock/{ticker}/info` | Basic stock info and fundamentals |
| `GET` | `/api/stock/{ticker}/financials` | Income statement and balance sheet |
| `GET` | `/api/stock/{ticker}/institutional` | Options flow, short interest, 13F holders, insiders |
| `GET` | `/api/stock/{ticker}/news?limit=10` | Stock-specific news |
| `POST` | `/api/screener/run` | Run screener with filters and universe selection |
| `GET` | `/api/screener/universes` | Available universes with ticker counts |
| `GET/POST/DELETE` | `/api/watchlist` | Watchlist management |
| `GET` | `/api/news?limit=20` | General market news feed |

---

## Design Decisions

**Why not a dark theme?** A light theme with high-contrast stage colors is easier to read at a glance when scanning multiple stocks. The stage colors (blue/green/amber/red) carry immediate meaning — dark themes tend to wash out these distinctions.

**Why separate institutional API call?** Fetching options chains and 13F data is slow (2–5 seconds). Splitting it from the main cycle analysis means the chart and signals appear immediately while institutional data loads in the background.

**Why ATR for all trade levels?** A fixed-percentage stop (e.g., always −5%) ignores that some stocks move 1% per day and others move 8%. ATR-based stops are proportional to the stock's actual volatility — the stop on NVDA is wider than on SPY because NVDA legitimately moves more. A stop that's too tight relative to normal daily movement gets hit by noise, not by the thesis being wrong.

**Why OBV for institutional detection rather than just volume?** A single high-volume day could be an index rebalance, an expiration, or a news event. OBV accumulated over 20 days filters that noise. A steadily rising 20-day OBV is harder to fake — it means sustained buying pressure across many sessions, which is the signature of a large fund building a position.
