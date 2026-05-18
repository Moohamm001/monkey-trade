import React, { useState, useEffect, useCallback } from 'react'
import {
  Plus, X, CheckCircle, XCircle, Clock, TrendingUp, TrendingDown,
  BarChart2, BookOpen, RefreshCw, ChevronDown, ChevronUp,
  Target, Shield, Zap, Award, AlertTriangle, Bot,
} from 'lucide-react'
import { useApi } from '../hooks/useApi'
import HelpBanner from '../components/HelpBanner'

// ── helpers ───────────────────────────────────────────────────────────────────
const pct = v => v == null ? '—' : `${v > 0 ? '+' : ''}${v}%`
const dollar = v => v == null ? '—' : `${v >= 0 ? '+' : ''}$${Math.abs(v).toFixed(2)}`
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v))

const STAGE_COLORS = {
  accumulation: 'bg-blue-100 text-blue-800 border-blue-300',
  markup:       'bg-green-100 text-green-800 border-green-300',
  distribution: 'bg-amber-100 text-amber-800 border-amber-300',
  markdown:     'bg-red-100 text-red-800 border-red-300',
}

const STATUS_ICON = {
  open:         <Clock size={13} className="text-amber-500" />,
  closed_win:   <CheckCircle size={13} className="text-green-500" />,
  closed_loss:  <XCircle size={13} className="text-red-500" />,
  closed_manual:<X size={13} className="text-muted" />,
}

const REASONS = { stop_hit: '🛑 Stop hit', target_hit: '🎯 Target hit', manual: '✋ Manual' }

// ── Smart Money Score badge ───────────────────────────────────────────────────
// SMS is the bot's institutional alignment score (0-100). Aggregated from
// 6 sources: SEC Form 4 insiders, 13D/G activist filings, FINRA dark pool,
// options flow, congressional trades, CFTC COT futures positioning.
function smsClass(score) {
  if (score == null) return null
  if (score >= 80) return { bg: 'bg-green-700',   text: 'text-white',       label: 'EXTREME BULLISH' }
  if (score >= 65) return { bg: 'bg-green-500',   text: 'text-white',       label: 'BULLISH'         }
  if (score >= 45) return { bg: 'bg-gray-200',    text: 'text-ink',         label: 'NEUTRAL'         }
  if (score >= 30) return { bg: 'bg-amber-400',   text: 'text-white',       label: 'BEARISH'         }
  return                  { bg: 'bg-red-600',     text: 'text-white',       label: 'EXTREME BEARISH' }
}

function SmartMoneyBadge({ score, compact = false }) {
  if (score == null) return null
  const cls = smsClass(score)
  if (compact) {
    return (
      <span title={`Smart Money Score: ${score} — ${cls.label}`}
        className={`text-xs font-bold px-1.5 py-0.5 rounded ${cls.bg} ${cls.text}`}>
        🐋 {Math.round(score)}
      </span>
    )
  }
  return (
    <div className={`rounded-lg p-2 ${cls.bg} ${cls.text}`}>
      <div className="text-xs opacity-90 flex items-center gap-1">🐋 Smart Money</div>
      <div className="font-mono font-extrabold text-lg leading-none">{Math.round(score)}</div>
      <div className="text-xs opacity-90 font-semibold mt-0.5">{cls.label}</div>
    </div>
  )
}

// ── sub-components ────────────────────────────────────────────────────────────

// Lightweight markdown renderer: converts **bold** + *italic* in a paragraph
// to <strong>/<em>. Splits the notes string on blank lines.
function MdInline({ text }) {
  const parts = []
  let i = 0
  const regex = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g
  let m, last = 0, key = 0
  while ((m = regex.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index))
    const tok = m[0]
    if (tok.startsWith('**'))      parts.push(<strong key={key++} className="text-ink font-bold">{tok.slice(2, -2)}</strong>)
    else if (tok.startsWith('`'))  parts.push(<code key={key++} className="text-xs bg-surface px-1 rounded font-mono">{tok.slice(1, -1)}</code>)
    else                           parts.push(<em key={key++} className="text-sub italic">{tok.slice(1, -1)}</em>)
    last = m.index + tok.length
  }
  if (last < text.length) parts.push(text.slice(last))
  return <>{parts}</>
}

