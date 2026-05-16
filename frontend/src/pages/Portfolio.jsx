import { useEffect, useState, useCallback } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from 'recharts'
import {
  DollarSign, TrendingUp, TrendingDown, Activity,
  RefreshCw, RotateCcw, Layers, Award, AlertCircle,
} from 'lucide-react'

const API = 'http://localhost:8000'

const fmt  = (n, d = 2) => (n == null ? '—' : Number(n).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d }))
const fmtD = (n) => n == null ? '—' : `$${fmt(n)}`
const fmtP = (n) => n == null ? '—' : `${n >= 0 ? '+' : ''}${fmt(n)}%`

const STAGE_COLOR = {
  accumulation: 'bg-blue-100 text-blue-800',
  markup:       'bg-green-100 text-green-800',
  distribution: 'bg-orange-100 text-orange-800',
  markdown:     'bg-red-100 text-red-800',
}

function KPI({ icon: Icon, label, value, sub, color = 'text-ink' }) {
  return (
    <div className="bg-white border border-border rounded-xl p-3 flex flex-col gap-0.5 shadow-sm">
      <div className="flex items-center gap-1.5 text-muted text-xs">
        <Icon size={12} />{label}
      </div>
      <div className={`text-lg font-bold ${color}`}>{value}</div>
      {sub && <div className="text-xs text-muted">{sub}</div>}
    </div>
  )
}

