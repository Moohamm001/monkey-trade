import numpy as np
import pandas as pd
from ta.trend import SMAIndicator, EMAIndicator, MACD
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import OnBalanceVolumeIndicator


STAGES = {
    "accumulation": {
        "label": "Accumulation",
        "color": "#3B82F6",
        "emoji": "🔵",
        "description": "Big players quietly buying. Price moves sideways at low levels. Patient investor zone.",
        "suitable_for": "Long-term investors who can wait. Low risk entry.",
        "action": "BUY / ACCUMULATE",
    },
    "markup": {
        "label": "Markup",
        "color": "#22C55E",
        "emoji": "🟢",
        "description": "Price rising aggressively. Momentum builds. News and stories appear.",
        "suitable_for": "Breakout & momentum traders. Manage risk with trailing stops.",
        "action": "RIDE / ADD ON PULLBACKS",
    },
    "distribution": {
        "label": "Distribution",
        "color": "#F59E0B",
        "emoji": "🟡",
        "description": "Big players gradually selling. Price moves sideways at high levels.",
        "suitable_for": "Swing traders. Buy low of range, sell high. Tight discipline required.",
        "action": "RANGE TRADE / REDUCE",
    },
    "markdown": {
        "label": "Markdown",
        "color": "#EF4444",
        "emoji": "🔴",
        "description": "Price in persistent downtrend. Rebounds are traps. Avoid.",
        "suitable_for": "Short sellers only. Most investors should stay away entirely.",
        "action": "AVOID / SHORT ONLY",
    },
}


def _calc_trade_levels(stage: str, cur_price: float, cur_atr: float,
                       cur_sma20: float, cur_sma50: float,
                       bb_lower: float, bb_upper: float,
                       low_20: float, high_20: float,
                       high_52: float, low_52: float) -> dict:
    """
    Compute stage-appropriate stop loss, target, and R:R.
    All levels use ATR as the base unit so they scale with volatility.
    """
    atr = cur_atr
    price = cur_price

    if stage == "accumulation":
        # Entry near current price; stop below the 20-day range low (structure low)
        # Target = previous markup (test of 52w high or 2× ATR above SMA50)
        stop = round(min(low_20, bb_lower) - atr * 0.5, 4)
        target = round(max(cur_sma50 * 1.15, price + atr * 4), 4)
        reasoning = (
            "Stop placed below the accumulation range low and lower Bollinger Band. "
            "Institutions defend this level — a break below confirms the stage thesis is wrong. "
            "Target projects to the markup phase entry, roughly 15%+ above SMA50."
        )

    elif stage == "markup":
        # Trailing stop: below SMA20 (first support in uptrend) minus 1 ATR buffer
        # Target: measured move = range height added to breakout point
        stop = round(cur_sma20 - atr * 1.0, 4)
        measured_move = high_52 - low_52
        target = round(min(price + measured_move * 0.5, price + atr * 6), 4)
        reasoning = (
            "Stop set 1 ATR below SMA20 — the first dynamic support in a healthy uptrend. "
            "Price reclaiming SMA20 after a pullback is the re-entry signal. "
            "Target uses 50% of the 52-week measured move projected from current price, capped at 6× ATR."
        )

    elif stage == "distribution":
        # Range trade: stop below range low, target at range high
        range_buffer = atr * 0.5
        stop = round(low_20 - range_buffer, 4)
        target = round(high_20 - range_buffer * 0.2, 4)
        reasoning = (
            "Distribution trades the defined range. Stop is placed just below the 20-day low "
            "with a half-ATR buffer to avoid stop hunts. Target is the top of the range. "
            "If price fails to reach the high and rolls over, exit immediately — distribution is ending."
        )

    elif stage == "markdown":
        # Short entry: stop above recent 20-day high, target at 52w low (or new low)
        stop = round(high_20 + atr * 0.75, 4)
        target = round(max(low_52 * 0.95, price - atr * 5), 4)
        reasoning = (
            "Short setup: stop placed above the 20-day high plus buffer — any close above that "
            "level invalidates the downtrend. Target projects to the 52-week low or 5× ATR below entry. "
            "For long holders: exit immediately. Markdown rallies are short-covering traps, not reversals."
        )
    else:
        return {}

    risk = abs(price - stop)
    reward = abs(target - price)
    rr = round(reward / risk, 2) if risk > 0 else 0

    return {
        "entry": round(price, 4),
        "stop_loss": stop,
        "target": target,
        "risk_per_share": round(risk, 4),
        "reward_per_share": round(reward, 4),
        "risk_reward": rr,
        "stop_pct": round(risk / price * 100, 2),
        "target_pct": round(reward / price * 100, 2),
        "reasoning": reasoning,
    }