function BotReasoning({ notes, technical }) {
  const [showTech, setShowTech] = useState(false)
  if (!notes) return null
  const paragraphs = notes.split(/\n\n+/).map(p => p.trim()).filter(Boolean)
  return (
    <div className="bg-primary-light/30 border border-primary/20 rounded-lg p-3 space-y-2">
      <div className="flex items-center gap-1.5 text-xs font-bold text-primary uppercase tracking-wide">
        <Bot size={12} /> Why the bot chose this
      </div>
      <div className="space-y-2 text-sm text-ink leading-relaxed">
        {paragraphs.map((p, i) => (
          <p key={i} className={p.startsWith('*') && !p.startsWith('**')
            ? 'text-xs text-sub italic'
            : ''}>
            <MdInline text={p} />
          </p>
        ))}
      </div>
      {technical && (
        <>
          <button
            onClick={() => setShowTech(v => !v)}
            className="text-xs font-semibold text-primary hover:underline flex items-center gap-1"
          >
            {showTech ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
            {showTech ? 'Hide technical breakdown' : 'Show technical breakdown'}
          </button>
          {showTech && (
            <div className="text-xs text-sub bg-white/60 border border-border rounded p-2 font-mono leading-relaxed whitespace-pre-wrap">
              {technical}
            </div>
          )}
        </>
      )}
    </div>
  )
}

function PnlBar({ entry, current, stop, target, direction = 'long' }) {
  if (!entry || !current) return null
  const full = Math.abs((target ?? entry * 1.1) - (stop ?? entry * 0.95))
  const low  = Math.min(stop ?? entry * 0.95, target ?? entry * 1.1)

  const entryPx = clamp((entry - low) / full * 100, 0, 100)
  const curPx   = clamp((current - low) / full * 100, 0, 100)
  const isUp    = current >= entry

  return (
    <div className="mt-2">
      <div className="relative h-2.5 bg-gray-100 rounded-full overflow-hidden">
        {stop && <div className="absolute left-0 top-0 h-full bg-red-200 rounded-full" style={{ width: `${clamp((stop - low) / full * 100, 0, 100)}%` }} />}
        {target && <div className="absolute right-0 top-0 h-full bg-green-100 rounded-full" style={{ left: `${clamp((entry - low) / full * 100, 0, 100)}%` }} />}
        <div
          className={`absolute top-0 h-full w-1.5 rounded-full z-10 ${isUp ? 'bg-green-500' : 'bg-red-500'}`}
          style={{ left: `calc(${curPx}% - 3px)` }}
        />
        <div className="absolute top-0 h-full w-0.5 bg-ink/40 z-20" style={{ left: `${entryPx}%` }} />
      </div>
      <div className="flex justify-between text-xs mt-0.5 text-muted">
        <span className="text-red-500">{stop ? `SL ${stop.toFixed(2)}` : ''}</span>
        <span className="text-ink font-mono font-semibold">{current.toFixed(2)}</span>
        <span className="text-green-600">{target ? `TP ${target.toFixed(2)}` : ''}</span>
      </div>
    </div>
  )
}

function TradeCard({ trade, onClose, onLesson, onDelete }) {
  const [expanded, setExpanded] = useState(false)
  const [closeMode, setCloseMode] = useState(false)
  const [exitPrice, setExitPrice] = useState(trade.current_price || trade.entry_price)
  const [lessonMode, setLessonMode] = useState(false)
  const [lesson, setLesson] = useState(trade.lesson || '')
  const [rating, setRating] = useState(trade.rating || 0)

  const isOpen   = trade.status === 'open'
  const isWin    = trade.status === 'closed_win'
  const isLoss   = trade.status === 'closed_loss'
  const pnlValue = isOpen ? trade.unrealized_pnl_pct : trade.pnl_pct

  const pnlColor = pnlValue == null ? 'text-ink'
    : pnlValue > 0 ? 'text-green-600' : pnlValue < 0 ? 'text-red-500' : 'text-ink'

  return (
    <div className={`bg-white border rounded-xl shadow-sm overflow-hidden transition-all ${
      isWin ? 'border-green-200' : isLoss ? 'border-red-200' : 'border-border'
    }`}>
      {/* ── header row ── */}
      <div className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-surface/60 transition-colors"
        onClick={() => setExpanded(v => !v)}>

        <div className="flex-shrink-0">{STATUS_ICON[trade.status]}</div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-bold text-ink">{trade.ticker}</span>
            <span className={`text-xs px-1.5 py-0.5 rounded font-semibold border ${
              trade.direction === 'short' ? 'bg-red-50 text-red-700 border-red-200' : 'bg-green-50 text-green-700 border-green-200'
            }`}>{trade.direction.toUpperCase()}</span>
            {trade.stage && (
              <span className={`text-xs px-1.5 py-0.5 rounded-full border font-semibold ${STAGE_COLORS[trade.stage] || 'bg-surface text-sub border-border'}`}>
                {trade.stage}
              </span>
            )}
            {trade.smart_money_score != null && (
              <SmartMoneyBadge score={trade.smart_money_score} compact />
            )}
            {trade.technique && (
              <span className="text-xs text-muted italic">{trade.technique}</span>
            )}
          </div>
          <div className="text-xs text-muted mt-0.5">
            Entry ${trade.entry_price?.toFixed(2)} · {trade.entry_date}
            {trade.exit_date && ` → ${trade.exit_date}`}
            {trade.days_held != null && isOpen && ` · ${trade.days_held}d held`}
          </div>
        </div>

        <div className="text-right flex-shrink-0">
          <div className={`font-bold font-mono text-sm ${pnlColor}`}>{pct(pnlValue)}</div>
          <div className={`text-xs font-mono ${pnlColor}`}>
            {isOpen ? dollar(trade.unrealized_pnl_dollar) : dollar(trade.pnl_dollar)}
          </div>
          {isOpen && (
            <div className="text-xs text-muted mt-0.5">${trade.current_price?.toFixed(2)}</div>
          )}
        </div>

        {expanded ? <ChevronUp size={14} className="text-muted flex-shrink-0" /> : <ChevronDown size={14} className="text-muted flex-shrink-0" />}
      </div>

      {/* ── expanded detail ── */}
      {expanded && (
        <div className="px-3 pb-3 border-t border-border/60 pt-2 space-y-2">

          {/* P&L bar (open trades) */}
          {isOpen && (
            <PnlBar
              entry={trade.entry_price}
              current={trade.current_price}
              stop={trade.stop_loss}
              target={trade.target}
              direction={trade.direction}
            />
          )}

          {/* Stats row */}
          <div className="grid grid-cols-3 gap-2 text-center text-xs">
            {trade.stop_loss && (
              <div className="bg-red-50 rounded-lg p-2">
                <div className="text-muted">Stop Loss</div>
                <div className="font-mono font-bold text-red-600">${trade.stop_loss.toFixed(2)}</div>
              </div>
            )}
            {trade.target && (
              <div className="bg-green-50 rounded-lg p-2">
                <div className="text-muted">Target</div>
                <div className="font-mono font-bold text-green-700">${trade.target.toFixed(2)}</div>
              </div>
            )}
            {trade.confidence != null && (
              <div className="bg-surface rounded-lg p-2">
                <div className="text-muted">Confidence</div>
                <div className="font-bold text-primary">{Math.round(trade.confidence * 100)}%</div>
              </div>
            )}
            {trade.smart_money_score != null && (
              <SmartMoneyBadge score={trade.smart_money_score} />
            )}
            {isOpen && trade.max_gain_pct != null && (
              <div className="bg-green-50 rounded-lg p-2">
                <div className="text-muted">Max Gain</div>
                <div className="font-mono font-bold text-green-600">{pct(trade.max_gain_pct)}</div>
              </div>
            )}
            {isOpen && trade.max_drawdown_pct != null && (
              <div className="bg-red-50 rounded-lg p-2">
                <div className="text-muted">Max Draw</div>
                <div className="font-mono font-bold text-red-500">{pct(trade.max_drawdown_pct)}</div>
              </div>
            )}
            {!isOpen && trade.exit_reason && (
              <div className="bg-surface rounded-lg p-2">
                <div className="text-muted">Exit</div>
                <div className="font-semibold text-ink text-xs">{REASONS[trade.exit_reason] || trade.exit_reason}</div>
              </div>
            )}
          </div>

          {/* Signals */}
          {trade.signals?.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {trade.signals.map((s, i) => (
                <span key={i} className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded-full font-medium">{s}</span>
              ))}
            </div>
          )}

          {/* Notes — bot's plain-English "why" + optional technical breakdown */}
          {trade.notes && <BotReasoning notes={trade.notes} technical={trade.technical_notes} />}

          {/* Lesson */}
          {(trade.lesson || !isOpen) && !lessonMode && (
            <div className={`rounded-lg p-2.5 border ${trade.lesson ? 'bg-amber-50 border-amber-200' : 'bg-surface border-border'}`}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-bold text-amber-700 flex items-center gap-1">
                  <BookOpen size={11} /> Daily Lesson
                </span>
                <button onClick={() => setLessonMode(true)} className="text-xs text-primary hover:underline">Edit</button>
              </div>
              {trade.lesson
                ? <p className="text-xs text-sub leading-relaxed">{trade.lesson}</p>
                : <p className="text-xs text-muted italic">No lesson recorded yet — tap Edit to add one.</p>
              }
              {trade.rating && (
                <div className="mt-1 text-xs text-amber-600 font-semibold">{'⭐'.repeat(trade.rating)} ({trade.rating}/5)</div>
              )}
            </div>
          )}

          {lessonMode && (
            <div className="space-y-2">
              <textarea
                rows={3}
                className="input w-full text-xs"
                placeholder="What did this trade teach you? Was the signal accurate? Did you follow the plan?"
                value={lesson}
                onChange={e => setLesson(e.target.value)}
              />
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted">Rating:</span>
                {[1,2,3,4,5].map(n => (
                  <button key={n} onClick={() => setRating(n)}
                    className={`text-lg leading-none transition-opacity ${n <= rating ? 'opacity-100' : 'opacity-30 hover:opacity-60'}`}>⭐</button>
                ))}
              </div>
              <div className="flex gap-2">
                <button className="btn-primary text-xs" onClick={() => { onLesson(trade.id, lesson, rating); setLessonMode(false) }}>Save</button>
                <button className="btn-ghost text-xs" onClick={() => setLessonMode(false)}>Cancel</button>
              </div>
            </div>
          )}

          {/* Close form */}
          {isOpen && !closeMode && (
            <div className="flex gap-2 pt-1">
              <button className="btn-ghost text-xs flex-1" onClick={() => setCloseMode(true)}>
                <X size={12} /> Close Trade
              </button>
              <button className="btn-danger text-xs" onClick={() => onDelete(trade.id)}>Delete</button>
            </div>
          )}

          {isOpen && closeMode && (
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs text-muted">Exit price</span>
              <input type="number" step="0.01"
                className="input w-24 text-xs"
                value={exitPrice}
                onChange={e => setExitPrice(parseFloat(e.target.value))}
              />
              <button className="btn-primary text-xs" onClick={() => { onClose(trade.id, exitPrice, 'manual'); setCloseMode(false) }}>
                Confirm
              </button>
              <button className="btn-ghost text-xs" onClick={() => setCloseMode(false)}>Cancel</button>
            </div>
          )}

          {!isOpen && (
            <button className="text-xs text-red-400 hover:text-red-600 transition-colors" onClick={() => onDelete(trade.id)}>
              Delete record
            </button>
          )}
        </div>
      )}
    </div>
  )
}

