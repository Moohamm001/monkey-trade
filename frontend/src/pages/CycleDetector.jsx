import React, { useState } from 'react'
import { Search, TrendingUp, TrendingDown, Minus, AlertCircle, ChevronDown, ChevronUp, Target, Shield, DollarSign } from 'lucide-react'
import { useApi } from '../hooks/useApi'
import StageBadge from '../components/StageBadge'
import StageScoreBar from '../components/StageScoreBar'
import CandlestickChart from '../components/CandlestickChart'

const PERIODS = ['6mo', '1y', '2y', '5y']

const SignalIcon = ({ type }) => {
  if (type === 'bullish') return <TrendingUp size={13} className="text-green-600 flex-shrink-0 mt-0.5" />
  if (type === 'bearish') return <TrendingDown size={13} className="text-red-500 flex-shrink-0 mt-0.5" />
  return <Minus size={13} className="text-muted flex-shrink-0 mt-0.5" />
}

const typeColor = {
  bullish: { text: 'text-green-700', bg: 'bg-green-50',  border: 'border-green-200', badge: 'bg-green-100 text-green-700' },
  bearish: { text: 'text-red-700',   bg: 'bg-red-50',    border: 'border-red-200',   badge: 'bg-red-100 text-red-700' },
  neutral: { text: 'text-sub',       bg: 'bg-surface',   border: 'border-border',    badge: 'bg-surface text-muted' },
}

function SignalCard({ signal }) {
  const [open, setOpen] = useState(false)
  const c = typeColor[signal.type] || typeColor.neutral

  return (
    <div className={`rounded-lg border ${c.border} ${c.bg} overflow-hidden`}>
      <button
        className="w-full text-left px-3 py-2 flex items-start gap-2"
        onClick={() => setOpen(v => !v)}
      >
        <SignalIcon type={signal.type} />
        <div className="flex-1 min-w-0">
          <span className={`text-xs font-medium ${c.text}`}>{signal.text}</span>
          {signal.technique && (
            <span className={`ml-2 text-xs px-1.5 py-0.5 rounded ${c.badge}`}>{signal.technique}</span>
          )}
        </div>
        {open ? <ChevronUp size={12} className="text-gray-500 flex-shrink-0 mt-0.5" /> : <ChevronDown size={12} className="text-gray-500 flex-shrink-0 mt-0.5" />}
      </button>
      {open && signal.why && (
        <div className="px-3 pb-3 space-y-1.5 border-t border-black/5 pt-2">
          <div>
            <span className="text-xs text-muted font-medium">What this measures</span>
            <p className="text-xs text-sub mt-0.5">{signal.why}</p>
          </div>
          <div>
            <span className="text-xs text-muted font-medium">What it means</span>
            <p className={`text-xs mt-0.5 font-medium ${c.text}`}>{signal.implication}</p>
          </div>
        </div>
      )}
    </div>
  )
}

function TradeLevelCard({ levels, stage }) {
  if (!levels || !levels.entry) return null

  const isShort = stage === 'markdown'
  const rrColor = levels.risk_reward >= 2.5 ? 'text-green-400' : levels.risk_reward >= 1.5 ? 'text-yellow-400' : 'text-red-400'

  return (
    <div className="card border border-primary/20 bg-primary-light/30">
      <div className="text-xs font-semibold text-sub mb-2 flex items-center gap-2">
        <DollarSign size={13} className="text-primary" />
        Trade Levels {isShort ? '(Short)' : '(Long)'}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-2">
        <div className="bg-surface rounded-lg p-2 text-center">
          <div className="text-xs text-muted">Entry</div>
          <div className="text-sm font-bold font-mono text-ink">{levels.entry?.toFixed(2)}</div>
        </div>
        <div className="bg-red-50 border border-red-200 rounded-lg p-2 text-center">
          <div className="text-xs text-red-500 flex items-center justify-center gap-1">
            <Shield size={9} /> Stop
          </div>
          <div className="text-sm font-bold font-mono text-red-500">{levels.stop_loss?.toFixed(2)}</div>
          <div className="text-xs text-red-400">−{levels.stop_pct?.toFixed(1)}%</div>
        </div>
        <div className="bg-green-50 border border-green-200 rounded-lg p-2 text-center">
          <div className="text-xs text-green-600 flex items-center justify-center gap-1">
            <Target size={9} /> Target
          </div>
          <div className="text-sm font-bold font-mono text-green-600">{levels.target?.toFixed(2)}</div>
          <div className="text-xs text-green-500">+{levels.target_pct?.toFixed(1)}%</div>
        </div>
        <div className="bg-surface rounded-lg p-2 text-center">
          <div className="text-xs text-muted">R:R</div>
          <div className={`text-sm font-bold font-mono ${rrColor}`}>1:{levels.risk_reward}</div>
          <div className={`text-xs ${rrColor}`}>
            {levels.risk_reward >= 2.5 ? 'Excellent' : levels.risk_reward >= 1.5 ? 'OK' : 'Poor'}
          </div>
        </div>
      </div>

      <p className="text-xs text-muted leading-relaxed">{levels.reasoning}</p>
    </div>
  )
}

