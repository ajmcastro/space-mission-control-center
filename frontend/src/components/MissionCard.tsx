import type { Mission } from '@/types';
import { Link } from 'react-router-dom';

interface Props { mission: Mission }

const STATUS_COLORS: Record<string, string> = {
  draft: '#64748b', planned: '#38bdf8', active: '#22c55e',
  paused: '#f59e0b', completed: '#a855f7', failed: '#ef4444', aborted: '#dc2626',
};

export function MissionCard({ mission }: Props) {
  const c = STATUS_COLORS[mission.status] ?? '#6b7280';

  return (
    <Link to={`/missions/${mission.id}`} style={{ textDecoration: 'none' }}>
      <div
        style={{
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          borderRadius: 10,
          padding: 16,
          cursor: 'pointer',
        }}
        onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--accent)')}
        onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border)')}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
          <span style={{ fontWeight: 700, color: 'var(--text)', fontSize: 14 }}>{mission.name}</span>
          <span style={{
            background: c + '22',
            color: c,
            border: `1px solid ${c}55`,
            fontSize: 10, padding: '2px 8px', borderRadius: 12,
            fontWeight: 600, textTransform: 'uppercase',
          }}>
            {mission.status}
          </span>
        </div>

        {mission.description && (
          <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '0 0 10px 0' }}>
            {mission.description}
          </p>
        )}

        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-faint)', marginBottom: 4 }}>
            <span>{mission.objectives.length} objectives</span>
            <span>{mission.progress_pct}%</span>
          </div>
          <div style={{ background: 'var(--border)', borderRadius: 4, height: 4 }}>
            <div style={{
              width: `${mission.progress_pct}%`, height: '100%',
              background: c, borderRadius: 4, transition: 'width 0.4s',
            }} />
          </div>
        </div>

        <div style={{ marginTop: 10, fontSize: 11, color: 'var(--text-faint)', display: 'flex', gap: 16 }}>
          <span>Rovers: {mission.rover_ids.length}</span>
          <span>{new Date(mission.created_at).toLocaleDateString()}</span>
        </div>
      </div>
    </Link>
  );
}
