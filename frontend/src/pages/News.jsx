import React, { useEffect, useState } from 'react'
import { ExternalLink, RefreshCw, TrendingUp } from 'lucide-react'
import { useApi } from '../hooks/useApi'

const relTime = (iso) => {
  if (!iso) return ''
  try {
    const diff = (Date.now() - new Date(iso)) / 1000
    if (diff < 3600)  return `${Math.floor(diff / 60)}m ago`
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
    return `${Math.floor(diff / 86400)}d ago`
  } catch { return '' }
}

export default function News() {
  const [articles, setArticles] = useState([])
  const [filter, setFilter] = useState('all')
  const { call, loading } = useApi()

  const load = async () => {
    const data = await call('/api/news?limit=40')
    if (data) setArticles(data)
  }

  useEffect(() => { load() }, [])

  const displayed = filter === 'strategy'
    ? articles.filter(a => a.strategy_relevance > 0)
    : articles

  return (
    <div className="p-5 space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-bold text-ink">Market News & Insights</h1>
          <p className="text-sm text-muted mt-0.5">Strategy-scored — articles mentioning cycle signals rank higher</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setFilter('all')}
            className={`btn text-xs ${filter === 'all' ? 'btn-primary' : 'btn-ghost'}`}>All</button>
          <button onClick={() => setFilter('strategy')}
            className={`btn text-xs ${filter === 'strategy' ? 'btn-primary' : 'btn-ghost'}`}>
            <TrendingUp size={12} /> Strategy Only
          </button>
          <button onClick={load} disabled={loading} className="btn-ghost text-xs">
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
        </div>
      </div>

      {loading && articles.length === 0 && (
        <div className="text-muted text-sm flex items-center gap-2">
          <RefreshCw size={14} className="animate-spin" /> Fetching news…
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {displayed.map((a, i) => (
          <a key={i} href={a.link} target="_blank" rel="noopener noreferrer"
            className="card hover:shadow-card-hover transition-shadow group block">
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                  <span className="text-xs font-semibold text-primary">{a.source || a.publisher}</span>
                  <span className="text-xs text-muted">{relTime(a.published)}</span>
                  {a.strategy_relevance > 0 && (
                    <span className="text-xs bg-amber-50 text-amber-600 border border-amber-200 rounded-full px-2 py-0.5 font-medium">
                      signal ×{a.strategy_relevance}
                    </span>
                  )}
                </div>
                <h3 className="text-sm font-medium text-ink group-hover:text-primary transition-colors leading-snug">
                  {a.title}
                </h3>
                {a.summary && (
                  <p className="text-xs text-muted mt-1 line-clamp-2">{a.summary}</p>
                )}
                {a.tags?.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {a.tags.slice(0, 4).map(tag => (
                      <span key={tag} className="text-xs bg-primary-light text-primary rounded px-1.5 py-0.5">{tag}</span>
                    ))}
                  </div>
                )}
              </div>
              <ExternalLink size={13} className="text-muted group-hover:text-primary flex-shrink-0 mt-0.5" />
            </div>
          </a>
        ))}
      </div>

      {!loading && displayed.length === 0 && (
        <div className="text-center py-16 text-muted">No articles. Try refreshing.</div>
      )}
    </div>
  )
}
