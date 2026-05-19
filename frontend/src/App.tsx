import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import { useTheme } from '@/hooks/useTheme';
import { Dashboard } from '@/pages/Dashboard';
import { MissionPlanner } from '@/pages/MissionPlanner';
import { MissionView } from '@/pages/MissionView';
import { missionsApi, simulationApi } from '@/services/api';
import type { Mission, Rover } from '@/types';

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 2000 } },
});

function useLinkStatus() {
  const { data: missions = [] } = useQuery<Mission[]>({
    queryKey: ['missions'],
    queryFn: missionsApi.list,
    refetchInterval: 5000,
  });
  const { data: rovers = [] } = useQuery<Rover[]>({
    queryKey: ['rovers', undefined],
    queryFn: () => simulationApi.listRovers(),
    refetchInterval: 3000,
  });

  const activeMissionIds = new Set(missions.filter(m => m.status === 'active').map(m => m.id));
  const activeRovers     = rovers.filter(r => r.mission_id && activeMissionIds.has(r.mission_id));
  const commLost         = activeRovers.filter(r => r.state === 'comm_lost');

  if (activeMissionIds.size === 0) {
    return { label: 'NO ACTIVE MISSIONS', color: '#6b7280', detail: 'Δt +67 min (one-way)' } as const;
  }
  if (commLost.length > 0) {
    const names = commLost.map(r => r.name).join(', ');
    return { label: 'LINK DEGRADED', color: '#f59e0b', detail: `${commLost.length} rover${commLost.length > 1 ? 's' : ''} comm lost: ${names}` } as const;
  }
  return {
    label: 'LINK NOMINAL',
    color: '#22c55e',
    detail: `${activeRovers.length} rover${activeRovers.length !== 1 ? 's' : ''} · Δt +67 min`,
  } as const;
}

function Sidebar() {
  const { toggle, isDark } = useTheme();
  const link = useLinkStatus();

  return (
    <aside style={{
      width: 200,
      minHeight: '100vh',
      background: 'var(--bg-sidebar)',
      borderRight: '1px solid var(--border)',
      padding: '24px 12px',
      display: 'flex',
      flexDirection: 'column',
      gap: 4,
      position: 'fixed',
      left: 0, top: 0, bottom: 0,
    }}>
      {/* Logo */}
      <div style={{ marginBottom: 24, paddingLeft: 8 }}>
        <div style={{ fontSize: 14, fontWeight: 800, color: 'var(--accent)', lineHeight: 1.2 }}>
          ENCELADUS
        </div>
        <div style={{ fontSize: 10, color: 'var(--text-muted)', letterSpacing: '0.15em', textTransform: 'uppercase' }}>
          Mission Control
        </div>
      </div>

      {/* Nav links */}
      <NavLink to="/" end style={({ isActive }) => navStyle(isActive)}>
        Dashboard
      </NavLink>
      <NavLink to="/planner" style={({ isActive }) => navStyle(isActive)}>
        Mission Planner
      </NavLink>

      {/* Bottom: status + theme toggle */}
      <div style={{ marginTop: 'auto' }}>
        <div style={{
          padding: '10px 10px 12px',
          marginBottom: 12,
          borderTop: '1px solid var(--border)',
        }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 5, textTransform: 'uppercase', letterSpacing: '0.12em', fontWeight: 600 }}>
            Saturn System
          </div>
          <div style={{ fontSize: 12, color: link.color, fontWeight: 700, marginBottom: 3, transition: 'color 0.3s' }}>
            ● {link.label}
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', lineHeight: 1.4 }}>{link.detail}</div>
        </div>

        {/* Theme toggle */}
        <button
          onClick={toggle}
          title={`Switch to ${isDark ? 'light' : 'dark'} theme`}
          style={{
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 6,
            padding: '7px 10px',
            color: 'var(--text-sec)',
            fontSize: 12,
            cursor: 'pointer',
            fontFamily: 'inherit',
            fontWeight: 600,
          }}
        >
          <span style={{ fontSize: 15 }}>{isDark ? '☀️' : '🌙'}</span>
          {isDark ? 'Light mode' : 'Dark mode'}
        </button>
      </div>
    </aside>
  );
}

function navStyle(isActive: boolean): React.CSSProperties {
  return {
    color: isActive ? 'var(--text)' : 'var(--text-muted)',
    textDecoration: 'none',
    fontSize: 13,
    fontWeight: 600,
    padding: '6px 12px',
    borderRadius: 6,
    background: isActive ? 'var(--surface)' : 'transparent',
    display: 'block',
  };
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter future={{ v7_startTransition: true }}>
        <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--bg)' }}>
          <Sidebar />
          <main style={{ marginLeft: 200, flex: 1, overflowX: 'hidden' }}>
            <Routes>
              <Route path="/"            element={<Dashboard />} />
              <Route path="/planner"     element={<MissionPlanner />} />
              <Route path="/missions/:id" element={<MissionView />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
