import React, { useState } from 'react'
import {
  ComposedChart, AreaChart, Area, BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ReferenceLine, Cell,
} from 'recharts'
import {
  Brain, TrendingUp, Activity, FlaskConical, Sigma,
  ChevronDown, ChevronUp, AlertCircle, Target, Loader,
} from 'lucide-react'
import HelpBanner from '../components/HelpBanner'

const QAPI  = 'http://localhost:8000/api/quant'
const SAPI  = 'http://localhost:8000/api/stock'

// ── Shared helpers ────────────────────────────────────────────────────────────

function PanelCard({ icon: Icon, title, color = '#6366F1', children, loading }) {
  return (
    <div className="bg-white rounded-xl border border-border shadow-sm overflow-hidden">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border">
        <Icon size={13} style={{ color }} />
        <span className="font-semibold text-ink text-xs">{title}</span>
      </div>
      <div className="p-3">
        {loading
          ? <div className="h-24 flex items-center justify-center text-muted text-sm">
              <Loader size={14} className="animate-spin mr-2" /> Computing…
            </div>
          : children}
      </div>
    </div>
  )
}

function StatBox({ label, value, sub, color }) {
  return (
    <div className="bg-surface rounded-lg p-2">
      <div className="text-xs text-muted mb-0.5">{label}</div>
      <div className="font-bold text-ink text-sm leading-tight" style={color ? { color } : {}}>
        {value ?? '—'}
      </div>
      {sub && <div className="text-xs text-muted mt-0.5">{sub}</div>}
    </div>
  )
}

function SigBadge({ significant }) {
  return significant
    ? <span className="px-1.5 py-0.5 rounded text-xs font-semibold bg-green-100 text-green-700">p&lt;0.05 ✓</span>
    : <span className="px-1.5 py-0.5 rounded text-xs font-semibold bg-surface text-muted">not sig.</span>
}

function ErrorBox({ msg }) {
  return (
    <div className="flex items-center gap-2 text-red-600 text-sm bg-red-50 rounded-lg p-3">
      <AlertCircle size={14} className="flex-shrink-0" />
      <span>{msg}</span>
    </div>
  )
}

const fmt2 = v => (typeof v === 'number' ? v.toFixed(2) : '—')
const fmt4 = v => (typeof v === 'number' ? v.toFixed(4) : '—')

// ── 0. Decision Panel (combined cycle + quant) ────────────────────────────────

const STAGE_SCORE  = { Accumulation: 0.8, Markup: 1.0, Distribution: -0.5, Markdown: -1.0 }
const HMM_SCORE    = { Markup: 1.0, Accumulation: 0.5, 'High Volatility': 0, Bear: -1.0 }
const DIR_SCORE    = { BULLISH: 0.5, FLAT: 0, BEARISH: -0.5 }

function scoreToVerdict(score) {
  if (score >= 2.0) return { label: 'STRONG BUY',  color: '#16A34A', bg: 'bg-green-100',  border: 'border-green-300' }
  if (score >= 1.0) return { label: 'BUY',          color: '#22C55E', bg: 'bg-green-50',   border: 'border-green-200' }
  if (score >= -0.5)return { label: 'NEUTRAL',      color: '#6366F1', bg: 'bg-indigo-50',  border: 'border-indigo-200' }
  if (score >= -1.5)return { label: 'SELL',          color: '#F59E0B', bg: 'bg-amber-50',   border: 'border-amber-200' }
  return               { label: 'STRONG SELL',  color: '#DC2626', bg: 'bg-red-50',     border: 'border-red-200' }
}

