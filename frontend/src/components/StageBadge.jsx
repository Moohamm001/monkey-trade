import React from 'react'
import clsx from 'clsx'

const META = {
  accumulation: { label: 'Accumulation', pill: 'bg-blue-600 text-white' },
  markup:       { label: 'Markup',       pill: 'bg-green-600 text-white' },
  distribution: { label: 'Distribution', pill: 'bg-amber-500 text-white' },
  markdown:     { label: 'Markdown',     pill: 'bg-red-600   text-white' },
  unknown:      { label: 'Unknown',      pill: 'bg-gray-400  text-white' },
}

export default function StageBadge({ stage, confidence, size = 'sm' }) {
  const meta = META[stage] || META.unknown
  return (
    <span className={clsx(
      'inline-flex items-center gap-1.5 rounded-full font-semibold shadow-sm',
      size === 'sm' ? 'px-2.5 py-0.5 text-xs' : 'px-3.5 py-1 text-sm',
      meta.pill
    )}>
      <span>{meta.label}</span>
      {confidence != null && (
        <span className="bg-white/25 rounded-full px-1.5 py-0.5 text-xs font-bold">
          {confidence}%
        </span>
      )}
    </span>
  )
}