# Signal technique catalogue — each entry has a full trader explanation
def _make_signal(sig_type: str, short: str, technique: str, why: str, implication: str) -> dict:
    return {
        "type": sig_type,
        "text": short,
        "technique": technique,
        "why": why,
        "implication": implication,
    }


def _analyze_volume(close: pd.Series, volume: pd.Series, high: pd.Series, low: pd.Series) -> dict:
    """Detect whale / institutional activity from volume patterns."""
    n = len(close)
    avg_vol_20 = float(volume.rolling(20).mean().iloc[-1]) if n >= 20 else float(volume.mean())
    avg_vol_50 = float(volume.rolling(50).mean().iloc[-1]) if n >= 50 else float(volume.mean())
    cur_vol    = float(volume.iloc[-1])
    vol_ratio  = cur_vol / (avg_vol_20 + 1e-9)

    # Classify current session volume
    if vol_ratio >= 5:
        vol_label    = "Extreme Spike"
        whale_level  = "extreme"
    elif vol_ratio >= 3:
        vol_label    = "Major Spike"
        whale_level  = "strong"
    elif vol_ratio >= 1.8:
        vol_label    = "Above Average"
        whale_level  = "moderate"
    else:
        vol_label    = "Normal"
        whale_level  = "none"

    # Last 10 days: separate up-day volume from down-day volume
    lookback = min(10, n - 1)
    buy_vol  = 0.0
    sell_vol = 0.0
    for i in range(-lookback, 0):
        day_vol = float(volume.iloc[i])
        if float(close.iloc[i]) >= float(close.iloc[i - 1]):
            buy_vol  += day_vol
        else:
            sell_vol += day_vol

    total_vol     = buy_vol + sell_vol + 1e-9
    buy_pressure  = round(buy_vol / total_vol * 100, 1)
    sell_pressure = round(sell_vol / total_vol * 100, 1)

    if buy_pressure >= 65:
        pressure_label = "Strong Buying"
        pressure_type  = "bullish"
    elif buy_pressure >= 55:
        pressure_label = "Mild Buying"
        pressure_type  = "bullish"
    elif sell_pressure >= 65:
        pressure_label = "Strong Selling"
        pressure_type  = "bearish"
    elif sell_pressure >= 55:
        pressure_label = "Mild Selling"
        pressure_type  = "bearish"
    else:
        pressure_label = "Balanced"
        pressure_type  = "neutral"

    # Recent volume spikes (last 20 days) — days where vol > 2.5× average
    spikes = []
    look20 = min(20, n)
    for i in range(-look20, 0):
        v = float(volume.iloc[i])
        ratio = v / (avg_vol_20 + 1e-9)
        if ratio >= 2.5:
            date_str = volume.index[i].strftime("%Y-%m-%d") if hasattr(volume.index[i], "strftime") else str(volume.index[i])
            direction = "🟢 Buy" if float(close.iloc[i]) >= float(close.iloc[i - 1]) else "🔴 Sell"
            spikes.append({
                "date":      date_str,
                "ratio":     round(ratio, 1),
                "direction": direction,
                "volume":    int(v),
            })

    # OBV slope as institutional conviction
    from ta.volume import OnBalanceVolumeIndicator
    obv = OnBalanceVolumeIndicator(close, volume).on_balance_volume()
    obv_slope_5  = (float(obv.iloc[-1]) - float(obv.iloc[-6]))  / (abs(float(obv.iloc[-6]))  + 1e-9) if n >= 6  else 0
    obv_slope_20 = (float(obv.iloc[-1]) - float(obv.iloc[-21])) / (abs(float(obv.iloc[-21])) + 1e-9) if n >= 21 else 0

    # Whale interpretation
    if whale_level in ("strong", "extreme") and pressure_type == "bullish":
        whale_msg = (
            f"Volume is {vol_ratio:.1f}× the 20-day average with {buy_pressure:.0f}% buy-side pressure. "
            "This is a whale / institutional accumulation signature — large players are entering aggressively. "
            "High-volume up-days that hold their gains confirm real demand, not a pump."
        )
    elif whale_level in ("strong", "extreme") and pressure_type == "bearish":
        whale_msg = (
            f"Volume is {vol_ratio:.1f}× the 20-day average with {sell_pressure:.0f}% sell-side pressure. "
            "This is a whale / institutional distribution signature — large players are exiting. "
            "High-volume down-days that close near lows confirm heavy selling. Avoid or reduce long exposure."
        )
    elif whale_level == "moderate" and pressure_type == "bullish":
        whale_msg = (
            f"Volume is {vol_ratio:.1f}× the 20-day average. Elevated buying interest — could be early "
            "institutional accumulation or a retail momentum push. Watch OBV over the next few sessions "
            "to confirm if smart money is behind this move."
        )
    elif obv_slope_20 > 0.05 and pressure_type == "bullish":
        whale_msg = (
            f"Volume is normal today ({vol_ratio:.1f}× avg) but OBV has been rising for 20 days. "
            "This is stealth accumulation — institutions spreading purchases across many sessions "
            "to avoid moving the price. The most reliable whale signature."
        )
    elif obv_slope_20 < -0.05 and pressure_type == "bearish":
        whale_msg = (
            f"Volume is normal today ({vol_ratio:.1f}× avg) but OBV has been declining for 20 days. "
            "Stealth distribution — institutions selling gradually without triggering panic. "
            "Price may look stable but the smart money is quietly leaving."
        )
    else:
        whale_msg = (
            f"No unusual institutional activity detected. Volume is {vol_ratio:.1f}× the 20-day average "
            f"with {buy_pressure:.0f}% buy-side pressure. Normal retail-driven session."
        )

    return {
        "current_volume":   int(cur_vol),
        "avg_volume_20d":   int(avg_vol_20),
        "avg_volume_50d":   int(avg_vol_50),
        "volume_ratio":     round(vol_ratio, 2),
        "volume_label":     vol_label,
        "whale_level":      whale_level,
        "buy_pressure":     buy_pressure,
        "sell_pressure":    sell_pressure,
        "pressure_label":   pressure_label,
        "pressure_type":    pressure_type,
        "obv_slope_5d":     round(obv_slope_5,  4),
        "obv_slope_20d":    round(obv_slope_20, 4),
        "recent_spikes":    spikes[-5:],   # last 5 notable spikes
        "whale_message":    whale_msg,
    }


