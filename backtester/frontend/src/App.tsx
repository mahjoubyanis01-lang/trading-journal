import { BrowserRouter, NavLink, Navigate, Route, Routes } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Sessions from './pages/Sessions'
import SessionDetailPage from './pages/SessionDetail'
import Stats from './pages/Stats'
import ConfigPage from './pages/Config'

const NAV_ITEMS = [
  { to: '/', label: 'Tableau de bord', icon: '◧', end: true },
  { to: '/sessions', label: 'Historique', icon: '≣', end: false },
  { to: '/stats', label: 'Statistiques', icon: '∿', end: false },
  { to: '/config', label: 'Configuration', icon: '⚙', end: false },
]

export default function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <aside className="sidebar">
          <div className="brand">
            <div className="brand-title">S&amp;P 500 Macro Bias</div>
            <div className="brand-sub">Backtester</div>
          </div>
          <nav className="nav" aria-label="Navigation principale">
            {NAV_ITEMS.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end}>
                <span className="nav-icon" aria-hidden="true">
                  {item.icon}
                </span>
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="sidebar-foot">
            Information ≤ 15:29 Paris · mesure 09:30 NY → minuit Paris
          </div>
        </aside>
        <main className="main">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/sessions" element={<Sessions />} />
            <Route path="/sessions/:date" element={<SessionDetailPage />} />
            <Route path="/stats" element={<Stats />} />
            <Route path="/config" element={<ConfigPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
