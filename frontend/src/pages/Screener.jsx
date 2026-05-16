import React, { useState, useMemo } from 'react'
import { Filter, Play, ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react'
import { useApi } from '../hooks/useApi'
import StageBadge from '../components/StageBadge'

// ─── helpers ────────────────────────────────────────────────────────────────
const fmt = (n, prefix = '') => {
  if (n == null) return '—'
  if (Math.abs(n) >= 1e12) return `${prefix}${(n/1e12).toFixed(1)}T`
  if (Math.abs(n) >= 1e9)  return `${prefix}${(n/1e9).toFixed(1)}B`
  if (Math.abs(n) >= 1e6)  return `${prefix}${(n/1e6).toFixed(1)}M`
  return `${prefix}${n.toFixed(2)}`
}
const pct = n => n != null ? `${(n*100).toFixed(1)}%` : '—'

// ─── stage filter buttons ────────────────────────────────────────────────────
const STAGE_CONFIG = [
  { key: 'accumulation', label: 'Accumulation', dot: 'bg-blue-500',
    active: 'bg-blue-50 border-blue-400 text-blue-700',
    idle:   'bg-white border-border text-sub hover:border-blue-300 hover:text-blue-600' },
  { key: 'markup',       label: 'Markup',       dot: 'bg-green-500',
    active: 'bg-green-50 border-green-400 text-green-700',
    idle:   'bg-white border-border text-sub hover:border-green-300 hover:text-green-600' },
  { key: 'distribution', label: 'Distribution', dot: 'bg-amber-400',
    active: 'bg-amber-50 border-amber-400 text-amber-700',
    idle:   'bg-white border-border text-sub hover:border-amber-300 hover:text-amber-600' },
  { key: 'markdown',     label: 'Markdown',     dot: 'bg-red-500',
    active: 'bg-red-50 border-red-400 text-red-700',
    idle:   'bg-white border-border text-sub hover:border-red-300 hover:text-red-600' },
]

// ─── sortable column definitions ─────────────────────────────────────────────
const COLS = [
  { key: 'symbol',          label: 'Ticker',       sortFn: r => r.symbol },
  { key: 'name',            label: 'Name',         sortFn: r => r.name },
  { key: 'sector',          label: 'Sector',       sortFn: r => r.sector },
  { key: 'price',           label: 'Price',        sortFn: r => r.price ?? -Infinity },
  { key: 'market_cap',      label: 'Mkt Cap',      sortFn: r => r.market_cap ?? -Infinity },
  { key: 'pe_ratio',        label: 'P/E',          sortFn: r => r.pe_ratio ?? -Infinity },
  { key: 'revenue_growth',  label: 'Rev Growth',   sortFn: r => r.revenue_growth ?? -Infinity },
  { key: 'earnings_growth', label: 'Earn Growth',  sortFn: r => r.earnings_growth ?? -Infinity },
  { key: 'net_margins',     label: 'Net Margin',   sortFn: r => r.net_margins ?? -Infinity },
  { key: 'cycle_confidence',label: 'Cycle',        sortFn: r => r.cycle_confidence ?? -Infinity },
]

const SortIcon = ({ col, sortKey, sortDir }) => {
  if (sortKey !== col) return <ChevronsUpDown size={12} className="text-muted opacity-50" />
  return sortDir === 'asc'
    ? <ChevronUp size={12} className="text-primary" />
    : <ChevronDown size={12} className="text-primary" />
}

// ─── component ───────────────────────────────────────────────────────────────
export default function Screener() {
  const [universe, setUniverse] = useState('top100')
  const [filters, setFilters] = useState({
    min_revenue_growth: '', min_earnings_growth: '',
    max_pe: '', min_net_margin: '',
    cycle_stages: [], tickers: '',
  })
  const [results, setResults]   = useState([])
  const [ran, setRan]           = useState(false)
  const [sortKey, setSortKey]   = useState('cycle_confidence')
  const [sortDir, setSortDir]   = useState('desc')
  const { call, loading }       = useApi()

  const setF = (k, v) => setFilters(f => ({ ...f, [k]: v }))

  const toggleStage = s => setFilters(f => ({
    ...f,
    cycle_stages: f.cycle_stages.includes(s)
      ? f.cycle_stages.filter(x => x !== s)
      : [...f.cycle_stages, s],
  }))

  const handleSort = col => {
    if (sortKey === col) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(col); setSortDir('desc') }
  }

  const sorted = useMemo(() => {
    const colDef = COLS.find(c => c.key === sortKey)
    if (!colDef) return results
    return [...results].sort((a, b) => {
      const va = colDef.sortFn(a)
      const vb = colDef.sortFn(b)
      if (typeof va === 'string') return sortDir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va)
      return sortDir === 'asc' ? va - vb : vb - va
    })
  }, [results, sortKey, sortDir])

  const run = async () => {
    const payload = {
      universe,
      tickers:              filters.tickers ? filters.tickers.split(',').map(t => t.trim().toUpperCase()).filter(Boolean) : null,
      min_revenue_growth:   filters.min_revenue_growth  ? +filters.min_revenue_growth  : null,
      min_earnings_growth:  filters.min_earnings_growth ? +filters.min_earnings_growth : null,
      max_pe:               filters.max_pe               ? +filters.max_pe               : null,
      min_net_margin:       filters.min_net_margin       ? +filters.min_net_margin       : null,
      cycle_stages:         filters.cycle_stages.length  ? filters.cycle_stages          : null,
    }
    const data = await call('/api/screener/run', { method: 'POST', body: JSON.stringify(payload) })
    if (data) { setResults(data); setRan(true) }
  }

  const UNIVERSE_OPTS = [
    { v: 'top100', label: '⚡ Top 100',        sub: 'fast ~30s' },
    { v: 'sp500',  label: '📊 Full S&P 500',   sub: '~5-10 min' },
    { v: 'custom', label: '✏️ Custom tickers', sub: '' },
  ]

  return (
    <div className="p-3 space-y-3">
      {/* ── Filter panel ── */}
      <div className="card space-y-2.5">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-2 text-sm font-semibold text-ink">
            <Filter size={13} className="text-primary" /> Stock Screener
            <span className="text-xs font-normal text-muted">— filter by fundamentals + cycle stage</span>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={run} disabled={loading} className="btn-primary text-xs flex items-center gap-1.5">
              <Play size={12} />
              {loading
                ? `Scanning ${universe === 'sp500' ? 'S&P 500' : universe === 'top100' ? 'Top 100' : 'custom'}…`
                : 'Run Screener'}
            </button>
            {loading && <span className="text-xs text-muted">{universe === 'sp500' ? '5–10 min' : '~30s'}</span>}
          </div>
        </div>

        {/* Universe selector */}
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-xs text-muted font-medium flex-shrink-0">Universe:</span>
          <div className="flex gap-1.5 flex-wrap">
            {UNIVERSE_OPTS.map(({ v, label, sub }) => (
              <button key={v} onClick={() => setUniverse(v)}
                className={`px-2.5 py-1 rounded-lg border text-xs font-medium transition-colors ${
                  universe === v
                    ? 'bg-primary text-white border-primary shadow-sm'
                    : 'bg-white border-border text-sub hover:border-primary/40 hover:text-primary'
                }`}>
                {label}
                {sub && <span className={`ml-1 font-normal ${universe === v ? 'opacity-70' : 'text-muted'}`}>{sub}</span>}
              </button>
            ))}
          </div>
          {universe === 'custom' && (
            <input className="input flex-1 min-w-[200px]" placeholder="AAPL, NVDA, TSLA, MSFT …"
              value={filters.tickers} onChange={e => setF('tickers', e.target.value)} />
          )}
        </div>

        {/* Fundamental filters inline */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-muted font-medium flex-shrink-0">Filters:</span>
          {[
            { key: 'min_revenue_growth',  label: 'Rev Growth ≥ %', ph: '10' },
            { key: 'min_earnings_growth', label: 'Earn Growth ≥ %', ph: '5' },
            { key: 'max_pe',              label: 'P/E ≤',           ph: '40' },
            { key: 'min_net_margin',      label: 'Margin ≥ %',      ph: '5' },
          ].map(({ key, label, ph }) => (
            <label key={key} className="flex items-center gap-1">
              <span className="text-xs text-muted whitespace-nowrap">{label}</span>
              <input className="input w-16 text-xs" placeholder={ph}
                value={filters[key]} onChange={e => setF(key, e.target.value)} />
            </label>
          ))}
        </div>

        {/* Stage filter */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-muted font-medium flex-shrink-0">Stage:</span>
          {STAGE_CONFIG.map(({ key, label, dot, active, idle }) => {
            const on = filters.cycle_stages.includes(key)
            return (
              <button key={key} onClick={() => toggleStage(key)}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs font-semibold transition-all ${on ? active : idle}`}>
                <span className={`w-2 h-2 rounded-full ${dot}`} />
                {label}
              </button>
            )
          })}
        </div>
      </div>

      {/* ── Results table ── */}
      {ran && (
        <div className="card p-0 overflow-hidden">
          <div className="flex items-center justify-between px-3 py-2 border-b border-border">
            <span className="text-sm font-semibold text-ink">{results.length} stocks matched</span>
            <span className="text-xs text-muted">Click column to sort</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-surface">
                <tr>
                  {COLS.map(col => (
                    <th key={col.key}
                      onClick={() => handleSort(col.key)}
                      className="th cursor-pointer select-none hover:text-primary transition-colors">
                      <div className="flex items-center gap-1">
                        {col.label}
                        <SortIcon col={col.key} sortKey={sortKey} sortDir={sortDir} />
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sorted.map(r => (
                  <tr key={r.symbol} className="hover:bg-primary-light/40 transition-colors">
                    <td className="td font-bold text-primary">{r.symbol}</td>
                    <td className="td text-ink max-w-[160px] truncate">{r.name}</td>
                    <td className="td text-xs text-muted">{r.sector || '—'}</td>
                    <td className="td font-mono">{r.price?.toFixed(2) ?? '—'}</td>
                    <td className="td font-mono text-sub">{fmt(r.market_cap, '$')}</td>
                    <td className="td font-mono">{r.pe_ratio?.toFixed(1) ?? '—'}</td>
                    <td className={`td font-mono font-semibold ${r.revenue_growth > 0 ? 'text-green-600' : r.revenue_growth < 0 ? 'text-red-500' : 'text-sub'}`}>
                      {pct(r.revenue_growth)}
                    </td>
                    <td className={`td font-mono font-semibold ${r.earnings_growth > 0 ? 'text-green-600' : r.earnings_growth < 0 ? 'text-red-500' : 'text-sub'}`}>
                      {pct(r.earnings_growth)}
                    </td>
                    <td className="td font-mono text-sub">{pct(r.net_margins)}</td>
                    <td className="td">
                      {r.cycle_stage
                        ? <StageBadge stage={r.cycle_stage} confidence={r.cycle_confidence} />
                        : <span className="text-muted">—</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {results.length === 0 && (
              <div className="py-10 text-center text-muted text-sm">
                No stocks matched your filters
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
