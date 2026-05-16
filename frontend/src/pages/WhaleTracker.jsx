import React, { useState, useCallback, useEffect } from 'react'
import {
  Radar, RefreshCw, TrendingUp, TrendingDown, Minus,
  AlertTriangle, ChevronDown, ChevronUp, ExternalLink,
} from 'lucide-react'
import {
  RadialBarChart, RadialBar, PolarAngleAxis,
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  BarChart, Bar,
} from 'recharts'
import { useApi } from '../hooks/useApi'
import HelpBanner from '../components/HelpBanner'

// ── helpers ───────────────────────────────────────────────────────────────────
const fmtNum = v => {
  if (v == null) return '—'
  if (Math.abs(v) >= 1e9) return `${(v/1e9).toFixed(1)}B`
  if (Math.abs(v) >= 1e6) return `${(v/1e6).toFixed(1)}M`
  if (Math.abs(v) >= 1e3) return `${(v/1e3).toFixed(0)}K`
  return String(v)
}

const sigColor = s =>
  s === 'bullish' ? 'text-green-600' :
  s === 'bearish' ? 'text-red-600'   : 'text-amber-600'

const sigBg = s =>
  s === 'bullish' ? 'bg-green-50 border-green-200' :
  s === 'bearish' ? 'bg-red-50 border-red-200'     : 'bg-amber-50 border-amber-200'

const sigDot = s =>
  s === 'bullish' ? 'bg-green-400' :
  s === 'bearish' ? 'bg-red-500'   : 'bg-amber-400'

// ── shared ────────────────────────────────────────────────────────────────────
const Card = ({ title, icon, children, className = '' }) => (
  <div className={`bg-white rounded-xl border border-border shadow-card p-4 ${className}`}>
    {title && (
      <div className="flex items-center gap-2 mb-3 pb-2 border-b border-border">
        {icon && <span className="text-sm">{icon}</span>}
        <span className="text-xs font-bold text-muted uppercase tracking-widest">{title}</span>
      </div>
    )}
    {children}
  </div>
)

const Row = ({ label, value, vc = 'text-ink' }) => (
  <div className="flex justify-between items-center py-1 border-b border-border/40 last:border-0">
    <span className="text-xs text-muted">{label}</span>
    <span className={`text-xs font-bold font-mono ${vc}`}>{value ?? '—'}</span>
  </div>
)

