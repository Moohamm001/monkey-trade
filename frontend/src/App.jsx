import React, { useState } from 'react'
import { Routes, Route, NavLink } from 'react-router-dom'
import {
  BarChart2, Search, BookOpen, Newspaper, Star,
  LayoutDashboard, Activity, Radar, FlaskConical,
  ChevronLeft, ChevronRight, TrendingUp, Bot, Wallet
} from 'lucide-react'
import Dashboard from './pages/Dashboard'
import CycleDetector from './pages/CycleDetector'
import Screener from './pages/Screener'
import Watchlist from './pages/Watchlist'
import Education from './pages/Education'
import News from './pages/News'
import OrderFlow from './pages/OrderFlow'
import WhaleTracker from './pages/WhaleTracker'
import QuantEngine from './pages/QuantEngine'
import BotControl from './pages/BotControl'
import Trading from './pages/Trading'

const NAV = [
  { to: '/',          icon: LayoutDashboard, label: 'Dashboard',     desc: 'Stock analysis & cycle stage' },
  { to: '/cycle',     icon: Search,          label: 'Cycle Detector', desc: 'Detect Wyckoff market phases' },
  { to: '/screener',  icon: BarChart2,        label: 'Screener',       desc: 'Scan stocks by stage' },
  { to: '/orderflow', icon: Activity,         label: 'Order Flow',     desc: 'Bid/ask pressure & tape' },
  { to: '/whale',     icon: Radar,            label: 'Whale Tracker',  desc: 'Institutional volume spikes' },
  { to: '/quant',       icon: FlaskConical, label: 'Quant Engine',  desc: 'HMM · Kalman · Kelly sizing' },
  { to: '/bot',         icon: Bot,          label: 'Auto Bot',       desc: 'Autonomous scanner & learning model' },
  { to: '/portfolio',   icon: Wallet,       label: 'Trading',        desc: 'Portfolio + forward-test paper trades' },
  { to: '/watchlist',   icon: Star,          label: 'Watchlist',     desc: 'Your saved tickers' },
  { to: '/news',      icon: Newspaper,        label: 'Market News',    desc: 'Latest market headlines' },
  { to: '/education', icon: BookOpen,         label: 'Strategy Guide', desc: 'Learn Wyckoff & cycles' },
]

export default function App() {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div className="flex h-screen overflow-hidden bg-surface">

      {/* ── Sidebar ── */}
      <aside
        className={`flex-shrink-0 bg-white border-r border-border flex flex-col shadow-sm transition-all duration-200 ${
          collapsed ? 'w-14' : 'w-56'
        }`}
      >
        {/* Logo */}
        <div className={`border-b border-border flex items-center ${collapsed ? 'justify-center px-0 py-3' : 'px-4 py-4 gap-3'}`}>
          <div className="relative flex-shrink-0">
            <img
              src="/monkey_pic.jpg"
              alt="MonkeyTrade"
              className="w-9 h-9 rounded-xl object-cover shadow border-2 border-primary/20"
            />
            <span className="absolute -bottom-1 -right-1 w-3.5 h-3.5 bg-green-400 border-2 border-white rounded-full" title="Live" />
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <div className="font-extrabold text-ink text-sm leading-tight tracking-tight">MonkeyTrade</div>
              <div className="text-xs text-primary font-medium mt-0.5 flex items-center gap-1">
                <TrendingUp size={10} />
                Cycle Intelligence
              </div>
            </div>
          )}
        </div>

        {/* Nav */}
        <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto">
          {NAV.map(({ to, icon: Icon, label, desc }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              title={collapsed ? `${label} — ${desc}` : desc}
              className={({ isActive }) =>
                `group flex items-center gap-2.5 rounded-lg text-sm font-medium transition-all duration-150 ${
                  collapsed ? 'justify-center px-0 py-2.5' : 'px-3 py-2.5'
                } ${
                  isActive
                    ? 'bg-primary/10 text-primary font-semibold shadow-sm ring-1 ring-primary/20'
                    : 'text-sub hover:bg-surface hover:text-ink'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <Icon size={16} className={isActive ? 'text-primary' : 'text-muted group-hover:text-ink'} />
                  {!collapsed && (
                    <div className="min-w-0">
                      <div className="truncate leading-tight">{label}</div>
                    </div>
                  )}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Collapse toggle */}
        <div className="px-2 py-2 border-t border-border">
          <button
            onClick={() => setCollapsed(v => !v)}
            className={`w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-xs text-muted hover:bg-surface hover:text-ink transition-colors ${
              collapsed ? 'justify-center' : ''
            }`}
          >
            {collapsed
              ? <ChevronRight size={14} />
              : <><ChevronLeft size={14} /><span>Collapse</span></>
            }
          </button>
          {!collapsed && (
            <div className="px-2.5 pt-1.5 pb-0.5">
              <div className="text-xs text-muted">MonkeyTrade v1.0</div>
              <div className="text-xs text-muted/70">via Yahoo Finance</div>
            </div>
          )}
        </div>
      </aside>

      {/* ── Main ── */}
      <div className="flex-1 flex flex-col overflow-hidden">

        {/* Top bar */}
        <header className="flex-shrink-0 bg-white border-b border-border px-5 py-2.5 flex items-center justify-between shadow-sm">
          <div className="flex items-center gap-2">
            <img src="/monkey_pic.jpg" alt="" className="w-6 h-6 rounded-lg object-cover opacity-80" />
            <span className="text-sm font-semibold text-ink">MonkeyTrade</span>
            <span className="hidden sm:inline text-xs text-muted">— Wyckoff Cycle Analytics</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 text-xs text-green-700 bg-green-50 border border-green-200 px-2.5 py-1 rounded-full font-semibold">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
              Live
            </span>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto">
          <Routes>
            <Route path="/"          element={<Dashboard />} />
            <Route path="/cycle"     element={<CycleDetector />} />
            <Route path="/screener"  element={<Screener />} />
            <Route path="/watchlist" element={<Watchlist />} />
            <Route path="/news"      element={<News />} />
            <Route path="/orderflow" element={<OrderFlow />} />
            <Route path="/whale"     element={<WhaleTracker />} />
            <Route path="/quant"       element={<QuantEngine />} />
            <Route path="/forwardtest" element={<Trading />} />
            <Route path="/bot"         element={<BotControl />} />
            <Route path="/portfolio"   element={<Trading />} />
            <Route path="/education"   element={<Education />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}
