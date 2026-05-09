import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import type { TelemetryEvent, Rover } from '@/types';

interface Props {
  rovers: Rover[];
  // Polled events (HTTP) — always populated after plan runs regardless of WS state.
  telemetryEvents: TelemetryEvent[];
  // WebSocket buffer — used to supplement live events not yet persisted.
  telemetryBuffer: Record<string, TelemetryEvent[]>;
}

const ROVER_COLORS = ['#38bdf8', '#4ade80', '#fb923c', '#f472b6'];

export function BatteryChart({ rovers, telemetryEvents, telemetryBuffer }: Props) {
  if (rovers.length === 0) {
    return (
      <p style={{ color: 'var(--text-muted)', fontSize: 12 }}>
        No rovers deployed — execute a plan to see battery telemetry.
      </p>
    );
  }

  // Merge polled events with live WS buffer, deduplicated by event id.
  const seenIds = new Set<string>();
  const merged: TelemetryEvent[] = [];
  for (const ev of [...telemetryEvents, ...Object.values(telemetryBuffer).flat()]) {
    if (!seenIds.has(ev.id)) {
      seenIds.add(ev.id);
      merged.push(ev);
    }
  }

  // Build a unified timeline: each point has timestamp + battery_pct per rover
  const allEvents = rovers.flatMap(r =>
    merged
      .filter(e => e.rover_id === r.id && e.battery_pct != null)
      .map(e => ({ roverId: r.id, roverName: r.name, t: e.timestamp, pct: e.battery_pct! }))
  );

  if (allEvents.length === 0) {
    return (
      <p style={{ color: 'var(--text-muted)', fontSize: 12 }}>
        No battery telemetry yet — execute a plan to start streaming.
      </p>
    );
  }

  // Collect all timestamps and sort; for each, capture latest known pct per rover
  const byRover: Record<string, { t: string; pct: number }[]> = {};
  rovers.forEach(r => {
    byRover[r.id] = merged
      .filter(e => e.rover_id === r.id && e.battery_pct != null)
      .map(e => ({ t: e.timestamp, pct: e.battery_pct! }))
      .sort((a, b) => a.t.localeCompare(b.t));
  });

  // Sample at most 100 points per rover, pick every Nth
  const MAX_POINTS = 100;
  const chartData: Record<string, number | string>[] = [];
  const sampleRover = rovers[0];
  const src = byRover[sampleRover.id] ?? [];
  const step = Math.max(1, Math.ceil(src.length / MAX_POINTS));
  src.filter((_, i) => i % step === 0).forEach(({ t }) => {
    const point: Record<string, number | string> = {
      time: new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
    };
    rovers.forEach(r => {
      const events = byRover[r.id] ?? [];
      const closest = events.reduce<{ t: string; pct: number } | null>((best, ev) => {
        if (!best) return ev;
        return Math.abs(new Date(ev.t).getTime() - new Date(t).getTime()) <
               Math.abs(new Date(best.t).getTime() - new Date(t).getTime())
          ? ev : best;
      }, null);
      if (closest) point[r.name] = parseFloat(closest.pct.toFixed(1));
    });
    chartData.push(point);
  });

  return (
    <div>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>
        Battery level over time · {chartData.length} data points
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={chartData} margin={{ top: 4, right: 16, left: -20, bottom: 0 }}>
          <XAxis
            dataKey="time"
            tick={{ fontSize: 10, fill: 'var(--text-muted)' }}
            interval="preserveStartEnd"
          />
          <YAxis
            domain={[0, 100]}
            tick={{ fontSize: 10, fill: 'var(--text-muted)' }}
            unit="%"
          />
          <Tooltip
            contentStyle={{
              background: 'var(--surface)', border: '1px solid var(--border)',
              borderRadius: 6, fontSize: 11,
            }}
            labelStyle={{ color: 'var(--text-muted)' }}
            formatter={(val) => [`${val}%`, '']}
          />
          {rovers.length > 1 && (
            <Legend wrapperStyle={{ fontSize: 11, color: 'var(--text-sec)' }} />
          )}
          {rovers.map((r, i) => (
            <Line
              key={r.id}
              type="monotone"
              dataKey={r.name}
              stroke={ROVER_COLORS[i % ROVER_COLORS.length]}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
