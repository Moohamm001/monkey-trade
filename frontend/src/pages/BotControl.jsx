import React, { useState, useEffect, useRef, useCallback } from 'react'
import {
  Play, RefreshCw, RotateCcw, Brain, Activity, Zap,
  TrendingUp, TrendingDown, CheckCircle, XCircle,
  ChevronDown, ChevronUp, AlertTriangle, BookOpen, Bot,
  FileText, Globe, Layers
} from 'lucide-react'
import { useApi } from '../hooks/useApi'
import HelpBanner from '../components/HelpBanner'

// ── helpers ───────────────────────────────────────────────────────────────────
const pct  = v => v == null ? '—' : `${v >= 0 ? '+' : ''}${v}%`
const bar  = (v, max = 1) => `${Math.round(Math.min(1, v / max) * 100)}%`

const STAGE_COLOR = {
  accumulation: 'bg-blue-400',
  markup:       'bg-green-400',
  distribution: 'bg-amber-400',
  markdown:     'bg-red-400',
}

const STAGE_TEXT = {
  accumulation: 'text-blue-700',
  markup:       'text-green-700',
  distribution: 'text-amber-700',
  markdown:     'text-red-600',
}

// Smart Money Score: 0-100 institutional alignment score from the
// 6-source whale intel (insiders / 13D / dark pool / options / congress / COT).
function smsClass(s) {
  if (s == null) return null
  if (s >= 80) return { bg: 'bg-green-700',   text: 'text-white', label: 'EXT BULL' }
  if (s >= 65) return { bg: 'bg-green-500',   text: 'text-white', label: 'BULL'     }
  if (s >= 45) return { bg: 'bg-gray-200',    text: 'text-ink',   label: 'NEUTRAL'  }
  if (s >= 30) return { bg: 'bg-amber-400',   text: 'text-white', label: 'BEAR'     }
  return                { bg: 'bg-red-600',     text: 'text-white', label: 'EXT BEAR' }
}

function SmsChip({ score }) {
  if (score == null) return <span className="text-muted text-xs">—</span>
  const c = smsClass(score)
  return (
    <span title={`Smart Money Score: ${score}/100 — ${c.label}`}
      className={`inline-flex items-center gap-1 text-xs font-bold px-1.5 py-0.5 rounded ${c.bg} ${c.text}`}>
      🐋 {Math.round(score)}
    </span>
  )
}

