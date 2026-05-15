import React from 'react'
import { Routes, Route, NavLink } from 'react-router-dom'
import { BarChart2, Search, BookOpen, Newspaper, Star, LayoutDashboard } from 'lucide-react'
import Dashboard from './pages/Dashboard'
import CycleDetector from './pages/CycleDetector'
import Screener from './pages/Screener'
import Watchlist from './pages/Watchlist'
import Education from './pages/Education'
import News from './pages/News'

const NAV = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/cycle', icon: Search, label: 'Cycle Detector' },
  { to: '/screener', icon: BarChart2, label: 'Screener' },
  { to: '/watchlist', icon: Star, label: 'Watchlist' },
  { to: '/news', icon: Newspaper, label: 'Market News' },
  { to: '/education', icon: BookOpen, label: 'Strategy Guide' },
]

export default function App() {
  return (
    <div className="flex h-screen overflow-hidden bg-surface">
      {/* Sidebar */}
      <aside className="w-52 flex-shrink-0 bg-white border-r border-border flex flex-col shadow-sm">
        <div className="px-5 py-5 border-b border-border">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-primary flex items-center justify-center text-white text-lg shadow">
              🐒
            </div>
            <div>
              <div className="font-bold text-ink text-sm leading-none">MonkeyTrade</div>
              <div className="text-xs text-muted mt-0.5">Cycle Intelligence</div>
            </div>
          </div>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-0.5">
          {NAV.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-primary-light text-primary font-semibold'
                    : 'text-sub hover:bg-surface hover:text-ink'
                }`
              }
            >
              <Icon size={15} />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="px-5 py-4 border-t border-border">
          <div className="text-xs text-muted">MonkeyTrade v1.0</div>
          <div className="text-xs text-muted mt-0.5">Data via Yahoo Finance</div>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/cycle" element={<CycleDetector />} />
          <Route path="/screener" element={<Screener />} />
          <Route path="/watchlist" element={<Watchlist />} />
          <Route path="/news" element={<News />} />
          <Route path="/education" element={<Education />} />
        </Routes>
      </main>
    </div>
  )
}
