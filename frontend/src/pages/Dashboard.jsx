import React, { useState, useEffect, useCallback } from 'react'
import { BarChart2, Search, BookOpen, Star, ArrowRight, RefreshCw,
         TrendingUp, TrendingDown, Minus, ChevronDown, ChevronUp } from 'lucide-react'
import { NavLink } from 'react-router-dom'
import { useApi } from '../hooks/useApi'
import StageBadge from '../components/StageBadge'
import CandlestickChart from '../components/CandlestickChart'

const QUICK = ['SPY', 'QQQ', 'NVDA', 'AAPL', 'TSLA', 'MSFT', 'BTC-USD']

// ─── tiny helpers ─────────────────────────────────────────────────────────────
const fmtNum = v => {
  if (v == null) return '—'
  if (Math.abs(v) >= 1e12) return `${(v/1e12).toFixed(1)}T`
  if (Math.abs(v) >= 1e9)  return `${(v/1e9).toFixed(1)}B`
  if (Math.abs(v) >= 1e6)  return `${(v/1e6).toFixed(1)}M`
  if (Math.abs(v) >= 1e3)  return `${(v/1e3).toFixed(0)}K`
  return `${v}`
}

const STAGE_BG = {
  accumulation: 'bg-blue-50   border-blue-200',
  markup:       'bg-green-50  border-green-200',
  distribution: 'bg-amber-50  border-amber-200',
  markdown:     'bg-red-50    border-red-200',
}
const ACTION_COLOR = {
  accumulation: 'text-blue-700',
  markup:       'text-green-700',
  distribution: 'text-amber-700',
  markdown:     'text-red-700',
}

// ─── sub-components ───────────────────────────────────────────────────────────
const Row = ({ label, value, valueClass = 'text-ink' }) => (
  <div className="flex items-center justify-between py-1 border-b border-border/50 last:border-0">
    <span className="text-xs text-muted">{label}</span>
    <span className={`text-xs font-semibold font-mono ${valueClass}`}>{value ?? '—'}</span>
  </div>
)

const MiniCard = ({ title, children, className = '' }) => (
  <div className={`bg-white rounded-xl border border-border p-3 shadow-card ${className}`}>
    <div className="text-xs font-bold text-muted uppercase tracking-widest mb-2">{title}</div>
    {children}
  </div>
)

const SignalPill = ({ s }) => {
  const [open, setOpen] = useState(false)
  const isBull = s.type === 'bullish', isBear = s.type === 'bearish'
  return (
    <div className={`rounded-lg border-l-4 px-3 py-2 text-xs cursor-pointer ${
      isBull ? 'border-l-green-400 bg-green-50'  :
      isBear ? 'border-l-red-400   bg-red-50'    :
               'border-l-gray-300  bg-gray-50'
    }`} onClick={() => setOpen(v => !v)}>
      <div className="flex items-center gap-1.5 justify-between">
        <div className="flex items-center gap-1.5">
          {isBull ? <TrendingUp  size={11} className="text-green-600 flex-shrink-0" /> :
           isBear ? <TrendingDown size={11} className="text-red-500  flex-shrink-0" /> :
                    <Minus       size={11} className="text-gray-400 flex-shrink-0" />}
          {s.technique && (
            <span className={`font-bold px-1.5 py-0.5 rounded-full text-xs ${
              isBull ? 'bg-green-200 text-green-800' :
              isBear ? 'bg-red-200   text-red-800'   :
                       'bg-gray-200  text-gray-700'
            }`}>{s.technique}</span>
          )}
        </div>
        {open ? <ChevronUp size={11} className="text-muted flex-shrink-0" />
              : <ChevronDown size={11} className="text-muted flex-shrink-0" />}
      </div>
      <p className={`font-semibold mt-1 leading-snug ${
        isBull ? 'text-green-800' : isBear ? 'text-red-800' : 'text-gray-700'
      }`}>{s.text}</p>
      {open && s.implication && (
        <p className={`mt-1.5 leading-relaxed ${
          isBull ? 'text-green-700' : isBear ? 'text-red-700' : 'text-sub'
        }`}>{s.implication}</p>
      )}
    </div>
  )
}