def _calc_buying_point(stage: str, cur_price: float, cur_atr: float,
                       cur_sma20: float, cur_sma50: float,
                       cur_bb_lower: float, cur_bb_upper: float,
                       low_20: float, high_20: float) -> dict:
    """Return the ideal buying zone and entry type for the current stage."""
    if stage == "accumulation":
        ideal    = round(cur_bb_lower + cur_atr * 0.3, 4)
        zone_lo  = round(low_20, 4)
        zone_hi  = round(cur_sma20, 4)
        entry_type = "Range Low Entry"
        trigger    = "Buy near the lower Bollinger Band or at 20-day range lows. Wait for a close ABOVE SMA20 for confirmation."
        avoid_if   = "Price breaks below the 20-day low on heavy volume — the accumulation base has failed."
    elif stage == "markup":
        ideal    = round(cur_sma20 + cur_atr * 0.2, 4)
        zone_lo  = round(cur_sma20 - cur_atr * 0.5, 4)
        zone_hi  = round(cur_sma20 + cur_atr * 1.0, 4)
        entry_type = "Pullback to SMA20"
        trigger    = "Buy on a pullback that touches or slightly undercuts SMA20, then closes back above it. This is the 'buy the dip' zone in an uptrend."
        avoid_if   = "Price closes below SMA50 — the uptrend structure is broken."
    elif stage == "distribution":
        ideal    = round(low_20 + cur_atr * 0.5, 4)
        zone_lo  = round(low_20, 4)
        zone_hi  = round(low_20 + cur_atr * 1.5, 4)
        entry_type = "Range Bottom Swing"
        trigger    = "Buy near the bottom of the established range only. This is a swing trade, not a hold. Sell at the range top — do not hold through it."
        avoid_if   = "Price breaks below range low — distribution is turning to markdown. Exit immediately."
    else:  # markdown
        ideal      = None
        zone_lo    = None
        zone_hi    = None
        entry_type = "No Long Entry"
        trigger    = "Do not buy. Markdown stocks decline further. Any bounce is a short-covering trap, not a reversal. Wait for a full base to form over many weeks before considering entry."
        avoid_if   = "Trying to catch a falling knife based on 'cheap' valuation."

    return {
        "ideal_entry": ideal,
        "zone_low":    zone_lo,
        "zone_high":   zone_hi,
        "entry_type":  entry_type,
        "trigger":     trigger,
        "avoid_if":    avoid_if,
    }


