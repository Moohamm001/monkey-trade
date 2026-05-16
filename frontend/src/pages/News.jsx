import React, { useEffect, useMemo, useState } from 'react'
import {
  ExternalLink, RefreshCw, TrendingUp, TrendingDown, Minus, Search,
  Brain, Newspaper, AlertTriangle, Target, Sparkles,
  ChevronLeft, ChevronRight, ChevronDown, ChevronUp, Info, Clock,
  Crown, Landmark, Building2, Briefcase, Star,
} from 'lucide-react'
import { useApi } from '../hooks/useApi'
import HelpBanner from '../components/HelpBanner'

// ── helpers ───────────────────────────────────────────────────────────────────

const relTime = (iso) => {
  if (!iso) return ''
  try {
    const diff = (Date.now() - new Date(iso)) / 1000
    if (diff < 3600)  return `${Math.floor(diff / 60)}m ago`
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
    return `${Math.floor(diff / 86400)}d ago`
  } catch { return '' }
}

const sentimentMeta = {
  bullish: { color: 'text-green-800 bg-green-100 border-green-300', dot: 'bg-green-500', Icon: TrendingUp,   label: 'Bullish' },
  bearish: { color: 'text-red-800   bg-red-100   border-red-300',   dot: 'bg-red-500',   Icon: TrendingDown, label: 'Bearish' },
  neutral: { color: 'text-slate-800 bg-slate-100 border-slate-300', dot: 'bg-slate-400', Icon: Minus,        label: 'Neutral' },
}

const qualityMeta = {
  A: { color: 'bg-emerald-100 text-emerald-800 border-emerald-400', label: 'Strong setup' },
  B: { color: 'bg-blue-100    text-blue-800    border-blue-400',    label: 'Tradeable' },
  C: { color: 'bg-amber-100   text-amber-800   border-amber-400',   label: 'Watch only' },
  D: { color: 'bg-slate-200   text-slate-700   border-slate-400',   label: 'Skip' },
}

const toneMeta = {
  'Risk-On':  'bg-green-100 text-green-800 border-green-300',
  'Risk-Off': 'bg-red-100   text-red-800   border-red-300',
  'Mixed':    'bg-amber-100 text-amber-800 border-amber-300',
}

// Plain-English action label derived from opp + confidence + ticker.
const actionLabel = (opp, conf, hasTicker, smartMoney) => {
  if (smartMoney?.detected && smartMoney.direction === 'buy')
    return { text: 'FOLLOW MONEY', color: 'bg-amber-200 text-amber-900 border-amber-500' }
  if (smartMoney?.detected && smartMoney.direction === 'sell')
    return { text: 'HEED WARNING', color: 'bg-red-200 text-red-900 border-red-500' }
  if (!hasTicker)                    return { text: 'WATCH SECTOR',  color: 'bg-slate-100 text-slate-700 border-slate-300' }
  if (opp >= 75 && conf >= 70)       return { text: 'STRONG SETUP',  color: 'bg-emerald-100 text-emerald-800 border-emerald-400' }
  if (opp >= 60)                     return { text: 'TRADEABLE',     color: 'bg-blue-100 text-blue-800 border-blue-400' }
  if (opp >= 45)                     return { text: 'WATCHLIST',     color: 'bg-amber-100 text-amber-800 border-amber-400' }
  return                                    { text: 'NO ACTION',     color: 'bg-slate-100 text-slate-600 border-slate-300' }
}

// Icon + color per smart-money category.
const smCategoryMeta = {
  'Billionaire Investor':  { Icon: Crown,      color: 'text-amber-600',   bg: 'bg-amber-50 border-amber-300' },
  'Politician':            { Icon: Landmark,   color: 'text-purple-600',  bg: 'bg-purple-50 border-purple-300' },
  'Activist / Hedge Fund': { Icon: Briefcase,  color: 'text-red-600',     bg: 'bg-red-50 border-red-300' },
  'Mega Institution':      { Icon: Building2,  color: 'text-blue-600',    bg: 'bg-blue-50 border-blue-300' },
  'Mega-Cap CEO':          { Icon: Star,       color: 'text-emerald-600', bg: 'bg-emerald-50 border-emerald-300' },
}

const smDirectionMeta = {
  buy:     { color: 'bg-green-600 text-white',  label: 'BUYING' },
  sell:    { color: 'bg-red-600 text-white',    label: 'SELLING / SHORTING' },
  neutral: { color: 'bg-slate-500 text-white',  label: 'MENTIONED' },
}

