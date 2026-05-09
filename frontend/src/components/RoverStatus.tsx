import type { Rover } from '@/types';

interface Props { rover: Rover }

const STATE_COLORS: Record<string, string> = {
  idle: '#22c55e', moving: '#3b82f6', sampling: '#f59e0b',
  charging: '#a855f7', stuck: '#ef4444', comm_lost: '#f97316', error: '#dc2626',
};

export function RoverStatus({ rover }: Props) {
  const batteryColor =
    rover.battery_pct > 50 ? 'var(--accent-green)' :
    rover.battery_pct > 20 ? 'var(--accent-amber)' : 'var(--accent-red)';

  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: 8,
      padding: 14,
      marginBottom: 10,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <span style={{ fontWeight: 700, color: 'var(--text)', fontSize: 13 }}>{rover.name}</span>
        <span style={{
          background: (STATE_COLORS[rover.state] ?? '#6b7280') + '28',
          color: STATE_COLORS[rover.state] ?? '#6b7280',
          fontSize: 10, padding: '2px 8px', borderRadius: 12,
          fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em',
        }}>
          {rover.state.replace('_', ' ')}
        </span>
      </div>

      <Row label="Position" value={`(${rover.x}, ${rover.y})`} />
      <Row label="Steps"    value={rover.steps_taken.toString()} />
      <Row label="Samples"  value={rover.samples_collected.toString()} />

      <div style={{ marginTop: 10 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-sec)', marginBottom: 4 }}>
          <span>Battery</span>
          <span style={{ color: batteryColor, fontWeight: 700 }}>{rover.battery_pct.toFixed(1)}%</span>
        </div>
        <div style={{ background: 'var(--border)', borderRadius: 4, height: 6, overflow: 'hidden' }}>
          <div style={{
            width: `${rover.battery_pct}%`, height: '100%',
            background: batteryColor, transition: 'width 0.4s ease',
          }} />
        </div>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
      <span style={{ color: 'var(--text-muted)' }}>{label}</span>
      <span style={{ color: 'var(--text-sec)', fontFamily: 'monospace' }}>{value}</span>
    </div>
  );
}