function StatCard({ title, value, sub, color = 'text-ink', icon }) {
  return (
    <div className="bg-white border border-border rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-1">
        {icon && <span className="text-muted">{icon}</span>}
        <span className="text-xs font-bold text-muted uppercase tracking-wide">{title}</span>
      </div>
      <div className={`text-2xl font-extrabold font-mono ${color}`}>{value}</div>
      {sub && <div className="text-xs text-muted mt-0.5">{sub}</div>}
    </div>
  )
}

// ── Add-trade form ────────────────────────────────────────────────────────────

const DEFAULT_FORM = {
  ticker: '', direction: 'long', entry_price: '', shares: '1',
  stop_loss: '', target: '', stage: '', confidence: '',
  signals: '', technique: '', notes: '',
}

function AddTradeForm({ onAdd, onCancel }) {
  const [f, setF] = useState(DEFAULT_FORM)
  const set = (k, v) => setF(prev => ({ ...prev, [k]: v }))

  const submit = (e) => {
    e.preventDefault()
    if (!f.ticker || !f.entry_price) return
    onAdd({
      ticker:      f.ticker.trim().toUpperCase(),
      direction:   f.direction,
      entry_price: parseFloat(f.entry_price),
      shares:      parseFloat(f.shares) || 1,
      stop_loss:   f.stop_loss ? parseFloat(f.stop_loss) : null,
      target:      f.target    ? parseFloat(f.target)    : null,
      stage:       f.stage     || null,
      confidence:  f.confidence ? parseFloat(f.confidence) / 100 : null,
      signals:     f.signals ? f.signals.split(',').map(s => s.trim()).filter(Boolean) : [],
      technique:   f.technique  || null,
      notes:       f.notes      || '',
    })
  }

  const Field = ({ label, children }) => (
    <div>
      <label className="block text-xs font-semibold text-muted mb-1">{label}</label>
      {children}
    </div>
  )

  return (
    <form onSubmit={submit} className="bg-white border border-primary/30 rounded-xl shadow-sm p-3 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-bold text-ink text-sm">Log New Paper Trade</h3>
        <button type="button" onClick={onCancel} className="text-muted hover:text-ink"><X size={16} /></button>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <Field label="Ticker *">
          <input className="input w-full text-sm uppercase" placeholder="AAPL"
            value={f.ticker} onChange={e => set('ticker', e.target.value.toUpperCase())} required />
        </Field>
        <Field label="Direction">
          <select className="input w-full text-sm" value={f.direction} onChange={e => set('direction', e.target.value)}>
            <option value="long">Long ↑</option>
            <option value="short">Short ↓</option>
          </select>
        </Field>
        <Field label="Entry Price *">
          <input type="number" step="0.01" className="input w-full text-sm" placeholder="195.00"
            value={f.entry_price} onChange={e => set('entry_price', e.target.value)} required />
        </Field>
        <Field label="Shares">
          <input type="number" step="0.01" className="input w-full text-sm" placeholder="10"
            value={f.shares} onChange={e => set('shares', e.target.value)} />
        </Field>
        <Field label="Stop Loss">
          <input type="number" step="0.01" className="input w-full text-sm" placeholder="185.00"
            value={f.stop_loss} onChange={e => set('stop_loss', e.target.value)} />
        </Field>
        <Field label="Target">
          <input type="number" step="0.01" className="input w-full text-sm" placeholder="220.00"
            value={f.target} onChange={e => set('target', e.target.value)} />
        </Field>
        <Field label="Stage">
          <select className="input w-full text-sm" value={f.stage} onChange={e => set('stage', e.target.value)}>
            <option value="">— select —</option>
            <option value="accumulation">Accumulation</option>
            <option value="markup">Markup</option>
            <option value="distribution">Distribution</option>
            <option value="markdown">Markdown</option>
          </select>
        </Field>
        <Field label="Confidence %">
          <input type="number" min="0" max="100" className="input w-full text-sm" placeholder="72"
            value={f.confidence} onChange={e => set('confidence', e.target.value)} />
        </Field>
        <Field label="Technique">
          <input className="input w-full text-sm" placeholder="Wyckoff Spring"
            value={f.technique} onChange={e => set('technique', e.target.value)} />
        </Field>
      </div>

      <Field label="Signals (comma-separated)">
        <input className="input w-full text-sm" placeholder="RSI oversold, MACD cross, Volume surge"
          value={f.signals} onChange={e => set('signals', e.target.value)} />
      </Field>

      <Field label="Notes / Thesis">
        <textarea rows={2} className="input w-full text-sm"
          placeholder="Why this trade? What's the setup thesis?"
          value={f.notes} onChange={e => set('notes', e.target.value)} />
      </Field>

      <div className="flex gap-2">
        <button type="submit" className="btn-primary text-sm flex-1">
          <Plus size={14} /> Log Trade
        </button>
        <button type="button" onClick={onCancel} className="btn-ghost text-sm">Cancel</button>
      </div>
    </form>
  )
}