function DecisionPanel({ ticker }) {
  const [state, setState] = useState({ data: null, loading: false, error: null })

  async function runAnalysis() {
    setState({ data: null, loading: true, error: null })
    try {
      const [cycleRes, quantRes] = await Promise.all([
        fetch(`${SAPI}/${ticker}/cycle`).then(r => r.json()),
        fetch(`${QAPI}/${ticker}/full`).then(r => r.json()),
      ])
      setState({ data: { cycle: cycleRes, quant: quantRes }, loading: false, error: null })
    } catch (e) {
      setState({ data: null, loading: false, error: e.message })
    }
  }

  const { data, loading, error } = state

  // Build score breakdown from loaded data
  let score = 0
  const breakdown = []
  if (data) {
    const { cycle, quant } = data

    // Wyckoff stage
    const stage = cycle?.stage
    const stageS = STAGE_SCORE[stage] ?? 0
    score += stageS
    breakdown.push({ label: 'Wyckoff Stage', value: stage ?? '—', delta: stageS,
      color: { Accumulation:'#6366F1', Markup:'#22C55E', Distribution:'#F59E0B', Markdown:'#DC2626' }[stage] })

    // HMM
    const hmmState = quant?.hmm?.current_state
    const hmmConf  = quant?.hmm?.confidence ?? 0
    const hmmS = (HMM_SCORE[hmmState] ?? 0) * (hmmConf / 100)
    score += hmmS
    breakdown.push({ label: 'HMM Regime', value: hmmState ? `${hmmState} (${hmmConf}%)` : '—',
      delta: hmmS, color: quant?.hmm?.current_color })

    // O-U z-score
    const z = quant?.mean_reversion?.zscore?.current_z
    const ouSig = quant?.mean_reversion?.zscore?.signal
    const ouS = z != null ? (z < -2 ? 1.0 : z < -0.5 ? 0.3 : z > 2 ? -1.0 : z > 0.5 ? -0.3 : 0) : 0
    score += ouS
    breakdown.push({ label: 'O-U Z-Score', value: z != null ? `z=${z.toFixed(2)} (${ouSig})` : '—',
      delta: ouS, color: ouS > 0 ? '#22C55E' : ouS < 0 ? '#DC2626' : '#6366F1' })

    // Kalman trend
    const dir = quant?.kalman?.direction
    const dirS = DIR_SCORE[dir] ?? 0
    score += dirS
    breakdown.push({ label: 'Kalman Trend', value: dir ?? '—',
      delta: dirS, color: quant?.kalman?.direction_color })

    // IC quality boost
    const sigSigs = quant?.signal_quality?.significant_signals ?? 0
    const icBoost = (sigSigs / 8) * 0.5
    score += icBoost
    breakdown.push({ label: 'Signal IC Quality', value: `${sigSigs}/8 significant`,
      delta: icBoost, color: sigSigs >= 4 ? '#22C55E' : '#6b7280' })
  }

  const verdict = scoreToVerdict(score)
  const scoreBar = Math.max(0, Math.min(100, (score + 3.5) / 7 * 100))

  return (
    <div className={`rounded-xl border shadow-sm overflow-hidden ${data ? verdict.border : 'border-border'} bg-white`}>
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border">
        <Target size={13} style={{ color: '#6366F1' }} />
        <span className="font-semibold text-ink text-xs">Combined Decision — Cycle + Quant Consensus</span>
      </div>
      <div className="p-3">
        {!data && !loading && !error && (
          <div className="flex items-center justify-between">
            <div className="text-sm text-muted max-w-lg">
              Combines Wyckoff cycle stage, HMM regime, O-U z-score, Kalman velocity, and IC signal quality
              into a single weighted verdict. Fetches cycle + all 5 quant models simultaneously.
            </div>
            <button onClick={runAnalysis}
              className="ml-4 flex-shrink-0 px-5 py-2.5 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary/90">
              Run Full Analysis
            </button>
          </div>
        )}
        {loading && (
          <div className="flex items-center gap-3 text-muted text-sm">
            <Loader size={16} className="animate-spin" />
            Running 5 models + cycle analysis — this takes ~10s…
          </div>
        )}
        {error && <ErrorBox msg={error} />}
        {data && (
          <div className="space-y-3">
            {/* Verdict */}
            <div className={`rounded-lg p-4 border ${verdict.border} ${verdict.bg} flex items-center justify-between`}>
              <div>
                <div className="text-base font-bold" style={{ color: verdict.color }}>{verdict.label}</div>
                <div className="text-xs text-muted mt-1">
                  Composite score: {score.toFixed(2)} / 3.5 max
                </div>
              </div>
              <div className="text-right">
                <button onClick={runAnalysis} className="text-xs text-primary hover:underline">Refresh</button>
              </div>
            </div>

            {/* Score bar */}
            <div>
              <div className="flex justify-between text-xs text-muted mb-1">
                <span>Strong Sell</span><span>Neutral</span><span>Strong Buy</span>
              </div>
              <div className="h-3 bg-surface rounded-full overflow-hidden relative">
                <div className="absolute inset-0 flex">
                  <div className="w-2/7 bg-red-200 opacity-60 rounded-l-full" />
                  <div className="w-1/7 bg-amber-200 opacity-60" />
                  <div className="w-2/7 bg-indigo-100 opacity-60" />
                  <div className="w-1/7 bg-green-200 opacity-60" />
                  <div className="w-1/7 bg-green-300 opacity-60 rounded-r-full" />
                </div>
                <div className="absolute top-0.5 w-2 h-2 rounded-full bg-ink shadow"
                  style={{ left: `${scoreBar}%`, transform: 'translateX(-50%)' }} />
              </div>
            </div>

            {/* Breakdown */}
            <div className="space-y-2">
              <div className="text-xs font-semibold text-muted uppercase">Score Breakdown</div>
              {breakdown.map(({ label, value, delta, color }) => (
                <div key={label} className="flex items-center gap-3 bg-surface rounded-lg px-3 py-2">
                  <div className="w-32 text-xs text-muted">{label}</div>
                  <div className="flex-1 text-xs font-medium text-ink" style={color ? { color } : {}}>{value}</div>
                  <div className="text-xs font-mono font-semibold w-14 text-right"
                    style={{ color: delta > 0 ? '#22C55E' : delta < 0 ? '#DC2626' : '#6b7280' }}>
                    {delta > 0 ? '+' : ''}{delta.toFixed(2)}
                  </div>
                </div>
              ))}
              <div className="flex items-center gap-3 bg-surface rounded-lg px-3 py-2 border-t border-border">
                <div className="w-32 text-xs font-semibold text-ink">Total Score</div>
                <div className="flex-1" />
                <div className="text-sm font-bold w-14 text-right" style={{ color: verdict.color }}>
                  {score.toFixed(2)}
                </div>
              </div>
            </div>

            {/* Cycle stage quick view */}
            {data.cycle?.stage && (
              <div className="grid grid-cols-3 gap-2 text-xs">
                <div className="bg-surface rounded p-2">
                  <div className="text-muted">Wyckoff Stage</div>
                  <div className="font-semibold mt-0.5">{data.cycle.stage}</div>
                </div>
                <div className="bg-surface rounded p-2">
                  <div className="text-muted">Cycle Confidence</div>
                  <div className="font-semibold mt-0.5">{data.cycle.confidence?.toFixed(1) ?? '—'}%</div>
                </div>
                <div className="bg-surface rounded p-2">
                  <div className="text-muted">HMM + Kalman</div>
                  <div className="font-semibold mt-0.5">
                    {data.quant?.hmm?.current_state ?? '—'} · {data.quant?.kalman?.direction ?? '—'}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ── 1. HMM Panel ──────────────────────────────────────────────────────────────

const STATE_COLORS = { Bear: '#DC2626', 'High Volatility': '#F59E0B', Accumulation: '#6366F1', Markup: '#22C55E' }

function HMMPanel({ ticker }) {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)

  async function load() {
    setLoading(true); setError(null)
    try {
      const j = await fetch(`${QAPI}/${ticker}/hmm`).then(r => r.json())
      if (j.error) throw new Error(j.error)
      setData(j)
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  return (
    <PanelCard icon={Brain} title="Hidden Markov Model — Regime" color="#6366F1" loading={loading}>
      {!data && !error && (
        <div className="text-center space-y-2">
          <p className="text-xs text-muted">4-state HMM via Baum-Welch. Viterbi decoding reveals most probable state sequence.</p>
          <button onClick={load} className="px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary/90">Run HMM</button>
        </div>
      )}
      {error && <ErrorBox msg={error} />}
      {data && (
        <div className="space-y-3">
          <div className="flex items-start gap-3">
            <div className="px-3 py-1.5 rounded-lg text-white font-bold text-sm flex-shrink-0"
              style={{ background: data.current_color ?? '#6366F1' }}>
              {data.current_state}
            </div>
            <div>
              <div className="text-xs text-ink">{data.action}</div>
              <div className="text-xs text-muted mt-0.5">Confidence {data.confidence}% · LL/obs {data.log_likelihood_per_obs}</div>
            </div>
          </div>

          {/* State probabilities */}
          <div className="space-y-1.5">
            <div className="text-xs font-semibold text-muted uppercase">Posterior State Probabilities</div>
            {Object.entries(data.state_probabilities ?? {}).map(([state, prob]) => (
              <div key={state} className="flex items-center gap-2">
                <div className="w-24 text-xs text-ink truncate">{state}</div>
                <div className="flex-1 h-3 bg-surface rounded-full overflow-hidden">
                  <div className="h-full rounded-full" style={{ width: `${prob}%`, background: STATE_COLORS[state] ?? '#6366F1' }} />
                </div>
                <div className="w-9 text-right text-xs font-medium text-ink">{prob}%</div>
              </div>
            ))}
          </div>

          {/* Expected durations */}
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(data.expected_durations_days ?? {}).map(([state, days]) => (
              <StatBox key={state} label={state} value={`${days}d`} color={STATE_COLORS[state]} />
            ))}
          </div>

          {/* Transition matrix */}
          {data.transition_matrix && data.state_labels && (
            <div>
              <div className="text-xs font-semibold text-muted uppercase mb-1.5">Transition Matrix A[i→j]</div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr>
                      <th className="text-left text-muted p-1 font-normal">From╲To</th>
                      {data.state_labels.map(l => (
                        <th key={l} className="text-center p-1 font-medium" style={{ color: STATE_COLORS[l] }}>
                          {l.split(' ')[0]}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.transition_matrix.map((row, i) => (
                      <tr key={i}>
                        <td className="p-1 font-medium text-xs" style={{ color: STATE_COLORS[data.state_labels[i]] }}>
                          {data.state_labels[i].split(' ')[0]}
                        </td>
                        {row.map((val, j) => (
                          <td key={j} className="text-center p-1 font-mono rounded text-xs"
                            style={{
                              background: i === j ? `${STATE_COLORS[data.state_labels[i]] ?? '#6366F1'}22` : 'transparent',
                              fontWeight: i === j ? 700 : 400,
                            }}>
                            {(val * 100).toFixed(1)}%
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="text-xs text-muted mt-1">Diagonal = persistence. Off-diagonal = switching probability.</p>
              </div>
            </div>
          )}

          {/* Price history with regime coloring */}
          {data.history?.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-muted uppercase mb-1">Viterbi State History</div>
              <ResponsiveContainer width="100%" height={110}>
                <AreaChart data={data.history}>
                  <XAxis dataKey="date" tick={{ fontSize: 9 }} tickFormatter={d => d.slice(5)} interval="preserveStartEnd" />
                  <YAxis domain={['auto', 'auto']} tick={{ fontSize: 9 }} width={45} />
                  <Tooltip formatter={(v) => [typeof v === 'number' ? v.toFixed(2) : v, 'price']} contentStyle={{ fontSize: 11 }} />
                  <Area type="monotone" dataKey="price" stroke="#6366F1" fill="#6366F122" strokeWidth={1.5} dot={false} />
                </AreaChart>
              </ResponsiveContainer>
              <div className="flex flex-wrap gap-3 mt-1.5">
                {Object.entries(STATE_COLORS).map(([s, c]) => (
                  <span key={s} className="flex items-center gap-1 text-xs text-muted">
                    <span className="w-2 h-2 rounded-full inline-block" style={{ background: c }} />{s}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </PanelCard>
  )
}

// ── 2. Mean Reversion Panel ───────────────────────────────────────────────────

const Z_COLORS = { 'LONG': '#16A34A', 'WATCH LONG': '#22C55E', NEUTRAL: '#6366F1', 'WATCH SHORT': '#F59E0B', SHORT: '#DC2626' }

function MeanReversionPanel({ ticker }) {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)

  async function load() {
    setLoading(true); setError(null)
    try {
      const j = await fetch(`${QAPI}/${ticker}/mean-revert`).then(r => r.json())
      if (j.error) throw new Error(j.error)
      setData(j)
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  return (
    <PanelCard icon={Activity} title="Ornstein-Uhlenbeck — Mean Reversion" color="#22C55E" loading={loading}>
      {!data && !error && (
        <div className="text-center space-y-2">
          <p className="text-xs text-muted">dX = θ(μ−X)dt + σdW. ADF stationarity test. Rolling z-score entry signal.</p>
          <button onClick={load} className="px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary/90">Run O-U Analysis</button>
        </div>
      )}
      {error && <ErrorBox msg={error} />}
      {data && (
        <div className="space-y-3">
          {/* ADF */}
          <div className={`rounded-lg p-2.5 ${data.adf?.stationary ? 'bg-green-50 border border-green-200' : 'bg-amber-50 border border-amber-200'}`}>
            <div className="flex items-center justify-between">
              <span className="font-semibold text-sm">
                {data.adf?.stationary ? '✓ Stationary — Reversion Confirmed' : '✗ Unit Root — Random Walk'}
              </span>
              <span className="text-xs font-mono text-muted">p={data.adf?.p_value}</span>
            </div>
            <div className="text-xs text-muted mt-0.5">
              ADF {data.adf?.adf_statistic} | 5% critical {data.adf?.critical_5pct} | {data.adf?.mean_reversion_strength}
            </div>
          </div>

          {/* O-U params */}
          {data.ou_params?.mean_reverting !== false ? (
            <div className="grid grid-cols-2 gap-2">
              <StatBox label="Half-Life" value={data.ou_params?.half_life_days != null ? `${data.ou_params.half_life_days}d` : '—'} sub="ln(2)/θ — 50% decay" />
              <StatBox label="Speed θ" value={fmt4(data.ou_params?.theta)} sub="Mean reversion rate" />
              <StatBox label="Equilibrium μ" value={data.ou_params?.mu != null ? `$${data.ou_params.mu.toFixed(2)}` : '—'} sub="Long-run mean" />
              <StatBox label="Noise σ" value={fmt4(data.ou_params?.sigma)} sub="Residual std dev" />
            </div>
          ) : (
            <div className="text-xs text-amber-700 bg-amber-50 rounded p-2">{data.ou_params?.message}</div>
          )}

          {/* Z-score gauge */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-semibold text-muted uppercase">Z-Score Signal</span>
              <span className="px-2 py-0.5 rounded text-xs font-bold text-white"
                style={{ background: Z_COLORS[data.zscore?.signal] ?? '#6366F1' }}>
                {data.zscore?.signal}
              </span>
            </div>
            <div className="relative h-5 bg-surface rounded-full overflow-hidden mb-1">
              <div className="absolute inset-0 flex">
                {['#16A34A44','#22C55E33','#f3f4f6','#F59E0B33','#DC262644'].map((bg, i) => (
                  <div key={i} className="flex-1" style={{ background: bg }} />
                ))}
              </div>
              <div className="absolute top-0.5 w-1 h-4 rounded bg-ink shadow"
                style={{ left: `${Math.max(2, Math.min(98, ((data.zscore?.current_z ?? 0) + 4) / 8 * 100))}%`, transform: 'translateX(-50%)' }} />
            </div>
            <div className="flex justify-between text-xs text-muted mb-1">
              <span>-4σ</span><span>-2σ</span><span>0</span><span>+2σ</span><span>+4σ</span>
            </div>
            <div className="text-center text-base font-bold" style={{ color: Z_COLORS[data.zscore?.signal] ?? '#6366F1' }}>
              z = {data.zscore?.current_z ?? '—'}
            </div>
          </div>

          {/* Bands */}
          <div className="grid grid-cols-3 gap-1.5 text-xs text-center">
            <div className="bg-green-50 rounded p-1.5"><div className="font-semibold text-green-700">Entry</div>|z| &gt; 2.0</div>
            <div className="bg-surface rounded p-1.5"><div className="font-semibold text-muted">Exit</div>|z| &lt; 0.5</div>
            <div className="bg-red-50 rounded p-1.5"><div className="font-semibold text-red-700">Stop</div>|z| &gt; 3.0</div>
          </div>

          {/* Z-score chart */}
          {data.zscore?.history?.length > 0 && (
            <ResponsiveContainer width="100%" height={90}>
              <LineChart data={data.zscore.history}>
                <XAxis dataKey="date" tick={{ fontSize: 9 }} tickFormatter={d => d.slice(5)} interval="preserveStartEnd" />
                <YAxis domain={[-4, 4]} tick={{ fontSize: 9 }} width={30} />
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <Tooltip formatter={v => [typeof v === 'number' ? v.toFixed(3) : v, 'z']} contentStyle={{ fontSize: 11 }} />
                <ReferenceLine y={2} stroke="#DC2626" strokeDasharray="4 2" />
                <ReferenceLine y={-2} stroke="#22C55E" strokeDasharray="4 2" />
                <ReferenceLine y={0} stroke="#6366F1" />
                <Line type="monotone" dataKey="z" stroke="#6366F1" dot={false} strokeWidth={1.5} />
              </LineChart>
            </ResponsiveContainer>
          )}
          <div className="text-xs text-muted bg-surface rounded p-2">{data.summary}</div>
        </div>
      )}
    </PanelCard>
  )
}

// ── 3. Kalman Panel ───────────────────────────────────────────────────────────

function KalmanPanel({ ticker }) {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)

  async function load() {
    setLoading(true); setError(null)
    try {
      const j = await fetch(`${QAPI}/${ticker}/kalman`).then(r => r.json())
      if (j.error) throw new Error(j.error)
      setData(j)
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  return (
    <PanelCard icon={TrendingUp} title="Kalman Filter — Trend Estimation" color="#F59E0B" loading={loading}>
      {!data && !error && (
        <div className="text-center space-y-2">
          <p className="text-xs text-muted">State [level, velocity]. K = P·H'/(H·P·H'+R). Smoothed price removes noise; velocity = trend speed.</p>
          <button onClick={load} className="px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary/90">Run Kalman</button>
        </div>
      )}
      {error && <ErrorBox msg={error} />}
      {data && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-2">
            <StatBox label="Trend" value={data.direction} color={data.direction_color} />
            <StatBox label="Velocity (ann.)" value={`${(data.trend_velocity_annualized_pct ?? 0) > 0 ? '+' : ''}${fmt2(data.trend_velocity_annualized_pct)}%/yr`} color={data.direction_color} />
            <StatBox label="Smoothed Price" value={`$${fmt2(data.smoothed_price)}`} sub={`±$${fmt2(data.uncertainty_1sigma)} (1σ)`} />
            <StatBox label="Price vs Kalman" value={`${(data.price_vs_smooth_pct ?? 0) > 0 ? '+' : ''}${fmt2(data.price_vs_smooth_pct)}%`}
              color={(data.price_vs_smooth_pct ?? 0) > 0 ? '#22C55E' : '#DC2626'} />
          </div>

          {/* 1σ band labels */}
          <div className="flex gap-2 text-xs">
            <div className="flex-1 bg-green-50 rounded p-2 text-center">
              <div className="text-green-700 font-semibold">Upper 1σ</div>
              <div className="text-ink">${fmt2(data.upper_band)}</div>
            </div>
            <div className="flex-1 bg-indigo-50 rounded p-2 text-center">
              <div className="text-indigo-700 font-semibold">Kalman</div>
              <div className="text-ink">${fmt2(data.smoothed_price)}</div>
            </div>
            <div className="flex-1 bg-red-50 rounded p-2 text-center">
              <div className="text-red-700 font-semibold">Lower 1σ</div>
              <div className="text-ink">${fmt2(data.lower_band)}</div>
            </div>
          </div>

          {/* Price + smoothed + band — ComposedChart */}
          {data.history?.length > 0 && (
            <ResponsiveContainer width="100%" height={140}>
              <ComposedChart data={data.history}>
                <XAxis dataKey="date" tick={{ fontSize: 9 }} tickFormatter={d => d.slice(5)} interval="preserveStartEnd" />
                <YAxis domain={['auto', 'auto']} tick={{ fontSize: 9 }} width={50} />
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <Tooltip formatter={(v, n) => [`$${typeof v === 'number' ? v.toFixed(2) : v}`, n]} contentStyle={{ fontSize: 11 }} />
                {/* 1σ band as shaded area between upper and lower */}
                <Area type="monotone" dataKey="upper_1sigma" fill="#6366F118" stroke="none" name="Upper 1σ" legendType="none" />
                <Area type="monotone" dataKey="lower_1sigma" fill="#ffffff" stroke="none" name="Lower 1σ" legendType="none" />
                <Line type="monotone" dataKey="price" stroke="#cbd5e1" dot={false} strokeWidth={1} name="Price" />
                <Line type="monotone" dataKey="smoothed" stroke="#6366F1" dot={false} strokeWidth={2} name="Kalman" />
              </ComposedChart>
            </ResponsiveContainer>
          )}

          {/* Velocity bars */}
          {data.history?.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-muted uppercase mb-1">Trend Velocity per Day</div>
              <ResponsiveContainer width="100%" height={65}>
                <BarChart data={data.history.slice(-30)}>
                  <XAxis dataKey="date" hide />
                  <YAxis tick={{ fontSize: 9 }} width={40} />
                  <ReferenceLine y={0} stroke="#6366F1" />
                  <Tooltip formatter={v => [typeof v === 'number' ? v.toFixed(4) : v, 'velocity']} contentStyle={{ fontSize: 11 }} />
                  <Bar dataKey="velocity" radius={[2, 2, 0, 0]}>
                    {data.history.slice(-30).map((entry, i) => (
                      <Cell key={i} fill={(entry.velocity ?? 0) >= 0 ? '#22C55E' : '#EF4444'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
          <div className="text-xs text-muted bg-surface rounded p-2">{data.message}</div>
        </div>
      )}
    </PanelCard>
  )
}

// ── 4. Signal Quality Panel ───────────────────────────────────────────────────

const GRADE_COLOR = { A: '#22C55E', B: '#6366F1', C: '#F59E0B', D: '#EF4444' }

function SignalQualityPanel({ ticker }) {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)
  const [expanded, setExpanded] = useState(false)

  async function load() {
    setLoading(true); setError(null)
    try {
      const j = await fetch(`${QAPI}/${ticker}/signal-quality`).then(r => r.json())
      if (j.error) throw new Error(j.error)
      setData(j)
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  return (
    <PanelCard icon={FlaskConical} title="Signal Quality — IC · Hurst · Ljung-Box" color="#EF4444" loading={loading}>
      {!data && !error && (
        <div className="text-center space-y-2">
          <p className="text-xs text-muted">IC = corr(signal, forward_return). Ljung-Box autocorrelation. Hurst via R/S analysis.</p>
          <button onClick={load} className="px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary/90">Run Signal Quality</button>
        </div>
      )}
      {error && <ErrorBox msg={error} />}
      {data && (
        <div className="space-y-3">
          <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-2.5">
            <div className="font-semibold text-indigo-800 text-sm">{data.market_efficiency_verdict}</div>
            <div className="text-xs text-indigo-600 mt-0.5">{data.significant_signals}/{data.total_signals} signals p&lt;0.05</div>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div className="bg-surface rounded-lg p-3">
              <div className="text-xs text-muted">Hurst Exponent</div>
              <div className="text-base font-bold text-ink mt-0.5">{data.hurst?.hurst ?? '—'}</div>
              <div className="text-xs font-medium" style={{
                color: (data.hurst?.hurst ?? 0.5) > 0.55 ? '#22C55E' : (data.hurst?.hurst ?? 0.5) < 0.45 ? '#6366F1' : '#6b7280'
              }}>{data.hurst?.regime}</div>
              <div className="text-xs text-muted mt-1 leading-relaxed">{data.hurst?.implication}</div>
            </div>
            <div className="bg-surface rounded-lg p-3">
              <div className="text-xs text-muted">Ljung-Box Test</div>
              <div className={`text-sm font-semibold mt-0.5 ${data.ljung_box?.predictable ? 'text-green-700' : 'text-muted'}`}>
                {data.ljung_box?.predictable ? '✓ Autocorrelated' : '✗ Random'}
              </div>
              <div className="text-xs text-muted mt-1">Q={data.ljung_box?.Q_statistic} p={data.ljung_box?.p_value}</div>
              <div className="text-xs text-muted">
                Dominant lag: {data.ljung_box?.dominant_lag ?? '—'}d (ρ={data.ljung_box?.dominant_autocorr ?? '—'})
              </div>
            </div>
          </div>

          {/* IC table */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <div className="text-xs font-semibold text-muted uppercase">Signal IC vs Forward Returns</div>
              <button onClick={() => setExpanded(e => !e)} className="text-xs text-primary flex items-center gap-0.5">
                {expanded ? 'Less' : 'Details'} {expanded ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
              </button>
            </div>
            <div className="space-y-1">
              {(data.signal_ic?.summary ?? []).map(row => (
                <div key={row.signal} className="flex items-center gap-2 bg-surface rounded px-2 py-1.5">
                  <div className="w-5 h-5 rounded text-xs font-bold flex items-center justify-center text-white flex-shrink-0"
                    style={{ background: GRADE_COLOR[row.grade] ?? '#6b7280' }}>
                    {row.grade}
                  </div>
                  <div className="flex-1 text-xs text-ink truncate">{row.signal}</div>
                  <div className="text-xs font-mono font-semibold"
                    style={{ color: (row.ic ?? 0) >= 0 ? '#22C55E' : '#EF4444' }}>
                    {row.ic != null ? `IC=${row.ic.toFixed(4)}` : '—'}
                  </div>
                  {expanded && (
                    <div className="text-xs text-muted">t={row.t_stat != null ? row.t_stat.toFixed(2) : '—'} {row.best_horizon}</div>
                  )}
                  <SigBadge significant={row.significant} />
                </div>
              ))}
            </div>
            <div className="text-xs text-muted mt-2 bg-surface rounded p-2 leading-relaxed">{data.signal_ic?.interpretation}</div>
          </div>

          {/* Autocorrelation bars */}
          {data.ljung_box?.autocorrelations && Object.keys(data.ljung_box.autocorrelations).length > 0 && (
            <div>
              <div className="text-xs font-semibold text-muted uppercase mb-1">Return Autocorrelations ρ(lag)</div>
              <ResponsiveContainer width="100%" height={75}>
                <BarChart data={Object.entries(data.ljung_box.autocorrelations).map(([k, v]) => ({ lag: `${k}d`, rho: typeof v === 'number' ? v : 0 }))}>
                  <XAxis dataKey="lag" tick={{ fontSize: 9 }} />
                  <YAxis domain={[-0.3, 0.3]} tick={{ fontSize: 9 }} width={30} />
                  <ReferenceLine y={0} stroke="#6366F1" />
                  <Tooltip formatter={v => [typeof v === 'number' ? v.toFixed(4) : '—', 'ρ']} contentStyle={{ fontSize: 11 }} />
                  <Bar dataKey="rho" radius={[2, 2, 0, 0]}>
                    {Object.values(data.ljung_box.autocorrelations).map((v, i) => (
                      <Cell key={i} fill={(typeof v === 'number' ? v : 0) >= 0 ? '#22C55E' : '#EF4444'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}
    </PanelCard>
  )
}

// ── 5. Kelly Panel ────────────────────────────────────────────────────────────

const STAGE_COLOR = { Markup: '#22C55E', Accumulation: '#6366F1', Distribution: '#F59E0B', Markdown: '#EF4444' }

function KellyPanel({ ticker }) {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)
  const [balance, setBalance] = useState('100000')

  async function load() {
    setLoading(true); setError(null)
    try {
      const j = await fetch(`${QAPI}/${ticker}/kelly`).then(r => r.json())
      if (j.error) throw new Error(j.error)
      setData(j)
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  const ck  = data?.continuous_kelly
  const bal = parseFloat(balance) || 0

  return (
    <PanelCard icon={Sigma} title="Kelly Criterion — Optimal Position Sizing" color="#22C55E" loading={loading}>
      {!data && !error && (
        <div className="text-center space-y-2">
          <p className="text-xs text-muted">f* = μ/σ² (continuous) · (p·b−q)/b (discrete). Half-Kelly = Renaissance-style safety margin.</p>
          <button onClick={load} className="px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium hover:bg-primary/90">Compute Kelly</button>
        </div>
      )}
      {error && <ErrorBox msg={error} />}
      {data && (
        <div className="space-y-3">
          {ck && !ck.error && (
            <div className="space-y-3">
              <div className="text-xs font-semibold text-muted uppercase">Continuous Kelly (f* = μ/σ²)</div>
              <div className="bg-surface rounded-lg p-2.5 font-mono text-xs text-muted">
                {ck.formula}
              </div>
              <div className="grid grid-cols-3 gap-2">
                <StatBox label="Full Kelly" value={`${((ck.kelly_full ?? 0) * 100).toFixed(1)}%`} color="#EF4444" sub="~50% max drawdown" />
                <StatBox label="Half-Kelly ★" value={`${(Math.max(0, ck.kelly_half ?? 0) * 100).toFixed(1)}%`} color="#22C55E" sub="Renaissance-style" />
                <StatBox label="Sharpe (ann.)" value={fmt2(ck.sharpe_annual)} />
              </div>
              <div className="flex items-center gap-2">
                <SigBadge significant={ck.return_significant} />
                <span className="text-xs text-muted">t={fmt2(ck.t_stat)} · p={ck.p_value} · n={ck.n_observations}d</span>
              </div>

              {/* Calculator */}
              <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-3">
                <div className="text-xs font-semibold text-indigo-700 mb-2">Dollar Position Calculator</div>
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs text-muted whitespace-nowrap">Account $</span>
                  <input type="number" value={balance} onChange={e => setBalance(e.target.value)}
                    className="flex-1 border border-border rounded px-2 py-1 text-xs text-gray-900 bg-white" />
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div><span className="text-muted">Full Kelly: </span>
                    <span className="font-bold text-ink">${Math.round(bal * Math.max(0, ck.kelly_full ?? 0)).toLocaleString()}</span></div>
                  <div><span className="text-muted">Half-Kelly: </span>
                    <span className="font-bold text-green-700">${Math.round(bal * Math.max(0, ck.kelly_half ?? 0)).toLocaleString()}</span></div>
                </div>
              </div>
            </div>
          )}
          {ck?.error && <ErrorBox msg={ck.error} />}

          {/* Stage Kelly */}
          {data.stage_kelly && (
            <div>
              <div className="text-xs font-semibold text-muted uppercase mb-2">Per-Stage Kelly (Walk-Forward Backtest)</div>
              <div className="grid grid-cols-2 gap-2">
                {Object.entries(data.stage_kelly).map(([stage, sk]) => (
                  <div key={stage} className="bg-surface rounded-lg p-3">
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="font-semibold text-sm" style={{ color: STAGE_COLOR[stage] }}>{stage}</span>
                      {!sk.message && (
                        <span className="text-xs font-semibold" style={{ color: (sk.kelly_half ?? 0) > 0 ? '#22C55E' : '#EF4444' }}>
                          {((sk.kelly_half ?? 0) * 100).toFixed(1)}%
                        </span>
                      )}
                    </div>
                    {sk.message
                      ? <div className="text-xs text-muted">{sk.message}</div>
                      : <div className="grid grid-cols-2 gap-x-3 text-xs">
                          <div><span className="text-muted">Win%: </span><span className="font-medium">{((sk.win_rate ?? 0) * 100).toFixed(1)}%</span></div>
                          <div><span className="text-muted">R:R: </span><span className="font-medium">{fmt2(sk.payoff_ratio)}</span></div>
                          <div><span className="text-muted">Edge: </span>
                            <span className="font-medium" style={{ color: (sk.edge ?? 0) > 0 ? '#22C55E' : '#EF4444' }}>{fmt4(sk.edge)}</span></div>
                          <div><span className="text-muted">n: </span><span className="font-medium">{sk.n}</span></div>
                        </div>
                    }
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="text-xs text-muted bg-surface rounded p-2 leading-relaxed">{data.simons_rule}</div>
        </div>
      )}
    </PanelCard>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function QuantEngine() {
  const [ticker, setTicker] = useState('AAPL')
  const [input, setInput]   = useState('AAPL')

  function handleSearch(e) {
    e.preventDefault()
    const t = input.trim().toUpperCase()
    if (t) { setTicker(t); setInput(t) }
  }

  return (
    <div className="p-3 space-y-3">
      <HelpBanner
        pageKey="quant"
        title="Quant Engine — Jim Simons Stack"
        whatIsThis="Runs four classical quant models on one stock: Hidden Markov regime detection, Ornstein-Uhlenbeck mean reversion, Kalman filter trend, Information Coefficient signal quality, and Kelly position sizing."
        steps={[
          "Type a ticker (e.g. <b>SPY</b>) and load.",
          "Read the <b>HMM regime</b> — tells you the latent market state probability.",
          "Use the <b>Kelly fraction</b> as a sanity check on position size — never exceed <b>quarter-Kelly (25% of Kelly)</b>.",
        ]}
        tips={[
          "If <b>IC p-value > 0.05</b>, the signal is statistically noise — don't trade it.",
          "Quarter-Kelly is capped at <b>20%/trade</b> here on purpose — full Kelly is for theory, not real accounts.",
          "Use this page for <b>position sizing</b> after Dashboard / Cycle Detector tell you <i>what</i> to trade.",
        ]}
      />

      {/* Header */}
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-sm font-bold text-ink">Quant Engine</span>
        <span className="text-xs text-muted">HMM · O-U · Kalman · IC · Kelly</span>
        <form onSubmit={handleSearch} className="ml-auto flex gap-2 flex-shrink-0">
          <input
            type="text"
            className="input w-24"
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="Ticker"
            autoComplete="off"
            spellCheck={false}
          />
          <button type="submit"
            className="btn-primary text-xs">
            Analyze
          </button>
        </form>
      </div>

      {/* Method strip */}
      <div className="grid grid-cols-5 gap-2">
        {[
          { icon: Brain,        label: 'HMM',      sub: 'Baum-Welch · Viterbi',     color: '#6366F1' },
          { icon: Activity,     label: 'O-U',       sub: 'ADF · θ · half-life · z',  color: '#22C55E' },
          { icon: TrendingUp,   label: 'Kalman',    sub: '[level, velocity] · 1σ',   color: '#F59E0B' },
          { icon: FlaskConical, label: 'IC / Hurst',sub: 'Signal validation · LB',   color: '#EF4444' },
          { icon: Sigma,        label: 'Kelly f*',  sub: 'μ/σ² · half-Kelly',        color: '#0EA5E9' },
        ].map(({ icon: Icon, label, sub, color }) => (
          <div key={label} className="bg-white border border-border rounded-xl p-3 text-center shadow-sm">
            <Icon size={18} style={{ color }} className="mx-auto mb-1" />
            <div className="font-semibold text-ink text-sm">{label}</div>
            <div className="text-xs text-muted mt-0.5 leading-tight">{sub}</div>
          </div>
        ))}
      </div>

      {/* Combined decision — full width */}
      <DecisionPanel ticker={ticker} />

      {/* Individual panels */}
      <div className="grid grid-cols-2 gap-5">
        <HMMPanel           ticker={ticker} />
        <MeanReversionPanel ticker={ticker} />
        <KalmanPanel        ticker={ticker} />
        <SignalQualityPanel ticker={ticker} />
      </div>

      <KellyPanel ticker={ticker} />
    </div>
  )
}
