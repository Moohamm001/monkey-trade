import React, { useState } from 'react'
import { BookOpen, X, HelpCircle, Info } from 'lucide-react'

/**
 * Reusable per-page help banner.
 *
 * Props
 * ─────
 *   pageKey   string  — unique key for localStorage persistence (e.g. "dashboard")
 *   title     string  — bold heading shown in the banner
 *   whatIsThis  string — one-sentence "what does this page do?"
 *   steps      string[] — ordered, plain-English how-to (≤ 4 entries)
 *   tips       string[] — pro tips, optional
 *   disclaimer string — small grey footer (defaults to standard disclaimer)
 */
export default function HelpBanner({
  pageKey,
  title,
  whatIsThis,
  steps = [],
  tips = [],
  disclaimer = "Analytical aid — not financial advice. Always confirm signals with price action and risk-manage every trade.",
}) {
  const storeKey = `help_dismissed_${pageKey}`
  const [open, setOpen] = useState(() => {
    try { return localStorage.getItem(storeKey) !== '1' }
    catch { return true }
  })

  const dismiss = () => {
    setOpen(false)
    try { localStorage.setItem(storeKey, '1') } catch {}
  }
  const restore = () => {
    setOpen(true)
    try { localStorage.removeItem(storeKey) } catch {}
  }

  // Compact button shown when dismissed
  if (!open) {
    return (
      <button
        onClick={restore}
        title="Show help for this page"
        className="inline-flex items-center gap-1.5 text-xs font-semibold text-primary hover:text-primary-dark bg-primary-light border border-primary/30 rounded-lg px-2.5 py-1.5"
      >
        <HelpCircle size={13} /> Help — How does this page work?
      </button>
    )
  }

  return (
    <div className="card border-2 border-primary/40 bg-primary-light/40">
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 w-9 h-9 rounded-full bg-primary text-white flex items-center justify-center shadow">
          <BookOpen size={18} />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2 mb-1.5">
            <h3 className="font-extrabold text-ink text-base leading-tight">{title}</h3>
            <button
              onClick={dismiss}
              title="Hide help (you can bring it back any time)"
              className="text-sub hover:text-ink p-1 -m-1 flex-shrink-0">
              <X size={16} />
            </button>
          </div>

          {whatIsThis && (
            <p className="text-sm text-ink mb-2.5 leading-snug">{whatIsThis}</p>
          )}

          {steps.length > 0 && (
            <div className="mb-2.5">
              <div className="text-xs font-bold text-primary uppercase tracking-wide mb-1.5">
                How to use it
              </div>
              <ol className="space-y-1">
                {steps.map((step, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-ink">
                    <span className="flex-shrink-0 w-5 h-5 rounded-full bg-primary text-white text-xs font-bold flex items-center justify-center mt-0.5">
                      {i + 1}
                    </span>
                    <span className="leading-snug" dangerouslySetInnerHTML={{ __html: step }} />
                  </li>
                ))}
              </ol>
            </div>
          )}

          {tips.length > 0 && (
            <div className="mb-2.5">
              <div className="text-xs font-bold text-amber-700 uppercase tracking-wide mb-1.5">
                Pro tips
              </div>
              <ul className="space-y-0.5">
                {tips.map((tip, i) => (
                  <li key={i} className="text-sm text-ink leading-snug flex items-start gap-1.5">
                    <span className="text-amber-600 font-bold mt-0.5">★</span>
                    <span dangerouslySetInnerHTML={{ __html: tip }} />
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="text-xs text-sub bg-white/70 rounded-lg p-2 border border-border flex items-start gap-1.5">
            <Info size={12} className="flex-shrink-0 mt-0.5 text-primary" />
            <span>{disclaimer}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