function EquityCurve({ curve, initial }) {
  if (!curve || curve.length === 0) return null

  const data = curve.map(p => ({
    date:  p.date.slice(5),   // MM-DD
    equity: p.equity,
    cash:   p.cash,
    positions_value: p.positions_value,
  }))

  const last = data[data.length - 1]?.equity ?? initial
  const color = last >= initial ? '#22c55e' : '#ef4444'

  return (
    <div className="bg-white border border-border rounded-xl p-5 shadow-sm">
      <div className="flex items-center justify-between mb-2">
        <div className="text-sm font-semibold text-ink flex items-center gap-2">
          <Activity size={15} className="text-primary" />
          Equity Curve
        </div>
        <div className="text-xs text-muted">
          Started ${fmt(initial)} → Current ${fmt(last)}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="date" tick={{ fontSize: 11 }} />
          <YAxis domain={['auto', 'auto']} tick={{ fontSize: 11 }}
            tickFormatter={v => `$${(v / 1000).toFixed(1)}k`} />
          <Tooltip formatter={(v) => [`$${fmt(v)}`, '']} />
          <ReferenceLine y={initial} stroke="#94a3b8" strokeDasharray="4 4" label={{ value: 'Start', position: 'insideLeft', fontSize: 10 }} />
          <Line type="monotone" dataKey="equity" stroke={color} strokeWidth={2} dot={false} name="Equity" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

function PositionRow({ pos }) {
  const stageClass = STAGE_COLOR[pos.stage] || 'bg-gray-100 text-gray-700'
  return (
    <tr className="border-t border-border hover:bg-surface transition-colors">
      <td className="px-4 py-3 font-bold text-ink">{pos.ticker}</td>
      <td className="px-4 py-3">
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${stageClass}`}>
          {pos.stage}
        </span>
      </td>
      <td className="px-4 py-3 text-sm capitalize text-muted">{pos.direction}</td>
      <td className="px-4 py-3 text-sm">${fmt(pos.entry_price)}</td>
      <td className="px-4 py-3 text-sm">{fmt(pos.shares, 4)}</td>
      <td className="px-4 py-3 text-sm font-medium text-primary">{fmtD(pos.cost_basis)}</td>
    </tr>
  )
}

function TradeRow({ t }) {
  const win = t.outcome === 'win'
  return (
    <tr className="border-t border-border hover:bg-surface transition-colors">
      <td className="px-4 py-3 font-bold text-ink">{t.ticker}</td>
      <td className="px-4 py-3 text-sm capitalize text-muted">{t.direction}</td>
      <td className="px-4 py-3 text-sm">${fmt(t.entry_price)}</td>
      <td className="px-4 py-3 text-sm">${fmt(t.exit_price)}</td>
      <td className={`px-4 py-3 text-sm font-bold ${win ? 'text-green-600' : 'text-red-500'}`}>
        {win ? '+' : ''}{fmtD(t.pnl_dollar)}
      </td>
      <td className={`px-4 py-3 text-sm font-bold ${win ? 'text-green-600' : 'text-red-500'}`}>
        {fmtP(t.pnl_pct)}
      </td>
      <td className="px-4 py-3">
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${win ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
          {t.outcome}
        </span>
      </td>
      <td className="px-4 py-3 text-xs text-muted">{t.closed_at?.slice(0, 10)}</td>
    </tr>
  )
}

export default function Portfolio() {
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [tab, setTab] = useState('overview')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const r = await fetch(`${API}/api/portfolio/`)
      setSummary(await r.json())
    } catch { /* backend not running */ }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const handleReset = async () => {
    if (!window.confirm('Reset portfolio to $10,000? This cannot be undone.')) return
    setResetting(true)
    await fetch(`${API}/api/portfolio/reset`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ balance: 10000 }) })
    await load()
    setResetting(false)
  }

  if (!summary && loading) {
    return <div className="p-8 text-muted text-sm animate-pulse">Loading portfolio…</div>
  }

  if (!summary) {
    return <div className="p-8 text-muted text-sm">Backend not reachable. Start the FastAPI server.</div>
  }

  const { initial_balance, cash, equity, positions_value, total_return_pct, stats, equity_curve, open_positions, recent_trades } = summary
  const isUp = (equity ?? initial_balance) >= initial_balance

  const TABS = ['overview', 'positions', 'history']

  return (
    <div className="p-3 space-y-3">

      <HelpBanner
        pageKey="portfolio"
        title="Virtual Portfolio — $10k Paper Account"
        whatIsThis="A self-managing $10,000 virtual account. The bot allocates capital using quarter-Kelly sizing (capped 20%/trade), opens & closes positions automatically, and tracks the equity curve."
        steps={[
          "View the <b>equity curve</b> on the Overview tab — see the running P&L.",
          "Open <b>Positions</b> tab to see what the bot currently holds with unrealized P&L.",
          "Open <b>History</b> tab to review closed trades, win/loss, and learning outcomes.",
        ]}
        tips={[
          "Each trade is <b>capped at 20% of equity</b> via quarter-Kelly — preserves the account through losing streaks.",
          "All trades are <b>paper</b> — no real money. Use it to test strategy before going live.",
          "The bot logs <i>why</i> it opened each trade — read those reasons to learn its decision process.",
        ]}
      />

      {/* Header */}
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-sm font-bold text-ink flex items-center gap-1.5">
          <DollarSign size={15} className="text-primary" /> Virtual Portfolio
        </span>
        <span className="text-xs text-muted">$10k auto paper trading — bot allocates &amp; closes positions automatically</span>
        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={load}
            disabled={loading}
            className="flex items-center gap-1.5 text-xs text-muted hover:text-ink border border-border px-3 py-1.5 rounded-lg hover:bg-surface transition-colors"
          >
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
          <button
            onClick={handleReset}
            disabled={resetting}
            className="flex items-center gap-1.5 text-xs text-red-600 hover:text-red-700 border border-red-200 hover:border-red-300 px-3 py-1.5 rounded-lg hover:bg-red-50 transition-colors"
          >
            <RotateCcw size={12} /> Reset to $10k
          </button>
        </div>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <KPI
          icon={DollarSign}
          label="Total Equity"
          value={fmtD(equity)}
          sub={`Started ${fmtD(initial_balance)}`}
          color={isUp ? 'text-green-600' : 'text-red-500'}
        />
        <KPI
          icon={isUp ? TrendingUp : TrendingDown}
          label="Total Return"
          value={fmtP(total_return_pct)}
          sub={`P&L ${fmtD(stats?.total_pnl_dollar)}`}
          color={isUp ? 'text-green-600' : 'text-red-500'}
        />
        <KPI
          icon={Layers}
          label="Cash Available"
          value={fmtD(cash)}
          sub={`${open_positions?.length ?? 0} open positions`}
        />
        <KPI
          icon={Award}
          label="Win Rate"
          value={stats?.total_trades ? `${Math.round(stats.wins / stats.total_trades * 100)}%` : '—'}
          sub={`${stats?.wins ?? 0}W / ${stats?.losses ?? 0}L · ${stats?.total_trades ?? 0} trades`}
        />
      </div>

      {/* Equity curve (always visible) */}
      <EquityCurve curve={equity_curve} initial={initial_balance} />

      {/* Tabs */}
      <div className="flex gap-1 border-b border-border pb-0">
        {TABS.map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium capitalize transition-colors border-b-2 -mb-px ${
              tab === t
                ? 'border-primary text-primary'
                : 'border-transparent text-muted hover:text-ink'
            }`}
          >
            {t === 'positions' ? `Open (${open_positions?.length ?? 0})` : t}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === 'overview' && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <StatCard label="Best Trade" value={fmtP(stats?.best_trade_pct)} color="text-green-600" />
          <StatCard label="Worst Trade" value={fmtP(stats?.worst_trade_pct)} color="text-red-500" />
          <StatCard label="Positions Value" value={fmtD(positions_value)} />
          <div className="sm:col-span-3 bg-blue-50 border border-blue-200 rounded-xl p-4 flex items-start gap-3 text-sm text-blue-800">
            <AlertCircle size={16} className="mt-0.5 flex-shrink-0" />
            <div>
              <strong>Fully Automated:</strong> The bot opens positions during scans using quarter-Kelly sizing (capped at 20% of cash per trade,
              max 6 concurrent positions). Positions close automatically on stop-loss or target during daily review.
              Run a scan in <strong>Auto Bot</strong>, then <strong>Daily Review</strong> to process closes.
            </div>
          </div>
        </div>
      )}

      {tab === 'positions' && (
        <div className="bg-white border border-border rounded-xl overflow-hidden shadow-sm">
          {(!open_positions || open_positions.length === 0) ? (
            <div className="p-8 text-center text-muted text-sm">No open positions. Run a bot scan to open trades.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-surface text-xs text-muted uppercase tracking-wide">
                  <tr>
                    {['Ticker', 'Stage', 'Direction', 'Entry', 'Shares', 'Allocated'].map(h => (
                      <th key={h} className="px-4 py-3 text-left font-semibold">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {open_positions.map(pos => <PositionRow key={pos.trade_id} pos={pos} />)}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {tab === 'history' && (
        <div className="bg-white border border-border rounded-xl overflow-hidden shadow-sm">
          {(!recent_trades || recent_trades.length === 0) ? (
            <div className="p-8 text-center text-muted text-sm">No closed trades yet.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-surface text-xs text-muted uppercase tracking-wide">
                  <tr>
                    {['Ticker', 'Dir', 'Entry', 'Exit', 'P&L $', 'P&L %', 'Result', 'Closed'].map(h => (
                      <th key={h} className="px-4 py-3 text-left font-semibold">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {recent_trades.map((t, i) => <TradeRow key={i} t={t} />)}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function StatCard({ label, value, color = 'text-ink' }) {
  return (
    <div className="bg-white border border-border rounded-xl p-4 shadow-sm">
      <div className="text-xs text-muted mb-1">{label}</div>
      <div className={`text-lg font-bold ${color}`}>{value ?? '—'}</div>
    </div>
  )
}
