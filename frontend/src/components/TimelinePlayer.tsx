import { useState, useEffect, useRef, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { telemetryApi } from '@/services/api';
import { GridMap } from './GridMap';
import type { Rover, Environment } from '@/types';

interface Props {
  missionId: string;
  rovers: Rover[];
  environment: Environment | null;
  targetCells?: [number, number][];
}

const SPEEDS = [
  { label: '0.5×', ms: 1000 },
  { label: '1×',   ms: 500  },
  { label: '2×',   ms: 250  },
  { label: '5×',   ms: 100  },
];

export function TimelinePlayer({ missionId, rovers, environment, targetCells = [] }: Props) {
  const [stepIdx, setStepIdx] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speedMs, setSpeedMs] = useState(500);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const { data: rawEvents = [], isLoading } = useQuery({
    queryKey: ['telemetry-timeline', missionId],
    queryFn: () => telemetryApi.getEvents(missionId, 5000),
    staleTime: 30_000,
  });

  // Only position events carry x/y; sort chronologically.
  const events = useMemo(
    () =>
      [...rawEvents]
        .filter(e => e.x != null && e.y != null)
        .sort((a, b) => a.timestamp.localeCompare(b.timestamp)),
    [rawEvents],
  );

  // Auto-play: advance one step every speedMs ms.
  useEffect(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    if (!playing) return;
    timerRef.current = setInterval(() => {
      setStepIdx(i => {
        if (i >= events.length - 1) { setPlaying(false); return i; }
        return i + 1;
      });
    }, speedMs);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [playing, speedMs, events.length]);

  const cIdx = Math.min(stepIdx, Math.max(0, events.length - 1));
  const currentEvent = events[cIdx] ?? null;
  const currentRover = rovers.find(r => r.id === currentEvent?.rover_id);

  // Build virtual rover snapshots at cIdx: last-known position + traversed path.
  const virtualRovers = useMemo((): Rover[] => {
    const slice = events.slice(0, cIdx + 1);
    return rovers.map(r => {
      const rEvents = slice.filter(e => e.rover_id === r.id);
      const last = rEvents[rEvents.length - 1];
      // Deduplicate consecutive identical positions for the path overlay.
      const pathHistory: [number, number][] = rEvents
        .filter((e, i, arr) => i === 0 || e.x !== arr[i - 1].x || e.y !== arr[i - 1].y)
        .map(e => [e.x!, e.y!]);
      return {
        ...r,
        x: last?.x ?? r.x,
        y: last?.y ?? r.y,
        battery: last?.battery ?? r.battery,
        battery_pct: last?.battery_pct ?? r.battery_pct,
        state: 'idle' as const,
        path_history: pathHistory,
      };
    });
  }, [rovers, events, cIdx]);

  if (isLoading) {
    return <p style={{ color: 'var(--text-muted)', fontSize: 12 }}>Loading telemetry…</p>;
  }
  if (events.length === 0) {
    return (
      <p style={{ color: 'var(--text-muted)', fontSize: 12 }}>
        No positional telemetry yet — execute a plan first.
      </p>
    );
  }

  const atStart = cIdx === 0;
  const atEnd   = cIdx >= events.length - 1;

  function ctrlBtn(label: string, onClick: () => void, disabled: boolean, accent = false) {
    return (
      <button
        onClick={onClick}
        disabled={disabled}
        style={{
          background: accent ? 'var(--btn-primary)' : disabled ? 'var(--border)' : 'var(--surface)',
          color: accent ? '#fff' : disabled ? 'var(--text-muted)' : 'var(--text)',
          border: `1px solid ${disabled ? 'var(--border)' : 'var(--border)'}`,
          borderRadius: 5, padding: '5px 11px', fontSize: 14,
          cursor: disabled ? 'not-allowed' : 'pointer',
          fontFamily: 'inherit', fontWeight: accent ? 700 : 400,
          minWidth: accent ? 72 : undefined,
        }}
      >
        {label}
      </button>
    );
  }

  return (
    <div>
      {/* Info bar */}
      <div style={{
        display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap',
        padding: '8px 12px', marginBottom: 12,
        background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8,
        fontSize: 12,
      }}>
        <span style={{ color: 'var(--text-muted)' }}>
          Step{' '}
          <span style={{ color: 'var(--text)', fontWeight: 700 }}>{cIdx + 1}</span>
          {' '}/ {events.length}
        </span>
        {currentEvent && (
          <>
            <span style={{ color: 'var(--text-muted)' }}>
              {new Date(currentEvent.timestamp).toLocaleTimeString([], {
                hour: '2-digit', minute: '2-digit', second: '2-digit',
              })}
            </span>
            {currentRover && (
              <span style={{ color: 'var(--accent)', fontWeight: 600 }}>{currentRover.name}</span>
            )}
            <span style={{ color: 'var(--text-sec)' }}>
              ({currentEvent.x}, {currentEvent.y})
            </span>
            {currentEvent.battery_pct != null && (
              <span style={{
                fontWeight: 600,
                color: currentEvent.battery_pct < 20 ? 'var(--accent-red)' : 'var(--accent-green)',
              }}>
                {currentEvent.battery_pct.toFixed(1)}% battery
              </span>
            )}
          </>
        )}
      </div>

      {/* Transport controls */}
      <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 10, flexWrap: 'wrap' }}>
        {ctrlBtn('⏮', () => { setPlaying(false); setStepIdx(0); }, atStart)}
        {ctrlBtn('⏪', () => { setPlaying(false); setStepIdx(i => Math.max(0, i - 1)); }, atStart)}
        {ctrlBtn(playing ? '⏸ Pause' : '▶ Play', () => setPlaying(p => !p), false, true)}
        {ctrlBtn('⏩', () => { setPlaying(false); setStepIdx(i => Math.min(events.length - 1, i + 1)); }, atEnd)}
        {ctrlBtn('⏭', () => { setPlaying(false); setStepIdx(events.length - 1); }, atEnd)}
        <select
          value={speedMs}
          onChange={e => setSpeedMs(Number(e.target.value))}
          style={{
            marginLeft: 8, background: 'var(--surface)', border: '1px solid var(--border)',
            borderRadius: 5, color: 'var(--text)', fontSize: 11,
            padding: '5px 8px', fontFamily: 'inherit', cursor: 'pointer',
          }}
        >
          {SPEEDS.map(s => <option key={s.ms} value={s.ms}>{s.label}</option>)}
        </select>
      </div>

      {/* Scrubber */}
      <input
        type="range"
        min={0}
        max={events.length - 1}
        value={cIdx}
        onChange={e => { setPlaying(false); setStepIdx(Number(e.target.value)); }}
        style={{ width: '100%', marginBottom: 16, accentColor: 'var(--accent)' }}
      />

      {/* Historical map */}
      {environment && (
        <GridMap
          environment={environment}
          rovers={virtualRovers}
          targetCells={targetCells}
          cellSize={22}
        />
      )}
    </div>
  );
}
