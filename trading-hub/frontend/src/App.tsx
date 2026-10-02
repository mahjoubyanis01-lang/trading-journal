import { useState } from 'react';
import { Route, Routes } from 'react-router-dom';
import { Sidebar } from './components/layout/Sidebar';
import { TopBar } from './components/layout/TopBar';
import { AddAccountModal } from './components/AddAccountModal';
import { AddAccountContext } from './components/AddAccountContext';
import { useDashboard } from './hooks/data';
import { Dashboard } from './pages/Dashboard';
import { Accounts } from './pages/Accounts';
import { AccountDetailPage } from './pages/AccountDetail';
import { PropFirms } from './pages/PropFirms';
import { PropFirmDetailPage } from './pages/PropFirmDetail';
import { Robots } from './pages/Robots';
import { Markets } from './pages/Markets';
import { Attention } from './pages/Attention';
import { SettingsPage } from './pages/Settings';

export default function App() {
  const [addOpen, setAddOpen] = useState(false);
  const dashboard = useDashboard();

  const attentionCount = dashboard.data
    ? (dashboard.data.by_health.attention ?? 0) + (dashboard.data.by_health.error ?? 0)
    : undefined;

  return (
    <AddAccountContext.Provider value={() => setAddOpen(true)}>
      <div className="flex h-screen overflow-hidden bg-bg text-zinc-200">
        <Sidebar attentionCount={attentionCount} />
        <div className="flex min-w-0 flex-1 flex-col">
          <TopBar dashboard={dashboard.data} onAddAccount={() => setAddOpen(true)} />
          <main className="flex-1 overflow-y-auto">
            <div className="mx-auto max-w-[1600px] px-6 py-6">
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/accounts" element={<Accounts />} />
                <Route path="/accounts/:id" element={<AccountDetailPage />} />
                <Route path="/prop-firms" element={<PropFirms />} />
                <Route path="/prop-firms/:id" element={<PropFirmDetailPage />} />
                <Route path="/robots" element={<Robots />} />
                <Route path="/markets" element={<Markets />} />
                <Route path="/attention" element={<Attention />} />
                <Route path="/settings" element={<SettingsPage />} />
              </Routes>
            </div>
          </main>
        </div>
      </div>

      <AddAccountModal
        open={addOpen}
        onClose={() => setAddOpen(false)}
        onCreated={() => dashboard.refetch()}
      />
    </AddAccountContext.Provider>
  );
}
