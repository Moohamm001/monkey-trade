import React, { useMemo } from 'react'
import { ComposedChart, Bar, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  const d = payload[0]?.payload
  return (
    <div className="bg-white border border-border rounded-xl shadow-card-hover p-3 text-xs space-y-1 min-w-[140px]">
      <div className="text-sub font-medium">{label}</div>
      <div className="grid grid-cols-2 gap-x-3 gap-y-0.5">
        <span className="text-muted">Open</span><span className="font-mono text-ink">{d?.Open?.toFixed(2)}</span>
        <span className="text-muted">High</span><span className="font-mono text-green-600">{d?.High?.toFixed(2)}</span>
        <span className="text-muted">Low</span><span className="font-mono text-red-500">{d?.Low?.toFixed(2)}</span>
        <span className="text-muted">Close</span><span className="font-mono font-bold text-ink">{d?.Close?.toFixed(2)}</span>
        <span className="text-muted">Vol</span><span className="font-mono text-primary">{d?.Volume?.toLocaleString()}</span>
      </div>
    </div>
  )
}

export default function CandlestickChart({ data = [] }) {
  const thinned = useMemo(() => {
    if (data.length <= 120) return data
    const step = Math.ceil(data.length / 120)
    return data.filter((_, i) => i % step === 0)
  }, [data])

  return (
    <ResponsiveContainer width="100%" height={260}>
      <ComposedChart data={thinned} margin={{ top: 5, right: 5, bottom: 0, left: 0 }}>
        <XAxis dataKey="date" tickFormatter={v => v?.slice(5)}
          tick={{ fill: '#A0AABF', fontSize: 10 }} axisLine={false} tickLine={false}
          interval="preserveStartEnd" />
        <YAxis domain={['auto', 'auto']}
          tick={{ fill: '#A0AABF', fontSize: 10 }} axisLine={false} tickLine={false}
          width={52} tickFormatter={v => v.toFixed(0)} />
        <Tooltip content={<CustomTooltip />} />
        <Line type="monotone" dataKey="Close" stroke="#6366F1" dot={false} strokeWidth={1.8} />
        <Bar dataKey="Volume" yAxisId={1} fill="#E0E7FF" opacity={0.8} />
        <YAxis yAxisId={1} hide domain={[0, d => d * 8]} />
      </ComposedChart>
    </ResponsiveContainer>
  )
}
