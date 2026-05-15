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
        className="w-full text-left px-4 py-3 flex items-start gap-2"
        onClick={() => setOpen(v => !v)}
      >
        <SignalIcon type={signal.type} />
        <div className="flex-1 min-w-0">
          <span className={`text-sm font-medium ${c.text}`}>{signal.text}</span>
          {signal.technique && (
            <span className={`ml-2 text-xs px-1.5 py-0.5 rounded ${c.badge}`}>{signal.technique}</span>
          )}
        </div>
        {open ? <ChevronUp size={14} className="text-gray-500 flex-shrink-0 mt-0.5" /> : <ChevronDown size={14} className="text-gray-500 flex-shrink-0 mt-0.5" />}
      </button>
      {open && signal.why && (
        <div className="px-4 pb-4 space-y-2 border-t border-black/5 pt-3">
          <div>
            <span className="text-xs text-muted uppercase tracking-wide font-medium">What this measures</span>
            <p className="text-sm text-sub mt-0.5">{signal.why}</p>
          </div>
          <div>
            <span className="text-xs text-muted uppercase tracking-wide font-medium">What it means for this stock</span>
            <p className={`text-sm mt-0.5 font-medium ${c.text}`}>{signal.implication}</p>
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
      <div className="text-sm font-semibold text-sub mb-4 flex items-center gap-2">
        <DollarSign size={15} className="text-primary" />
        Trade Levels {isShort ? '(Short Setup)' : '(Long Setup)'}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <div className="bg-dark-700 rounded-lg p-3 text-center">
          <div className="text-xs text-gray-500 mb-1">Entry</div>
          <div className="text-lg font-bold font-mono">{levels.entry?.toFixed(2)}</div>
          <div className="text-xs text-gray-500">Current price</div>
        </div>
        <div className="bg-red-600/10 border border-red-600/20 rounded-lg p-3 text-center">
          <div className="text-xs text-red-400 mb-1 flex items-center justify-center gap-1">
            <Shield size={10} /> Stop Loss
          </div>
          <div className="text-lg font-bold font-mono text-red-400">{levels.stop_loss?.toFixed(2)}</div>
          <div className="text-xs text-red-400/60">−{levels.stop_pct?.toFixed(1)}% risk</div>
        </div>
        <div className="bg-green-600/10 border border-green-600/20 rounded-lg p-3 text-center">
          <div className="text-xs text-green-400 mb-1 flex items-center justify-center gap-1">
            <Target size={10} /> Target
          </div>
          <div className="text-lg font-bold font-mono text-green-400">{levels.target?.toFixed(2)}</div>
          <div className="text-xs text-green-400/60">+{levels.target_pct?.toFixed(1)}% reward</div>
        </div>
        <div className="bg-dark-700 rounded-lg p-3 text-center">
          <div className="text-xs text-gray-500 mb-1">Risk : Reward</div>
          <div className={`text-lg font-bold font-mono ${rrColor}`}>1 : {levels.risk_reward}</div>
          <div className={`text-xs ${rrColor} opacity-70`}>
            {levels.risk_reward >= 2.5 ? 'Excellent' : levels.risk_reward >= 1.5 ? 'Acceptable' : 'Poor — skip'}
          </div>
        </div>
      </div>

      <div className="bg-surface rounded-lg p-3">
        <div className="text-xs text-muted uppercase tracking-wide mb-1 font-medium">Why these levels</div>
        <p className="text-sm text-sub">{levels.reasoning}</p>
      </div>
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
    <div className="p-5 space-y-5 max-w-5xl">
      <div>
        <h1 className="text-xl font-bold text-ink">Market Cycle Detector</h1>
        <p className="text-sm text-muted mt-0.5">Full Wyckoff stage analysis — RSI, MACD, OBV, Stochastic, BB with trader reasoning</p>
      </div>

      <form onSubmit={analyze} className="flex flex-wrap gap-3">
        <input
          value={ticker}
          onChange={e => setTicker(e.target.value.toUpperCase())}
          placeholder="Enter ticker (e.g. AAPL, NVDA, TSLA)"
          className="input flex-1 min-w-[200px] text-base"
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
        <div className="space-y-5">
          {/* Stage banner */}
          <div className={`rounded-xl border p-4 ${
            result.stage === 'accumulation' ? 'bg-blue-50 border-blue-200' :
            result.stage === 'markup'       ? 'bg-green-50 border-green-200' :
            result.stage === 'distribution' ? 'bg-amber-50 border-amber-200' :
            'bg-red-50 border-red-200'
          }`}>
            <div className="flex items-start justify-between flex-wrap gap-4">
              <div className="flex items-start gap-4">
                <span className="text-4xl">{result.stage_info?.emoji}</span>
                <div>
                  <div className="flex items-center gap-3 flex-wrap mb-1">
                    <span className="text-xl font-bold text-ink">{result.stage_info?.label} Stage</span>
                    <StageBadge stage={result.stage} confidence={result.confidence} size="md" />
                  </div>
                  <p className="text-sub text-sm">{result.stage_info?.description}</p>
                  <div className="mt-2 text-sm">
                    <span className="text-muted">Suitable for: </span>
                    <span className="text-sub">{result.stage_info?.suitable_for}</span>
                  </div>
                  <div className="mt-1">
                    <span className="text-muted text-sm">Action: </span>
                    <span className={`font-bold text-sm ${
                      result.stage === 'markup' || result.stage === 'accumulation' ? 'text-green-600' :
                      result.stage === 'markdown' ? 'text-red-600' : 'text-amber-600'
                    }`}>{result.stage_info?.action}</span>
                  </div>
                </div>
              </div>
              <div className="min-w-[220px]">
                <div className="text-xs text-muted mb-2 uppercase tracking-wide font-medium">Stage Probability</div>
                <StageScoreBar scores={ind.scores} />
              </div>
            </div>
          </div>

          {/* Trade levels */}
          <TradeLevelCard levels={result.trade_levels} stage={result.stage} />

          {/* Chart */}
          {chart.length > 0 && (
            <div className="card">
              <div className="text-sm font-medium text-gray-400 mb-3">Price History</div>
              <CandlestickChart data={chart} />
            </div>
          )}

          {/* Indicators grid */}
          <div className="card">
            <div className="text-xs font-semibold text-muted mb-3 uppercase tracking-wide">Key Indicators</div>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
              {[
                { label: 'RSI (14)',     value: ind.rsi,       color: ind.rsi > 70 ? 'text-red-600' : ind.rsi < 30 ? 'text-green-600' : 'text-ink' },
                { label: 'Stoch %K',    value: ind.stoch_k,   color: ind.stoch_k > 80 ? 'text-red-600' : ind.stoch_k < 20 ? 'text-green-600' : 'text-ink' },
                { label: 'MACD Line',   value: ind.macd_line, color: ind.macd_line > 0 ? 'text-green-600' : 'text-red-500' },
                { label: 'MACD Signal', value: ind.macd_signal },
                { label: 'SMA 20',      value: ind.sma20 },
                { label: 'SMA 50',      value: ind.sma50 },
                { label: 'SMA 200',     value: ind.sma200 },
                { label: 'BB Upper',    value: ind.bb_upper,  color: 'text-amber-600' },
                { label: 'BB Lower',    value: ind.bb_lower,  color: 'text-blue-600' },
                { label: 'ATR (14)',    value: ind.atr },
                { label: '20d Change',  value: ind.price_change_20d != null ? `${ind.price_change_20d > 0 ? '+' : ''}${ind.price_change_20d}%` : null, color: ind.price_change_20d > 0 ? 'text-green-600' : 'text-red-500' },
                { label: '52W Position',value: ind.price_position_52w != null ? `${Math.round(ind.price_position_52w * 100)}%` : null },
              ].map(({ label, value, color }) => (
                <div key={label} className="bg-surface rounded-lg px-3 py-2">
                  <div className="text-xs text-muted">{label}</div>
                  <div className={`font-mono font-semibold text-sm mt-0.5 ${color || 'text-ink'}`}>
                    {value != null ? value : '—'}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Signal cards — expandable with full reasoning */}
          <div>
            <div className="text-xs font-semibold text-muted mb-3 uppercase tracking-wide">
              Signal Analysis ({result.signals?.length || 0} signals detected — click to expand reasoning)
            </div>
            <div className="space-y-2">
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
