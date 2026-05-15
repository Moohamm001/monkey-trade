import React from 'react'

const STAGES = [
  { key: 'accumulation', label: 'Accumulation', color: '#2563EB', bg: 'bg-blue-100' },
  { key: 'markup',       label: 'Markup',       color: '#16A34A', bg: 'bg-green-100' },
  { key: 'distribution', label: 'Distribution', color: '#D97706', bg: 'bg-amber-100' },
  { key: 'markdown',     label: 'Markdown',     color: '#DC2626', bg: 'bg-red-100' },
]

export default function StageScoreBar({ scores = {} }) {
  return (
    <div className="space-y-2">
      {STAGES.map(({ key, label, color, bg }) => {
        const val = scores[key] || 0
        return (
          <div key={key} className="flex items-center gap-2.5">
            <div className="w-20 text-xs text-sub text-right">{label}</div>
            <div className={`flex-1 h-2 ${bg} rounded-full overflow-hidden`}>
              <div className="h-full rounded-full transition-all duration-500"
                style={{ width: `${val}%`, background: color }} />
            </div>
            <div className="w-7 text-xs text-sub text-right font-mono">{val}%</div>
          </div>
        )
      })}
    </div>
  )
}
