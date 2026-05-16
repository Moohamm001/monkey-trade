import React, { useState } from 'react'
import HelpBanner from './../components/HelpBanner'

const STAGES = [
  {
    key: 'accumulation', label: 'Accumulation', emoji: '🔵',
    cardBg: 'bg-blue-50 border-blue-200', titleColor: 'text-blue-700',
    badge: 'bg-blue-100 text-blue-700 border-blue-300',
    actionColor: 'text-green-600', action: 'BUY / ACCUMULATE',
    summary: 'Big players quietly buying at low prices. Price moves sideways near lows.',
    details: [
      'Stock has stopped falling and moves in a tight range',
      'Volume is low on down days, picks up on up days',
      'News is quiet or negative — retail sells to institutions',
      'RSI stays in 30–50. No excitement. Long and boring.',
      'OBV slowly rises even while price stays flat',
    ],
    suitable: 'Long-term investors who are patient. Low risk, highest reward potential.',
    profit_pattern: 'Best: Revenue rising, costs flat/falling. EoS forming.',
    trap: 'Impatient sellers dump at a loss thinking the stock is dead.',
    chart_shape: '── Flat base, tight range, low volatility',
  },
  {
    key: 'markup', label: 'Markup', emoji: '🟢',
    cardBg: 'bg-green-50 border-green-200', titleColor: 'text-green-700',
    badge: 'bg-green-100 text-green-700 border-green-300',
    actionColor: 'text-green-600', action: 'RIDE / ADD ON PULLBACKS',
    summary: 'Price rises quickly. Momentum builds. News and stories appear.',
    details: [
      'Price breaks out of accumulation range on heavy volume',
      'SMA20 > SMA50 > SMA200 — Golden Order confirmed',
      'RSI moves into 55–80. MACD turns positive.',
      'Analyst upgrades, earnings beats appear',
      'Retail investors buy late — institutions already positioned',
    ],
    suitable: 'Momentum traders. Use trailing stops below SMA20.',
    profit_pattern: 'Best: Top Line growing faster than costs. EPS beats quarterly.',
    trap: 'Chasing too late — buying at the end of markup = buying into distribution.',
    chart_shape: '↗ Rising channel, higher highs and higher lows',
  },
  {
    key: 'distribution', label: 'Distribution', emoji: '🟡',
    cardBg: 'bg-amber-50 border-amber-200', titleColor: 'text-amber-700',
    badge: 'bg-amber-100 text-amber-700 border-amber-300',
    actionColor: 'text-amber-600', action: 'RANGE TRADE / REDUCE',
    summary: 'Big players gradually selling. Price moves sideways at high levels.',
    details: [
      'Price stops making new highs. Volume increases but price doesn\'t follow',
      'RSI stays elevated (60–80) while price churns — exhaustion sign',
      'MACD diverging: price holds but MACD weakens',
      'News remains positive — institutions sell into good news',
      'Classic retail trap: "just consolidating before the next leg up"',
    ],
    suitable: 'Swing traders. Buy range low, sell range high. Small losses, moderate gains.',
    profit_pattern: 'Revenue growth slowing. Margins compressing. Management guides down.',
    trap: 'Holding full position believing markup will resume. It usually doesn\'t.',
    chart_shape: '── Wide choppy range at highs, false breakouts',
  },
  {
    key: 'markdown', label: 'Markdown', emoji: '🔴',
    cardBg: 'bg-red-50 border-red-200', titleColor: 'text-red-700',
    badge: 'bg-red-100 text-red-700 border-red-300',
    actionColor: 'text-red-600', action: 'AVOID / SHORT SELLERS ONLY',
    summary: 'Price in persistent downtrend. Rallies are traps. Destination is lower.',
    details: [
      'SMA20 < SMA50 < SMA200 — Death Order alignment',
      'Lower highs and lower lows consistently',
      'Rallies to resistance get sold hard — last distribution',
      'RSI oversold readings don\'t bounce — weakness keeps extending',
      '"Cheap" stocks keep getting cheaper. Valuation is meaningless here.',
    ],
    suitable: 'Short sellers only. Long investors: exit completely.',
    profit_pattern: 'Revenue declining, costs rising. EPS misses. Management blames macro.',
    trap: '"It\'s too cheap to sell" — the most common and costly investor mistake.',
    chart_shape: '↘ Declining channel, dead cat bounces, lower lows',
  },
]

const PROFIT_ANALYSIS = [
  { rating: '⭐⭐⭐ Best',    label: 'Revenue ↑, Cost ↓',    color: 'text-green-700 bg-green-50 border-green-200', desc: 'Sales growing AND costs falling = Economies of Scale. The ideal profile.' },
  { rating: '⭐⭐ Good',     label: 'Revenue ↑↑, Cost ↑',   color: 'text-blue-700 bg-blue-50 border-blue-200',   desc: 'Revenue grows faster than cost. Usually means branch expansion — costs will stabilize.' },
  { rating: '⭐⭐ Good',     label: 'Revenue ↑, Cost → flat',color: 'text-blue-700 bg-blue-50 border-blue-200',   desc: 'Revenue growing, costs holding steady — EoS beginning to kick in.' },
  { rating: '⭐ Neutral',    label: 'Revenue → flat, Cost ↓',color: 'text-amber-700 bg-amber-50 border-amber-200',desc: 'Cost cutting as growth stalls. Watch: seasonal adjustment or structural decline?' },
  { rating: '❌ Avoid',      label: 'Revenue ↓, Cost →',    color: 'text-red-700 bg-red-50 border-red-200',      desc: 'Shrinking business. Costs not adapting. Chart will turn to markdown.' },
]

