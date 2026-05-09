import type { Anomaly } from '@/types';

interface Props {
  anomalies: Anomaly[];
  maxVisible?: number;
  onResolve?: (id: string) => void;
}

const SEVERITY_COLORS: Record<string, string> = {
  low: '#4ade80', medium: '#fb923c', high: '#f87171', critical: '#dc2626',
};

const ANOMALY_ICONS: Record<string, string> = {
  wheel_stuck: '⚙', comm_loss: '📡', energy_spike: '⚡',
  sensor_fault: '🔬', geyser_proximity: '🌋', low_battery: '🔋',
  path_blocked: '🚧', unknown: '❓',
};

const RESOLUTION_LABELS: Record<string, string> = {
  pending: 'Pending',
  auto_recovered: 'Auto-recovered',
  replanned: 'Replanned',
  aborted: 'Aborted',
  ignored: 'Dismissed',
};

export function AnomalyAlert({ anomalies, maxVisible = 5, onResolve }: Props) {
  const visible = anomalies.slice(0, maxVisible);

  if (visible.length === 0) {
    return (
      <div style={{ color: 'var(--text-faint)', fontSize: 12, textAlign: 'center', padding: '16px 0' }}>
        No anomalies detected
      </div>
    );
  }

  return (
    <div>
      {visible.map((a) => {
        const c = SEVERITY_COLORS[a.severity] ?? '#6b7280';
        const resolved = a.resolution !== 'pending';
        return (
          <div key={a.id} style={{
            background: 'var(--surface)',
            border: `1px solid ${resolved ? 'var(--border)' : c + '40'}`,
            borderLeft: `3px solid ${resolved ? 'var(--border)' : c}`,
            borderRadius: 6,
            padding: '8px 12px',
            marginBottom: 6,
            opacity: resolved ? 0.55 : 1,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)' }}>
                {ANOMALY_ICONS[a.type] ?? '!'} {a.type.replace(/_/g, ' ')}
              </span>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <span style={{ fontSize: 10, color: resolved ? 'var(--text-faint)' : c, fontWeight: 700, textTransform: 'uppercase' }}>
                  {resolved ? RESOLUTION_LABELS[a.resolution] : a.severity}
                </span>
                {!resolved && onResolve && (
                  <button
                    onClick={() => onResolve(a.id)}
                    title={
                      a.type === 'comm_loss' ? 'Restore communication link' :
                      a.type === 'low_battery' ? 'Emergency recharge to 100%' :
                      'Dismiss anomaly'
                    }
                    style={{
                      background: 'none',
                      border: `1px solid var(--border)`,
                      borderRadius: 4,
                      color: 'var(--text-muted)',
                      cursor: 'pointer',
                      fontSize: 10,
                      padding: '1px 6px',
                      fontFamily: 'inherit',
                    }}
                  >
                    {a.type === 'comm_loss' ? 'Restore comms' :
                     a.type === 'low_battery' ? 'Recharge' :
                     'Dismiss'}
                  </button>
                )}
              </div>
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-sec)', marginTop: 4 }}>{a.description}</div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 3 }}>
              ({a.x}, {a.y}) · {new Date(a.detected_at).toLocaleTimeString()}
            </div>
          </div>
        );
      })}
    </div>
  );
}
