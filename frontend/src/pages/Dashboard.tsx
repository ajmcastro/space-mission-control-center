import { useMissions, useRovers } from '@/hooks/useMissions';
import { telemetryApi } from '@/services/api';
import { useQuery } from '@tanstack/react-query';
import { MissionCard } from '@/components/MissionCard';
import { AnomalyAlert } from '@/components/AnomalyAlert';
import type { Mission } from '@/types';

function StatBox({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: 10,
      padding: '16px 20px',
      minWidth: 140,
    }}>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ fontSize: 28, fontWeight: 800, color: 'var(--text)', lineHeight: 1 }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: 11, color: 'var(--text-faint)', marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

export function Dashboard() {
  const { data: missions = [], isLoading } = useMissions();
  const { data: rovers = [] } = useRovers();
  const { data: anomalies = [] } = useQuery({
    queryKey: ['anomalies'],
    queryFn: () => telemetryApi.getAnomalies(),
    refetchInterval: 5000,
  });

  const active    = missions.filter((m: Mission) => m.status === 'active').length;
  const completed = missions.filter((m: Mission) => m.status === 'completed').length;
  const failed    = missions.filter((m: Mission) => m.status === 'failed').length;
  const avgBattery = rovers.length
    ? Math.round(rovers.reduce((s, r) => s + r.battery_pct, 0) / rovers.length)
    : 0;

  return (
    <div style={{ padding: '24px 32px', maxWidth: 1400, margin: '0 auto' }}>
      <header style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 22, fontWeight: 800, color: 'var(--text)', margin: 0 }}>
          Mission Control — Enceladus Surface Operations
        </h1>
        <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 6 }}>
          Real-time rover coordination · Saturn System · {new Date().toUTCString()}
        </p>
      </header>

      {/* Stats */}
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginBottom: 28 }}>
        <StatBox label="Total Missions" value={missions.length} />
        <StatBox label="Active"    value={active}    sub="missions running" />
        <StatBox label="Completed" value={completed} />
        <StatBox label="Failed"    value={failed} />
        <StatBox label="Rovers"    value={rovers.length} sub="deployed" />
        <StatBox label="Avg Battery" value={`${avgBattery}%`} sub="across fleet" />
        <StatBox label="Anomalies" value={anomalies.length} sub="total detected" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 24, alignItems: 'start' }}>
        {/* Mission list */}
        <div>
          <h2 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-sec)', margin: '0 0 14px 0' }}>
            All Missions
          </h2>
          {isLoading && <p style={{ color: 'var(--text-muted)' }}>Loading missions…</p>}
          {!isLoading && missions.length === 0 && (
            <div style={{
              background: 'var(--surface)',
              border: '1px dashed var(--border)',
              borderRadius: 10, padding: 32, textAlign: 'center',
              color: 'var(--text-muted)',
            }}>
              <div style={{ fontSize: 36, marginBottom: 12 }}>🛸</div>
              <div>No missions yet. Create one in Mission Planner.</div>
            </div>
          )}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12 }}>
            {missions.map((m: Mission) => <MissionCard key={m.id} mission={m} />)}
          </div>
        </div>

        {/* Anomaly feed */}
        <div>
          <h2 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-sec)', margin: '0 0 14px 0' }}>
            Anomaly Feed
          </h2>
          <AnomalyAlert anomalies={anomalies} maxVisible={10} />
        </div>
      </div>
    </div>
  );
}