def detect_cycle(df: pd.DataFrame) -> dict:
    if len(df) < 50:
        return {"stage": "unknown", "confidence": 0, "signals": [], "indicators": {}, "trade_levels": {}}

    close = df["Close"]
    volume = df["Volume"]
    high = df["High"]
    low = df["Low"]

    sma20 = SMAIndicator(close, window=20).sma_indicator()
    sma50 = SMAIndicator(close, window=50).sma_indicator()
    sma200 = SMAIndicator(close, window=200).sma_indicator() if len(df) >= 200 else None

    rsi = RSIIndicator(close, window=14).rsi()
    macd_obj = MACD(close)
    macd_line = macd_obj.macd()
    macd_signal_line = macd_obj.macd_signal()
    macd_diff = macd_obj.macd_diff()

    bb = BollingerBands(close, window=20)
    bb_upper = bb.bollinger_hband()
    bb_lower = bb.bollinger_lband()
    bb_mid = bb.bollinger_mavg()
    bb_width = (bb_upper - bb_lower) / bb_mid

    obv = OnBalanceVolumeIndicator(close, volume).on_balance_volume()
    atr = AverageTrueRange(high, low, close, window=14).average_true_range()

    stoch = StochasticOscillator(high, low, close, window=14, smooth_window=3)
    stoch_k = stoch.stoch()
    stoch_d = stoch.stoch_signal()

    cur_price  = float(close.iloc[-1])
    cur_sma20  = float(sma20.iloc[-1])
    cur_sma50  = float(sma50.iloc[-1])
    cur_sma200 = float(sma200.iloc[-1]) if sma200 is not None else None
    cur_rsi    = float(rsi.iloc[-1])
    cur_macd_diff   = float(macd_diff.iloc[-1])
    cur_macd_line   = float(macd_line.iloc[-1])
    cur_macd_signal = float(macd_signal_line.iloc[-1])
    cur_bb_upper = float(bb_upper.iloc[-1])
    cur_bb_lower = float(bb_lower.iloc[-1])
    cur_bb_width = float(bb_width.iloc[-1])
    cur_atr      = float(atr.iloc[-1])
    cur_stoch_k  = float(stoch_k.iloc[-1])
    cur_stoch_d  = float(stoch_d.iloc[-1])

    lookback_60 = min(60, len(df) - 1)
    lookback_20 = min(20, len(df) - 1)
    price_change_60 = (cur_price - float(close.iloc[-lookback_60])) / float(close.iloc[-lookback_60])
    price_change_20 = (cur_price - float(close.iloc[-lookback_20])) / float(close.iloc[-lookback_20])

    low_20  = float(low.iloc[-lookback_20:].min())
    high_20 = float(high.iloc[-lookback_20:].max())

    obv_slope = (float(obv.iloc[-1]) - float(obv.iloc[-20])) / (abs(float(obv.iloc[-20])) + 1e-9) if len(df) >= 20 else 0
    bb_width_pct = float(bb_width.rank(pct=True).iloc[-1])

    high_52 = float(close.rolling(252).max().iloc[-1]) if len(df) >= 252 else float(close.max())
    low_52  = float(close.rolling(252).min().iloc[-1]) if len(df) >= 252 else float(close.min())
    price_position = (cur_price - low_52) / (high_52 - low_52 + 1e-9)

    # MACD divergence: price making higher high but MACD making lower high = bearish div
    macd_vals = macd_line.dropna()
    bearish_div = False
    if len(macd_vals) >= 20:
        price_high_recent = float(close.iloc[-10:].max())
        price_high_prior  = float(close.iloc[-20:-10].max())
        macd_high_recent  = float(macd_vals.iloc[-10:].max())
        macd_high_prior   = float(macd_vals.iloc[-20:-10].max())
        if price_high_recent > price_high_prior and macd_high_recent < macd_high_prior:
            bearish_div = True

    bullish_div = False
    if len(macd_vals) >= 20:
        price_low_recent = float(close.iloc[-10:].min())
        price_low_prior  = float(close.iloc[-20:-10].min())
        macd_low_recent  = float(macd_vals.iloc[-10:].min())
        macd_low_prior   = float(macd_vals.iloc[-20:-10].min())
        if price_low_recent < price_low_prior and macd_low_recent > macd_low_prior:
            bullish_div = True

    # -----------------------------------------------------------------------
    # Scoring
    # -----------------------------------------------------------------------
    scores = {"accumulation": 0, "markup": 0, "distribution": 0, "markdown": 0}
    signals = []

    # 1. 60-day price trend
    if price_change_60 < -0.15:
        scores["markdown"] += 3
        signals.append(_make_signal(
            "bearish",
            f"Price −{abs(price_change_60*100):.1f}% in 60 days — persistent downtrend",
            "60-Day Price Trend",
            "Measures the net price direction over 3 months — long enough to filter noise and identify the dominant trend.",
            f"A {abs(price_change_60*100):.1f}% decline over 60 days without recovery is the hallmark of Markdown. "
            "Institutions are not stepping in to buy. Every rally gets sold into. Stay out or short only."
        ))
    elif price_change_60 < -0.05:
        scores["markdown"] += 1
        scores["distribution"] += 1
        signals.append(_make_signal(
            "neutral",
            f"Price −{abs(price_change_60*100):.1f}% in 60 days — mild weakness",
            "60-Day Price Trend",
            "Measures net 3-month direction.",
            f"Mild negative drift of {abs(price_change_60*100):.1f}% — could be a late distribution pullback or early markdown. "
            "Watch whether bounces are sold or whether buyers step in near support."
        ))
    elif price_change_60 > 0.15:
        scores["markup"] += 3
        signals.append(_make_signal(
            "bullish",
            f"Price +{price_change_60*100:.1f}% in 60 days — strong uptrend",
            "60-Day Price Trend",
            "Measures net 3-month momentum.",
            f"A {price_change_60*100:.1f}% gain in 60 days confirms institutions are actively accumulating and pushing price. "
            "This is the Markup signature. Pullbacks to SMA20 are buying opportunities, not exits."
        ))
    elif -0.05 <= price_change_60 <= 0.05:
        if cur_sma200 is not None and cur_price < cur_sma200 * 0.95:
            scores["accumulation"] += 2
            signals.append(_make_signal(
                "neutral",
                "Sideways below SMA200 — accumulation base forming",
                "60-Day Price Trend + SMA200",
                "Flat price action below the 200-day MA indicates neither bulls nor bears are dominant.",
                "Price is chopping in a tight range at depressed levels. This is when institutions quietly buy "
                "from impatient retail sellers. The longer the base, the more powerful the eventual breakout."
            ))
        else:
            scores["distribution"] += 2
            signals.append(_make_signal(
                "neutral",
                "Sideways near highs — distribution range",
                "60-Day Price Trend + SMA200",
                "Flat price action at elevated levels means supply is absorbing demand.",
                "Price is moving sideways at highs — the classic distribution signature. Institutions are selling "
                "into retail buying. Range top = resistance to reduce. Range bottom = bounce level only."
            ))

    # 2. Moving average alignment
    if cur_sma20 > cur_sma50:
        if cur_sma200 is not None and cur_sma50 > cur_sma200:
            scores["markup"] += 2
            signals.append(_make_signal(
                "bullish",
                "SMA20 > SMA50 > SMA200 — full bull alignment (Golden order)",
                "Moving Average Alignment",
                "When short-term MA is above medium-term MA which is above long-term MA, every timeframe is in uptrend.",
                "This 'Golden Order' is the strongest MA confirmation of Markup. Institutions are fully long. "
                "Price pullbacks to SMA20 should be bought; only a close below SMA50 breaks the structure."
            ))
        else:
            scores["markup"] += 1
            signals.append(_make_signal(
                "bullish",
                "SMA20 > SMA50 — short-term bullish but SMA200 not confirmed",
                "Moving Average Alignment",
                "Short-term and medium-term MAs are aligned bullish, but the long-term trend is not yet confirmed.",
                "Emerging uptrend — possibly late accumulation turning to early markup. "
                "Wait for price to also clear SMA200 before high conviction. Volume confirmation required."
            ))
    else:
        if cur_sma200 is not None and cur_sma50 < cur_sma200:
            scores["markdown"] += 2
            signals.append(_make_signal(
                "bearish",
                "SMA20 < SMA50 < SMA200 — full bear alignment (Death order)",
                "Moving Average Alignment",
                "All three major MAs are stacked bearishly — every timeframe confirms a downtrend.",
                "The 'Death Order' is the clearest Markdown confirmation. Institutions are net sellers. "
                "Rallies back to SMA20 are short-selling opportunities, not recoveries. Do not buy."
            ))
        else:
            scores["markdown"] += 1
            signals.append(_make_signal(
                "bearish",
                "SMA20 < SMA50 — short-term bearish",
                "Moving Average Alignment",
                "Short-term MA crossed below medium-term MA.",
                "Bearish short-term cross. Could be distribution turning to markdown, or a deep pullback in markup. "
                "Context matters: if price is near all-time highs this is more dangerous than near 52w lows."
            ))

    # 3. RSI
    if cur_rsi > 75:
        scores["distribution"] += 3
        signals.append(_make_signal(
            "bearish",
            f"RSI {cur_rsi:.0f} — extreme overbought, distribution risk high",
            "RSI (14-period Relative Strength Index)",
            "RSI measures the speed and magnitude of price moves on a 0–100 scale. Above 70 = overbought.",
            f"RSI at {cur_rsi:.0f} means recent up-moves are outsized versus down-moves — a condition that cannot "
            "persist. At these levels institutions often distribute aggressively into retail FOMO buying. "
            "Expect either a sharp correction or a sideways chop that slowly bleeds RSI lower."
        ))
    elif cur_rsi > 60:
        scores["markup"] += 2
        signals.append(_make_signal(
            "bullish",
            f"RSI {cur_rsi:.0f} — healthy bullish momentum zone",
            "RSI (14-period Relative Strength Index)",
            "RSI in the 60–70 range during an uptrend signals strong momentum without extreme overbought risk.",
            f"RSI at {cur_rsi:.0f} is the 'sweet spot' of Markup — strong enough to confirm institutional buying, "
            "not so extreme that a reversal is imminent. Pullbacks that hold RSI above 50 are buyable dips."
        ))
    elif cur_rsi > 45:
        signals.append(_make_signal(
            "neutral",
            f"RSI {cur_rsi:.0f} — neutral, no strong momentum signal",
            "RSI (14-period Relative Strength Index)",
            "RSI in the 40–60 range indicates balance between buyers and sellers.",
            f"RSI at {cur_rsi:.0f} is non-committal. Neither side has control. "
            "Look at other signals for context — MA alignment, OBV, and price structure will tell the real story."
        ))
    elif cur_rsi > 30:
        scores["distribution"] += 1
        scores["markdown"] += 1
        signals.append(_make_signal(
            "bearish",
            f"RSI {cur_rsi:.0f} — weak, sellers in control",
            "RSI (14-period Relative Strength Index)",
            "RSI declining toward oversold signals increasing selling pressure.",
            f"RSI at {cur_rsi:.0f} shows sellers dominating. Combined with downtrend price action this confirms "
            "distribution turning to markdown. Be cautious of 'cheap' narratives — RSI can stay low for months."
        ))
    else:
        if price_change_60 < -0.10:
            scores["markdown"] += 2
            signals.append(_make_signal(
                "bearish",
                f"RSI {cur_rsi:.0f} — oversold in downtrend (sell climax risk)",
                "RSI (14-period Relative Strength Index)",
                "RSI below 30 in a downtrend means panic selling — but in Markdown, oversold gets more oversold.",
                f"RSI at {cur_rsi:.0f} with a {abs(price_change_60*100):.1f}% drop is a sell climax. "
                "There may be a sharp bounce (dead cat), but without volume reversal and base-building, "
                "the downtrend resumes. Do not buy 'because it's cheap.'"
            ))
        else:
            scores["accumulation"] += 2
            signals.append(_make_signal(
                "bullish",
                f"RSI {cur_rsi:.0f} — oversold with stable price (accumulation signal)",
                "RSI (14-period Relative Strength Index)",
                "RSI below 30 while price is not making new lows suggests selling exhaustion.",
                f"RSI at {cur_rsi:.0f} but price not collapsing = selling pressure is drying up. "
                "This is the classic early accumulation RSI signature. Institutions absorb the last sellers. "
                "Look for OBV to confirm: if OBV rises while price stays flat, accumulation is real."
            ))

    # 4. MACD
    if cur_macd_diff > 0 and cur_macd_line > 0:
        scores["markup"] += 2
        signals.append(_make_signal(
            "bullish",
            "MACD above zero, histogram positive — momentum accelerating",
            "MACD (Moving Average Convergence Divergence)",
            "MACD measures momentum by comparing 12-EMA vs 26-EMA. Histogram shows acceleration/deceleration.",
            "MACD line above zero AND histogram positive means both trend direction and momentum favor bulls. "
            "This is the strongest MACD confirmation for Markup. Each histogram bar growing = institutions adding."
        ))
    elif cur_macd_diff > 0 and cur_macd_line <= 0:
        scores["accumulation"] += 1
        scores["markup"] += 1
        signals.append(_make_signal(
            "bullish",
            "MACD histogram turning positive — momentum shifting bullish",
            "MACD (Moving Average Convergence Divergence)",
            "Histogram crossing from negative to positive is the first momentum reversal signal.",
            "The histogram going positive while MACD is still below zero is the earliest momentum buy signal. "
            "Often appears at the end of accumulation — institutions beginning to push price."
        ))
    elif cur_macd_diff < 0 and cur_macd_line < 0:
        scores["markdown"] += 2
        signals.append(_make_signal(
            "bearish",
            "MACD below zero, histogram negative — momentum declining",
            "MACD (Moving Average Convergence Divergence)",
            "MACD line below zero AND histogram negative = trend and momentum both bearish.",
            "Both momentum and trend direction are bearish. This is the Markdown MACD signature. "
            "Do not fight it — even if the stock 'looks cheap', MACD says sellers are still dominant."
        ))
    else:
        scores["distribution"] += 1
        signals.append(_make_signal(
            "bearish",
            "MACD histogram turning negative — momentum decelerating",
            "MACD (Moving Average Convergence Divergence)",
            "Histogram crossing negative while price holds = momentum diverging from price.",
            "Price may still look stable but momentum is leaving the building. "
            "This early deceleration is the first warning sign of distribution turning to markdown."
        ))

    # 5. MACD divergence
    if bearish_div:
        scores["distribution"] += 2
        signals.append(_make_signal(
            "bearish",
            "Bearish MACD divergence — price making new highs but momentum fading",
            "MACD Divergence",
            "Divergence occurs when price and momentum move in opposite directions — a leading reversal warning.",
            "Price hit a new recent high but MACD did NOT confirm it with a higher high. "
            "This means the last price rally was driven by fewer buyers — institutions quietly stepping back. "
            "Classic distribution signal before a breakdown. Reduce longs on any weakness."
        ))
    elif bullish_div:
        scores["accumulation"] += 2
        signals.append(_make_signal(
            "bullish",
            "Bullish MACD divergence — price making new lows but momentum recovering",
            "MACD Divergence",
            "Divergence occurs when price and momentum move in opposite directions — a leading reversal warning.",
            "Price made a new recent low but MACD did NOT confirm it with a lower low. "
            "Sellers are exhausted — each new low has less force behind it. "
            "Institutions are quietly stepping in. This is the earliest and most reliable accumulation signal."
        ))

    # 6. Bollinger Bands
    if bb_width_pct < 0.2:
        if cur_price < cur_sma50:
            scores["accumulation"] += 2
            signals.append(_make_signal(
                "neutral",
                "BB squeeze below SMA50 — volatility compression at lows",
                "Bollinger Band Width (Squeeze)",
                "When BB width is in the bottom 20th percentile, volatility has compressed to historic lows. "
                "Squeezes always resolve in an explosive move — the direction is the question.",
                "The squeeze is happening below SMA50, suggesting the resolution is likely to be upward. "
                "This is the coiled spring in late accumulation — when it breaks out, it moves fast. "
                "Watch for a BB expansion day on above-average volume as the entry trigger."
            ))
        else:
            scores["distribution"] += 2
            signals.append(_make_signal(
                "neutral",
                "BB squeeze above SMA50 — volatility compression at highs",
                "Bollinger Band Width (Squeeze)",
                "Bollinger Band squeeze at elevated prices = distribution compressing before breakdown.",
                "The squeeze is at highs. This is more dangerous than it looks — institutions are selling "
                "into an artificially calm market. When the bands expand, the move is usually down. "
                "Reduce position size or set tight stops below the squeeze low."
            ))
    elif cur_price > cur_bb_upper:
        scores["distribution"] += 1
        signals.append(_make_signal(
            "bearish",
            "Price outside upper Bollinger Band — statistically overextended",
            "Bollinger Bands (2σ)",
            "Bollinger Bands represent ±2 standard deviations from the 20-day mean. "
            "Price outside the band is a statistically rare event that rarely sustains.",
            "Only 5% of price action occurs outside the bands. Being outside the upper band means "
            "the stock has moved too far too fast. Mean reversion is likely. "
            "Not a sell signal in a strong markup (can ride the band), but a warning to tighten stops."
        ))
    elif cur_price < cur_bb_lower:
        if price_change_60 < -0.10:
            scores["markdown"] += 1
            signals.append(_make_signal(
                "bearish",
                "Price outside lower Bollinger Band in downtrend — weakness persisting",
                "Bollinger Bands (2σ)",
                "Price below the lower band in a downtrend = trend so strong it keeps breaking statistical norms.",
                "In Markdown, price can 'walk the lower band' — staying outside for extended periods. "
                "This is NOT an oversold buy signal. It confirms extreme selling pressure. Wait for a "
                "full band re-entry and base formation before considering any long."
            ))
        else:
            scores["accumulation"] += 1
            signals.append(_make_signal(
                "bullish",
                "Price outside lower Bollinger Band — potential mean-reversion bounce",
                "Bollinger Bands (2σ)",
                "Price touching or below the lower band in a stable range suggests a short-term oversold condition.",
                "With stable price action (not a crashing stock), touching the lower band is often the "
                "range-trade buy signal. Risk is defined: stop below the band low, target the middle band (SMA20)."
            ))

    # 7. OBV
    if obv_slope > 0.05:
        scores["accumulation"] += 1
        scores["markup"] += 1
        signals.append(_make_signal(
            "bullish",
            f"OBV rising +{obv_slope*100:.1f}% — smart money accumulating on volume",
            "OBV (On-Balance Volume)",
            "OBV adds volume on up-days and subtracts on down-days. Rising OBV when price is flat = "
            "institutional buying pressure hidden beneath the surface.",
            f"OBV gained {obv_slope*100:.1f}% recently. When OBV rises before or during price stagnation, "
            "it means institutions are quietly accumulating — they buy on down-days to suppress price "
            "while they fill their position. This is the most reliable X-ray of institutional intent."
        ))
    elif obv_slope < -0.05:
        scores["distribution"] += 1
        scores["markdown"] += 1
        signals.append(_make_signal(
            "bearish",
            f"OBV declining −{abs(obv_slope*100):.1f}% — distribution volume signature",
            "OBV (On-Balance Volume)",
            "OBV falling means more volume is happening on down-days than up-days — institutional selling.",
            f"OBV dropped {abs(obv_slope*100):.1f}%. Even if price is holding up, the volume tells the real story. "
            "Institutions are selling into strength — each up-day has lower volume, each down-day higher. "
            "This is the classic distribution pattern before a price breakdown."
        ))
    else:
        signals.append(_make_signal(
            "neutral",
            "OBV flat — volume conviction absent",
            "OBV (On-Balance Volume)",
            "Neutral OBV means up-volume and down-volume are balanced.",
            "No institutional conviction in either direction. The market is uncertain. "
            "Wait for OBV to break its own trendline to confirm which way institutions are leaning."
        ))

    # 8. Stochastic
    if cur_stoch_k > 80 and cur_stoch_k < cur_stoch_d:
        scores["distribution"] += 1
        signals.append(_make_signal(
            "bearish",
            f"Stochastic {cur_stoch_k:.0f} — overbought with bearish K/D cross",
            "Stochastic Oscillator (14,3)",
            "Stochastic measures where price closes relative to its high-low range. "
            "%K crossing below %D in overbought territory is a sell signal.",
            f"Stochastic at {cur_stoch_k:.0f} is overbought AND %K just crossed below %D — "
            "momentum is rolling over while price is still elevated. Distribution signal. "
            "In range-bound markets this is the range-top sell trigger."
        ))
    elif cur_stoch_k < 20 and cur_stoch_k > cur_stoch_d:
        scores["accumulation"] += 1
        signals.append(_make_signal(
            "bullish",
            f"Stochastic {cur_stoch_k:.0f} — oversold with bullish K/D cross",
            "Stochastic Oscillator (14,3)",
            "Stochastic below 20 with %K crossing above %D is an oversold buy signal.",
            f"Stochastic at {cur_stoch_k:.0f} — price closed near the bottom of its recent range AND "
            "%K just crossed above %D. In accumulation ranges this is the short-term bounce trigger. "
            "Use as confirmation, not standalone entry."
        ))

    # -----------------------------------------------------------------------
    # Finalize
    # -----------------------------------------------------------------------
    total = sum(scores.values()) or 1
    stage = max(scores, key=scores.get)
    confidence = round(scores[stage] / total * 100)

    trade_levels  = _calc_trade_levels(
        stage, cur_price, cur_atr,
        cur_sma20, cur_sma50,
        cur_bb_lower, cur_bb_upper,
        low_20, high_20,
        high_52, low_52,
    )
    volume_analysis = _analyze_volume(close, volume, high, low)
    buying_point    = _calc_buying_point(
        stage, cur_price, cur_atr,
        cur_sma20, cur_sma50,
        cur_bb_lower, cur_bb_upper,
        low_20, high_20,
    )

    indicators = {
        "rsi": round(cur_rsi, 2),
        "stoch_k": round(cur_stoch_k, 2),
        "stoch_d": round(cur_stoch_d, 2),
        "sma20": round(cur_sma20, 4),
        "sma50": round(cur_sma50, 4),
        "sma200": round(cur_sma200, 4) if cur_sma200 is not None else None,
        "macd_line": round(cur_macd_line, 4),
        "macd_signal": round(cur_macd_signal, 4),
        "macd_diff": round(cur_macd_diff, 4),
        "bb_upper": round(cur_bb_upper, 4),
        "bb_lower": round(cur_bb_lower, 4),
        "bb_width_pct": round(bb_width_pct, 2),
        "obv_slope": round(obv_slope, 4),
        "price_change_60d": round(price_change_60 * 100, 2),
        "price_change_20d": round(price_change_20 * 100, 2),
        "price_position_52w": round(price_position, 2),
        "atr": round(cur_atr, 4),
        "scores": {k: round(v / total * 100) for k, v in scores.items()},
    }

    return {
        "stage": stage,
        "stage_info": STAGES[stage],
        "confidence": confidence,
        "signals": signals,
        "indicators": indicators,
        "trade_levels": trade_levels,
        "volume_analysis": volume_analysis,
        "buying_point": buying_point,
    }
