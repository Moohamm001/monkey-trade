import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Wallet, Target } from 'lucide-react'
import Portfolio from './Portfolio'
import ForwardTest from './ForwardTest'

const SECTIONS = [
  { id: 'portfolio',   path: '/portfolio',   label: 'Portfolio',    icon: Wallet, desc: '$10k auto-managed virtual portfolio' },
  { id: 'forwardtest', path: '/forwardtest', label: 'Forward Test', icon: Target, desc: 'Manual paper trades & learning log' },
]

export default function Trading() {
  const location = useLocation()
  const navigate = useNavigate()

  const initial = SECTIONS.find(s => location.pathname.startsWith(s.path))?.id ?? 'portfolio'
  const [section, setSection] = useState(initial)

  const handleSwitch = (s) => {
    setSection(s.id)
    navigate(s.path, { replace: true })
  }

  return (
    <div className="flex flex-col">
      {/* Section switcher */}
      <div className="flex-shrink-0 bg-white border-b border-border px-3 pt-3">
        <div className="flex items-end gap-1">
          {SECTIONS.map(s => {
            const Icon = s.icon
            const active = section === s.id
            return (
              <button
                key={s.id}
                onClick={() => handleSwitch(s)}
                className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold border-b-2 -mb-px transition-colors rounded-t-lg ${
                  active
                    ? 'border-primary text-primary bg-primary/5'
                    : 'border-transparent text-muted hover:text-ink hover:bg-surface'
                }`}
                title={s.desc}
              >
                <Icon size={15} />
                {s.label}
              </button>
            )
          })}
        </div>
      </div>

      {/* Active section */}
      <div className="flex-1">
        {section === 'portfolio'   && <Portfolio />}
        {section === 'forwardtest' && <ForwardTest />}
      </div>
    </div>
  )
}