function SignalBadge({ direction, strength }) {
  const Icon = direction === 'bullish' ? TrendingUp : direction === 'bearish' ? TrendingDown : Minus
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded-full border ${
      direction === 'bullish' ? 'bg-green-100 text-green-700 border-green-200' :
      direction === 'bearish' ? 'bg-red-100 text-red-600 border-red-200'       :
                                'bg-gray-100 text-gray-600 border-gray-200'
    }`}>
      <Icon size={9} />
      {direction}
    </span>
  )
}

// ── 1. Smart Money Score Gauge ────────────────────────────────────────────────
function ScoreGauge({ score, rating, ratingColor, summary }) {
  if (score == null) return null

  const gaugeData = [{ value: score, fill: ratingColor }]
  const scoreLabel =
    score >= 80 ? 'EXTREME BULLISH' :
    score >= 65 ? 'BULLISH'         :
    score >= 45 ? 'NEUTRAL'         :
    score >= 30 ? 'BEARISH'         : 'EXTREME BEARISH'

  return (
    <div className="flex flex-col items-center">
      <div className="relative">
        <RadialBarChart
          width={180} height={100}
          cx={90} cy={95}
          innerRadius={60} outerRadius={85}
          startAngle={180} endAngle={0}
          data={gaugeData}
        >
          <PolarAngleAxis type="number" domain={[0, 100]} angleAxisId={0} tick={false} />
          <RadialBar
            dataKey="value" cornerRadius={4}
            background={{ fill: '#F4F6FB' }}
            angleAxisId={0}
          />
        </RadialBarChart>
        <div className="absolute inset-0 flex flex-col items-center justify-end pb-2">
          <span className="text-3xl font-black" style={{ color: ratingColor }}>{score}</span>
          <span className="text-xs font-bold" style={{ color: ratingColor }}>{scoreLabel}</span>
        </div>
      </div>
      <p className="text-xs text-sub text-center leading-relaxed mt-2 max-w-[240px]">{summary}</p>
    </div>
  )
}

// ── 2. Signal Feed ────────────────────────────────────────────────────────────
function SignalFeed({ signals }) {
  const [expanded, setExpanded] = useState(null)
  if (!signals?.length) return <p className="text-xs text-muted text-center py-4">No signals detected.</p>

  return (
    <div className="space-y-2">
      {signals.map((s, i) => (
        <div key={i}
          className={`rounded-lg border px-3 py-2 cursor-pointer transition-colors ${sigBg(s.direction)}`}
          onClick={() => setExpanded(expanded === i ? null : i)}
        >
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <span className={`w-2 h-2 rounded-full flex-shrink-0 ${sigDot(s.direction)}`} />
              <span className="text-xs font-bold text-muted flex-shrink-0">{s.icon} {s.source}</span>
              <span className="text-xs font-semibold text-ink truncate">{s.title}</span>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <span className={`text-xs font-bold ${s.delta >= 0 ? 'text-green-700' : 'text-red-600'}`}>
                {s.delta > 0 ? '+' : ''}{s.delta}pts
              </span>
              {expanded === i ? <ChevronUp size={11} className="text-muted" /> : <ChevronDown size={11} className="text-muted" />}
            </div>
          </div>
          {expanded === i && (
            <p className={`text-xs mt-2 leading-relaxed ${sigColor(s.direction)}`}>{s.detail}</p>
          )}
        </div>
      ))}
    </div>
  )
}

// ── 3. Dark Pool Panel ────────────────────────────────────────────────────────
function DarkPoolPanel({ ticker }) {
  const [data, setData] = useState(null)
  const { call, loading } = useApi()

  useEffect(() => {
    call(`/api/whale/${ticker}/darkpool`).then(d => d && setData(d))
  }, [ticker])

  if (loading && !data) return <div className="text-xs text-muted text-center py-4"><RefreshCw size={12} className="animate-spin inline mr-1" />Loading dark pool data…</div>
  if (!data?.daily?.length) return <p className="text-xs text-muted text-center py-4">No FINRA dark pool data available.</p>

  return (
    <div className="space-y-3">
      <div className={`rounded-lg border p-2.5 ${sigBg(data.signal)}`}>
        <div className="flex items-center justify-between mb-1">
          <span className={`text-xs font-bold ${sigColor(data.signal)}`}>
            {data.signal === 'bullish' ? '🌑 Stealth Accumulation' :
             data.signal === 'bearish' ? '🌑 Distribution Detected' : '🌑 Normal Activity'}
          </span>
          <span className={`text-sm font-black font-mono ${sigColor(data.signal)}`}>
            {data.latest_dark_pct}%
          </span>
        </div>
        <p className="text-xs text-sub leading-relaxed">{data.message}</p>
      </div>
      <div className="grid grid-cols-3 gap-2 text-center text-xs">
        <div className="bg-surface rounded-lg p-2">
          <div className="text-muted">Latest</div>
          <div className="font-bold text-ink">{data.latest_dark_pct}%</div>
        </div>
        <div className="bg-surface rounded-lg p-2">
          <div className="text-muted">10d Avg</div>
          <div className="font-bold text-ink">{data.avg_dark_pct}%</div>
        </div>
        <div className={`rounded-lg p-2 ${data.spike ? 'bg-purple-100' : 'bg-surface'}`}>
          <div className="text-muted">Spike</div>
          <div className={`font-bold ${data.spike ? 'text-purple-700' : 'text-ink'}`}>{data.spike ? 'YES' : 'No'}</div>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={80}>
        <AreaChart data={data.daily}>
          <defs>
            <linearGradient id="dpGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#6366F1" stopOpacity={0.2} />
              <stop offset="95%" stopColor="#6366F1" stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis dataKey="date" tick={{ fontSize: 8 }} tickLine={false}
            tickFormatter={d => d.slice(5)} interval="preserveStartEnd" />
          <YAxis domain={[0, 100]} tick={{ fontSize: 8 }} tickLine={false} width={28} />
          <Tooltip contentStyle={{ fontSize: 10, borderRadius: 8 }}
            formatter={v => [`${v}%`, 'Dark Pool %']} />
          <Area type="monotone" dataKey="dark_pct" stroke="#6366F1" strokeWidth={1.5}
            fill="url(#dpGrad)" dot={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

// ── 4. Insider Transactions ───────────────────────────────────────────────────
function InsiderPanel({ data }) {
  if (!data) return null
  const { summary, activist } = data

  return (
    <div className="space-y-3">
      {/* Summary */}
      <div className={`rounded-lg border p-2.5 ${sigBg(summary?.signal)}`}>
        <div className="flex items-center gap-2 mb-1">
          {summary?.cluster_buy && <span className="text-xs bg-green-200 text-green-800 font-bold px-2 py-0.5 rounded-full">CLUSTER BUY</span>}
          {summary?.cluster_sell && <span className="text-xs bg-red-200 text-red-800 font-bold px-2 py-0.5 rounded-full">CLUSTER SELL</span>}
          <span className="text-xs font-semibold text-muted ml-auto">
            {summary?.buys_30d} buys / {summary?.sells_30d} sells (30d)
          </span>
        </div>
        <p className="text-xs text-sub leading-relaxed">{summary?.message}</p>
      </div>

      {/* Activist filings */}
      {activist?.length > 0 && (
        <div>
          <div className="text-xs font-bold text-muted mb-1.5">13D/G Filings (Last 6 Months)</div>
          {activist.map((a, i) => (
            <div key={i} className={`rounded-lg border px-2.5 py-2 mb-1 text-xs ${a.is_activist ? 'bg-amber-50 border-amber-200' : 'bg-surface border-border'}`}>
              <div className="flex justify-between">
                <span className={`font-bold ${a.is_activist ? 'text-amber-700' : 'text-ink'}`}>
                  {a.is_activist ? '⚡ ACTIVIST' : '📋 PASSIVE'} — {a.form}
                </span>
                <span className="text-muted">{a.filing_date}</span>
              </div>
              <span className="text-sub">{a.filer}</span>
            </div>
          ))}
        </div>
      )}

      {/* Transaction table */}
      {summary?.transactions?.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border text-left">
                <th className="pb-1.5 text-muted font-semibold pr-3">Date</th>
                <th className="pb-1.5 text-muted font-semibold pr-3">Insider</th>
                <th className="pb-1.5 text-muted font-semibold pr-3">Type</th>
                <th className="pb-1.5 text-muted font-semibold text-right">Value</th>
              </tr>
            </thead>
            <tbody>
              {summary.transactions.slice(0, 8).map((tx, i) => (
                <tr key={i} className={`border-b border-border/40 last:border-0 ${tx.is_buy ? 'hover:bg-green-50' : 'hover:bg-red-50'}`}>
                  <td className="py-1.5 pr-3 text-muted">{tx.date}</td>
                  <td className="py-1.5 pr-3 font-medium text-ink max-w-[140px] truncate">{tx.insider}</td>
                  <td className="py-1.5 pr-3">
                    <span className={`font-bold ${tx.is_buy ? 'text-green-700' : 'text-red-600'}`}>
                      {tx.is_buy ? '🟢 BUY' : '🔴 SELL'}
                    </span>
                  </td>
                  <td className="py-1.5 text-right font-mono text-sub">{tx.value ? `$${fmtNum(tx.value)}` : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── 5. Options Flow Panel ─────────────────────────────────────────────────────
function OptionsFlowPanel({ data }) {
  if (!data) return null

  return (
    <div className="space-y-3">
      {/* Flow signal */}
      <div className={`rounded-lg border p-2.5 ${sigBg(data.flow_signal)}`}>
        <div className="flex justify-between items-center mb-1">
          <span className={`text-xs font-bold ${sigColor(data.flow_signal)}`}>
            💸 Premium Flow — {data.call_premium_pct}% Call-Dominated
          </span>
          <span className="text-xs text-muted">Spot: ${data.spot_price}</span>
        </div>
        <p className="text-xs text-sub leading-relaxed">{data.flow_message}</p>
      </div>

      {/* Key stats row */}
      <div className="grid grid-cols-2 gap-2">
        {data.expected_move_pct && (
          <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-2 text-center">
            <div className="text-xs text-muted">Expected Move</div>
            <div className="font-black text-indigo-700 text-lg">±{data.expected_move_pct}%</div>
            <div className="text-xs text-indigo-500">Options market implied</div>
          </div>
        )}
        {data.iv_skew != null && (
          <div className={`rounded-lg p-2 text-center border ${
            data.iv_skew_signal === 'bearish' ? 'bg-red-50 border-red-200' :
            data.iv_skew_signal === 'bullish' ? 'bg-green-50 border-green-200' : 'bg-surface border-border'
          }`}>
            <div className="text-xs text-muted">IV Skew (P-C)</div>
            <div className={`font-black text-lg ${sigColor(data.iv_skew_signal)}`}>{data.iv_skew}%</div>
            <div className={`text-xs ${sigColor(data.iv_skew_signal)}`}>
              {data.iv_skew > 3 ? 'Fear premium' : data.iv_skew < -2 ? 'Greed premium' : 'Normal'}
            </div>
          </div>
        )}
      </div>

      {/* Premium bars */}
      <div>
        <div className="flex justify-between text-xs mb-1">
          <span className="text-green-600 font-semibold">Call ${fmtNum(data.total_call_premium)}</span>
          <span className="text-red-500 font-semibold">Put ${fmtNum(data.total_put_premium)}</span>
        </div>
        <div className="h-3 bg-red-100 rounded-full overflow-hidden">
          <div className="h-full bg-green-400 rounded-full transition-all"
            style={{ width: `${data.call_premium_pct}%` }} />
        </div>
      </div>

      {/* Unusual activity */}
      {data.unusual_activity?.length > 0 && (
        <div>
          <div className="text-xs font-bold text-muted mb-1.5">🔥 Unusual Activity (Vol &gt; OI)</div>
          <div className="space-y-1">
            {data.unusual_activity.slice(0, 6).map((u, i) => (
              <div key={i} className={`rounded-lg px-2.5 py-1.5 text-xs flex items-center gap-2 ${
                u.is_bullish ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'
              }`}>
                <span className={`font-bold flex-shrink-0 w-14 ${u.is_bullish ? 'text-green-700' : 'text-red-600'}`}>
                  {u.type.toUpperCase()} {u.strike}
                </span>
                <span className="text-muted flex-shrink-0">{u.expiry}</span>
                <span className="font-mono text-ink">{u.vol_oi_ratio}× OI</span>
                <span className={`font-bold font-mono ml-auto ${u.is_bullish ? 'text-green-700' : 'text-red-600'}`}>
                  ${fmtNum(u.premium_usd)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Deep ITM calls */}
      {data.deep_itm_calls?.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-2.5">
          <div className="text-xs font-bold text-amber-700 mb-1">⚠️ Deep ITM Calls Detected</div>
          {data.deep_itm_calls.slice(0, 3).map((d, i) => (
            <div key={i} className="text-xs text-amber-700 flex justify-between">
              <span>Strike {d.strike} · {d.expiry}</span>
              <span className="font-bold">${fmtNum(d.premium_usd)}</span>
            </div>
          ))}
          <p className="text-xs text-amber-600 mt-1 leading-snug">
            Institutions use deep ITM calls to gain equity-like exposure while avoiding 13F reporting thresholds.
          </p>
        </div>
      )}
    </div>
  )
}

// ── 6. Congressional Trades ───────────────────────────────────────────────────
function CongressPanel({ data }) {
  if (!data) return null

  return (
    <div className="space-y-3">
      <div className={`rounded-lg border p-2.5 ${sigBg(data.signal)}`}>
        <div className="flex items-center gap-2 mb-1">
          {data.cluster_buy && <span className="text-xs bg-green-200 text-green-800 font-bold px-2 py-0.5 rounded-full">CLUSTER BUY</span>}
          <span className="text-xs font-semibold text-muted ml-auto">
            {data.buys_90d} buys / {data.sells_90d} sells (90d)
          </span>
        </div>
        <p className="text-xs text-sub leading-relaxed">{data.message}</p>
      </div>

      {data.trades?.length > 0 ? (
        <div className="space-y-1">
          {data.trades.slice(0, 8).map((t, i) => (
            <div key={i} className={`rounded-lg px-2.5 py-1.5 text-xs flex items-center gap-2 ${
              t.is_buy ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'
            }`}>
              <span className={`font-bold flex-shrink-0 ${t.is_buy ? 'text-green-700' : 'text-red-600'}`}>
                {t.is_buy ? '🟢' : '🔴'} {t.chamber}
              </span>
              <span className="font-semibold text-ink truncate flex-1">{t.member}</span>
              <span className={`text-xs px-1.5 py-0.5 rounded font-bold ${
                t.party === 'Republican' || t.party === 'R' ? 'bg-red-100 text-red-700' :
                t.party === 'Democrat'   || t.party === 'D' ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600'
              }`}>{(t.party || '?')[0]}</span>
              <span className="text-muted flex-shrink-0">{t.trade_date}</span>
              <span className="font-mono text-sub flex-shrink-0">{t.amount}</span>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs text-muted text-center py-2">No congressional trades on record for this ticker.</p>
      )}
    </div>
  )
}

// ── 7. COT Panel ──────────────────────────────────────────────────────────────
function CotPanel({ cots }) {
  if (!cots?.length) return null

  return (
    <div className="space-y-3">
      {cots.map((cot, i) => (
        <div key={i} className="space-y-2">
          <div className={`rounded-lg border p-2.5 ${sigBg(cot.signal)}`}>
            <div className="flex justify-between items-center mb-1">
              <span className={`text-xs font-bold ${sigColor(cot.signal)}`}>
                📊 {cot.instrument} Futures
              </span>
              <span className="text-xs text-muted">{cot.latest_date}</span>
            </div>
            <div className="grid grid-cols-3 gap-2 mb-2 text-center text-xs">
              <div className="bg-white/60 rounded p-1.5">
                <div className="text-muted">Asset Mgr Net</div>
                <div className={`font-bold font-mono ${cot.asset_mgr_net > 0 ? 'text-green-700' : 'text-red-600'}`}>
                  {cot.asset_mgr_net > 0 ? '+' : ''}{fmtNum(cot.asset_mgr_net)}
                </div>
              </div>
              <div className="bg-white/60 rounded p-1.5">
                <div className="text-muted">WoW Change</div>
                <div className={`font-bold font-mono ${cot.asset_mgr_chg > 0 ? 'text-green-700' : 'text-red-600'}`}>
                  {cot.asset_mgr_chg > 0 ? '+' : ''}{fmtNum(cot.asset_mgr_chg)}
                </div>
              </div>
              <div className="bg-white/60 rounded p-1.5">
                <div className="text-muted">Lev. Funds Net</div>
                <div className={`font-bold font-mono ${cot.lev_net > 0 ? 'text-green-700' : 'text-red-600'}`}>
                  {cot.lev_net > 0 ? '+' : ''}{fmtNum(cot.lev_net)}
                </div>
              </div>
            </div>
            <p className="text-xs text-sub leading-relaxed">{cot.message}</p>
          </div>

          {/* COT history chart */}
          {cot.weeks?.length > 0 && (
            <ResponsiveContainer width="100%" height={90}>
              <BarChart data={cot.weeks.slice(-8)}>
                <XAxis dataKey="date" tick={{ fontSize: 8 }} tickLine={false}
                  tickFormatter={d => d.slice(5)} />
                <YAxis tick={{ fontSize: 8 }} tickLine={false} width={40}
                  tickFormatter={v => fmtNum(v)} />
                <Tooltip contentStyle={{ fontSize: 10, borderRadius: 8 }}
                  formatter={v => [fmtNum(v), 'Net']} />
                <Bar dataKey="asset_mgr_net" name="Asset Mgr Net" radius={[2,2,0,0]}>
                  {cot.weeks.slice(-8).map((w, j) => (
                    <Cell key={j} fill={w.asset_mgr_net >= 0 ? '#22C55E' : '#EF4444'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      ))}
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────
const QUICK = ['SPY', 'QQQ', 'NVDA', 'AAPL', 'TSLA', 'MSFT', 'AMZN']

export default function WhaleTracker() {
  const [ticker,  setTicker]  = useState('SPY')
  const [input,   setInput]   = useState('SPY')
  const [data,    setData]    = useState(null)
  const [insider, setInsider] = useState(null)
  const [optFlow, setOptFlow] = useState(null)
  const [congress,setCongress]= useState(null)
  const { call, loading }     = useApi()

  const load = useCallback(async (t) => {
    setData(null); setInsider(null); setOptFlow(null); setCongress(null)

    // Load whale score + signals first (fast render)
    const main = await call(`/api/whale/${t}`)
    if (main) setData(main)

    // Load secondary panels in parallel (slower sources)
    const [ins, opt, cong] = await Promise.all([
      call(`/api/whale/${t}/insider`),
      call(`/api/whale/${t}/options-flow`),
      call(`/api/whale/${t}/congress`),
    ])
    if (ins)  setInsider(ins)
    if (opt)  setOptFlow(opt)
    if (cong) setCongress(cong)
  }, [call])

  useEffect(() => { load(ticker) }, [])

  const submit = e => {
    e.preventDefault()
    const t = input.trim().toUpperCase()
    if (t) { setTicker(t); load(t) }
  }

  return (
    <div className="p-3 space-y-3 max-w-6xl">

      <HelpBanner
        pageKey="whale"
        title="Whale Tracker — Follow the Smart Money"
        whatIsThis="Aggregates 6 institutional signals — SEC Form 4 insider trades, 13D/G activist filings, FINRA dark pool prints, options flow, COT reports, and congressional trades — into one Smart Money Score (0-100) per stock."
        steps={[
          "Type a ticker (e.g. <b>NVDA</b>) and load — wait ~5 seconds for the 6-source pull.",
          "Read the <b>Smart Money Score</b>: 80+ = EXT BULL (follow the buyers), 30- = EXT BEAR (warning).",
          "Drill into each panel: <b>Insider cluster buying</b> + <b>13D activist entry</b> are the strongest signals.",
        ]}
        tips={[
          "Insider <b>cluster buying</b> (≥3 insiders in 30 days) cannot be explained by personal reasons — it's a thesis.",
          "<b>13D filings</b> precede strategic action (buyback, spin-off, sale) within 60-90 days historically.",
          "Politician trades (Pelosi / Tuberville etc.) generate <b>reflexive retail momentum</b> — read also: News → Smart Money tab.",
        ]}
      />

      {/* Header */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-3">
          <Radar size={20} className="text-primary" />
          <div>
            <h1 className="text-lg font-bold text-ink">Whale Tracker</h1>
            <p className="text-xs text-muted">
              SEC Form 4 · 13D/G Activist · FINRA Dark Pool · Options Flow · COT · Congress Trades
            </p>
          </div>
        </div>
        <form onSubmit={submit} className="flex gap-2">
          <input value={input} onChange={e => setInput(e.target.value.toUpperCase())}
            className="input w-24 text-sm" placeholder="Ticker" />
          <button type="submit" className="btn-primary text-xs px-3">
            {loading ? <RefreshCw size={11} className="animate-spin" /> : 'Analyze'}
          </button>
        </form>
      </div>

      {/* Quick chips */}
      <div className="flex gap-1.5 flex-wrap">
        {QUICK.map(t => (
          <button key={t} onClick={() => { setTicker(t); setInput(t); load(t) }}
            className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border transition-colors ${
              ticker === t
                ? 'bg-primary text-white border-primary'
                : 'bg-white border-border text-sub hover:border-primary/50 hover:text-primary'
            }`}>{t}</button>
        ))}
      </div>

      {/* Data source legend */}
      <div className="flex gap-2 flex-wrap text-xs">
        {[
          { label: 'SEC EDGAR (Form 4, 13D/G)', color: 'bg-blue-100 text-blue-700 border-blue-200' },
          { label: 'FINRA Dark Pool', color: 'bg-purple-100 text-purple-700 border-purple-200' },
          { label: 'Options Flow', color: 'bg-green-100 text-green-700 border-green-200' },
          { label: 'CFTC COT', color: 'bg-amber-100 text-amber-700 border-amber-200' },
          { label: 'Congress STOCK Act', color: 'bg-red-100 text-red-700 border-red-200' },
        ].map(s => (
          <span key={s.label} className={`px-2 py-0.5 rounded-full border font-medium ${s.color}`}>{s.label}</span>
        ))}
      </div>

      {loading && !data && (
        <div className="flex items-center gap-2 text-muted text-sm">
          <RefreshCw size={13} className="animate-spin" /> Scanning {ticker} across all intelligence sources…
        </div>
      )}

      {data && (
        <div className="space-y-3">

          {/* ── Score + Top Signals ── */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <Card title="Smart Money Score" icon="🐋" className="flex flex-col items-center">
              <ScoreGauge
                score={data.score}
                rating={data.rating}
                ratingColor={data.rating_color}
                summary={data.summary}
              />
              <div className="w-full mt-3 space-y-0.5">
                {Object.entries(data.breakdown || {}).filter(([,v]) => v.score_delta).map(([k, v]) => (
                  <div key={k} className="flex justify-between items-center text-xs">
                    <span className="text-muted capitalize">{k.replace('_', ' ')}</span>
                    <span className={`font-bold font-mono ${v.score_delta > 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {v.score_delta > 0 ? '+' : ''}{v.score_delta}
                    </span>
                  </div>
                ))}
              </div>
            </Card>

            <Card title="Signal Feed — Ranked by Conviction" icon="📡" className="lg:col-span-2">
              <SignalFeed signals={data.signals} />
            </Card>
          </div>

          {/* ── Row 2: Dark Pool + Insider ── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card title="FINRA Dark Pool & Off-Exchange Volume" icon="🌑">
              <DarkPoolPanel ticker={ticker} />
            </Card>
            <Card title="SEC Form 4 Insider Transactions + 13D/G Activist Filings" icon="🏛">
              {insider
                ? <InsiderPanel data={insider} />
                : <div className="text-xs text-muted text-center py-4">
                    <RefreshCw size={11} className="animate-spin inline mr-1" />Loading insider data…
                  </div>
              }
            </Card>
          </div>

          {/* ── Row 3: Options + Congress ── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card title="Options Flow Intelligence" icon="💸">
              {optFlow
                ? <OptionsFlowPanel data={optFlow} />
                : <div className="text-xs text-muted text-center py-4">
                    <RefreshCw size={11} className="animate-spin inline mr-1" />Loading options flow…
                  </div>
              }
            </Card>
            <Card title="Congressional Trading — STOCK Act Disclosures" icon="🏛️">
              {congress
                ? <CongressPanel data={congress} />
                : <div className="text-xs text-muted text-center py-4">
                    <RefreshCw size={11} className="animate-spin inline mr-1" />Loading congressional data…
                  </div>
              }
            </Card>
          </div>

          {/* ── Row 4: COT Report ── */}
          {data.breakdown?.cot && (
            <Card title="CFTC Commitment of Traders — Institutional Futures Positioning" icon="📊">
              <div className="text-xs text-muted mb-3 leading-relaxed">
                Shows how Asset Managers (pension funds, endowments) and Leveraged Funds (hedge funds, CTAs)
                are positioned in futures contracts relevant to this stock.
                Asset Manager net long + increasing = institutional tailwind.
                Divergence (Inst. long, Hedge Funds short) = classic pre-squeeze setup.
              </div>
              <CotFetcher ticker={ticker} />
            </Card>
          )}

        </div>
      )}
    </div>
  )
}

// Separate component so COT loads independently
function CotFetcher({ ticker }) {
  const [cots, setCots] = useState(null)
  const { call }        = useApi()

  useEffect(() => {
    call(`/api/whale/${ticker}`).then(d => {
      if (d?.breakdown?.cot?.instruments) {
        Promise.all(
          d.breakdown.cot.instruments.map(inst =>
            call(`/api/whale/cot/${inst}`)
          )
        ).then(results => setCots(results.filter(Boolean)))
      }
    })
  }, [ticker])

  if (!cots) return <div className="text-xs text-muted text-center py-4"><RefreshCw size={11} className="animate-spin inline mr-1" />Loading COT data…</div>
  return <CotPanel cots={cots} />
}