// ── Stats panel ───────────────────────────────────────────────────────────────

function StatsPanel({ stats }) {
  if (!stats) return <div className="text-sm text-muted text-center py-10">No closed trades yet — log and close trades to see analytics.</div>

  const {
    win_rate, avg_win_pct, avg_loss_pct, expectancy,
    stage_stats, current_streak, total_pnl_pct,
    wins, losses, equity_curve,
  } = stats

  const stageList = Object.entries(stage_stats || {}).sort((a, b) => b[1].win_rate - a[1].win_rate)

  return (
    <div className="space-y-3">
      {/* KPI strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard title="Win Rate" value={`${win_rate}%`}
          color={win_rate >= 50 ? 'text-green-600' : 'text-red-500'}
          sub={`${wins}W / ${losses}L`}
          icon={<Award size={14} />}
        />
        <StatCard title="Expectancy" value={`${expectancy > 0 ? '+' : ''}${expectancy}%`}
          color={expectancy >= 0 ? 'text-green-600' : 'text-red-500'}
          sub="per trade (avg)"
          icon={<Zap size={14} />}
        />
        <StatCard title="Avg Win" value={`+${avg_win_pct}%`} color="text-green-600"
          sub="closed winners" icon={<TrendingUp size={14} />}
        />
        <StatCard title="Avg Loss" value={`${avg_loss_pct}%`} color="text-red-500"
          sub="closed losers" icon={<TrendingDown size={14} />}
        />
      </div>

      {/* Totals + streak */}
      <div className="grid grid-cols-2 gap-3">
        <StatCard title="Total P&L" value={`${total_pnl_pct >= 0 ? '+' : ''}${total_pnl_pct}%`}
          color={total_pnl_pct >= 0 ? 'text-green-600' : 'text-red-500'}
          sub="cumulative (sum of closed trades)"
          icon={<BarChart2 size={14} />}
        />
        {current_streak?.count > 0 && (
          <StatCard
            title={`${current_streak.type === 'win' ? '🔥' : '❄️'} Current Streak`}
            value={`${current_streak.count} ${current_streak.type === 'win' ? 'wins' : 'losses'}`}
            color={current_streak.type === 'win' ? 'text-green-600' : 'text-red-500'}
            sub="in a row"
          />
        )}
      </div>

      {/* Stage breakdown */}
      {stageList.length > 0 && (
        <div className="bg-white border border-border rounded-xl p-4 shadow-sm">
          <div className="text-xs font-bold text-muted uppercase tracking-wide mb-3">Win Rate by Market Stage</div>
          <div className="space-y-2.5">
            {stageList.map(([stage, v]) => (
              <div key={stage}>
                <div className="flex justify-between text-xs mb-1">
                  <span className={`px-2 py-0.5 rounded-full border font-semibold text-xs ${STAGE_COLORS[stage] || 'bg-surface text-sub border-border'}`}>{stage}</span>
                  <span className="font-bold font-mono text-ink">{v.win_rate}% ({v.wins}/{v.total})</span>
                </div>
                <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${v.win_rate >= 60 ? 'bg-green-400' : v.win_rate >= 40 ? 'bg-amber-400' : 'bg-red-400'}`}
                    style={{ width: `${v.win_rate}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Equity curve (simple text list) */}
      {equity_curve?.length > 0 && (
        <div className="bg-white border border-border rounded-xl p-4 shadow-sm">
          <div className="text-xs font-bold text-muted uppercase tracking-wide mb-3">Equity Curve (cumulative P&L %)</div>
          <div className="space-y-1 max-h-48 overflow-y-auto">
            {equity_curve.map((pt, i) => (
              <div key={i} className="flex items-center gap-3 text-xs py-0.5 border-b border-border/40 last:border-0">
                <span className="text-muted w-20 flex-shrink-0">{pt.date}</span>
                <span className="font-semibold text-ink w-12">{pt.ticker}</span>
                <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${pt.cumulative_pnl >= 0 ? 'bg-green-400' : 'bg-red-400'}`}
                    style={{ width: `${Math.min(100, Math.abs(pt.cumulative_pnl) * 3)}%` }}
                  />
                </div>
                <span className={`font-mono font-bold w-16 text-right ${pt.cumulative_pnl >= 0 ? 'text-green-600' : 'text-red-500'}`}>
                  {pt.cumulative_pnl >= 0 ? '+' : ''}{pt.cumulative_pnl}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Daily lesson prompt */}
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
        <div className="flex items-center gap-2 mb-2">
          <BookOpen size={14} className="text-amber-600" />
          <span className="text-xs font-bold text-amber-800">Daily Learning Habit</span>
        </div>
        <p className="text-xs text-amber-700 leading-relaxed">
          After each trade closes, open it and fill in the <strong>Daily Lesson</strong>.
          Ask: Was my stage read correct? Did signals confirm? Did I follow my plan?
          Over time, your win rate by stage and signal shows where your edge actually is.
        </p>
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ForwardTest() {
  const [tab, setTab]       = useState('open')
  const [trades, setTrades] = useState([])
  const [stats, setStats]   = useState(null)
  const [adding, setAdding] = useState(false)
  const { call, loading }   = useApi()

  const loadAll = useCallback(async () => {
    const [t, s] = await Promise.all([
      call('/api/forwardtest'),
      call('/api/forwardtest/stats'),
    ])
    if (t) setTrades(t)
    if (s) setStats(s)
  }, [call])

  useEffect(() => { loadAll() }, [loadAll])

  const handleAdd = async (body) => {
    const res = await call('/api/forwardtest', { method: 'POST', body })
    if (res) { setAdding(false); loadAll() }
  }

  const handleClose = async (id, exitPrice, reason) => {
    await call(`/api/forwardtest/${id}/close`, { method: 'PATCH', body: { exit_price: exitPrice, exit_reason: reason } })
    loadAll()
  }

  const handleLesson = async (id, lesson, rating) => {
    await call(`/api/forwardtest/${id}/lesson`, { method: 'PATCH', body: { lesson, rating } })
    loadAll()
  }

  const handleDelete = async (id) => {
    await call(`/api/forwardtest/${id}`, { method: 'DELETE' })
    loadAll()
  }

  const openTrades   = trades.filter(t => t.status === 'open')
  const closedTrades = trades.filter(t => t.status !== 'open')

  const TABS = [
    { id: 'open',   label: 'Open Trades',   count: openTrades.length },
    { id: 'closed', label: 'Closed Trades',  count: closedTrades.length },
    { id: 'stats',  label: 'Performance',    count: null },
  ]

  return (
    <div className="p-3 space-y-3 max-w-4xl">

      <HelpBanner
        pageKey="forwardtest"
        title="Forward Test — Manual Paper Trades"
        whatIsThis="A learning journal where YOU place paper trades. The system tracks outcomes vs. the original signal so you learn which setups actually work for you."
        steps={[
          "Click <b>+ New Trade</b>, enter ticker + entry / stop / target + reasoning.",
          "When the trade hits stop or target (or you decide to close), click <b>Close</b> and log the lesson learned.",
          "Review the <b>summary stats</b> over time — win rate, avg R, best/worst setups.",
        ]}
        tips={[
          "Use this <b>before</b> the autonomous bot — develop your own intuition on which signals work.",
          "Always write a <b>one-line lesson</b> on every closed trade — this is where real edge compounds.",
          "Aim for <b>R ≥ 1.5</b> on average over 20+ trades before scaling size or going live.",
        ]}
      />

      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-lg font-bold text-ink">Forward Test</h1>
          <p className="text-xs text-muted mt-0.5">Paper-trade signals in real-time · learn from every outcome</p>
        </div>
        <div className="flex gap-2">
          <button onClick={loadAll} className="btn-ghost text-xs" disabled={loading}>
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
          <button onClick={() => setAdding(v => !v)} className="btn-primary text-xs">
            <Plus size={14} />
            Log Trade
          </button>
        </div>
      </div>

      {/* Add form */}
      {adding && <AddTradeForm onAdd={handleAdd} onCancel={() => setAdding(false)} />}

      {/* Summary strip */}
      {stats && stats.closed_trades > 0 && (
        <div className="grid grid-cols-4 gap-2">
          {[
            { l: 'Win Rate', v: `${stats.win_rate}%`, c: stats.win_rate >= 50 ? 'text-green-600' : 'text-red-500' },
            { l: 'Total P&L', v: `${stats.total_pnl_pct >= 0 ? '+' : ''}${stats.total_pnl_pct}%`, c: stats.total_pnl_pct >= 0 ? 'text-green-600' : 'text-red-500' },
            { l: 'Open', v: stats.open_trades, c: 'text-amber-600' },
            { l: 'Closed', v: stats.closed_trades, c: 'text-ink' },
          ].map(({ l, v, c }) => (
            <div key={l} className="bg-white border border-border rounded-lg px-3 py-2 text-center shadow-sm">
              <div className="text-xs text-muted">{l}</div>
              <div className={`font-bold font-mono text-sm ${c}`}>{v}</div>
            </div>
          ))}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 border-b border-border pb-0">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === t.id
                ? 'border-primary text-primary'
                : 'border-transparent text-sub hover:text-ink'
            }`}>
            {t.label}
            {t.count != null && (
              <span className={`ml-1.5 text-xs px-1.5 py-0.5 rounded-full font-semibold ${
                tab === t.id ? 'bg-primary/10 text-primary' : 'bg-surface text-muted'
              }`}>{t.count}</span>
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === 'open' && (
        <div className="space-y-3">
          {loading && openTrades.length === 0 && (
            <div className="flex items-center gap-2 text-muted text-sm">
              <RefreshCw size={13} className="animate-spin" /> Loading live prices…
            </div>
          )}
          {openTrades.length === 0 && !loading && (
            <div className="text-center py-8 text-muted text-sm">
              <Target size={32} className="mx-auto mb-3 opacity-30" />
              <p className="text-sm">No open paper trades.</p>
              <p className="text-xs mt-1">Click "Log Trade" to start forward testing a setup.</p>
            </div>
          )}
          {openTrades.map(t => (
            <TradeCard key={t.id} trade={t}
              onClose={handleClose} onLesson={handleLesson} onDelete={handleDelete} />
          ))}
        </div>
      )}

      {tab === 'closed' && (
        <div className="space-y-3">
          {closedTrades.length === 0 && (
            <div className="text-center py-8 text-muted text-sm">
              <CheckCircle size={32} className="mx-auto mb-3 opacity-30" />
              <p className="text-sm">No closed trades yet.</p>
              <p className="text-xs mt-1">Trades auto-close when stop or target is hit. Or close manually.</p>
            </div>
          )}
          {closedTrades.map(t => (
            <TradeCard key={t.id} trade={t}
              onClose={handleClose} onLesson={handleLesson} onDelete={handleDelete} />
          ))}
        </div>
      )}

      {tab === 'stats' && <StatsPanel stats={stats?.closed_trades > 0 ? stats : null} />}
    </div>
  )
}
