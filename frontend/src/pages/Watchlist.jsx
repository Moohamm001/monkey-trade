import React, { useState, useEffect } from 'react'
import { Plus, Trash2, AlertCircle, RefreshCw } from 'lucide-react'
import { useApi } from '../hooks/useApi'
import StageBadge from '../components/StageBadge'
import HelpBanner from '../components/HelpBanner'

const pct = n => n != null ? `${(n*100).toFixed(1)}%` : '—'

const rr = (item) => {
  const { info, entry_price: entry, target_price: target, stop_loss: stop } = item
  const price = info?.price
  if (!price || !entry || !target || !stop) return null
  const risk = entry - stop
  if (risk <= 0) return null
  return ((target - entry) / risk).toFixed(1)
}

export default function Watchlist() {
  const [items, setItems]       = useState([])
  const [form, setForm]         = useState({ ticker: '', note: '', entry_price: '', target_price: '', stop_loss: '' })
  const [showForm, setShowForm] = useState(false)
  const { call, loading, error } = useApi()

  const load = async () => {
    const data = await call('/api/watchlist')
    if (data) setItems(data)
  }

  useEffect(() => { load() }, [])

  const add = async (e) => {
    e.preventDefault()
    const res = await call('/api/watchlist', {
      method: 'POST',
      body: JSON.stringify({
        ticker:       form.ticker.toUpperCase(),
        note:         form.note,
        entry_price:  form.entry_price  ? +form.entry_price  : null,
        target_price: form.target_price ? +form.target_price : null,
        stop_loss:    form.stop_loss    ? +form.stop_loss    : null,
      }),
    })
    if (res?.ok) {
      setForm({ ticker: '', note: '', entry_price: '', target_price: '', stop_loss: '' })
      setShowForm(false)
      load()
    }
  }

  const remove = async (ticker) => {
    await call(`/api/watchlist/${ticker}`, { method: 'DELETE' })
    load()
  }

  return (
    <div className="p-3 space-y-3">
      <HelpBanner
        pageKey="watchlist"
        title="Watchlist — Your Saved Tickers"
        whatIsThis="A personal list of tickers you're monitoring with optional entry / stop / target prices. The live stage badge updates so you know when each setup matures."
        steps={[
          "Click <b>+ Add</b>, enter a ticker plus your planned entry / stop / target prices.",
          "The <b>R:R</b> column shows your risk-reward — only add trades where R:R ≥ 2.",
          "Check back daily — the <b>stage badge</b> updates as the cycle progresses.",
        ]}
        tips={[
          "Add a <b>note</b> explaining your thesis — future you needs to remember <i>why</i>.",
          "Don't keep tickers that have invalidated the setup — <b>delete and move on</b>.",
          "Use the Screener to find candidates, then promote the best to your Watchlist.",
        ]}
      />

      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-sm font-bold text-ink">Watchlist</span>
        <span className="text-xs text-muted">entry · stop · target · live stage</span>
        <div className="ml-auto flex gap-2">
          <button onClick={load} className="btn-ghost text-xs">
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
          <button onClick={() => setShowForm(v => !v)} className="btn-primary text-xs">
            <Plus size={12} /> Add
          </button>
        </div>
      </div>

      {/* Add form */}
      {showForm && (
        <form onSubmit={add} className="card space-y-3">
          <div className="text-sm font-semibold text-ink">Add to Watchlist</div>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {[
              { key: 'ticker',       label: 'Ticker *',     ph: 'AAPL',   required: true },
              { key: 'entry_price',  label: 'Entry Price',  ph: '150.00', type: 'number' },
              { key: 'target_price', label: 'Target Price', ph: '200.00', type: 'number' },
              { key: 'stop_loss',    label: 'Stop Loss',    ph: '140.00', type: 'number' },
            ].map(({ key, label, ph, required, type }) => (
              <label key={key} className="block">
                <span className="text-xs text-muted font-medium">{label}</span>
                <input required={required} className="input w-full mt-1"
                  type={type || 'text'} step="0.01" placeholder={ph}
                  value={form[key]}
                  onChange={e => setForm(f => ({ ...f, [key]: key === 'ticker' ? e.target.value.toUpperCase() : e.target.value }))} />
              </label>
            ))}
            <label className="block col-span-2">
              <span className="text-xs text-muted font-medium">Note</span>
              <input className="input w-full mt-1" placeholder="Why are you watching this?"
                value={form.note} onChange={e => setForm(f => ({ ...f, note: e.target.value }))} />
            </label>
          </div>
          <div className="flex gap-2">
            <button type="submit" disabled={loading} className="btn-primary text-xs">Add</button>
            <button type="button" onClick={() => setShowForm(false)} className="btn-ghost text-xs">Cancel</button>
          </div>
        </form>
      )}

      {error && (
        <div className="flex items-center gap-2 text-red-600 text-sm card bg-red-50 border-red-200">
          <AlertCircle size={15} /> {error}
        </div>
      )}

      {loading && items.length === 0 && (
        <div className="text-muted text-sm flex items-center gap-2">
          <RefreshCw size={14} className="animate-spin" /> Loading watchlist…
        </div>
      )}

      <div className="space-y-3">
        {items.map(item => {
          const info    = item.info || {}
          const cycle   = item.cycle || {}
          const ratio   = rr(item)
          const price   = info.price
          const pnl     = item.entry_price && price
            ? ((price - item.entry_price) / item.entry_price * 100).toFixed(1)
            : null

          const stageBg = {
            accumulation: 'border-l-blue-400',
            markup:       'border-l-green-400',
            distribution: 'border-l-amber-400',
            markdown:     'border-l-red-400',
          }[cycle.stage] || 'border-l-border'

          return (
            <div key={item.ticker} className={`card border-l-4 ${stageBg}`}>
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-bold text-primary">{item.ticker}</span>
                    {cycle.stage && <StageBadge stage={cycle.stage} confidence={cycle.confidence} />}
                  </div>
                  <div className="text-xs text-muted mt-0.5">{info.name} · {info.sector}</div>
                  {item.note && <div className="text-xs text-sub mt-1 italic">"{item.note}"</div>}

                  {cycle.signals?.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {cycle.signals.slice(0, 3).map((s, i) => (
                        <span key={i} className={`text-xs px-2 py-0.5 rounded-full border signal-${s.type}`}>
                          {s.text}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-4 text-sm flex-wrap">
                  {price && (
                    <div className="text-center">
                      <div className="text-xs text-muted">Price</div>
                      <div className="font-mono font-bold text-ink">{price.toFixed(2)}</div>
                    </div>
                  )}
                  {item.entry_price && (
                    <div className="text-center">
                      <div className="text-xs text-muted">Entry</div>
                      <div className="font-mono text-sub">{item.entry_price}</div>
                    </div>
                  )}
                  {pnl != null && (
                    <div className="text-center">
                      <div className="text-xs text-muted">P&L</div>
                      <div className={`font-mono font-bold ${+pnl >= 0 ? 'text-green-600' : 'text-red-500'}`}>
                        {pnl > 0 ? '+' : ''}{pnl}%
                      </div>
                    </div>
                  )}
                  {item.target_price && (
                    <div className="text-center">
                      <div className="text-xs text-muted">Target</div>
                      <div className="font-mono text-green-600">{item.target_price}</div>
                    </div>
                  )}
                  {item.stop_loss && (
                    <div className="text-center">
                      <div className="text-xs text-muted">Stop</div>
                      <div className="font-mono text-red-500">{item.stop_loss}</div>
                    </div>
                  )}
                  {ratio && (
                    <div className="text-center">
                      <div className="text-xs text-muted">R:R</div>
                      <div className={`font-mono font-bold ${+ratio >= 2 ? 'text-green-600' : +ratio >= 1 ? 'text-amber-500' : 'text-red-500'}`}>
                        1:{ratio}
                      </div>
                    </div>
                  )}
                  <button onClick={() => remove(item.ticker)}
                    className="text-muted hover:text-red-500 transition-colors p-1 rounded-lg hover:bg-red-50">
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            </div>
          )
        })}

        {!loading && items.length === 0 && (
          <div className="text-center py-10 text-muted text-sm">
            Watchlist empty. Add a stock to get started.
          </div>
        )}
      </div>
    </div>
  )
}