// ─── Whale block (compact) ────────────────────────────────────────────────────
function WhaleBlock({ va }) {
  if (!va) return null
  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-2">
        <div className="bg-surface rounded-lg p-2 text-center">
          <div className="text-xs text-muted">Vol Today</div>
          <div className="text-sm font-bold font-mono text-ink">{fmtNum(va.current_volume)}</div>
        </div>
        <div className={`rounded-lg p-2 text-center border ${
          va.volume_ratio >= 3 ? 'bg-purple-50 border-purple-200' :
          va.volume_ratio >= 1.8 ? 'bg-amber-50 border-amber-200' :
          'bg-surface border-border'
        }`}>
          <div className="text-xs text-muted">vs 20d Avg</div>
          <div className={`text-sm font-bold font-mono ${
            va.volume_ratio >= 3 ? 'text-purple-700' :
            va.volume_ratio >= 1.8 ? 'text-amber-600' : 'text-ink'
          }`}>{va.volume_ratio}×</div>
        </div>
      </div>

      {/* Buy/Sell pressure bar */}
      <div>
        <div className="flex justify-between text-xs mb-1">
          <span className="text-green-600 font-semibold">Buy {va.buy_pressure}%</span>
          <span className="text-red-500 font-semibold">Sell {va.sell_pressure}%</span>
        </div>
        <div className="h-2.5 bg-red-100 rounded-full overflow-hidden">
          <div className="h-full bg-green-400 rounded-full"
            style={{ width: `${va.buy_pressure}%` }} />
        </div>
      </div>

      {va.whale_level !== 'none' && (
        <div className={`rounded-lg px-2.5 py-1.5 text-xs font-semibold ${
          va.whale_level === 'extreme' ? 'bg-purple-100 text-purple-800 border border-purple-300' :
          va.whale_level === 'strong'  ? 'bg-red-100    text-red-800    border border-red-300'    :
                                         'bg-amber-100  text-amber-800  border border-amber-300'
        }`}>
          {va.whale_level === 'extreme' ? '🚨 Extreme spike' :
           va.whale_level === 'strong'  ? '🐋 Whale activity' :
                                          '📊 Elevated interest'}
          {' '}({va.volume_ratio}× avg)
        </div>
      )}

      <p className="text-xs text-sub leading-relaxed">{va.whale_message}</p>

      {va.recent_spikes?.length > 0 && (
        <div className="space-y-1 pt-1">
          <div className="text-xs font-semibold text-muted">Recent Spikes</div>
          {va.recent_spikes.map((sp, i) => (
            <div key={i} className="flex items-center justify-between text-xs bg-surface rounded px-2 py-1">
              <span className="text-muted">{sp.date}</span>
              <span>{sp.direction}</span>
              <span className="font-mono font-bold text-ink">{sp.ratio}×</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Institutional panel ──────────────────────────────────────────────────────
function InstitutionalPanel({ inst }) {
  if (!inst) return (
    <div className="text-xs text-muted text-center py-4">Loading institutional data…</div>
  )

  const { institutional_holders = [], insider_transactions = [],
          options, short_interest = {}, major_holders = [] } = inst

  const signalColor = s =>
    s === 'bullish' ? 'text-green-600' : s === 'bearish' ? 'text-red-500' : 'text-amber-600'

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">

      {/* Options flow */}
      {options && (
        <MiniCard title="📊 Options Flow (Put/Call)">
          <div className="grid grid-cols-2 gap-2 mb-2">
            <div className="text-center bg-green-50 rounded-lg p-2">
              <div className="text-xs text-muted">Call Vol</div>
              <div className="font-bold text-green-700 font-mono text-sm">{fmtNum(options.call_volume)}</div>
            </div>
            <div className="text-center bg-red-50 rounded-lg p-2">
              <div className="text-xs text-muted">Put Vol</div>
              <div className="font-bold text-red-600 font-mono text-sm">{fmtNum(options.put_volume)}</div>
            </div>
          </div>
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-xs text-muted">P/C Ratio (vol)</span>
            <span className={`text-sm font-bold ${signalColor(options.signal)}`}>
              {options.put_call_vol}
            </span>
          </div>
          <div className={`text-xs px-2 py-1.5 rounded-lg font-semibold mb-2 ${
            options.signal === 'bullish' ? 'bg-green-100 text-green-800' :
            options.signal === 'bearish' ? 'bg-red-100   text-red-800'   :
                                           'bg-amber-100 text-amber-800'
          }`}>
            {options.signal === 'bullish' ? '🟢 Call-heavy — bullish flow'  :
             options.signal === 'bearish' ? '🔴 Put-heavy — bearish hedge'   :
                                            '🟡 Balanced options activity'}
          </div>
          <p className="text-xs text-sub leading-relaxed">{options.message}</p>
        </MiniCard>
      )}

      {/* Short interest */}
      {short_interest?.short_pct_float != null && (
        <MiniCard title="🩳 Short Interest">
          <div className="space-y-0.5 mb-2">
            <Row label="Short % of Float"
              value={short_interest.short_pct_float != null ? `${short_interest.short_pct_float}%` : '—'}
              valueClass={short_interest.short_pct_float > 15 ? 'text-red-600' :
                          short_interest.short_pct_float > 8  ? 'text-amber-600' : 'text-green-600'} />
            <Row label="Shares Short" value={fmtNum(short_interest.shares_short)} />
            <Row label="Days to Cover" value={short_interest.days_to_cover} />
            <Row label="vs Prior Month"
              value={short_interest.change_vs_prior_month != null
                ? `${short_interest.change_vs_prior_month > 0 ? '+' : ''}${short_interest.change_vs_prior_month}%`
                : '—'}
              valueClass={short_interest.change_vs_prior_month > 0 ? 'text-red-600' : 'text-green-600'} />
          </div>
          <p className="text-xs text-sub leading-relaxed">{short_interest.message}</p>
        </MiniCard>
      )}

      {/* Top institutional holders */}
      {institutional_holders.length > 0 && (
        <MiniCard title="🏦 Top Institutional Holders" className="md:col-span-2">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left border-b border-border">
                  <th className="pb-1.5 text-muted font-semibold pr-3">Institution</th>
                  <th className="pb-1.5 text-muted font-semibold text-right pr-3">Shares</th>
                  <th className="pb-1.5 text-muted font-semibold text-right pr-3">Value</th>
                  <th className="pb-1.5 text-muted font-semibold text-right pr-3">% Held</th>
                  <th className="pb-1.5 text-muted font-semibold text-right">As of</th>
                </tr>
              </thead>
              <tbody>
                {institutional_holders.map((h, i) => (
                  <tr key={i} className="border-b border-border/50 last:border-0 hover:bg-surface transition-colors">
                    <td className="py-1.5 pr-3 font-medium text-ink max-w-[180px] truncate">{h.name}</td>
                    <td className="py-1.5 pr-3 text-right font-mono text-sub">{fmtNum(h.shares)}</td>
                    <td className="py-1.5 pr-3 text-right font-mono text-sub">${fmtNum(h.value)}</td>
                    <td className="py-1.5 pr-3 text-right font-bold text-primary">{h.pct_held != null ? `${h.pct_held}%` : '—'}</td>
                    <td className="py-1.5 text-right text-muted">{h.date_reported || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-muted mt-2 italic">
            Source: 13F filings (quarterly). Shows who holds this stock — if names like Vanguard, BlackRock,
            or hedge funds appear with large positions, price is supported by institutional demand.
          </p>
        </MiniCard>
      )}

      {/* Insider transactions */}
      {insider_transactions.length > 0 && (
        <MiniCard title="👤 Recent Insider Transactions" className="md:col-span-2">
          <div className="space-y-1">
            {insider_transactions.slice(0, 8).map((tx, i) => (
              <div key={i} className={`flex items-center gap-2 rounded-lg px-2.5 py-1.5 ${
                tx.is_buy ? 'bg-green-50' : 'bg-red-50'
              }`}>
                <span className={`flex-shrink-0 font-bold text-xs w-12 ${
                  tx.is_buy ? 'text-green-700' : 'text-red-600'
                }`}>{tx.is_buy ? '🟢 BUY' : '🔴 SELL'}</span>
                <span className="text-xs font-semibold text-ink flex-1 truncate">{tx.insider}</span>
                <span className="text-xs text-muted hidden md:block">{tx.title}</span>
                <span className="text-xs font-mono font-bold text-ink">{fmtNum(tx.shares)} shares</span>
                <span className={`text-xs font-mono ${tx.is_buy ? 'text-green-700' : 'text-red-600'}`}>
                  ${fmtNum(tx.value)}
                </span>
                <span className="text-xs text-muted">{tx.date}</span>
              </div>
            ))}
          </div>
          <p className="text-xs text-muted mt-2 italic">
            Insiders know their company best. Cluster buying by multiple insiders = strong bullish signal.
            Isolated sales are often for personal reasons (diversification, taxes) — cluster sells are the warning.
          </p>
        </MiniCard>
      )}

      {/* Major holder breakdown */}
      {major_holders.length > 0 && (
        <MiniCard title="📋 Ownership Breakdown">
          <div className="space-y-0.5">
            {major_holders.map((mh, i) => (
              <Row key={i} label={mh.label} value={mh.value} />
            ))}
          </div>
        </MiniCard>
      )}
    </div>
  )
}

// ─── Main Dashboard ───────────────────────────────────────────────────────────
export default function Dashboard() {
  const [ticker, setTicker]   = useState('SPY')
  const [input, setInput]     = useState('SPY')
  const [data, setData]       = useState(null)
  const [inst, setInst]       = useState(null)
  const [news, setNews]       = useState([])
  const [instLoading, setInstLoading] = useState(false)
  const { call, loading }     = useApi()

  const loadStock = useCallback(async (t) => {
    const d = await call(`/api/stock/${t}/cycle?period=1y`)
    if (d) setData({ ...d, ticker: t })
  }, [call])

  const loadInst = useCallback(async (t) => {
    setInstLoading(true)
    setInst(null)
    const d = await call(`/api/stock/${t}/institutional`)
    if (d) setInst(d)
    setInstLoading(false)
  }, [call])

  const loadNews = useCallback(async () => {
    const n = await call('/api/news?limit=5')
    if (n) setNews(n)
  }, [call])

  useEffect(() => {
    loadStock(ticker)
    loadInst(ticker)
    loadNews()
  }, [ticker])

  const submit = (e) => {
    e.preventDefault()
    const t = input.trim().toUpperCase()
    if (t) setTicker(t)
  }

  const ind = data?.indicators    || {}
  const tl  = data?.trade_levels  || {}
  const va  = data?.volume_analysis
  const bp  = data?.buying_point

  return (
    <div className="p-4 space-y-4 max-w-6xl">

      {/* ── Header ── */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h1 className="text-lg font-bold text-ink">Dashboard</h1>
        <form onSubmit={submit} className="flex gap-2">
          <input value={input} onChange={e => setInput(e.target.value.toUpperCase())}
            className="input w-24 text-sm" placeholder="Ticker" />
          <button type="submit" className="btn-primary text-xs px-3">
            {loading ? <RefreshCw size={12} className="animate-spin" /> : 'Go'}
          </button>
        </form>
      </div>

      {/* ── Quick chips ── */}
      <div className="flex gap-1.5 flex-wrap">
        {QUICK.map(t => (
          <button key={t} onClick={() => { setTicker(t); setInput(t) }}
            className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border transition-colors ${
              ticker === t
                ? 'bg-primary text-white border-primary'
                : 'bg-white border-border text-sub hover:border-primary/50 hover:text-primary'
            }`}>{t}</button>
        ))}
      </div>

      {loading && !data && (
        <div className="flex items-center gap-2 text-muted text-sm">
          <RefreshCw size={13} className="animate-spin" /> Analyzing {ticker}…
        </div>
      )}

      {data && (
        <div className="space-y-3">

          {/* ── Stage banner (compact) ── */}
          <div className={`rounded-xl border p-3 flex items-center gap-3 flex-wrap ${STAGE_BG[data.stage] || 'bg-surface border-border'}`}>
            <span className="text-3xl">{data.stage_info?.emoji}</span>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-bold text-ink">{data.ticker}</span>
                <StageBadge stage={data.stage} confidence={data.confidence} />
              </div>
              <p className="text-xs text-sub mt-0.5 leading-snug">{data.stage_info?.description}</p>
            </div>
            <div className={`text-sm font-bold flex-shrink-0 ${ACTION_COLOR[data.stage]}`}>
              {data.stage_info?.action}
            </div>
          </div>

          {/* ── Main 2-col grid ── */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">

            {/* LEFT (2/3) — chart + signals */}
            <div className="lg:col-span-2 space-y-3">

              {/* Indicator strip */}
              <div className="bg-white rounded-xl border border-border shadow-card px-3 py-2 flex flex-wrap gap-x-4 gap-y-1">
                {[
                  { l: 'RSI',  v: ind.rsi,  c: ind.rsi > 70 ? 'text-red-500' : ind.rsi < 30 ? 'text-green-600' : 'text-ink' },
                  { l: 'Stoch', v: ind.stoch_k, c: ind.stoch_k > 80 ? 'text-red-500' : ind.stoch_k < 20 ? 'text-green-600' : 'text-ink' },
                  { l: 'MACD', v: ind.macd_diff, c: ind.macd_diff > 0 ? 'text-green-600' : 'text-red-500' },
                  { l: '20d',  v: ind.price_change_20d != null ? `${ind.price_change_20d > 0 ? '+' : ''}${ind.price_change_20d}%` : null, c: ind.price_change_20d > 0 ? 'text-green-600' : 'text-red-500' },
                  { l: '60d',  v: ind.price_change_60d != null ? `${ind.price_change_60d > 0 ? '+' : ''}${ind.price_change_60d}%` : null, c: ind.price_change_60d > 0 ? 'text-green-600' : 'text-red-500' },
                  { l: '52W',  v: ind.price_position_52w != null ? `${Math.round(ind.price_position_52w * 100)}%` : null },
                  { l: 'SMA20', v: ind.sma20 },
                  { l: 'SMA50', v: ind.sma50 },
                  { l: 'ATR',  v: ind.atr },
                ].map(({ l, v, c }) => (
                  <div key={l} className="flex items-center gap-1">
                    <span className="text-xs text-muted">{l}</span>
                    <span className={`text-xs font-bold font-mono ${c || 'text-ink'}`}>{v ?? '—'}</span>
                  </div>
                ))}
              </div>

              {/* Chart */}
              {data.chart?.length > 0 && (
                <div className="bg-white rounded-xl border border-border shadow-card p-3">
                  <div className="text-xs font-bold text-muted uppercase tracking-widest mb-2">{data.ticker} — Price</div>
                  <CandlestickChart data={data.chart} />
                </div>
              )}

              {/* Signals — accordion, 2 col */}
              {data.signals?.length > 0 && (
                <div className="bg-white rounded-xl border border-border shadow-card p-3">
                  <div className="text-xs font-bold text-muted uppercase tracking-widest mb-2">
                    Signals ({data.signals.length}) — tap to expand
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {data.signals.map((s, i) => <SignalPill key={i} s={s} />)}
                  </div>
                </div>
              )}
            </div>

            {/* RIGHT (1/3) — trade levels + buying point + whale */}
            <div className="space-y-3">

              {/* Trade levels */}
              {tl.entry && (
                <MiniCard title="📐 Trade Levels">
                  <div className="space-y-1.5 mb-2">
                    <div className="flex justify-between items-center">
                      <span className="text-xs text-muted">Entry</span>
                      <span className="font-mono font-bold text-ink text-sm">{tl.entry?.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between items-center bg-red-50 rounded px-2 py-1">
                      <span className="text-xs text-red-500">Stop Loss</span>
                      <div className="text-right">
                        <span className="font-mono font-bold text-red-600 text-sm">{tl.stop_loss?.toFixed(2)}</span>
                        <span className="text-xs text-red-400 ml-1">−{tl.stop_pct?.toFixed(1)}%</span>
                      </div>
                    </div>
                    <div className="flex justify-between items-center bg-green-50 rounded px-2 py-1">
                      <span className="text-xs text-green-600">Target</span>
                      <div className="text-right">
                        <span className="font-mono font-bold text-green-700 text-sm">{tl.target?.toFixed(2)}</span>
                        <span className="text-xs text-green-500 ml-1">+{tl.target_pct?.toFixed(1)}%</span>
                      </div>
                    </div>
                    <div className={`flex justify-between items-center rounded px-2 py-1 ${
                      tl.risk_reward >= 2.5 ? 'bg-green-50' :
                      tl.risk_reward >= 1.5 ? 'bg-amber-50' : 'bg-red-50'
                    }`}>
                      <span className="text-xs text-muted">R : R</span>
                      <span className={`font-bold text-sm ${
                        tl.risk_reward >= 2.5 ? 'text-green-700' :
                        tl.risk_reward >= 1.5 ? 'text-amber-600' : 'text-red-600'
                      }`}>1 : {tl.risk_reward} {tl.risk_reward >= 2.5 ? '✓' : tl.risk_reward < 1.5 ? '✗' : ''}</span>
                    </div>
                  </div>
                  <p className="text-xs text-muted leading-relaxed">{tl.reasoning}</p>
                </MiniCard>
              )}

              {/* Buying point */}
              {bp && (
                <MiniCard title="🎯 Buying Point">
                  <div className={`text-xs font-bold mb-2 ${
                    data.stage === 'markdown' ? 'text-red-600' :
                    data.stage === 'distribution' ? 'text-amber-600' : 'text-green-700'
                  }`}>{bp.entry_type}</div>
                  {bp.ideal_entry && (
                    <div className="grid grid-cols-3 gap-1 mb-2 text-center">
                      <div className="bg-surface rounded p-1.5">
                        <div className="text-xs text-muted">Low</div>
                        <div className="font-mono font-bold text-xs text-ink">{bp.zone_low?.toFixed(2)}</div>
                      </div>
                      <div className="bg-green-50 border border-green-200 rounded p-1.5">
                        <div className="text-xs text-green-600">Ideal</div>
                        <div className="font-mono font-bold text-xs text-green-700">{bp.ideal_entry?.toFixed(2)}</div>
                      </div>
                      <div className="bg-surface rounded p-1.5">
                        <div className="text-xs text-muted">High</div>
                        <div className="font-mono font-bold text-xs text-ink">{bp.zone_high?.toFixed(2)}</div>
                      </div>
                    </div>
                  )}
                  <p className="text-xs text-sub leading-relaxed mb-2">{bp.trigger}</p>
                  <div className="bg-red-50 border border-red-100 rounded p-2">
                    <span className="text-xs font-bold text-red-500">⚠ Avoid if: </span>
                    <span className="text-xs text-red-700">{bp.avoid_if}</span>
                  </div>
                </MiniCard>
              )}

              {/* Whale compact */}
              <MiniCard title="🐋 Volume & Whales">
                <WhaleBlock va={va} />
              </MiniCard>

              {/* News */}
              <MiniCard title="📰 News">
                <div className="space-y-2">
                  {news.map((a, i) => (
                    <a key={i} href={a.link} target="_blank" rel="noopener noreferrer"
                      className="block hover:bg-surface rounded p-1 -mx-1 transition-colors">
                      <div className="text-xs text-primary font-semibold">{a.source}</div>
                      <div className="text-xs text-ink leading-snug">{a.title}</div>
                    </a>
                  ))}
                </div>
                <NavLink to="/news" className="block text-center text-xs text-primary hover:underline mt-2 pt-2 border-t border-border">All news →</NavLink>
              </MiniCard>

            </div>
          </div>

          {/* ── Institutional section (full width) ── */}
          <div className="bg-white rounded-xl border border-border shadow-card p-4">
            <div className="text-xs font-bold text-muted uppercase tracking-widest mb-3">
              🏦 Institutional Intelligence
              {instLoading && <span className="ml-2 text-primary font-normal normal-case">Loading…</span>}
            </div>
            <InstitutionalPanel inst={inst} />
          </div>

        </div>
      )}
    </div>
  )
}