// Compact card used inside the Spotlight grid. Much denser than IntelligenceCard
// so we can fit many on screen.
function SpotlightCard({ a }) {
  const sm = a.smart_money
  if (!sm?.detected) return null
  const top = sm.entities[0]
  const cm = smCategoryMeta[top.category] || smCategoryMeta['Billionaire Investor']
  const Icon = cm.Icon
  const dm = smDirectionMeta[sm.direction] || smDirectionMeta.neutral
  const stm = sentimentMeta[a.sentiment] || sentimentMeta.neutral
  const opp = a.signal?.opportunity ?? 0
  return (
    <a href={a.link} target="_blank" rel="noopener noreferrer"
       className={`block rounded-lg border-2 ${cm.bg} p-2 hover:shadow-card-hover transition-shadow group`}>
      <div className="flex items-center gap-1.5 mb-1.5 flex-wrap">
        <Icon size={13} className={cm.color} />
        <span className="text-xs font-extrabold text-ink truncate">{top.name}</span>
        <span className={`rounded px-1.5 py-0.5 text-[10px] font-extrabold ${dm.color}`}>{dm.label}</span>
        {sm.entities.length > 1 && (
          <span className="text-[10px] text-sub">+{sm.entities.length - 1}</span>
        )}
        <span className="ml-auto text-[10px] text-sub">{relTime(a.published)}</span>
      </div>

      <h4 className="text-xs font-bold text-ink leading-snug line-clamp-2 group-hover:text-primary mb-1.5">
        {a.title}
      </h4>

      <div className="flex items-center gap-1.5 flex-wrap text-[10px]">
        {a.tickers?.slice(0, 3).map(t => (
          <span key={t} className="font-mono font-bold bg-white border border-amber-300 text-amber-900 rounded px-1">
            ${t}
          </span>
        ))}
        <span className={`px-1 py-0.5 rounded border font-bold ${stm.color}`}>{stm.label}</span>
        <span className="ml-auto font-bold text-ink">Opp <b className="text-primary">{opp}</b></span>
        <span className="font-bold text-ink">Conf <b className="text-primary">{a.confidence}%</b></span>
      </div>
    </a>
  )
}

function SmartMoneyBadge({ sm, size = 'sm' }) {
  if (!sm?.detected) return null
  const top = sm.entities[0]
  const cm = smCategoryMeta[top.category] || smCategoryMeta['Billionaire Investor']
  const dm = smDirectionMeta[sm.direction] || smDirectionMeta.neutral
  const Icon = cm.Icon
  const more = sm.entities.length - 1
  return (
    <div className={`inline-flex items-center gap-1.5 rounded-lg border ${cm.bg} ${size === 'lg' ? 'px-2.5 py-1.5' : 'px-2 py-0.5'}`}>
      <Icon size={size === 'lg' ? 16 : 12} className={cm.color} />
      <span className={`font-bold text-ink ${size === 'lg' ? 'text-sm' : 'text-xs'}`}>{top.name}</span>
      {more > 0 && <span className="text-xs text-sub">+{more}</span>}
      <span className={`rounded px-1.5 py-0.5 text-[10px] font-extrabold ${dm.color}`}>{dm.label}</span>
    </div>
  )
}

// ── sub-components ────────────────────────────────────────────────────────────

function Stat({ label, value, hint, valueClass = '' }) {
  return (
    <div className="card">
      <div className="text-xs font-semibold text-sub uppercase tracking-wide">{label}</div>
      <div className={`text-2xl font-bold text-ink mt-0.5 ${valueClass}`}>{value}</div>
      {hint && <div className="text-xs text-sub mt-0.5">{hint}</div>}
    </div>
  )
}