function WinRateBar({ stage, data }) {
  const wr = data?.win_rate ?? (data?.win_rate === 0 ? 0 : null)
  const n  = data?.n ?? 0
  const pct_val = wr != null ? Math.round(wr * 100) : null
  return (
    <div>
      <div className="flex items-center justify-between text-xs mb-1">
        <span className={`font-semibold capitalize ${STAGE_TEXT[stage] || 'text-ink'}`}>{stage}</span>
        <div className="flex items-center gap-1.5">
          <span className="font-mono font-bold text-ink">{pct_val != null ? `${pct_val}%` : '—'}</span>
          <span className="text-muted">({n} trades)</span>
        </div>
      </div>
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${STAGE_COLOR[stage] || 'bg-gray-400'}`}
          style={{ width: pct_val != null ? `${pct_val}%` : '0%' }}
        />
      </div>
    </div>
  )
}

function SignalWeightRow({ name, data }) {
  const w = data?.weight ?? 0.5
  const n = data?.n ?? 0
  const trained = n > 0
  return (
    <div className="flex items-center gap-2 py-1 border-b border-border/40 last:border-0">
      <span className={`text-xs flex-1 truncate ${trained ? 'text-ink font-medium' : 'text-muted'}`}>{name}</span>
      <div className="w-20 h-1.5 bg-gray-100 rounded-full overflow-hidden flex-shrink-0">
        <div
          className={`h-full rounded-full ${w >= 0.60 ? 'bg-green-400' : w >= 0.50 ? 'bg-amber-300' : 'bg-red-300'}`}
          style={{ width: `${w * 100}%` }}
        />
      </div>
      <span className={`text-xs font-mono font-bold w-10 text-right ${w >= 0.60 ? 'text-green-600' : w >= 0.50 ? 'text-amber-600' : 'text-red-500'}`}>
        {Math.round(w * 100)}%
      </span>
      {trained && <span className="text-xs text-primary font-semibold w-12 text-right">×{n}</span>}
    </div>
  )
}

function LogLine({ line, idx }) {
  const isGood = line.includes('✓') || line.includes('DONE') || line.includes('Logged')
  const isBad  = line.includes('✗') || line.includes('SKIP') || line.includes('ERR')
  const isDone = line.includes('type":"done') || line.startsWith('🎯')
  return (
    <div className={`font-mono text-xs py-0.5 px-1 rounded ${
      isDone ? 'bg-green-50 text-green-800 font-bold' :
      isGood ? 'text-green-700' :
      isBad  ? 'text-muted' : 'text-ink'
    }`}>
      {line}
    </div>
  )
}

function ActivityEntry({ entry }) {
  const [open, setOpen] = useState(false)
  const isLearn  = entry.event === 'learned'
  const isScan   = entry.event === 'scan_complete'
  const isReview = entry.event === 'daily_review'

  const icon = isLearn ? <Brain size={12} /> : isScan ? <Play size={12} /> : isReview ? <RefreshCw size={12} /> : <Activity size={12} />
  const color = isLearn
    ? (entry.outcome === 'win' ? 'text-green-600' : 'text-red-500')
    : 'text-primary'

  return (
    <div className="border-b border-border/40 last:border-0 py-2 px-1">
      <div className="flex items-start gap-2 cursor-pointer" onClick={() => setOpen(v => !v)}>
        <span className={`mt-0.5 flex-shrink-0 ${color}`}>{icon}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`text-xs font-bold ${color}`}>
              {entry.event.replace('_', ' ').toUpperCase()}
            </span>
            {entry.ticker && <span className="text-xs font-mono text-ink">{entry.ticker}</span>}
            {entry.outcome && (
              <span className={`text-xs font-semibold px-1.5 py-0.5 rounded ${
                entry.outcome === 'win' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-600'
              }`}>{entry.outcome === 'win' ? '✓ WIN' : '✗ LOSS'}</span>
            )}
            {entry.pnl_pct != null && (
              <span className={`text-xs font-mono ${entry.pnl_pct >= 0 ? 'text-green-600' : 'text-red-500'}`}>
                {pct(entry.pnl_pct)}
              </span>
            )}
            {entry.trades_logged != null && (
              <span className="text-xs text-muted">{entry.trades_logged} trade{entry.trades_logged !== 1 ? 's' : ''} logged</span>
            )}
          </div>
          <p className="text-xs text-muted mt-0.5 truncate">{entry.note}</p>
        </div>
        <span className="text-xs text-muted flex-shrink-0">{entry.timestamp?.slice(11, 16)}</span>
        {open ? <ChevronUp size={11} className="text-muted flex-shrink-0 mt-1" />
               : <ChevronDown size={11} className="text-muted flex-shrink-0 mt-1" />}
      </div>
      {open && (
        <div className="mt-1.5 ml-5 text-xs text-sub bg-surface rounded p-2 leading-relaxed">
          {entry.note}
          {entry.tickers && <div className="mt-1 font-mono">Tickers: {entry.tickers.join(', ')}</div>}
          {entry.signals && entry.signals.length > 0 && (
            <div className="mt-1">Signals: {entry.signals.join(', ')}</div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function BotControl() {
  const [model, setModel]       = useState(null)
  const [activity, setActivity] = useState([])
  const [scanning, setScanning] = useState(false)
  const [reviewing, setReviewing] = useState(false)
  const [logLines, setLogLines] = useState([])
  const [tab, setTab]           = useState('model')
  const [scanMode, setScanMode] = useState('full')
  const [scanLogs, setScanLogs] = useState([])
  const [selectedLog, setSelectedLog] = useState(null)
  const [showResetConfirm, setShowResetConfirm] = useState(false)
  const { call, loading }       = useApi()
  const logRef = useRef(null)

  const loadData = useCallback(async () => {
    const [m, a, logs] = await Promise.all([
      call('/api/bot/model'),
      call('/api/bot/activity?limit=100'),
      call('/api/bot/scanlogs'),
    ])
    if (m)    setModel(m)
    if (a)    setActivity(a)
    if (logs) setScanLogs(logs)
  }, [call])

  const loadScanLog = useCallback(async (filename) => {
    const log = await call(`/api/bot/scanlogs/${filename}`)
    if (log) setSelectedLog(log)
  }, [call])

  useEffect(() => { loadData() }, [loadData])

  // Auto-scroll log
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [logLines])

  const runScan = async () => {
    setScanning(true)
    setLogLines([`🔍 Connecting to scanner (mode=${scanMode})…`])
    setTab('log')

    try {
      const resp = await fetch(`/api/bot/run-stream?mode=${scanMode}`)
      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop()

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const obj = JSON.parse(line.slice(6))
            if (obj.type === 'progress') {
              setLogLines(prev => [...prev, obj.msg])
            } else if (obj.type === 'done') {
              const n = obj.trades?.length ?? 0
              setLogLines(prev => [
                ...prev,
                `🎯 SCAN COMPLETE — ${n} trade${n !== 1 ? 's' : ''} logged`,
                ...(obj.trades || []).map(t => {
                  const sms = t.smart_money_score != null
                    ? ` 🐋SMS=${Math.round(t.smart_money_score)}`
                    : ''
                  return `  → ${t.ticker} [${t.stage}] entry=$${t.entry_price} score=${t.bot_score?.toFixed(3)}${sms}`
                }),
              ])
              await loadData()
            } else if (obj.type === 'error') {
              setLogLines(prev => [...prev, `❌ ERROR: ${obj.msg}`])
            }
          } catch (_) {}
        }
      }
    } catch (e) {
      setLogLines(prev => [...prev, `❌ Connection error: ${e.message}`])
    }

    setScanning(false)
  }

  const runDailyReview = async () => {
    setReviewing(true)
    const res = await call('/api/bot/daily-review', { method: 'POST' })
    setReviewing(false)
    if (res) {
      await loadData()
      const closed = res.closed_detail || []
      alert(
        `Daily Review Complete\n\n` +
        `Reviewed: ${res.reviewed} trades\n` +
        `Closed: ${res.closed} trades\n` +
        (closed.length > 0
          ? '\n' + closed.map(t => `${t.ticker}: ${t.status === 'closed_win' ? '✓' : '✗'} ${pct(t.pnl_pct)} (${t.exit_reason?.replace('_',' ')})`).join('\n')
          : '\nNo trades closed this review.')
      )
    }
  }

  const resetModel = async () => {
    await call('/api/bot/model/reset', { method: 'POST' })
    setShowResetConfirm(false)
    await loadData()
  }

  const TABS = [
    { id: 'model',    label: 'Model Brain',    icon: <Brain size={13} /> },
    { id: 'signals',  label: 'Signal Weights', icon: <Zap size={13} /> },
    { id: 'activity', label: 'Activity Log',   icon: <Activity size={13} /> },
    { id: 'log',      label: 'Scan Log',       icon: <Layers size={13} /> },
    { id: 'scanlogs', label: 'Scan History',   icon: <FileText size={13} /> },
  ]

  const stagePriors  = model?.stage_priors || {}
  const signalWeights = model?.signal_weights || {}
  const perfLog      = model?.performance_log || []

  return (
    <div className="p-3 space-y-3 max-w-4xl">

      <HelpBanner
        pageKey="bot"
        title="Autonomous Trading Bot"
        whatIsThis="A self-learning scanner that picks paper trades from your universe, executes them in the virtual portfolio, and adjusts its confidence based on outcomes."
        steps={[
          "Click <b>Run Scan</b> once to test it — see which tickers it would pick and why.",
          "Click <b>Start Bot</b> to let it scan continuously and place paper trades automatically.",
          "Watch the <b>Win Rate by Stage</b> bars — that's the bot learning which Wyckoff stages it's good at.",
        ]}
        tips={[
          "Let the bot accumulate <b>at least 50 closed trades</b> before trusting its win-rate stats.",
          "Smart Money Score chips show how well each pick aligns with insider/13D/dark pool flow.",
          "All trades are <b>paper</b> — they hit the virtual $10k portfolio, never real money.",
        ]}
      />

      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Bot size={20} className="text-primary" />
            <h1 className="text-lg font-bold text-ink">Autonomous Bot</h1>
          </div>
          <p className="text-xs text-muted mt-0.5">
            Scans the market, logs its own paper trades, and learns from every outcome
          </p>
        </div>
        <div className="flex gap-2 flex-wrap items-center">
          {/* Mode selector */}
          <div className="flex border border-border rounded-lg overflow-hidden text-xs">
            {[
              { id: 'quick', label: '⚡ Quick', sub: '~130', icon: <Zap size={11} /> },
              { id: 'full',  label: '🌐 Full',  sub: '~550', icon: <Globe size={11} /> },
            ].map(({ id, label, sub }) => (
              <button
                key={id}
                onClick={() => setScanMode(id)}
                disabled={scanning || reviewing}
                className={`px-3 py-1.5 font-medium transition-colors ${
                  scanMode === id
                    ? 'bg-primary text-white'
                    : 'bg-white text-sub hover:bg-surface'
                }`}
              >
                {label} <span className="opacity-60 text-xs">{sub}</span>
              </button>
            ))}
          </div>
          <button
            onClick={runDailyReview}
            disabled={reviewing || scanning}
            className="btn-ghost text-xs"
          >
            <RefreshCw size={13} className={reviewing ? 'animate-spin' : ''} />
            Daily Review
          </button>
          <button
            onClick={runScan}
            disabled={scanning || reviewing}
            className="btn-primary text-xs"
          >
            {scanning
              ? <><RefreshCw size={13} className="animate-spin" />Scanning…</>
              : <><Play size={13} />Run Scan</>
            }
          </button>
        </div>
      </div>

      {/* KPI strip */}
      {model && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          {[
            {
              label: 'Trades Learned',
              value: model.trades_learned_from,
              sub: `from ${model.total_scans} scans`,
              icon: <Brain size={14} />,
              color: 'text-primary',
            },
            {
              label: 'Score Threshold',
              value: model.min_score_threshold?.toFixed(2),
              sub: 'auto-adapts from results',
              icon: <Zap size={14} />,
              color: 'text-amber-600',
            },
            {
              label: 'Recent Win Rate',
              value: model.recent_win_rate != null ? `${model.recent_win_rate}%` : '—',
              sub: `last ${model.recent_n} closed`,
              icon: <Activity size={14} />,
              color: model.recent_win_rate >= 50 ? 'text-green-600' : 'text-red-500',
            },
            {
              label: 'Learning Rate α',
              value: model.alpha,
              sub: 'EMA weight per trade',
              icon: <BookOpen size={14} />,
              color: 'text-ink',
            },
            {
              label: 'Universe',
              value: scanMode === 'full' ? '~550' : '~130',
              sub: `${scanMode} mode selected`,
              icon: <Globe size={14} />,
              color: 'text-ink',
            },
          ].map(({ label, value, sub, icon, color }) => (
            <div key={label} className="bg-white border border-border rounded-xl p-3 shadow-sm">
              <div className="flex items-center gap-1.5 text-muted mb-1">{icon}<span className="text-xs font-bold uppercase tracking-wide">{label}</span></div>
              <div className={`text-xl font-extrabold font-mono ${color}`}>{value ?? '—'}</div>
              <div className="text-xs text-muted mt-0.5">{sub}</div>
            </div>
          ))}
        </div>
      )}

      {/* How it works callout */}
      <div className="bg-primary/5 border border-primary/20 rounded-xl p-4">
        <div className="flex items-center gap-2 mb-2">
          <Brain size={14} className="text-primary" />
          <span className="text-xs font-bold text-primary">How the Bot Learns</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-5 gap-2 text-xs text-sub">
          {[
            { step: '1', text: 'Full mode: ~550 tickers (full S&P 500 + ETFs + crypto + popular non-index). Quick mode: ~130 tickers. Batch pre-filters penny stocks and illiquid names first.' },
            { step: '2', text: 'Cycle scoring: stage win-rate × 30% + signal weight × 25% + confidence × 20% + volume × 5%' },
            { step: '3', text: 'Top candidates get 🐋 Smart Money Score (insiders + dark pool + options + congress + COT) added at × 20%' },
            { step: '4', text: 'Logs paper trades for top-scoring setups with quarter-Kelly position sizing (max 20% / 6 positions)' },
            { step: '5', text: 'Daily review: closes hits, runs EMA weight update (credit weighted by signal conviction)' },
          ].map(({ step, text }) => (
            <div key={step} className="flex gap-2">
              <span className="flex-shrink-0 w-5 h-5 bg-primary/20 text-primary text-xs font-bold rounded-full flex items-center justify-center">{step}</span>
              <span className="leading-relaxed">{text}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-0 border-b border-border overflow-x-auto">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`flex items-center gap-1.5 px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors whitespace-nowrap ${
              tab === t.id ? 'border-primary text-primary' : 'border-transparent text-sub hover:text-ink'
            }`}>
            {t.icon}{t.label}
            {t.id === 'activity' && activity.length > 0 && (
              <span className="ml-0.5 text-xs bg-primary/10 text-primary px-1.5 py-0.5 rounded-full">{activity.length}</span>
            )}
            {t.id === 'scanlogs' && scanLogs.length > 0 && (
              <span className="ml-0.5 text-xs bg-surface text-muted px-1.5 py-0.5 rounded-full">{scanLogs.length}</span>
            )}
          </button>
        ))}
      </div>

      {/* Tab: Model brain */}
      {tab === 'model' && (
        <div className="space-y-3">
          {/* Stage win rates */}
          <div className="bg-white border border-border rounded-xl p-4 shadow-sm">
            <div className="text-xs font-bold text-muted uppercase tracking-wide mb-2">Stage Win-Rate Priors (learned)</div>
            <div className="space-y-3">
              {Object.entries(stagePriors).map(([stage, data]) => (
                <WinRateBar key={stage} stage={stage} data={data} />
              ))}
            </div>
            <p className="text-xs text-muted mt-3 leading-relaxed">
              Starts at Wyckoff theory priors. Each closed paper trade updates the relevant stage via EMA (α={model?.alpha}).
              After enough trades, this reflects <em>your market's actual behaviour</em>, not just textbook theory.
            </p>
          </div>

          {/* Performance log */}
          {perfLog.length > 0 && (
            <div className="bg-white border border-border rounded-xl p-4 shadow-sm">
              <div className="text-xs font-bold text-muted uppercase tracking-wide mb-3">
                Recent Closed Trades (model training data)
              </div>
              <div className="space-y-1 max-h-48 overflow-y-auto">
                {[...perfLog].reverse().map((p, i) => (
                  <div key={i} className="flex items-center gap-3 text-xs py-0.5 border-b border-border/40 last:border-0">
                    <span className="text-muted w-20 flex-shrink-0">{p.date}</span>
                    <span className="font-semibold text-ink w-14">{p.ticker}</span>
                    <span className={`text-xs px-1.5 py-0.5 rounded capitalize ${STAGE_TEXT[p.stage] || 'text-sub'}`}>{p.stage || '—'}</span>
                    <span className={`ml-auto font-mono font-bold ${p.outcome === 'win' ? 'text-green-600' : 'text-red-500'}`}>
                      {p.outcome === 'win' ? '✓' : '✗'} {pct(p.pnl_pct)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Reset */}
          <div className="flex justify-end">
            {!showResetConfirm
              ? <button className="btn-danger text-xs" onClick={() => setShowResetConfirm(true)}><RotateCcw size={13} />Reset Model</button>
              : (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-red-600 font-semibold">Reset to initial priors?</span>
                  <button className="btn-danger text-xs" onClick={resetModel}>Yes, reset</button>
                  <button className="btn-ghost text-xs" onClick={() => setShowResetConfirm(false)}>Cancel</button>
                </div>
              )
            }
          </div>
        </div>
      )}

      {/* Tab: Signal weights */}
      {tab === 'signals' && (
        <div className="bg-white border border-border rounded-xl p-4 shadow-sm">
          <div className="text-xs font-bold text-muted uppercase tracking-wide mb-3">
            Signal Predictive Weights (learned)
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6">
            {Object.entries(signalWeights)
              .sort((a, b) => b[1].weight - a[1].weight)
              .map(([name, data]) => (
                <SignalWeightRow key={name} name={name} data={data} />
              ))
            }
          </div>
          <p className="text-xs text-muted mt-4 leading-relaxed">
            Bar = win rate for trades where this signal was present.
            Green ≥ 60%, Amber 50–60%, Red &lt; 50%.
            Bold count = times learned from real outcomes.
            Initially set from published IC research; updated from your actual paper trade results.
          </p>
        </div>
      )}

      {/* Tab: Activity log */}
      {tab === 'activity' && (
        <div className="bg-white border border-border rounded-xl p-4 shadow-sm">
          <div className="text-xs font-bold text-muted uppercase tracking-wide mb-3">Bot Activity Log</div>
          {activity.length === 0
            ? <p className="text-sm text-muted text-center py-6">No activity yet. Run a scan to start.</p>
            : (
              <div className="max-h-[500px] overflow-y-auto">
                {activity.map((entry, i) => <ActivityEntry key={i} entry={entry} />)}
              </div>
            )
          }
        </div>
      )}

      {/* Tab: Scan log (live terminal) */}
      {tab === 'log' && (
        <div className="bg-gray-900 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${scanning ? 'bg-green-400 animate-pulse' : 'bg-gray-500'}`} />
              <span className="text-xs font-bold text-gray-300 uppercase tracking-wide">
                {scanning ? `Live Scan — ${scanMode} mode` : 'Last Scan Output'}
              </span>
            </div>
            {!scanning && logLines.length > 0 && (
              <button onClick={() => setLogLines([])} className="text-xs text-gray-500 hover:text-gray-300">Clear</button>
            )}
          </div>
          <div ref={logRef} className="h-[500px] overflow-y-auto space-y-0.5 font-mono text-xs">
            {logLines.length === 0
              ? <div className="text-gray-500 text-center py-10">Press "Run Scan" to start the scanner.</div>
              : logLines.map((line, i) => <LogLine key={i} line={line} idx={i} />)
            }
            {scanning && <div className="text-green-400 animate-pulse">▋</div>}
          </div>
        </div>
      )}

      {/* Tab: Scan History */}
      {tab === 'scanlogs' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Log list */}
          <div className="bg-white border border-border rounded-xl p-4 shadow-sm">
            <div className="text-xs font-bold text-muted uppercase tracking-wide mb-3">
              Scan Logs ({scanLogs.length})
            </div>
            {scanLogs.length === 0
              ? <p className="text-sm text-muted text-center py-6">No scan logs yet. Run a scan first.</p>
              : (
                <div className="space-y-1 max-h-[500px] overflow-y-auto">
                  {scanLogs.map(fname => {
                    const parts = fname.replace('.json','').split('_')
                    const d = parts[0], t = parts[1] || ''
                    const label = `${d.slice(0,4)}-${d.slice(4,6)}-${d.slice(6,8)} ${t.slice(0,2)}:${t.slice(2,4)}`
                    const isSelected = selectedLog?.scan_id === fname.replace('.json','')
                    return (
                      <button
                        key={fname}
                        onClick={() => loadScanLog(fname)}
                        className={`w-full text-left px-3 py-2 rounded-lg text-xs font-mono transition-colors ${
                          isSelected ? 'bg-primary/10 text-primary font-bold' : 'hover:bg-surface text-ink'
                        }`}
                      >
                        {label}
                      </button>
                    )
                  })}
                </div>
              )
            }
          </div>

          {/* Log detail */}
          <div className="lg:col-span-2 bg-white border border-border rounded-xl p-4 shadow-sm">
            {!selectedLog
              ? <p className="text-sm text-muted text-center py-10">Select a scan log to view details.</p>
              : (
                <div className="space-y-3">
                  {/* Summary */}
                  <div className="flex items-center gap-3 flex-wrap">
                    <span className="text-xs font-bold text-muted uppercase tracking-wide">
                      {selectedLog.scan_id}
                    </span>
                    <span className={`text-xs px-2 py-0.5 rounded font-semibold ${
                      selectedLog.mode === 'full' ? 'bg-primary/10 text-primary' : 'bg-amber-100 text-amber-700'
                    }`}>
                      {selectedLog.mode} universe ({selectedLog.universe_size})
                    </span>
                  </div>
                  <div className="grid grid-cols-4 gap-2 text-center">
                    {[
                      { l: 'Scanned',    v: selectedLog.scanned },
                      { l: 'Dropped',    v: selectedLog.prefiltered_out },
                      { l: 'Candidates', v: selectedLog.candidates },
                      { l: 'Logged',     v: selectedLog.logged },
                    ].map(({ l, v }) => (
                      <div key={l} className="bg-surface rounded-lg p-2">
                        <div className="text-xs text-muted">{l}</div>
                        <div className="font-bold text-ink font-mono">{v ?? '—'}</div>
                      </div>
                    ))}
                  </div>

                  {selectedLog.top_picks?.length > 0 && (
                    <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                      <div className="text-xs font-bold text-green-800 mb-2">Logged Trades</div>
                      {selectedLog.top_picks.map((p, i) => (
                        <div key={i} className="flex items-center gap-3 text-xs py-1">
                          <span className="font-bold text-ink w-14">{p.ticker}</span>
                          <span className="text-sub capitalize">{p.stage}</span>
                          <div className="ml-auto flex items-center gap-2">
                            <SmsChip score={p.smart_money_score} />
                            <span className="font-mono font-bold text-primary">score={p.score}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Full result table */}
                  <div>
                    <div className="text-xs font-bold text-muted uppercase tracking-wide mb-2">
                      All Ticker Decisions ({selectedLog.results?.length ?? 0})
                    </div>
                    <div className="max-h-64 overflow-y-auto border border-border/60 rounded-lg">
                      <table className="w-full text-xs">
                        <thead className="sticky top-0 bg-surface">
                          <tr>
                            {['Ticker','Decision','Stage','Score','SMS','Signals','Reason'].map(h => (
                              <th key={h} className="th text-left px-2 py-1.5">{h}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {(selectedLog.results || []).map((r, i) => (
                            <tr key={i} className={`border-b border-border/40 last:border-0 ${
                              r.decision === 'candidate' ? 'bg-green-50' :
                              r.decision === 'error'     ? 'bg-red-50' : ''
                            }`}>
                              <td className="td font-mono font-bold px-2 py-1">{r.ticker}</td>
                              <td className="td px-2 py-1">
                                <span className={`px-1.5 py-0.5 rounded text-xs font-semibold ${
                                  r.decision === 'candidate'                  ? 'bg-green-100 text-green-800' :
                                  r.decision === 'below_threshold'            ? 'bg-surface text-muted' :
                                  r.decision === 'below_threshold_after_sms'  ? 'bg-amber-50 text-amber-700' :
                                  r.decision === 'error'                      ? 'bg-red-100 text-red-700' :
                                                                                'bg-gray-100 text-gray-600'
                                }`}>{r.decision}</span>
                              </td>
                              <td className="td px-2 py-1 capitalize text-muted">{r.stage || '—'}</td>
                              <td className="td px-2 py-1 font-mono">{r.score ?? '—'}</td>
                              <td className="td px-2 py-1"><SmsChip score={r.smart_money_score} /></td>
                              <td className="td px-2 py-1 text-primary">{r.signals?.slice(0,2).join(', ') || '—'}</td>
                              <td className="td px-2 py-1 text-muted text-xs truncate max-w-[140px]">{r.reason || '—'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              )
            }
          </div>
        </div>
      )}
    </div>
  )
}