export default function Education() {
  const [active, setActive] = useState('accumulation')
  const stage = STAGES.find(s => s.key === active)

  return (
    <div className="p-3 space-y-3 max-w-4xl">
      <HelpBanner
        pageKey="education"
        title="Strategy Guide — Wyckoff Market Cycle"
        whatIsThis="The foundation of how this app thinks: every stock cycles through 4 stages — Accumulation → Markup → Distribution → Markdown. Knowing the stage tells you what to do."
        steps={[
          "Tap a <b>stage chip</b> at the top (Accumulation / Markup / Distribution / Markdown).",
          "Read what the stage <b>looks like</b>, who <b>wins</b> in it, and what the <b>trap</b> is.",
          "Apply this lens on every chart you analyze in <b>Dashboard</b> or <b>Cycle Detector</b>.",
        ]}
        tips={[
          "The biggest money is made entering at the <b>end of Accumulation</b> / start of Markup.",
          "The biggest losses come from <b>buying late in Markup</b> when the stage is rolling into Distribution.",
          "<b>Markdown</b> = either short or stay flat. Catching falling knives is how accounts die.",
        ]}
      />

      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-sm font-bold text-ink">Strategy Guide</span>
        <span className="text-xs text-muted">Wyckoff Market Cycle · Profit analysis</span>
        <div className="ml-auto flex gap-1.5 flex-wrap">
          {STAGES.map(s => (
            <button key={s.key} onClick={() => setActive(s.key)}
              className={`flex items-center gap-1 px-3 py-1 rounded-full border text-xs font-semibold transition-all ${
                active === s.key ? s.badge : 'bg-white border-border text-sub hover:border-primary/40'
              }`}>
              <span>{s.emoji}</span>
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {/* Stage card */}
      {stage && (
        <div className={`rounded-xl border p-3 space-y-3 ${stage.cardBg}`}>
          <div className="flex items-center gap-2">
            <span className="text-2xl">{stage.emoji}</span>
            <div>
              <h2 className={`text-sm font-bold ${stage.titleColor}`}>{stage.label} Stage</h2>
              <p className="text-xs text-sub mt-0.5">{stage.summary}</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <div className="text-xs font-semibold text-muted uppercase tracking-wide mb-1.5">What's Happening</div>
              <ul className="space-y-1">
                {stage.details.map((d, i) => (
                  <li key={i} className={`text-xs flex gap-1.5 ${stage.titleColor}`}>
                    <span>›</span>
                    <span className="text-ink">{d}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="space-y-3">
              <div className="bg-white/60 rounded-lg p-3">
                <div className="text-xs font-semibold text-muted uppercase mb-1">Chart Pattern</div>
                <div className={`text-sm font-mono font-bold ${stage.titleColor}`}>{stage.chart_shape}</div>
              </div>
              <div className="bg-white/60 rounded-lg p-3">
                <div className="text-xs font-semibold text-muted uppercase mb-1">Action</div>
                <div className={`font-bold ${stage.actionColor}`}>{stage.action}</div>
                <div className="text-xs text-sub mt-0.5">{stage.suitable}</div>
              </div>
              <div className="bg-white/60 rounded-lg p-3">
                <div className="text-xs font-semibold text-muted uppercase mb-1">Fundamental Profile</div>
                <div className="text-sm text-ink">{stage.profit_pattern}</div>
              </div>
              <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                <div className="text-xs font-bold text-red-600 mb-1">⚠ Common Trap</div>
                <div className="text-sm text-red-700">{stage.trap}</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Cycle flow */}
      <div className="card">
        <div className="text-sm font-semibold text-sub mb-3">The Full Cycle</div>
        <div className="flex items-stretch gap-2 flex-wrap">
          {STAGES.map((s, i) => (
            <React.Fragment key={s.key}>
              <button onClick={() => setActive(s.key)}
                className={`flex-1 min-w-[100px] rounded-xl border p-3 text-center cursor-pointer transition-all hover:shadow-card-hover ${s.cardBg} ${active === s.key ? 'ring-2 ring-primary/30' : ''}`}>
                <div className="text-2xl">{s.emoji}</div>
                <div className={`text-xs font-bold mt-1 ${s.titleColor}`}>{s.label}</div>
              </button>
              {i < STAGES.length - 1 && (
                <div className="flex items-center text-muted text-lg">→</div>
              )}
            </React.Fragment>
          ))}
        </div>
        <p className="text-xs text-center text-muted mt-3">
          Cycles repeat. The difficulty is not knowing — it's distinguishing which stage you're in.
        </p>
      </div>

      {/* Profit analysis */}
      <div className="card">
        <div className="text-sm font-semibold text-sub mb-3">Profit Growth Framework</div>
        <div className="space-y-2">
          {PROFIT_ANALYSIS.map((p, i) => (
            <div key={i} className={`flex items-start gap-3 rounded-lg border p-3 ${p.color}`}>
              <div className="text-xs font-bold w-24 flex-shrink-0">{p.rating}</div>
              <div>
                <div className="text-sm font-semibold">{p.label}</div>
                <div className="text-xs opacity-80 mt-0.5">{p.desc}</div>
              </div>
            </div>
          ))}
        </div>
        <p className="text-xs text-muted italic mt-3">
          Key insight: Revenue = Top Line. Cost = Middle Line. Profit = Bottom Line.
          Understand what is driving growth, not just that growth exists.
        </p>
      </div>
    </div>
  )
}