function ScoreBar({ label, value }) {
  const pct = Math.max(0, Math.min(100, value * 10))
  const isRisk = label === 'Risk Level'
  const color = isRisk
    ? (value >= 7 ? 'bg-red-500' : value >= 5 ? 'bg-amber-500' : 'bg-green-500')
    : (value >= 7 ? 'bg-emerald-500' : value >= 5 ? 'bg-blue-500' : 'bg-slate-400')
  return (
    <div className="flex items-center gap-2 text-xs">
      <div className="w-36 text-sub truncate font-medium">{label}</div>
      <div className="flex-1 h-2 bg-slate-200 rounded-full overflow-hidden">
        <div className={`h-full ${color} transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <div className="w-7 text-right font-mono font-bold text-ink">{value}</div>
    </div>
  )
}

function IntelligenceCard({ a, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen)
  const sm  = sentimentMeta[a.sentiment] || sentimentMeta.neutral
  const SmI = sm.Icon
  const sig = a.signal || {}
  const hasTicker = (a.tickers || []).length > 0
  const smartMoney = a.smart_money
  const action = actionLabel(sig.opportunity ?? 0, a.confidence ?? 0, hasTicker, smartMoney)
  const qm = qualityMeta[sig.quality] || qualityMeta.D
  const smGlow = smartMoney?.detected
    ? 'ring-2 ring-amber-400 border-amber-300 shadow-[0_0_0_4px_rgba(251,191,36,0.08)]'
    : ''

  return (
    <div className={`card group hover:shadow-card-hover transition-shadow ${smGlow}`}>
      {smartMoney?.detected && (
        <div className="mb-2 -mt-1 flex items-center gap-2 flex-wrap">
          <span className="text-[10px] uppercase tracking-widest font-extrabold text-amber-700 flex items-center gap-1">
            <Crown size={12} /> Smart Money Signal
          </span>
          <SmartMoneyBadge sm={smartMoney} size="sm" />
        </div>
      )}
      {/* ── Header row: action + summary + meta ── */}
      <div className="flex items-start gap-3">
        {/* Action badge */}
        <div className="flex-shrink-0 flex flex-col items-center gap-1 w-24 text-center">
          <div className={`px-2 py-1 rounded-lg border text-xs font-extrabold leading-tight ${action.color}`}>
            {action.text}
          </div>
          <div className={`px-2 py-0.5 rounded-md border text-xs font-bold ${qm.color}`} title={qm.label}>
            Grade {sig.quality}
          </div>
        </div>

        {/* Title + meta */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap mb-1">
            <span className={`text-xs px-1.5 py-0.5 rounded-full border font-semibold ${sm.color} inline-flex items-center gap-1`}>
              <SmI size={10} /> {sm.label}
            </span>
            <span className="text-xs px-1.5 py-0.5 rounded-full bg-primary text-white font-semibold">
              {a.event_type}
            </span>
            {a.tickers?.slice(0, 4).map(t => (
              <span key={t} className="text-xs font-mono font-bold text-amber-900 bg-amber-100 border border-amber-300 rounded px-1.5 py-0.5">
                ${t}
              </span>
            ))}
            <span className="text-xs text-sub inline-flex items-center gap-1 ml-auto">
              <Clock size={10} /> {relTime(a.published)}
            </span>
            <span className="text-xs font-semibold text-ink">{a.source}</span>
          </div>
          <a href={a.link} target="_blank" rel="noopener noreferrer"
             className="text-sm font-bold text-ink group-hover:text-primary leading-snug block">
            {a.title} <ExternalLink size={11} className="inline opacity-60" />
          </a>
          {a.summary && (
            <p className="text-xs text-sub mt-1 line-clamp-2">{a.summary}</p>
          )}
        </div>

        {/* Numeric meters */}
        <div className="flex-shrink-0 grid grid-cols-2 gap-1.5 text-center w-32">
          <div className="bg-surface rounded-lg p-1.5 border border-border">
            <div className="text-[10px] text-sub uppercase font-semibold">Opp</div>
            <div className="text-lg font-extrabold text-ink leading-none mt-0.5">{sig.opportunity ?? 0}</div>
          </div>
          <div className="bg-surface rounded-lg p-1.5 border border-border">
            <div className="text-[10px] text-sub uppercase font-semibold">Conf</div>
            <div className="text-lg font-extrabold text-ink leading-none mt-0.5">{a.confidence ?? 0}<span className="text-xs">%</span></div>
          </div>
        </div>
      </div>

      {/* ── Recommendation strip ── */}
      <div className="mt-2 p-2 rounded-lg bg-primary-light border border-primary/30">
        <div className="flex items-start gap-2">
          <Target size={12} className="text-primary flex-shrink-0 mt-0.5" />
          <div className="text-xs text-ink"><b className="text-primary">What to do:</b> {a.recommendation}</div>
        </div>
      </div>

      {/* ── Toggle for details ── */}
      <button onClick={() => setOpen(o => !o)}
        className="mt-2 flex items-center gap-1 text-xs font-semibold text-primary hover:text-primary-dark">
        {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        {open ? 'Hide details' : 'Show details (scores, scenarios, analogs)'}
      </button>

      {open && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-3 pt-3 border-t border-border">
          {/* Signal scores */}
          <div className="space-y-1.5">
            <div className="text-xs font-bold text-ink uppercase tracking-wide mb-1.5 flex items-center gap-1">
              <Sparkles size={11} className="text-primary" /> Signal Scores
              <span className="text-sub font-normal normal-case">(0-10 each)</span>
            </div>
            {sig.factors && Object.entries(sig.factors).map(([k, v]) => (
              <ScoreBar key={k} label={k} value={v} />
            ))}
          </div>

          {/* Impact + scenarios + analogs */}
          <div className="space-y-3">
            <div>
              <div className="text-xs font-bold text-ink uppercase tracking-wide mb-1.5">Expected Price Move</div>
              <div className="grid grid-cols-3 gap-1.5 text-xs">
                <div className="bg-surface rounded-lg p-2 border border-border">
                  <div className="text-sub text-[10px] uppercase font-semibold">Short (1d-2w)</div>
                  <div className="font-mono font-bold text-ink mt-0.5">{a.impact?.short_term}</div>
                </div>
                <div className="bg-surface rounded-lg p-2 border border-border">
                  <div className="text-sub text-[10px] uppercase font-semibold">Medium (1-6m)</div>
                  <div className="font-mono font-bold text-ink mt-0.5">{a.impact?.medium_term}</div>
                </div>
                <div className="bg-surface rounded-lg p-2 border border-border">
                  <div className="text-sub text-[10px] uppercase font-semibold">Long (6m+)</div>
                  <div className="font-mono font-bold text-ink mt-0.5">{a.impact?.long_term}</div>
                </div>
              </div>
            </div>
            <div>
              <div className="text-xs font-bold text-ink uppercase tracking-wide mb-1.5">Scenarios</div>
              <div className="space-y-1 text-xs">
                <div className="p-1.5 bg-green-50 border border-green-200 rounded">
                  <span className="text-green-800 font-bold">Bull: </span><span className="text-ink">{a.scenarios?.bull}</span>
                </div>
                <div className="p-1.5 bg-slate-50 border border-slate-200 rounded">
                  <span className="text-slate-800 font-bold">Base: </span><span className="text-ink">{a.scenarios?.base}</span>
                </div>
                <div className="p-1.5 bg-red-50 border border-red-200 rounded">
                  <span className="text-red-800 font-bold">Bear: </span><span className="text-ink">{a.scenarios?.bear}</span>
                </div>
              </div>
            </div>
            {a.analogs?.length > 0 && (
              <div>
                <div className="text-xs font-bold text-ink uppercase tracking-wide mb-1.5">Historical Analogs</div>
                <ul className="text-xs text-ink list-disc pl-4 space-y-0.5 bg-surface p-2 rounded-lg border border-border">
                  {a.analogs.map((x, i) => <li key={i}>{x}</li>)}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function SimpleCard({ a }) {
  return (
    <a href={a.link} target="_blank" rel="noopener noreferrer"
       className="card hover:shadow-card-hover transition-shadow group block">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 mb-1 flex-wrap">
            <span className="text-xs font-bold text-primary">{a.source || a.publisher}</span>
            <span className="text-xs text-sub">{relTime(a.published)}</span>
            {a.strategy_relevance > 0 && (
              <span className="text-xs bg-amber-100 text-amber-800 border border-amber-300 rounded-full px-1.5 py-0.5 font-bold">
                {a.strategy_relevance} keyword{a.strategy_relevance > 1 ? 's' : ''}
              </span>
            )}
          </div>
          <h3 className="text-sm font-semibold text-ink group-hover:text-primary transition-colors leading-snug">
            {a.title}
          </h3>
          {a.tags?.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1.5">
              {a.tags.slice(0, 3).map(tag => (
                <span key={tag} className="text-xs bg-primary-light text-primary border border-primary/20 rounded px-1.5 py-0.5 font-semibold">{tag}</span>
              ))}
            </div>
          )}
        </div>
        <ExternalLink size={14} className="text-sub group-hover:text-primary flex-shrink-0 mt-0.5" />
      </div>
    </a>
  )
}

// ── pagination ────────────────────────────────────────────────────────────────

function Pagination({ page, totalPages, onPage, pageSize, onPageSize, total }) {
  if (total === 0) return null
  const pages = []
  const start = Math.max(1, page - 2)
  const end   = Math.min(totalPages, start + 4)
  for (let i = start; i <= end; i++) pages.push(i)
  return (
    <div className="card flex flex-wrap items-center gap-2 sticky bottom-2 z-10 bg-white shadow-card-hover">
      <div className="text-sm font-semibold text-ink">
        Page <span className="text-primary">{page}</span> of {totalPages}
        <span className="text-sub font-normal ml-2">({total} items)</span>
      </div>

      <div className="flex items-center gap-1 ml-auto">
        <button onClick={() => onPage(1)} disabled={page === 1}
          className="btn-ghost text-xs px-2 disabled:opacity-40">First</button>
        <button onClick={() => onPage(Math.max(1, page - 1))} disabled={page === 1}
          className="btn-ghost text-xs px-2 disabled:opacity-40">
          <ChevronLeft size={14} /> Prev
        </button>
        {pages.map(p => (
          <button key={p} onClick={() => onPage(p)}
            className={`text-xs px-2.5 py-1.5 rounded-lg font-semibold border ${
              p === page
                ? 'bg-primary text-white border-primary'
                : 'bg-white text-ink border-border hover:bg-surface'
            }`}>
            {p}
          </button>
        ))}
        <button onClick={() => onPage(Math.min(totalPages, page + 1))} disabled={page === totalPages}
          className="btn-ghost text-xs px-2 disabled:opacity-40">
          Next <ChevronRight size={14} />
        </button>
        <button onClick={() => onPage(totalPages)} disabled={page === totalPages}
          className="btn-ghost text-xs px-2 disabled:opacity-40">Last</button>
      </div>

      <div className="flex items-center gap-1.5 text-xs text-ink">
        <span className="text-sub font-semibold">Per page</span>
        <select value={pageSize} onChange={e => onPageSize(+e.target.value)}
          className="text-xs border border-border rounded px-2 py-1 bg-white font-semibold text-ink">
          {[5, 10, 15, 25].map(n => <option key={n} value={n}>{n}</option>)}
        </select>
      </div>
    </div>
  )
}

// ── main page ────────────────────────────────────────────────────────────────

export default function News() {
  const [tab, setTab]                 = useState('intelligence')
  const [intel, setIntel]             = useState(null)
  const [feed, setFeed]               = useState([])
  const [ticker, setTicker]           = useState('')
  const [tickerData, setTickerData]   = useState(null)
  const [eventFilter, setEventFilter] = useState('All')
  const [minConf, setMinConf]         = useState(0)
  const [page, setPage]               = useState(1)
  const [pageSize, setPageSize]       = useState(10)
  const [smartOnly, setSmartOnly]     = useState(false)
  const [entityFilter, setEntityFilter] = useState(null)   // canonical name or null
  const [expandSpotlight, setExpandSpotlight] = useState(false)
  const { call, loading }             = useApi()

  const loadIntel = async () => {
    const params = new URLSearchParams({ limit: '150', min_confidence: String(minConf) })
    if (eventFilter !== 'All') params.set('event_type', eventFilter)
    const data = await call(`/api/news/intelligence?${params}`)
    if (data) { setIntel(data); setPage(1) }
  }
  const loadFeed = async () => {
    const data = await call('/api/news?limit=60')
    if (data) { setFeed(data); setPage(1) }
  }
  const loadTicker = async (sym) => {
    if (!sym) return
    const data = await call(`/api/news/ticker/${sym.toUpperCase()}`)
    if (data) { setTickerData(data); setPage(1) }
  }

  useEffect(() => {
    if (tab === 'intelligence' && !intel) loadIntel()
    if (tab === 'feed' && feed.length === 0) loadFeed()
    setPage(1)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab])

  useEffect(() => {
    if (tab === 'intelligence') loadIntel()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eventFilter, minConf])

  useEffect(() => { setPage(1) }, [smartOnly, entityFilter])

  // pagination slicing
  let sourceList =
    tab === 'intelligence' ? (intel?.articles || []) :
    tab === 'feed'         ? feed :
    tab === 'ticker'       ? (tickerData?.articles || []) :
    []
  if (tab === 'intelligence' && smartOnly) {
    sourceList = sourceList.filter(a => a.smart_money?.detected)
  }
  if (tab === 'intelligence' && entityFilter) {
    sourceList = sourceList.filter(a =>
      a.smart_money?.entities?.some(e => e.name === entityFilter))
  }
  const totalPages = Math.max(1, Math.ceil(sourceList.length / pageSize))
  const pageStart  = (page - 1) * pageSize
  const pageSlice  = sourceList.slice(pageStart, pageStart + pageSize)

  const eventOptions = useMemo(
    () => ['All', ...(intel?.event_types || [])],
    [intel]
  )

  return (
    <div className="p-3 space-y-3">

      <HelpBanner
        pageKey="news"
        title="News & Market Impact Intelligence"
        whatIsThis="Aggregates headlines from 10+ reliable sources (Yahoo, MarketWatch, CNBC, WSJ, Bloomberg, Reuters, FT…), classifies each for event type, sentiment, and tickers, then scores impact and surfaces Smart Money moves."
        steps={[
          "Use the <b>Intelligence</b> tab — cards are ranked by Opportunity score; <b>gold-bordered</b> ones are Smart Money signals (Trump / Pelosi / Buffett / Burry / Ackman / BlackRock / Musk …).",
          "Each card shows a plain-English <b>Action label</b> (FOLLOW MONEY / STRONG SETUP / WATCHLIST / SKIP), plus Opp (0-100) and Conf (0-100%).",
          "Click <b>Show details</b> for signal-score breakdown, expected price move per horizon, bull/base/bear scenarios, and historical analogs.",
          "Use the <b>Ticker Lookup</b> tab to score news for a specific symbol.",
        ]}
        tips={[
          "Click <b>“Show Smart Money only”</b> to filter to just high-conviction capital-flow signals.",
          "<b>Politician + buying verb</b> = reflexive retail momentum catalyst (think viral on Reddit/X).",
          "<b>Burry / Hindenburg + short report</b> = step back; capitulation flush often comes within 30 days.",
        ]}
      />

      {/* ── Tab bar ───────────────────────────────────────────────────── */}
      <div className="flex items-center gap-2 flex-wrap">
        <button onClick={() => setTab('intelligence')}
          className={`btn text-sm font-semibold ${tab === 'intelligence' ? 'btn-primary' : 'btn-ghost'}`}>
          <Brain size={14} /> Intelligence
        </button>
        <button onClick={() => setTab('feed')}
          className={`btn text-sm font-semibold ${tab === 'feed' ? 'btn-primary' : 'btn-ghost'}`}>
          <Newspaper size={14} /> Market Feed
        </button>
        <button onClick={() => setTab('ticker')}
          className={`btn text-sm font-semibold ${tab === 'ticker' ? 'btn-primary' : 'btn-ghost'}`}>
          <Search size={14} /> Ticker Lookup
        </button>
        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={() => tab === 'intelligence' ? loadIntel() : tab === 'feed' ? loadFeed() : loadTicker(ticker)}
            disabled={loading}
            className="btn-ghost text-xs">
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
        </div>
      </div>

      {/* ── INTELLIGENCE TAB ─────────────────────────────────────────── */}
      {tab === 'intelligence' && (
        <>
          {/* Aggregates */}
          {intel && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              <div className="card">
                <div className="text-xs font-semibold text-sub uppercase tracking-wide">Market Tone</div>
                <div className={`mt-1 inline-block px-2.5 py-1 rounded-full border text-sm font-bold ${toneMeta[intel.market_tone] || ''}`}>
                  {intel.market_tone}
                </div>
                <div className="text-xs text-sub mt-1">Based on bullish vs bearish headlines</div>
              </div>
              <Stat
                label="Avg Confidence"
                value={`${intel.avg_confidence}%`}
                hint="Average signal reliability"
              />
              <div className="card">
                <div className="text-xs font-semibold text-sub uppercase tracking-wide">Sentiment Split</div>
                <div className="text-base font-bold text-ink mt-1 flex items-center gap-2 flex-wrap">
                  <span className="text-green-700">▲ {intel.by_sentiment.bullish}</span>
                  <span className="text-red-700">▼ {intel.by_sentiment.bearish}</span>
                  <span className="text-slate-700">● {intel.by_sentiment.neutral}</span>
                </div>
                <div className="text-xs text-sub mt-1">Bullish / Bearish / Neutral</div>
              </div>
              <div className="card">
                <div className="text-xs font-semibold text-sub uppercase tracking-wide">Top Mentioned</div>
                <div className="flex flex-wrap gap-1 mt-1">
                  {intel.top_tickers.length === 0
                    ? <span className="text-xs text-sub">No tickers extracted</span>
                    : intel.top_tickers.slice(0, 6).map(({ ticker: t, mentions }) => (
                      <button key={t}
                        onClick={() => { setTab('ticker'); setTicker(t); loadTicker(t) }}
                        className="text-xs font-mono font-bold bg-amber-100 border border-amber-300 text-amber-900 rounded px-1.5 py-0.5 hover:bg-amber-200">
                        ${t} <span className="text-sub">×{mentions}</span>
                      </button>
                    ))}
                </div>
                <div className="text-xs text-sub mt-1">Click to drill into a ticker</div>
              </div>
            </div>
          )}

          {/* ── Smart Money Spotlight ──────────────────────────────── */}
          {intel?.smart_money?.count > 0 && (() => {
            const allSpotlight = intel.smart_money.spotlight || []
            // Optional per-entity filter at the spotlight level.
            const filteredSpotlight = entityFilter
              ? allSpotlight.filter(a => a.smart_money?.entities?.some(e => e.name === entityFilter))
              : allSpotlight
            const visibleCount = expandSpotlight ? filteredSpotlight.length : Math.min(8, filteredSpotlight.length)
            const visible = filteredSpotlight.slice(0, visibleCount)
            return (
              <div className="card border-2 border-amber-300 bg-gradient-to-br from-amber-50/70 to-white">
                <div className="flex items-center gap-2 mb-2 flex-wrap">
                  <Crown size={18} className="text-amber-600" />
                  <h3 className="font-extrabold text-ink text-base">Smart Money Spotlight</h3>
                  <span className="text-xs text-amber-800 bg-amber-100 border border-amber-300 rounded-full px-2 py-0.5 font-bold">
                    {intel.smart_money.count} total signals
                  </span>
                  {entityFilter && (
                    <span className="text-xs text-amber-900 bg-amber-200 border border-amber-400 rounded-full px-2 py-0.5 font-bold flex items-center gap-1">
                      Filtering: {entityFilter}
                      <button onClick={() => setEntityFilter(null)}
                        title="Clear entity filter"
                        className="hover:text-red-700 font-extrabold">×</button>
                    </span>
                  )}
                  <button onClick={() => setSmartOnly(s => !s)}
                    className={`ml-auto text-xs font-bold px-2.5 py-1 rounded-lg border transition ${
                      smartOnly
                        ? 'bg-amber-500 text-white border-amber-600'
                        : 'bg-white text-amber-800 border-amber-300 hover:bg-amber-50'
                    }`}>
                    {smartOnly ? 'Showing Smart Money only ✓' : 'List below: Smart Money only'}
                  </button>
                </div>

                {/* Active Players — click to filter the spotlight + list */}
                {intel.smart_money.top_entities?.length > 0 && (
                  <div className="mb-3">
                    <div className="text-xs font-semibold text-sub uppercase mb-1.5">
                      Active Players ({intel.smart_money.top_entities.length}) — click to filter
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {intel.smart_money.top_entities.map(e => {
                        const cm = smCategoryMeta[e.category] || smCategoryMeta['Billionaire Investor']
                        const Icon = cm.Icon
                        const active = entityFilter === e.name
                        return (
                          <button key={e.name}
                            onClick={() => setEntityFilter(active ? null : e.name)}
                            className={`inline-flex items-center gap-1.5 rounded-lg border px-2 py-1 transition ${
                              active
                                ? 'bg-amber-500 border-amber-600 text-white shadow'
                                : `${cm.bg} hover:shadow-card-hover`
                            }`}>
                            <Icon size={12} className={active ? 'text-white' : cm.color} />
                            <span className={`text-xs font-bold ${active ? 'text-white' : 'text-ink'}`}>{e.name}</span>
                            <span className={`text-xs ${active ? 'text-white/80' : 'text-sub'}`}>×{e.count}</span>
                            {e.buys > 0  && <span className={`text-[10px] font-extrabold ${active ? 'text-white bg-green-700' : 'text-green-700 bg-green-100'} px-1 rounded`}>{e.buys}B</span>}
                            {e.sells > 0 && <span className={`text-[10px] font-extrabold ${active ? 'text-white bg-red-700'   : 'text-red-700   bg-red-100'}   px-1 rounded`}>{e.sells}S</span>}
                          </button>
                        )
                      })}
                    </div>
                  </div>
                )}

                {/* Spotlight article grid */}
                <div className="text-xs font-semibold text-sub uppercase mb-1.5">
                  Spotlight Signals — showing {visible.length} of {filteredSpotlight.length}
                </div>
                {filteredSpotlight.length === 0 ? (
                  <div className="text-center py-6 text-sub text-sm">
                    No spotlight items match this filter.
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-2">
                    {visible.map((a, i) => <SpotlightCard key={i} a={a} />)}
                  </div>
                )}

                {/* Expand / collapse */}
                {filteredSpotlight.length > 8 && (
                  <div className="mt-2 flex items-center justify-center">
                    <button onClick={() => setExpandSpotlight(s => !s)}
                      className="text-xs font-bold text-amber-800 hover:text-amber-900 flex items-center gap-1 bg-white border border-amber-300 rounded-lg px-3 py-1.5 hover:bg-amber-50">
                      {expandSpotlight
                        ? <><ChevronUp size={14} /> Show top 8</>
                        : <><ChevronDown size={14} /> Show all {filteredSpotlight.length} spotlight signals</>}
                    </button>
                  </div>
                )}

                <div className="text-xs text-sub mt-2 flex items-start gap-1.5">
                  <Info size={11} className="text-amber-600 mt-0.5 flex-shrink-0" />
                  <span>
                    Cards below with a <b className="text-amber-700">gold border</b> are smart-money flagged.
                    Click an <b>Active Player</b> chip to filter both the spotlight grid and the list below.
                  </span>
                </div>
              </div>
            )
          })()}

          {/* Filters */}
          <div className="card flex flex-wrap items-center gap-3">
            <div className="text-xs font-bold text-ink uppercase">Filters</div>
            <label className="text-xs font-semibold text-ink flex items-center gap-1.5">
              Event type
              <select value={eventFilter} onChange={e => setEventFilter(e.target.value)}
                className="text-xs border border-border rounded px-2 py-1 bg-white font-semibold text-ink">
                {eventOptions.map(o => <option key={o} value={o}>{o}</option>)}
              </select>
            </label>
            <label className="text-xs font-semibold text-ink flex items-center gap-2">
              Min confidence: <span className="font-mono font-bold text-primary">{minConf}%</span>
              <input type="range" min="0" max="90" step="10"
                value={minConf} onChange={e => setMinConf(+e.target.value)}
                className="accent-primary w-32" />
            </label>
            {(eventFilter !== 'All' || minConf > 0) && (
              <button onClick={() => { setEventFilter('All'); setMinConf(0) }}
                className="text-xs text-primary font-semibold hover:underline">
                Clear filters
              </button>
            )}
            {intel?.by_event && (
              <div className="ml-auto flex flex-wrap gap-1">
                {Object.entries(intel.by_event).slice(0, 8).map(([k, v]) => (
                  <button key={k}
                    onClick={() => setEventFilter(k)}
                    className={`text-xs rounded px-2 py-0.5 font-semibold border ${
                      eventFilter === k
                        ? 'bg-primary text-white border-primary'
                        : 'bg-white text-ink border-border hover:bg-surface'
                    }`}>
                    {k} <span className={eventFilter === k ? 'text-white/80' : 'text-sub'}>{v}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {loading && !intel && (
            <div className="text-ink text-sm flex items-center gap-2 p-3">
              <RefreshCw size={14} className="animate-spin text-primary" /> Aggregating multi-source intelligence…
            </div>
          )}

          <div className="space-y-2">
            {pageSlice.map((a, i) => <IntelligenceCard key={pageStart + i} a={a} />)}
            {intel && sourceList.length === 0 && (
              <div className="card text-center py-10">
                <AlertTriangle size={24} className="inline mb-2 text-amber-600" />
                <div className="text-ink font-semibold">No articles match the current filter.</div>
                <div className="text-sm text-sub mt-1">Try lowering the confidence or selecting <b>All</b> events.</div>
              </div>
            )}
          </div>

          <Pagination
            page={page} totalPages={totalPages} onPage={setPage}
            pageSize={pageSize} onPageSize={setPageSize} total={sourceList.length}
          />
        </>
      )}

      {/* ── MARKET FEED TAB ──────────────────────────────────────────── */}
      {tab === 'feed' && (
        <>
          {loading && feed.length === 0 && (
            <div className="text-ink text-sm flex items-center gap-2 p-3">
              <RefreshCw size={14} className="animate-spin text-primary" /> Fetching news…
            </div>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-2">
            {pageSlice.map((a, i) => <SimpleCard key={pageStart + i} a={a} />)}
          </div>
          {!loading && feed.length === 0 && (
            <div className="card text-center py-10 text-ink font-semibold">
              No articles. Try refreshing.
            </div>
          )}
          <Pagination
            page={page} totalPages={totalPages} onPage={setPage}
            pageSize={pageSize} onPageSize={setPageSize} total={sourceList.length}
          />
        </>
      )}

      {/* ── TICKER LOOKUP TAB ────────────────────────────────────────── */}
      {tab === 'ticker' && (
        <>
          <div className="card">
            <div className="flex items-center gap-2 flex-wrap">
              <Search size={14} className="text-primary" />
              <input
                type="text"
                value={ticker}
                onChange={e => setTicker(e.target.value.toUpperCase())}
                onKeyDown={e => { if (e.key === 'Enter') loadTicker(ticker) }}
                placeholder="Type a ticker — e.g. NVDA, AAPL, TSLA — then press Enter"
                className="flex-1 text-sm border border-border rounded px-2 py-1.5 font-mono text-ink font-semibold placeholder:text-sub placeholder:font-normal min-w-[240px]"
              />
              <button onClick={() => loadTicker(ticker)} disabled={loading || !ticker}
                className="btn-primary text-sm">
                <Sparkles size={14} /> Analyze
              </button>
            </div>
            <div className="text-xs text-sub mt-1.5">
              Pulls news from Yahoo Finance + Google News and scores each headline with the full Intelligence engine.
            </div>
          </div>

          {tickerData && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              <Stat label="Ticker" value={`$${tickerData.ticker}`} valueClass="font-mono" />
              <div className="card">
                <div className="text-xs font-semibold text-sub uppercase tracking-wide">Overall Tone</div>
                <div className={`text-xl font-extrabold mt-1 ${tickerData.tone === 'bullish' ? 'text-green-700' : tickerData.tone === 'bearish' ? 'text-red-700' : 'text-slate-700'}`}>
                  {tickerData.tone.toUpperCase()}
                </div>
                <div className="text-xs text-sub mt-1">From {tickerData.count} headlines</div>
              </div>
              <Stat label="Avg Opportunity" value={tickerData.avg_opportunity} hint="Higher = better edge (0-100)" />
              <div className="card">
                <div className="text-xs font-semibold text-sub uppercase tracking-wide">Bullish / Bearish</div>
                <div className="text-xl font-bold text-ink mt-1">
                  <span className="text-green-700">{tickerData.bullish_count}</span>
                  <span className="text-sub mx-1">/</span>
                  <span className="text-red-700">{tickerData.bearish_count}</span>
                </div>
                <div className="text-xs text-sub mt-1">Headline counts</div>
              </div>
            </div>
          )}

          {loading && (
            <div className="text-ink text-sm flex items-center gap-2 p-3">
              <RefreshCw size={14} className="animate-spin text-primary" /> Analyzing…
            </div>
          )}

          <div className="space-y-2">
            {pageSlice.map((a, i) => <IntelligenceCard key={pageStart + i} a={a} />)}
          </div>

          {tickerData && sourceList.length === 0 && (
            <div className="card text-center py-10">
              <AlertTriangle size={24} className="inline mb-2 text-amber-600" />
              <div className="text-ink font-semibold">No news found for ${tickerData.ticker}.</div>
              <div className="text-sm text-sub mt-1">Try another ticker.</div>
            </div>
          )}

          <Pagination
            page={page} totalPages={totalPages} onPage={setPage}
            pageSize={pageSize} onPageSize={setPageSize} total={sourceList.length}
          />
        </>
      )}
    </div>
  )
}