export default function CycleDetector() {
  const [ticker, setTicker] = useState('')
  const [period, setPeriod] = useState('1y')
  const [result, setResult] = useState(null)
  const { call, loading, error } = useApi()

  const analyze = async (e) => {
    e?.preventDefault()
    if (!ticker.trim()) return
    const data = await call(`/api/stock/${ticker.trim().toUpperCase()}/cycle?period=${period}`)
    if (data) setResult(data)
  }

  const ind = result?.indicators || {}
  const chart = result?.chart || []

  return (
    <div className="p-3 space-y-3 max-w-5xl">
      <form onSubmit={analyze} className="flex flex-wrap gap-2 items-center">
        <span className="text-sm font-bold text-ink flex-shrink-0">Cycle Detector</span>
        <input
          value={ticker}
          onChange={e => setTicker(e.target.value.toUpperCase())}
          placeholder="Ticker — e.g. AAPL, NVDA, TSLA"
          className="input flex-1 min-w-[180px]"
        />
        <div className="flex gap-1">
          {PERIODS.map(p => (
            <button key={p} type="button" onClick={() => setPeriod(p)}
              className={`btn text-xs ${period === p ? 'btn-primary' : 'btn-ghost'}`}>{p}</button>
          ))}
        </div>
        <button type="submit" disabled={loading} className="btn-primary flex items-center gap-2">
          <Search size={15} />
          {loading ? 'Analyzing...' : 'Analyze'}
        </button>
      </form>

      {error && (
        <div className="flex items-center gap-2 text-red-600 text-sm card bg-red-50 border-red-200">
          <AlertCircle size={15} /> {error}
        </div>
      )}

      {result && (
        <div className="space-y-3">
          {/* Stage banner */}
          <div className={`rounded-xl border px-4 py-2.5 flex items-center gap-3 flex-wrap ${
            result.stage === 'accumulation' ? 'bg-blue-50 border-blue-200' :
            result.stage === 'markup'       ? 'bg-green-50 border-green-200' :
            result.stage === 'distribution' ? 'bg-amber-50 border-amber-200' :
            'bg-red-50 border-red-200'
          }`}>
            <span className="text-2xl">{result.stage_info?.emoji}</span>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-base font-bold text-ink">{result.stage_info?.label} Stage</span>
                <StageBadge stage={result.stage} confidence={result.confidence} size="md" />
                <span className={`text-xs font-bold ${
                  result.stage === 'markup' || result.stage === 'accumulation' ? 'text-green-600' :
                  result.stage === 'markdown' ? 'text-red-600' : 'text-amber-600'
                }`}>{result.stage_info?.action}</span>
              </div>
              <p className="text-xs text-sub mt-0.5">{result.stage_info?.description}</p>
            </div>
            <div className="min-w-[180px]">
              <div className="text-xs text-muted mb-1">Stage Probability</div>
              <StageScoreBar scores={ind.scores} />
            </div>
          </div>

          {/* Trade levels */}
          <TradeLevelCard levels={result.trade_levels} stage={result.stage} />

          {/* Chart */}
          {chart.length > 0 && (
            <div className="card">
              <div className="text-xs font-semibold text-muted mb-2">Price History</div>
              <CandlestickChart data={chart} />
            </div>
          )}

          {/* Indicators grid */}
          <div className="card">
            <div className="text-xs font-semibold text-muted mb-2 uppercase tracking-wide">Key Indicators</div>
            <div className="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-1.5">
              {[
                { label: 'RSI',     value: ind.rsi,       color: ind.rsi > 70 ? 'text-red-600' : ind.rsi < 30 ? 'text-green-600' : 'text-ink' },
                { label: 'Stoch',   value: ind.stoch_k,   color: ind.stoch_k > 80 ? 'text-red-600' : ind.stoch_k < 20 ? 'text-green-600' : 'text-ink' },
                { label: 'MACD',    value: ind.macd_line, color: ind.macd_line > 0 ? 'text-green-600' : 'text-red-500' },
                { label: 'Sig',     value: ind.macd_signal },
                { label: 'SMA20',   value: ind.sma20 },
                { label: 'SMA50',   value: ind.sma50 },
                { label: 'SMA200',  value: ind.sma200 },
                { label: 'BB Hi',   value: ind.bb_upper,  color: 'text-amber-600' },
                { label: 'BB Lo',   value: ind.bb_lower,  color: 'text-blue-600' },
                { label: 'ATR',     value: ind.atr },
                { label: '20d',     value: ind.price_change_20d != null ? `${ind.price_change_20d > 0 ? '+' : ''}${ind.price_change_20d}%` : null, color: ind.price_change_20d > 0 ? 'text-green-600' : 'text-red-500' },
                { label: '52W Pos', value: ind.price_position_52w != null ? `${Math.round(ind.price_position_52w * 100)}%` : null },
              ].map(({ label, value, color }) => (
                <div key={label} className="bg-surface rounded px-2 py-1.5">
                  <div className="text-xs text-muted">{label}</div>
                  <div className={`font-mono font-semibold text-xs mt-0.5 ${color || 'text-ink'}`}>
                    {value != null ? value : '—'}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Signal cards */}
          <div className="card">
            <div className="text-xs font-semibold text-muted mb-2 uppercase tracking-wide">
              Signals ({result.signals?.length || 0}) — click to expand
            </div>
            <div className="space-y-1.5">
              {(result.signals || []).map((s, i) => (
                <SignalCard key={i} signal={s} />
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
