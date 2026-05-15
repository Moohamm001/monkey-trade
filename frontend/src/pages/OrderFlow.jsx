import React, { useState, useCallback, useEffect } from 'react'
import {
  Activity, Play, Square, RefreshCw, CheckCircle, XCircle,
  AlertTriangle, Shield, Zap, Brain, BarChart2,
} from 'lucide-react'
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis,
  Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import { useApi } from '../hooks/useApi'

// ── helpers ───────────────────────────────────────────────────────────────────
const fmt = v => v == null ? '—' : typeof v === 'number' ? v.toLocaleString() : v
const fmtPct = v => v == null ? '—' : `${v > 0 ? '+' : ''}${v}%`

const REGIME_COLOR = {
  'Trending':        { bg: 'bg-green-50',  border: 'border-green-200', text: 'text-green-700', dot: '#22C55E' },
  'Mean-Reverting':  { bg: 'bg-indigo-50', border: 'border-indigo-200',text: 'text-indigo-700',dot: '#6366F1' },
  'High Volatility': { bg: 'bg-red-50',    border: 'border-red-200',   text: 'text-red-700',   dot: '#EF4444' },
}

// ── shared ui ─────────────────────────────────────────────────────────────────
const Card = ({ title, icon: Icon, children, className = '' }) => (
  <div className={`bg-white rounded-xl border border-border shadow-card p-4 ${className}`}>
    {title && (
      <div className="flex items-center gap-2 mb-3 pb-2 border-b border-border">
        {Icon && <Icon size={14} className="text-primary" />}
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

const Pill = ({ ok, label }) => (
  <span className={`inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full border ${
    ok ? 'bg-green-100 text-green-700 border-green-200' : 'bg-red-100 text-red-600 border-red-200'
  }`}>
    {ok ? <CheckCircle size={10} /> : <XCircle size={10} />}
    {label}
  </span>
)

// ── 1. Market Regime ──────────────────────────────────────────────────────────
function RegimePanel() {
  const [ticker, setTicker] = useState('SPY')
  const [input, setInput]   = useState('SPY')
  const [data, setData]     = useState(null)
  const { call, loading }   = useApi()

  const load = useCallback(async (t) => {
    const d = await call(`/api/orderflow/regime/${t}?period=1y`)
    if (d) setData(d)
  }, [call])

  useEffect(() => { load(ticker) }, [])

  const style = data ? REGIME_COLOR[data.regime] || REGIME_COLOR['Mean-Reverting'] : null

  return (
    <Card title="Market Regime Filter" icon={Brain}>
      <div className="flex gap-2 mb-3">
        <input value={input} onChange={e => setInput(e.target.value.toUpperCase())}
          className="input flex-1 text-sm" placeholder="Ticker" />
        <button className="btn-primary text-xs px-3"
          onClick={() => { setTicker(input); load(input) }}>
          {loading ? <RefreshCw size={11} className="animate-spin" /> : 'Analyze'}
        </button>
      </div>

      {data && (
        <div className="space-y-3">
          <div className={`rounded-xl border p-3 ${style.bg} ${style.border}`}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full inline-block" style={{ background: style.dot }} />
                <span className={`font-bold text-sm ${style.text}`}>{data.regime}</span>
              </div>
              <span className={`text-xs font-bold px-2 py-0.5 rounded-full bg-white/70 ${style.text}`}>
                {data.confidence}% confidence
              </span>
            </div>
            <p className="text-xs mt-2 text-sub leading-relaxed">{data.action}</p>
          </div>

          {/* Regime history area chart */}
          {data.history?.length > 0 && (
            <div>
              <div className="text-xs text-muted mb-1 font-semibold">Price + Regime (60 days)</div>
              <ResponsiveContainer width="100%" height={120}>
                <AreaChart data={data.history}>
                  <defs>
                    <linearGradient id="priceGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#6366F1" stopOpacity={0.15} />
                      <stop offset="95%" stopColor="#6366F1" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="date" tick={{ fontSize: 9 }} tickLine={false}
                    interval={Math.floor(data.history.length / 5)} />
                  <YAxis domain={['auto', 'auto']} tick={{ fontSize: 9 }} tickLine={false} width={48} />
                  <Tooltip
                    contentStyle={{ fontSize: 11, borderRadius: 8, border: '1px solid #E4E9F5' }}
                    formatter={(v, n, p) => [v, p.payload.regime]}
                  />
                  <Area
                    type="monotone" dataKey="price" stroke="#6366F1" strokeWidth={1.5}
                    fill="url(#priceGrad)" dot={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
              {/* Regime legend strip */}
              <div className="flex gap-3 mt-1 flex-wrap">
                {Object.entries(REGIME_COLOR).map(([k, v]) => (
                  <div key={k} className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full" style={{ background: v.dot }} />
                    <span className="text-xs text-muted">{k}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  )
}

// ── 2. Data Pipeline ──────────────────────────────────────────────────────────
function PipelinePanel({ onStatusChange }) {
  const [symbol,  setSymbol]  = useState('BTCUSDT')
  const [status,  setStatus]  = useState(null)
  const { call, loading }     = useApi()

  const fetchStatus = useCallback(async () => {
    const d = await call('/api/orderflow/pipeline/status')
    if (d) { setStatus(d); onStatusChange?.(d) }
  }, [call])

  useEffect(() => { fetchStatus() }, [])

  const startPipeline = async () => {
    await call(`/api/orderflow/pipeline/start/${symbol}`, { method: 'POST' })
    setTimeout(fetchStatus, 1000)
  }

  const stopPipeline = async () => {
    await call('/api/orderflow/pipeline/stop', { method: 'POST' })
    setTimeout(fetchStatus, 500)
  }

  return (
    <Card title="WebSocket Data Pipeline" icon={Activity}>
      <div className="space-y-3">
        <div className="flex gap-2">
          <input value={symbol} onChange={e => setSymbol(e.target.value.toUpperCase())}
            className="input flex-1 text-sm font-mono" placeholder="e.g. BTCUSDT" />
          {status?.running
            ? <button onClick={stopPipeline} className="btn-danger text-xs px-3 flex items-center gap-1">
                <Square size={10} /> Stop
              </button>
            : <button onClick={startPipeline} className="btn-primary text-xs px-3 flex items-center gap-1">
                {loading ? <RefreshCw size={10} className="animate-spin" /> : <Play size={10} />}
                Start
              </button>
          }
          <button onClick={fetchStatus} className="btn-ghost text-xs px-2">
            <RefreshCw size={11} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>

        {status && (
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${status.running ? 'bg-green-400 animate-pulse' : 'bg-gray-300'}`} />
              <span className={`text-xs font-semibold ${status.running ? 'text-green-700' : 'text-muted'}`}>
                {status.running ? `Streaming ${status.symbol}` : 'Idle'}
              </span>
            </div>
            <Row label="DB File"     value={status.db_path} vc="text-muted" />
            <Row label="DB Exists"   value={status.db_exists ? 'Yes' : 'No'} vc={status.db_exists ? 'text-green-600' : 'text-red-500'} />
            <Row label="SVM Trained" value={status.svm_trained ? 'Yes' : 'No'} vc={status.svm_trained ? 'text-green-600' : 'text-amber-600'} />
            <Row label="Risk Mgr"    value={status.risk_initialized ? 'Ready' : 'Not init'} vc={status.risk_initialized ? 'text-green-600' : 'text-amber-600'} />
          </div>
        )}

        <div className="bg-blue-50 border border-blue-200 rounded-lg p-2.5 text-xs text-blue-700 leading-relaxed">
          <strong>How it works:</strong> Opens two Binance WebSocket streams — aggTrade (every matched trade)
          and depth5@100ms (top-5 bid/ask ladder). Trades are batched in memory and flushed
          to SQLite every 100 ticks to minimise write latency. Requires internet access to Binance.
        </div>
      </div>
    </Card>
  )
}

// ── 3. Footprint + VPVR ───────────────────────────────────────────────────────
function FootprintPanel({ pipelineRunning }) {
  const [symbol, setSymbol] = useState('BTCUSDT')
  const [data,   setData]   = useState(null)
  const { call, loading }   = useApi()

  const load = useCallback(async () => {
    const d = await call(`/api/orderflow/footprint/${symbol}?minutes=60`)
    if (d) setData(d)
  }, [call, symbol])

  const vpvr    = data?.vpvr   || {}
  const candles = data?.candles || []

  // Prepare VPVR chart data (top 20 levels)
  const profileData = (vpvr.profile || [])
    .sort((a, b) => b.volume - a.volume)
    .slice(0, 20)
    .sort((a, b) => a.price - b.price)

  return (
    <Card title="Footprint Chart & VPVR" icon={BarChart2}>
      <div className="flex gap-2 mb-3">
        <input value={symbol} onChange={e => setSymbol(e.target.value.toUpperCase())}
          className="input flex-1 text-sm font-mono" placeholder="Symbol" />
        <button onClick={load} className="btn-primary text-xs px-3">
          {loading ? <RefreshCw size={11} className="animate-spin" /> : 'Load'}
        </button>
      </div>

      {!pipelineRunning && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-2.5 text-xs text-amber-700 mb-3">
          <AlertTriangle size={11} className="inline mr-1" />
          Pipeline is not running. Start it above to collect tick data first.
        </div>
      )}

      {data?.message && !data.tick_count && (
        <p className="text-xs text-muted text-center py-4">{data.message}</p>
      )}

      {data?.tick_count > 0 && (
        <div className="space-y-3">
          {/* VPVR key levels */}
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="bg-green-50 border border-green-200 rounded-lg p-2">
              <div className="text-xs text-muted">VAH</div>
              <div className="font-bold font-mono text-green-700">{vpvr.value_area_high?.toFixed(2)}</div>
            </div>
            <div className="bg-primary/5 border border-primary/20 rounded-lg p-2">
              <div className="text-xs text-primary font-bold">POC</div>
              <div className="font-bold font-mono text-primary">{vpvr.poc?.toFixed(2)}</div>
            </div>
            <div className="bg-red-50 border border-red-200 rounded-lg p-2">
              <div className="text-xs text-muted">VAL</div>
              <div className="font-bold font-mono text-red-600">{vpvr.value_area_low?.toFixed(2)}</div>
            </div>
          </div>

          <div className="text-xs text-muted">
            <span className="font-semibold">{data.tick_count?.toLocaleString()}</span> ticks ·
            <span className="font-semibold"> {candles.length}</span> candles ·
            Total vol: <span className="font-semibold">{vpvr.total_volume?.toLocaleString()}</span>
          </div>

          {/* Volume Profile bar chart */}
          {profileData.length > 0 && (
            <div>
              <div className="text-xs text-muted font-semibold mb-1">Volume Profile (top 20 levels)</div>
              <ResponsiveContainer width="100%" height={140}>
                <BarChart data={profileData} layout="vertical" margin={{ left: 10, right: 0 }}>
                  <XAxis type="number" tick={{ fontSize: 9 }} tickLine={false} />
                  <YAxis type="category" dataKey="price" tick={{ fontSize: 9 }} tickLine={false} width={55} />
                  <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8, border: '1px solid #E4E9F5' }} />
                  <Bar dataKey="volume" radius={[0, 3, 3, 0]}>
                    {profileData.map((entry, i) => (
                      <Cell key={i} fill={entry.price === vpvr.poc ? '#6366F1' : '#A5B4FC'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Last 5 footprint candles summary */}
          {candles.length > 0 && (
            <div>
              <div className="text-xs text-muted font-semibold mb-1">Recent Candles (volume delta)</div>
              <div className="space-y-1">
                {candles.slice(-5).map((c, i) => (
                  <div key={i} className={`flex items-center justify-between rounded px-2.5 py-1.5 text-xs ${
                    c.delta > 0 ? 'bg-green-50' : 'bg-red-50'
                  }`}>
                    <span className="text-muted">{c.time?.slice(11, 16)}</span>
                    <span className="font-mono text-ink">{c.close?.toFixed(2)}</span>
                    <span className={`font-bold font-mono ${c.delta > 0 ? 'text-green-700' : 'text-red-600'}`}>
                      {c.delta > 0 ? '+' : ''}{c.delta?.toFixed(2)} Δ
                    </span>
                    <span className="text-muted">vol {c.volume?.toFixed(2)}</span>
                    {c.levels?.some(l => l.imbalance) && (
                      <span className="bg-amber-200 text-amber-800 px-1 rounded text-xs font-bold">⚡ IMB</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  )
}

// ── 4. SVM Classifier ─────────────────────────────────────────────────────────
function ClassifierPanel({ pipelineSymbol }) {
  const [symbol,  setSymbol]  = useState(pipelineSymbol || 'BTCUSDT')
  const [metrics, setMetrics] = useState(null)
  const [status,  setStatus]  = useState('')
  const { call, loading }     = useApi()

  const train = async () => {
    setStatus('Training…')
    const d = await call(`/api/orderflow/train-classifier/${symbol}`, { method: 'POST' })
    if (d) {
      setMetrics(d.metrics)
      setStatus(d.status === 'trained' ? 'Trained ✓' : 'Failed')
    }
  }

  const cm = metrics?.confusion_matrix || []

  return (
    <Card title="Institutional Flow Classifier (SVM)" icon={Brain}>
      <div className="flex gap-2 mb-3">
        <input value={symbol} onChange={e => setSymbol(e.target.value.toUpperCase())}
          className="input flex-1 text-sm font-mono" placeholder="Symbol" />
        <button onClick={train} className="btn-primary text-xs px-3">
          {loading ? <RefreshCw size={11} className="animate-spin" /> : 'Train'}
        </button>
      </div>

      {status && <div className="text-xs text-primary font-semibold mb-2">{status}</div>}

      <div className="bg-surface rounded-lg p-2.5 text-xs text-sub leading-relaxed mb-3">
        Trains a RBF-SVM on 4 hours of tick data. Features: volume delta,
        avg trade size, trade count, close vs VWAP, buy ratio. Top-quartile bars
        by size + delta conviction are auto-labelled as Institutional.
      </div>

      {metrics?.error && (
        <div className="bg-red-50 border border-red-200 rounded p-2 text-xs text-red-700">{metrics.error}</div>
      )}

      {metrics && !metrics.error && (
        <div className="space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-green-50 border border-green-200 rounded-lg p-2 text-center">
              <div className="text-xs text-muted">Accuracy</div>
              <div className="font-bold text-green-700">{(metrics.accuracy * 100).toFixed(1)}%</div>
            </div>
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-2 text-center">
              <div className="text-xs text-muted">Institutional Precision</div>
              <div className="font-bold text-blue-700">{(metrics.institutional_precision * 100).toFixed(1)}%</div>
            </div>
            <div className="bg-surface border border-border rounded-lg p-2 text-center">
              <div className="text-xs text-muted">Samples Trained</div>
              <div className="font-bold text-ink">{metrics.samples_trained}</div>
            </div>
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-2 text-center">
              <div className="text-xs text-muted">Inst % of Data</div>
              <div className="font-bold text-amber-700">{metrics.institutional_pct_in_dataset}%</div>
            </div>
          </div>

          {/* Confusion Matrix */}
          {cm.length === 2 && (
            <div>
              <div className="text-xs text-muted font-semibold mb-1">Confusion Matrix</div>
              <div className="grid grid-cols-2 gap-1 text-center text-xs font-mono">
                {['TN', 'FP', 'FN', 'TP'].map((label, i) => {
                  const row = Math.floor(i / 2)
                  const col = i % 2
                  const val = cm[row]?.[col] ?? 0
                  const isCorrect = label === 'TN' || label === 'TP'
                  return (
                    <div key={label} className={`rounded p-2 ${isCorrect ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-700'}`}>
                      <div className="text-xs opacity-70">{label}</div>
                      <div className="font-bold">{val}</div>
                    </div>
                  )
                })}
              </div>
              <div className="text-xs text-muted mt-1 text-center">Retail (left) · Institutional (right)</div>
            </div>
          )}
        </div>
      )}
    </Card>
  )
}

// ── 5. Risk Manager ───────────────────────────────────────────────────────────
function RiskPanel() {
  const [balance, setBalance] = useState('100000')
  const [status,  setStatus]  = useState(null)
  const [atr,     setAtr]     = useState('2.5')
  const [sizing,  setSizing]  = useState(null)
  const { call, loading }     = useApi()

  const init = async () => {
    const d = await call('/api/orderflow/risk/init', {
      method: 'POST',
      body: JSON.stringify({ account_balance: parseFloat(balance) }),
    })
    if (d) loadStatus()
  }

  const loadStatus = async () => {
    const d = await call('/api/orderflow/risk/status')
    if (d) setStatus(d)
  }

  const calcSize = async () => {
    const d = await call('/api/orderflow/risk/position-size', {
      method: 'POST',
      body: JSON.stringify({ atr: parseFloat(atr), risk_pct: 0.01, atr_multiplier: 2.0 }),
    })
    if (d) setSizing(d)
  }

  const resetDaily = async () => {
    const d = await call('/api/orderflow/risk/reset-daily', { method: 'POST' })
    if (d) setStatus(d)
  }

  return (
    <Card title="Risk Manager & Kill Switch" icon={Shield}>
      {!status ? (
        <div className="space-y-2">
          <div className="text-xs text-sub mb-2">Initialize with your account balance to enable position sizing and kill-switch protection.</div>
          <div className="flex gap-2">
            <input value={balance} onChange={e => setBalance(e.target.value)}
              className="input flex-1 text-sm font-mono" placeholder="Account balance ($)" />
            <button onClick={init} className="btn-primary text-xs px-3">
              {loading ? <RefreshCw size={11} className="animate-spin" /> : 'Init'}
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          {/* Status banner */}
          <div className={`rounded-lg border p-2.5 ${status.halted
            ? 'bg-red-50 border-red-300'
            : 'bg-green-50 border-green-200'
          }`}>
            <div className="flex items-center justify-between">
              <span className={`text-xs font-bold ${status.halted ? 'text-red-700' : 'text-green-700'}`}>
                {status.halted ? '🛑 TRADING HALTED — Kill Switch Active' : '✅ Active'}
              </span>
              {status.halted && (
                <button onClick={resetDaily} className="text-xs text-red-600 underline font-semibold">
                  Reset Daily
                </button>
              )}
            </div>
            {status.halt_reason && (
              <p className="text-xs text-red-600 mt-1 leading-snug">{status.halt_reason}</p>
            )}
          </div>

          {/* Portfolio stats */}
          <div className="space-y-0.5">
            <Row label="Account Balance"  value={`$${status.account_balance?.toLocaleString()}`} />
            <Row label="Equity"           value={`$${status.equity?.toLocaleString()}`} />
            <Row label="Unrealized PnL"   value={`$${status.total_unrealized}`}
              vc={status.total_unrealized >= 0 ? 'text-green-600' : 'text-red-600'} />
            <Row label="Daily Drawdown"   value={fmtPct(status.daily_drawdown)}
              vc={status.daily_drawdown < -3 ? 'text-red-600' : status.daily_drawdown < 0 ? 'text-amber-600' : 'text-green-600'} />
            <Row label="Kill Switch at"   value={`${status.kill_switch_threshold}%`} vc="text-red-500" />
            <Row label="Open Positions"   value={status.open_positions} />
          </div>

          {/* Daily drawdown bar */}
          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-muted">Daily Drawdown</span>
              <span className={status.daily_drawdown <= -3 ? 'text-red-600 font-bold' : 'text-muted'}>
                {fmtPct(status.daily_drawdown)} / {status.kill_switch_threshold}%
              </span>
            </div>
            <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${
                  Math.abs(status.daily_drawdown) >= Math.abs(status.kill_switch_threshold) * 0.8
                    ? 'bg-red-500' : 'bg-amber-400'
                }`}
                style={{ width: `${Math.min(Math.abs(status.daily_drawdown) / Math.abs(status.kill_switch_threshold) * 100, 100)}%` }}
              />
            </div>
          </div>

          {/* Position sizing calc */}
          <div className="border-t border-border pt-3">
            <div className="text-xs font-semibold text-muted mb-2">Position Size Calculator</div>
            <div className="flex gap-2 mb-2">
              <input value={atr} onChange={e => setAtr(e.target.value)}
                className="input flex-1 text-sm font-mono" placeholder="ATR" />
              <button onClick={calcSize} className="btn-ghost text-xs px-3">
                {loading ? <RefreshCw size={10} className="animate-spin" /> : 'Calc'}
              </button>
            </div>
            {sizing && (
              <div className="bg-surface rounded-lg p-2.5 space-y-0.5 text-xs">
                <div className="flex justify-between">
                  <span className="text-muted">Formula</span>
                  <span className="text-sub font-mono text-xs">{sizing.formula}</span>
                </div>
                <Row label="Position Size (units)" value={sizing.size?.toFixed(4)} vc="text-primary" />
                <Row label="Dollar Risk"           value={`$${sizing.dollar_risk}`} vc="text-red-500" />
                <Row label="Stop Distance"         value={sizing.stop_distance?.toFixed(4)} />
                <Row label="Max Position Value"    value={`$${sizing.max_position_value?.toLocaleString()}`} />
              </div>
            )}
          </div>
        </div>
      )}
    </Card>
  )
}

// ── 6. Trigger Engine ─────────────────────────────────────────────────────────
function TriggerPanel() {
  const [form, setForm] = useState({
    current_price: '', poc: '', volume_delta: '',
    svm_signal: '0', svm_confidence: '0',
  })
  const [result, setResult] = useState(null)
  const { call, loading }   = useApi()

  const evaluate = async () => {
    const payload = {
      current_price:  parseFloat(form.current_price),
      poc:            parseFloat(form.poc),
      volume_delta:   parseFloat(form.volume_delta),
      svm_signal:     parseInt(form.svm_signal),
      svm_confidence: parseFloat(form.svm_confidence),
    }
    if (Object.values(payload).some(isNaN)) return
    const d = await call('/api/orderflow/trigger/evaluate', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
    if (d) setResult(d)
  }

  const inp = (field, label, placeholder = '') => (
    <div>
      <label className="block text-xs text-muted mb-0.5">{label}</label>
      <input
        value={form[field]}
        onChange={e => setForm(p => ({ ...p, [field]: e.target.value }))}
        className="input w-full text-sm font-mono"
        placeholder={placeholder}
      />
    </div>
  )

  return (
    <Card title="Trigger Engine — Asymmetric Execution" icon={Zap}>
      <div className="space-y-2 mb-3">
        {inp('current_price', 'Current Price', 'e.g. 65420.5')}
        {inp('poc', 'POC (Point of Control)', 'from VPVR above')}
        {inp('volume_delta', 'Volume Delta', '+ = buyers dominant')}
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="block text-xs text-muted mb-0.5">SVM Signal (0/1)</label>
            <select value={form.svm_signal}
              onChange={e => setForm(p => ({ ...p, svm_signal: e.target.value }))}
              className="input w-full text-sm">
              <option value="0">0 — Retail</option>
              <option value="1">1 — Institutional</option>
            </select>
          </div>
          {inp('svm_confidence', 'SVM Confidence %', '0–100')}
        </div>
        <button onClick={evaluate} className="btn-primary w-full text-xs justify-center">
          {loading ? <RefreshCw size={11} className="animate-spin" /> : 'Evaluate Trigger'}
        </button>
      </div>

      {result && (
        <div className="space-y-3">
          {/* Decision banner */}
          <div className={`rounded-xl border p-3 text-center ${
            result.should_buy
              ? 'bg-green-50 border-green-300'
              : 'bg-gray-50 border-gray-200'
          }`}>
            <div className={`font-bold text-lg ${result.should_buy ? 'text-green-700' : 'text-gray-500'}`}>
              {result.should_buy ? '🟢 BUY SIGNAL' : '🔴 NO ENTRY'}
            </div>
            {result.should_buy && (
              <div className="grid grid-cols-2 gap-2 mt-2">
                <div className="bg-white rounded-lg p-2">
                  <div className="text-xs text-muted">Entry</div>
                  <div className="font-bold font-mono text-ink">{result.entry_price?.toFixed(4)}</div>
                </div>
                <div className="bg-red-50 rounded-lg p-2">
                  <div className="text-xs text-red-500">Stop (below POC)</div>
                  <div className="font-bold font-mono text-red-700">{result.stop_loss?.toFixed(4)}</div>
                </div>
              </div>
            )}
          </div>

          {/* Conditions checklist */}
          <div className="space-y-2">
            {Object.entries(result.conditions_met).map(([key, cond]) => (
              <div key={key} className={`rounded-lg border px-3 py-2 ${
                cond.met ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'
              }`}>
                <div className="flex items-center gap-2">
                  {cond.met
                    ? <CheckCircle size={13} className="text-green-600 flex-shrink-0" />
                    : <XCircle    size={13} className="text-red-500  flex-shrink-0" />}
                  <span className={`text-xs font-semibold ${cond.met ? 'text-green-800' : 'text-red-800'}`}>
                    {key === 'price_near_poc'       ? 'Price within 1% of POC' :
                     key === 'positive_delta'       ? 'Positive Volume Delta'   :
                                                      'Institutional SVM Signal'}
                  </span>
                </div>
                <p className="text-xs text-sub mt-0.5 ml-5">{cond.detail}</p>
              </div>
            ))}
          </div>

          {/* Reason log */}
          <div className="bg-surface rounded-lg p-2.5 space-y-0.5">
            {result.reasons.map((r, i) => (
              <p key={i} className="text-xs text-sub leading-snug">{r}</p>
            ))}
          </div>
        </div>
      )}

      {/* Logic explanation */}
      <div className="mt-3 bg-indigo-50 border border-indigo-200 rounded-lg p-2.5 text-xs text-indigo-700 leading-relaxed">
        <strong>Why all three must align:</strong> Any single signal can be noise.
        Price near POC alone = institutions may already be selling. Positive delta alone = could be retail FOMO.
        SVM alone = model confidence varies. All three together = multi-confirmation institutional entry
        with the stop defined by the POC break — asymmetric risk/reward by construction.
      </div>
    </Card>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function OrderFlow() {
  const [pipelineStatus, setPipelineStatus] = useState(null)

  return (
    <div className="p-4 space-y-4 max-w-6xl">
      <div className="flex items-center gap-3">
        <Activity size={18} className="text-primary" />
        <div>
          <h1 className="text-lg font-bold text-ink">Order Flow Intelligence</h1>
          <p className="text-xs text-muted">Tick data · Footprint · Market Regime · Institutional SVM · Risk Management</p>
        </div>
      </div>

      {/* Phase labels */}
      <div className="flex gap-2 flex-wrap text-xs">
        {[
          { label: 'Phase 1: Data & Footprint', color: 'bg-blue-100 text-blue-700 border-blue-200' },
          { label: 'Phase 2: ML Models',        color: 'bg-purple-100 text-purple-700 border-purple-200' },
          { label: 'Phase 3: Risk & Execution', color: 'bg-amber-100 text-amber-700 border-amber-200' },
        ].map(p => (
          <span key={p.label} className={`px-2.5 py-1 rounded-full border font-semibold ${p.color}`}>
            {p.label}
          </span>
        ))}
      </div>

      {/* Phase 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <PipelinePanel onStatusChange={setPipelineStatus} />
        <FootprintPanel pipelineRunning={pipelineStatus?.running} />
      </div>

      {/* Phase 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <RegimePanel />
        <ClassifierPanel pipelineSymbol={pipelineStatus?.symbol} />
      </div>

      {/* Phase 3 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <RiskPanel />
        <TriggerPanel />
      </div>
    </div>
  )
}
