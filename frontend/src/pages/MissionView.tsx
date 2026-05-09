import React, { useState, Suspense } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  useMission, useMissionEnvironment, useMissionPlans, useRovers,
  useStartMission, useSpawnRover, useAutoPlan, useRunPlan,
  useUpdateMission, useDeleteMission, useMultiAgentPlan, missionPlansKey,
} from '@/hooks/useMissions';
import { useLLMExplain } from '@/hooks/useExplain';
import { telemetryApi } from '@/services/api';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useTelemetrySocket } from '@/hooks/useTelemetry';
import { useMissionStore } from '@/store/missionStore';
import { GridMap } from '@/components/GridMap';
import { RoverStatus } from '@/components/RoverStatus';
import { AnomalyAlert } from '@/components/AnomalyAlert';
import { BatteryChart } from '@/components/BatteryChart';
import { TimelinePlayer } from '@/components/TimelinePlayer';
import type { Rover } from '@/types';

const TerrainCanvas = React.lazy(() =>
  import('@/components/TerrainCanvas').then(m => ({ default: m.TerrainCanvas }))
);

function ActionBtn({ label, onClick, disabled, color = 'var(--btn-primary)' }: {
  label: string; onClick: () => void; disabled?: boolean; color?: string;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        background: disabled ? 'var(--border)' : color,
        color: disabled ? 'var(--text-muted)' : '#fff',
        border: 'none', borderRadius: 6, padding: '7px 14px',
        fontSize: 12, cursor: disabled ? 'not-allowed' : 'pointer',
        fontFamily: 'inherit', fontWeight: 600,
      }}
    >
      {label}
    </button>
  );
}

const STATUS_COLORS: Record<string, string> = {
  draft: '#64748b', planned: '#38bdf8', active: '#22c55e',
  paused: '#f59e0b', completed: '#a855f7', failed: '#ef4444', aborted: '#dc2626',
};

function RoverPanel({
  rover,
  missionStatus,
  plan,
  onPlan,
  onRun,
  planPending,
  runPending,
}: {
  rover: Rover;
  missionStatus: string;
  plan?: { id: string; total_commands: number; estimated_total_battery: number; planner?: string; metadata?: Record<string, unknown> } | null;
  onPlan: (roverId: string, planner: string) => void;
  onRun: (planId: string) => void;
  planPending: boolean;
  runPending: boolean;
}) {
  const [selectedPlanner, setSelectedPlanner] = useState<'astar' | 'rl'>('astar');
  const isExecuting = ['moving', 'sampling', 'stuck'].includes(rover.state);
  const canPlan = missionStatus === 'active' && !isExecuting;
  const canRun  = missionStatus === 'active' && !!plan && !isExecuting;

  return (
    <div style={{
      background: 'var(--surface)', border: '1px solid var(--border)',
      borderRadius: 8, padding: '10px 12px', marginBottom: 10,
    }}>
      <RoverStatus rover={rover} />
      <div style={{ display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <select
          value={selectedPlanner}
          onChange={e => setSelectedPlanner(e.target.value as 'astar' | 'rl')}
          disabled={!canPlan || planPending}
          style={{
            background: 'var(--bg)', border: '1px solid var(--border)',
            borderRadius: 5, color: 'var(--text)', fontSize: 11,
            padding: '3px 6px', fontFamily: 'inherit', cursor: canPlan ? 'pointer' : 'not-allowed',
          }}
        >
          <option value="astar">A*</option>
          <option value="rl">RL</option>
        </select>
        <button
          onClick={() => onPlan(rover.id, selectedPlanner)}
          disabled={!canPlan || planPending}
          style={{
            background: !canPlan || planPending ? 'var(--border)' : '#0369a1',
            color: !canPlan || planPending ? 'var(--text-muted)' : '#fff',
            border: 'none', borderRadius: 5, padding: '4px 10px',
            fontSize: 11, cursor: !canPlan || planPending ? 'not-allowed' : 'pointer',
            fontFamily: 'inherit', fontWeight: 600,
          }}
        >
          {planPending ? 'Planning…' : isExecuting ? `Plan (${plan?.total_commands ?? '…'} steps)` : plan ? `Plan (${plan.total_commands} steps)` : 'Plan'}
        </button>
        <button
          onClick={() => plan && onRun(plan.id)}
          disabled={!canRun || runPending}
          style={{
            background: !canRun || runPending ? 'var(--border)' : '#b45309',
            color: !canRun || runPending ? 'var(--text-muted)' : '#fff',
            border: 'none', borderRadius: 5, padding: '4px 10px',
            fontSize: 11, cursor: !canRun || runPending ? 'not-allowed' : 'pointer',
            fontFamily: 'inherit', fontWeight: 600,
          }}
        >
          {isExecuting ? 'Executing…' : runPending ? 'Starting…' : 'Execute Plan'}
        </button>
      </div>
      {plan && (
        <div style={{ fontSize: 11, color: 'var(--text-sec)', marginTop: 5 }}>
          {plan.planner && (
            <span style={{
              background: plan.planner === 'rl' ? '#7c3aed22' : '#0369a122',
              color: plan.planner === 'rl' ? '#a78bfa' : '#38bdf8',
              border: `1px solid ${plan.planner === 'rl' ? '#7c3aed55' : '#0369a155'}`,
              borderRadius: 3, padding: '0 5px', marginRight: 6, fontSize: 10, fontWeight: 700,
            }}>
              {plan.planner.toUpperCase()}
            </span>
          )}
          Est. battery cost: <span style={{ color: 'var(--accent-amber)', fontWeight: 600 }}>{plan.estimated_total_battery.toFixed(1)}</span>
          {' · '}
          <span style={{ color: 'var(--text)', fontWeight: 600 }}>{plan.total_commands}</span> commands
        </div>
      )}
    </div>
  );
}

const SEVERITY_ORDER: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };
const SEVERITY_COLORS: Record<string, string> = {
  low: '#4ade80', medium: '#fb923c', high: '#f87171', critical: '#dc2626',
};
const ANOMALY_ICONS: Record<string, string> = {
  wheel_stuck: '⚙', comm_loss: '📡', energy_spike: '⚡',
  sensor_fault: '🔬', geyser_proximity: '🌋', low_battery: '🔋',
  path_blocked: '🚧', unknown: '❓',
};
const RESOLUTION_LABELS: Record<string, string> = {
  pending: 'Pending', auto_recovered: 'Auto-recovered',
  replanned: 'Replanned', aborted: 'Aborted', ignored: 'Dismissed',
};

function AnomaliesTab({ anomalies, onResolve, onDismissAll, dismissAllPending }: {
  anomalies: import('@/types').Anomaly[];
  onResolve: (id: string) => void;
  onDismissAll: () => void;
  dismissAllPending: boolean;
}) {
  const [sortBy, setSortBy]       = useState<'time_desc' | 'time_asc' | 'severity'>('time_desc');
  const [filterStatus, setFilterStatus] = useState<'all' | 'pending' | 'resolved'>('all');
  const [filterType, setFilterType]     = useState<string>('all');
  const [filterSeverity, setFilterSeverity] = useState<string>('all');

  const allTypes = Array.from(new Set(anomalies.map(a => a.type)));

  const filtered = anomalies
    .filter(a => filterStatus === 'all' ? true : filterStatus === 'pending' ? a.resolution === 'pending' : a.resolution !== 'pending')
    .filter(a => filterType === 'all' || a.type === filterType)
    .filter(a => filterSeverity === 'all' || a.severity === filterSeverity)
    .sort((a, b) => {
      if (sortBy === 'severity') return (SEVERITY_ORDER[a.severity] ?? 9) - (SEVERITY_ORDER[b.severity] ?? 9);
      const ta = new Date(a.detected_at).getTime();
      const tb = new Date(b.detected_at).getTime();
      return sortBy === 'time_desc' ? tb - ta : ta - tb;
    });

  const pendingCount = anomalies.filter(a => a.resolution === 'pending').length;

  const selectStyle: React.CSSProperties = {
    background: 'var(--surface)', border: '1px solid var(--border)',
    borderRadius: 5, color: 'var(--text)', fontSize: 11,
    padding: '4px 8px', fontFamily: 'inherit', cursor: 'pointer',
  };

  return (
    <div style={{ background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 10, padding: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14, flexWrap: 'wrap' }}>
        <h3 style={{ fontSize: 13, color: 'var(--text-sec)', margin: 0 }}>Anomaly History</h3>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          {filtered.length} shown · {pendingCount} active
        </span>
        {pendingCount > 1 && (
          <button
            onClick={onDismissAll}
            disabled={dismissAllPending}
            style={{ ...selectStyle, marginLeft: 'auto', color: 'var(--accent-red)', borderColor: 'var(--accent-red)' }}
          >
            {dismissAllPending ? 'Dismissing…' : 'Dismiss all active'}
          </button>
        )}
      </div>

      {/* Controls */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 14, flexWrap: 'wrap', alignItems: 'center' }}>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Sort:</span>
        <select value={sortBy} onChange={e => setSortBy(e.target.value as typeof sortBy)} style={selectStyle}>
          <option value="time_desc">Newest first</option>
          <option value="time_asc">Oldest first</option>
          <option value="severity">Severity</option>
        </select>
        <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 8 }}>Filter:</span>
        <select value={filterStatus} onChange={e => setFilterStatus(e.target.value as typeof filterStatus)} style={selectStyle}>
          <option value="all">All statuses</option>
          <option value="pending">Active only</option>
          <option value="resolved">Resolved only</option>
        </select>
        <select value={filterSeverity} onChange={e => setFilterSeverity(e.target.value)} style={selectStyle}>
          <option value="all">All severities</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
        <select value={filterType} onChange={e => setFilterType(e.target.value)} style={selectStyle}>
          <option value="all">All types</option>
          {allTypes.map(t => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}
        </select>
        {(filterStatus !== 'all' || filterType !== 'all' || filterSeverity !== 'all') && (
          <button
            onClick={() => { setFilterStatus('all'); setFilterType('all'); setFilterSeverity('all'); }}
            style={{ ...selectStyle, color: 'var(--accent)', borderColor: 'var(--accent)' }}
          >
            Clear filters
          </button>
        )}
      </div>

      {filtered.length === 0 ? (
        <div style={{ color: 'var(--text-muted)', fontSize: 12, textAlign: 'center', padding: '24px 0' }}>
          No anomalies match the current filters.
        </div>
      ) : (
        <div>
          {filtered.map(a => {
            const c = SEVERITY_COLORS[a.severity] ?? '#6b7280';
            const resolved = a.resolution !== 'pending';
            return (
              <div key={a.id} style={{
                background: 'var(--surface)',
                border: `1px solid ${resolved ? 'var(--border)' : c + '40'}`,
                borderLeft: `3px solid ${resolved ? 'var(--border-strong)' : c}`,
                borderRadius: 6, padding: '8px 12px', marginBottom: 6,
                opacity: resolved ? 0.65 : 1,
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text)' }}>
                    {ANOMALY_ICONS[a.type] ?? '!'} {a.type.replace(/_/g, ' ')}
                  </span>
                  <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                    <span style={{
                      fontSize: 10, fontWeight: 700, textTransform: 'uppercase',
                      color: resolved ? 'var(--text-muted)' : c,
                    }}>
                      {a.severity}
                    </span>
                    <span style={{
                      fontSize: 10, color: resolved ? 'var(--text-muted)' : '#f59e0b',
                      background: resolved ? 'var(--surface-alt)' : '#f59e0b18',
                      border: `1px solid ${resolved ? 'var(--border)' : '#f59e0b44'}`,
                      borderRadius: 4, padding: '1px 6px', fontWeight: 600,
                    }}>
                      {RESOLUTION_LABELS[a.resolution] ?? a.resolution}
                    </span>
                    {!resolved && (
                      <button
                        onClick={() => onResolve(a.id)}
                        style={{
                          background: 'none', border: '1px solid var(--border)',
                          borderRadius: 4, color: 'var(--text-muted)', cursor: 'pointer',
                          fontSize: 10, padding: '1px 6px', fontFamily: 'inherit',
                        }}
                      >
                        {a.type === 'comm_loss' ? 'Restore comms' : a.type === 'low_battery' ? 'Recharge' : 'Dismiss'}
                      </button>
                    )}
                  </div>
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-sec)', marginTop: 4 }}>{a.description}</div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 3 }}>
                  ({a.x}, {a.y}) · {new Date(a.detected_at).toLocaleTimeString()}
                  {a.resolved_at && ` · resolved ${new Date(a.resolved_at).toLocaleTimeString()}`}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function MissionView() {
  const { id: missionId = '' } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data: mission, isLoading } = useMission(missionId);
  const { data: env } = useMissionEnvironment(missionId);
  const { data: rovers = [] } = useRovers(missionId);
  const { data: plansByRover = {} } = useMissionPlans(missionId);
  const { data: anomalies = [] } = useQuery({
    queryKey: ['anomalies', missionId],
    queryFn: () => telemetryApi.getAnomalies(missionId),
    refetchInterval: 3000,
  });
  const { data: telemetryEvents = [] } = useQuery({
    queryKey: ['telemetry', missionId],
    queryFn: () => telemetryApi.getEvents(missionId, 200),
    refetchInterval: 2000,
    enabled: !!missionId,
  });

  const telemetryBuffer = useMissionStore(s => s.telemetryBuffer);

  const startMission   = useStartMission();
  const spawnRover     = useSpawnRover();
  const autoPlan       = useAutoPlan();
  const runPlan        = useRunPlan();
  const multiAgentPlan = useMultiAgentPlan();
  const updateMission  = useUpdateMission();
  const deleteMission  = useDeleteMission();

  const [resolveError, setResolveError]     = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete]   = useState(false);

  const [roverName, setRoverName]           = useState('');
  const [activeTab, setActiveTab]           = useState<'map' | 'telemetry' | 'charts' | 'timeline' | 'explain' | '3d' | 'anomalies'>('map');
  const [showAllSteps, setShowAllSteps]     = useState(false);
  const [editing, setEditing]               = useState(false);
  const [editName, setEditName]             = useState('');
  const [editDesc, setEditDesc]             = useState('');

  // Track which rover's plan to show in Explain tab
  const [explainRoverId, setExplainRoverId] = useState<string | null>(null);

  const dismissAll = useMutation({
    mutationFn: () => telemetryApi.dismissAll(missionId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['anomalies', missionId] });
      qc.invalidateQueries({ queryKey: ['rovers', missionId] });
    },
  });

  const resolveAnomaly = useMutation({
    mutationFn: (id: string) => telemetryApi.resolveAnomaly(id),
    onMutate: async (id) => {
      await qc.cancelQueries({ queryKey: ['anomalies', missionId] });
      const prev = qc.getQueryData<typeof anomalies>(['anomalies', missionId]);
      qc.setQueryData(['anomalies', missionId], (old: typeof anomalies = []) =>
        old.map(a => a.id === id ? { ...a, resolution: 'ignored' } : a)
      );
      return { prev };
    },
    onError: (_err, _id, ctx) => {
      if (ctx?.prev) qc.setQueryData(['anomalies', missionId], ctx.prev);
      setResolveError('Failed to dismiss anomaly — please try again.');
      setTimeout(() => setResolveError(null), 4000);
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ['anomalies', missionId] });
      qc.invalidateQueries({ queryKey: ['rovers', missionId] });
    },
  });

  useTelemetrySocket(missionId);

  // These must be computed before early returns so useLLMExplain is always called
  const explainRover = rovers.find(r => r.id === explainRoverId) ?? rovers[0];
  const explainPlan  = explainRover ? plansByRover[explainRover.id] : null;
  const llm = useLLMExplain('plan', explainPlan?.id ?? null);

  if (isLoading) return <div style={{ padding: 32, color: 'var(--text-muted)' }}>Loading mission...</div>;
  if (!mission)  return <div style={{ padding: 32, color: 'var(--accent-red)' }}>Mission not found</div>;

  const canStart      = mission.status === 'draft' || mission.status === 'planned';
  const canSpawnRover = mission.status === 'active' && rovers.length < 4;
  const completedCount = mission.objectives.filter(o => o.completed).length;
  const totalCount     = mission.objectives.length;
  const progressColor  = mission.progress_pct >= 100 ? '#a855f7'
    : mission.progress_pct > 0 ? '#22c55e' : 'var(--border)';

  // Aggregate all plan waypoints for the map overlay
  const allWaypoints: [number, number][] = Object.values(plansByRover)
    .flatMap(p => p.waypoints as [number, number][]);
  const targetCells: [number, number][] = mission.objectives.map(o => [o.target_x, o.target_y]);

  const displayedSteps = showAllSteps
    ? (explainPlan?.steps ?? [])
    : (explainPlan?.steps ?? []).slice(0, 30);

  function startEdit() {
    setEditName(mission!.name);
    setEditDesc(mission!.description ?? '');
    setEditing(true);
  }

  function handleAutoPlan(roverId: string, planner: string = 'astar') {
    const rover = rovers.find(r => r.id === roverId);
    autoPlan.mutate({
      mission_id: missionId,
      rover_id: roverId,
      start_x: rover?.x ?? 0,
      start_y: rover?.y ?? 0,
      planner,
    }, {
      onSuccess: () => qc.invalidateQueries({ queryKey: missionPlansKey(missionId) }),
    });
  }

  function handleMultiAgentPlan() {
    multiAgentPlan.mutate({
      mission_id: missionId,
      rover_ids: rovers.map(r => r.id),
    });
  }

  function handleRunPlan(planId: string) {
    runPlan.mutate({ mission_id: missionId, plan_id: planId });
  }

  const nextRoverName = `Enc-Rover-${rovers.length + 1}`;

  return (
    <div style={{ padding: '20px 28px', maxWidth: 1600 }}>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          {editing ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxWidth: 480 }}>
              <input
                value={editName}
                onChange={e => setEditName(e.target.value)}
                placeholder="Mission name"
                style={{
                  background: 'var(--bg)', border: '1px solid var(--accent)',
                  borderRadius: 6, padding: '6px 10px',
                  color: 'var(--text)', fontSize: 18, fontWeight: 800,
                  fontFamily: 'inherit',
                }}
              />
              <textarea
                value={editDesc}
                onChange={e => setEditDesc(e.target.value)}
                placeholder="Description (optional)"
                rows={2}
                style={{
                  background: 'var(--bg)', border: '1px solid var(--border)',
                  borderRadius: 6, padding: '6px 10px',
                  color: 'var(--text)', fontSize: 12,
                  fontFamily: 'inherit', resize: 'vertical',
                }}
              />
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  onClick={() => updateMission.mutate(
                    { id: missionId, payload: { name: editName, description: editDesc } },
                    { onSuccess: () => setEditing(false) }
                  )}
                  disabled={updateMission.isPending || !editName.trim()}
                  style={{
                    background: 'var(--btn-primary)', color: '#fff',
                    border: 'none', borderRadius: 6, padding: '6px 16px',
                    fontSize: 12, cursor: 'pointer', fontFamily: 'inherit', fontWeight: 600,
                  }}
                >
                  {updateMission.isPending ? 'Saving…' : 'Save'}
                </button>
                <button
                  onClick={() => setEditing(false)}
                  style={{
                    background: 'none', color: 'var(--text-muted)',
                    border: '1px solid var(--border)', borderRadius: 6,
                    padding: '6px 16px', fontSize: 12, cursor: 'pointer', fontFamily: 'inherit',
                  }}
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
              <div>
                <h1 style={{ fontSize: 20, fontWeight: 800, color: 'var(--text)', margin: 0 }}>{mission.name}</h1>
                <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '4px 0 0 0' }}>{mission.description}</p>
              </div>
              <button
                onClick={startEdit}
                title="Edit mission name and description"
                style={{
                  marginTop: 2, background: 'none', border: '1px solid var(--border)',
                  borderRadius: 5, color: 'var(--text-muted)', cursor: 'pointer',
                  fontSize: 12, padding: '3px 8px', fontFamily: 'inherit', flexShrink: 0,
                }}
              >
                ✏ Edit
              </button>
            </div>
          )}
        </div>

        <div style={{ display: 'flex', gap: 14, alignItems: 'center', marginLeft: 20 }}>
          <span style={{
            background: (STATUS_COLORS[mission.status] ?? '#6b7280') + '33',
            color: STATUS_COLORS[mission.status] ?? '#6b7280',
            border: `1px solid ${(STATUS_COLORS[mission.status] ?? '#6b7280')}cc`,
            fontSize: 12, padding: '4px 14px', borderRadius: 12, fontWeight: 800,
            textTransform: 'uppercase', letterSpacing: '0.06em',
          }}>
            {mission.status}
          </span>
          <div style={{ width: 1, height: 32, background: 'var(--border)' }} />
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 5 }}>
            <span style={{ fontSize: 12, color: 'var(--text-sec)', fontWeight: 600 }}>
              {completedCount}/{totalCount} objectives · {mission.progress_pct}%
            </span>
            <div style={{ width: 140, height: 7, background: 'var(--border)', borderRadius: 4 }}>
              <div style={{
                width: `${mission.progress_pct}%`, height: '100%',
                background: progressColor, borderRadius: 4, transition: 'width 0.4s',
              }} />
            </div>
          </div>
        </div>
      </div>

      {/* Action bar */}
      <div style={{
        display: 'flex', gap: 8, padding: '10px 14px',
        background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8, marginBottom: 20,
        alignItems: 'center', flexWrap: 'wrap',
      }}>
        <ActionBtn label="Start Mission" onClick={() => startMission.mutate(missionId)} disabled={!canStart} color="#16a34a" />

        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <input
            value={roverName || nextRoverName}
            onChange={e => setRoverName(e.target.value)}
            placeholder={nextRoverName}
            style={{
              background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 6,
              padding: '6px 10px', color: 'var(--text)', fontSize: 12, width: 140,
            }}
          />
          <ActionBtn
            label="Spawn Rover"
            onClick={() => {
              spawnRover.mutate({ mission_id: missionId, name: roverName || nextRoverName });
              setRoverName('');
            }}
            disabled={!canSpawnRover}
            color="#7c3aed"
          />
          {rovers.length >= 2 && (
            <ActionBtn
              label={multiAgentPlan.isPending ? 'Coordinating…' : 'Coordinate All Rovers'}
              onClick={handleMultiAgentPlan}
              disabled={mission.status !== 'active' || multiAgentPlan.isPending}
              color="#0f766e"
            />
          )}
        </div>

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            {rovers.length}/{4} rovers · {completedCount}/{totalCount} objectives
          </span>

          {confirmDelete ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 11, color: 'var(--accent-red)', fontWeight: 600 }}>
                Delete everything?
              </span>
              <button
                onClick={() => setConfirmDelete(false)}
                style={{
                  background: 'var(--surface)', color: 'var(--text)', border: '1px solid var(--border)',
                  borderRadius: 6, padding: '5px 12px', fontSize: 11,
                  cursor: 'pointer', fontFamily: 'inherit', fontWeight: 600,
                }}
              >
                Cancel
              </button>
              <button
                onClick={() => deleteMission.mutate(missionId, { onSuccess: () => navigate('/') })}
                disabled={deleteMission.isPending}
                style={{
                  background: 'none', color: '#dc2626', border: '1px solid #dc2626',
                  borderRadius: 6, padding: '5px 12px', fontSize: 11, cursor: 'pointer',
                  fontFamily: 'inherit', fontWeight: 600,
                }}
              >
                {deleteMission.isPending ? 'Deleting…' : 'Yes, delete'}
              </button>
            </div>
          ) : (
            <button
              onClick={() => setConfirmDelete(true)}
              style={{
                background: 'none', color: 'var(--accent-red)',
                border: '1px solid var(--accent-red)', borderRadius: 6,
                padding: '5px 12px', fontSize: 11, cursor: 'pointer',
                fontFamily: 'inherit', fontWeight: 600,
              }}
            >
              Delete mission
            </button>
          )}
        </div>
      </div>

      {/* Main layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 20, alignItems: 'start' }}>

        {/* Left: tabs */}
        <div>
          <div style={{ display: 'flex', gap: 2, marginBottom: 14 }}>
            {(['map', 'telemetry', 'charts', 'timeline', 'explain', '3d', 'anomalies'] as const).map(tab => {
              const pendingCount = tab === 'anomalies' ? anomalies.filter(a => a.resolution === 'pending').length : 0;
              const label = tab === '3d' ? '3D' : tab.charAt(0).toUpperCase() + tab.slice(1);
              return (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                style={{
                  background: activeTab === tab ? 'var(--btn-primary)' : 'var(--surface)',
                  color: activeTab === tab ? '#fff' : 'var(--text-muted)',
                  border: '1px solid var(--border)',
                  borderRadius: 6, padding: '6px 14px', fontSize: 12,
                  cursor: 'pointer', fontFamily: 'inherit',
                  fontWeight: activeTab === tab ? 700 : 400,
                  position: 'relative',
                }}
              >
                {label}
                {pendingCount > 0 && (
                  <span style={{
                    position: 'absolute', top: -5, right: -5,
                    background: '#dc2626', color: '#fff',
                    borderRadius: 10, fontSize: 9, fontWeight: 800,
                    padding: '1px 5px', lineHeight: 1.4,
                  }}>{pendingCount}</span>
                )}
              </button>
              );
            })}
          </div>

          {activeTab === 'map' && (
            <div style={{ background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 10, padding: 16 }}>
              {env ? (
                <GridMap
                  environment={env}
                  rovers={rovers}
                  highlightPath={allWaypoints}
                  targetCells={targetCells}
                  cellSize={26}
                />
              ) : (
                <p style={{ color: 'var(--text-muted)', fontSize: 12, margin: 0 }}>Loading terrain map…</p>
              )}
            </div>
          )}

          {activeTab === 'telemetry' && (
            <div style={{ background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 10, padding: 16 }}>
              <h3 style={{ fontSize: 13, color: 'var(--text-sec)', marginTop: 0 }}>Telemetry Stream</h3>
              {rovers.length === 0 && <p style={{ color: 'var(--text-muted)', fontSize: 12 }}>No rovers deployed.</p>}
              {rovers.length > 0 && telemetryEvents.length === 0 && (
                <p style={{ color: 'var(--text-muted)', fontSize: 12 }}>No telemetry yet — execute a plan to start streaming.</p>
              )}
              {rovers.map(r => {
                const events = telemetryEvents.filter(e => e.rover_id === r.id).slice(-20).reverse();
                if (events.length === 0) return null;
                return (
                  <div key={r.id} style={{ marginBottom: 16 }}>
                    <div style={{ fontSize: 12, color: 'var(--accent)', marginBottom: 6, fontWeight: 600 }}>{r.name}</div>
                    <div style={{ fontFamily: 'monospace', fontSize: 11 }}>
                      {events.map(ev => (
                        <div key={ev.id} style={{
                          display: 'flex', gap: 10, padding: '3px 0',
                          borderBottom: '1px solid var(--surface)', color: 'var(--text-sec)',
                        }}>
                          <span style={{ color: 'var(--text-muted)', minWidth: 80 }}>
                            {new Date(ev.timestamp).toLocaleTimeString()}
                          </span>
                          <span style={{ color: 'var(--accent)' }}>{ev.type}</span>
                          {ev.x != null && <span>({ev.x},{ev.y})</span>}
                          {ev.battery_pct != null && (
                            <span style={{ color: ev.battery_pct < 20 ? 'var(--accent-red)' : 'var(--accent-green)' }}>
                              🔋{ev.battery_pct.toFixed(1)}%
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {activeTab === 'charts' && (
            <div style={{ background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 10, padding: 16 }}>
              <h3 style={{ fontSize: 13, color: 'var(--text-sec)', marginTop: 0, marginBottom: 16 }}>
                Battery Over Time
              </h3>
              <BatteryChart rovers={rovers} telemetryEvents={telemetryEvents} telemetryBuffer={telemetryBuffer} />
            </div>
          )}

          {activeTab === '3d' && (
            <div style={{ background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden', height: 1040 }}>
              {env ? (
                <Suspense fallback={
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)', fontSize: 12 }}>
                    Loading 3D renderer…
                  </div>
                }>
                  <TerrainCanvas
                    environment={env}
                    rovers={rovers}
                    highlightPath={allWaypoints}
                    targetCells={targetCells}
                  />
                </Suspense>
              ) : (
                <p style={{ padding: 16, color: 'var(--text-muted)', fontSize: 12 }}>Loading terrain…</p>
              )}
            </div>
          )}

          {activeTab === 'timeline' && (
            <div style={{ background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 10, padding: 16 }}>
              <h3 style={{ fontSize: 13, color: 'var(--text-sec)', marginTop: 0, marginBottom: 16 }}>
                Timeline Playback
              </h3>
              <TimelinePlayer
                missionId={missionId}
                rovers={rovers}
                environment={env ?? null}
                targetCells={targetCells}
              />
            </div>
          )}

          {activeTab === 'explain' && (
            <div style={{ background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 10, padding: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                <h3 style={{ fontSize: 13, color: 'var(--text-sec)', margin: 0 }}>Plan Explanation</h3>
                {rovers.length > 1 && (
                  <select
                    value={explainRoverId ?? rovers[0]?.id ?? ''}
                    onChange={e => setExplainRoverId(e.target.value)}
                    style={{
                      background: 'var(--surface)', border: '1px solid var(--border)',
                      borderRadius: 5, color: 'var(--text)', fontSize: 11,
                      padding: '3px 8px', fontFamily: 'inherit', cursor: 'pointer',
                    }}
                  >
                    {rovers.map(r => (
                      <option key={r.id} value={r.id}>{r.name}</option>
                    ))}
                  </select>
                )}
              </div>
              {!explainPlan ? (
                <p style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                  No plan generated yet for {explainRover?.name ?? 'this rover'}.
                </p>
              ) : (
                <>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>
                    Planner: <span style={{ color: 'var(--accent)' }}>{explainPlan.planner}</span> ·{' '}
                    Steps: <span style={{ color: 'var(--text)' }}>{explainPlan.total_commands}</span> ·{' '}
                    Est. battery: <span style={{ color: 'var(--accent-amber)' }}>{explainPlan.estimated_total_battery.toFixed(1)}</span>
                  </div>
                  <div style={{ fontFamily: 'monospace', fontSize: 11 }}>
                    {displayedSteps.map((step, i) => (
                      <div key={i} style={{
                        display: 'flex', gap: 10, padding: '3px 0',
                        borderBottom: '1px solid var(--surface)', color: 'var(--text-sec)',
                      }}>
                        <span style={{ color: 'var(--text-muted)', minWidth: 24 }}>#{step.sequence}</span>
                        <span style={{ color: 'var(--accent)', minWidth: 80 }}>{step.command.type}</span>
                        {step.command.target_x != null && (
                          <span>→ ({step.command.target_x},{step.command.target_y})</span>
                        )}
                        <span style={{ color: 'var(--text-muted)' }}>{step.rationale}</span>
                      </div>
                    ))}
                  </div>
                  {explainPlan.steps.length > 30 && (
                    <button
                      onClick={() => setShowAllSteps(s => !s)}
                      style={{
                        marginTop: 10, background: 'none', border: '1px solid var(--border)',
                        borderRadius: 6, color: 'var(--accent)', cursor: 'pointer',
                        fontSize: 11, padding: '4px 12px', fontFamily: 'inherit',
                      }}
                    >
                      {showAllSteps
                        ? 'Show fewer steps'
                        : `Show all ${explainPlan.steps.length} steps (${explainPlan.steps.length - 30} more)`}
                    </button>
                  )}

                  {/* Claude AI explanation */}
                  <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid var(--border)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                      <span style={{ fontSize: 12, color: 'var(--text-sec)', fontWeight: 600 }}>Claude Analysis</span>
                      <button
                        onClick={llm.loading ? llm.reset : llm.trigger}
                        style={{
                          background: llm.loading ? '#b45309' : 'var(--btn-primary)',
                          color: '#fff', border: 'none', borderRadius: 5,
                          padding: '3px 10px', fontSize: 11, cursor: 'pointer',
                          fontFamily: 'inherit', fontWeight: 600,
                        }}
                      >
                        {llm.loading ? 'Stop' : llm.text ? 'Regenerate' : 'Ask Claude'}
                      </button>
                    </div>
                    {llm.error && (
                      <p style={{ fontSize: 11, color: 'var(--accent-red)', margin: 0 }}>{llm.error}</p>
                    )}
                    {llm.text && (
                      <p style={{
                        fontSize: 12, color: 'var(--text)', lineHeight: 1.6,
                        margin: 0, fontStyle: 'italic',
                        borderLeft: '2px solid var(--accent)', paddingLeft: 10,
                      }}>
                        {llm.text}
                        {llm.loading && <span style={{ color: 'var(--accent)', animation: 'none' }}>▌</span>}
                      </p>
                    )}
                  </div>
                </>
              )}
            </div>
          )}

          {activeTab === 'anomalies' && (
            <AnomaliesTab
              anomalies={anomalies}
              onResolve={id => resolveAnomaly.mutate(id)}
              onDismissAll={() => dismissAll.mutate()}
              dismissAllPending={dismissAll.isPending}
            />
          )}
        </div>

        {/* Right sidebar */}
        <div>
          {/* Rovers */}
          <h3 style={{ fontSize: 13, color: 'var(--text-sec)', margin: '0 0 10px 0' }}>
            Rovers ({rovers.length}/4)
          </h3>
          {rovers.length === 0 && (
            <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              Start the mission, then spawn rovers and assign plans.
            </p>
          )}
          {rovers.map(r => (
            <RoverPanel
              key={r.id}
              rover={r}
              missionStatus={mission.status}
              plan={plansByRover[r.id] ?? null}
              onPlan={handleAutoPlan}
              onRun={handleRunPlan}
              planPending={autoPlan.isPending && autoPlan.variables?.rover_id === r.id}
              runPending={runPlan.isPending && runPlan.variables?.plan_id === plansByRover[r.id]?.id}
            />
          ))}

          {/* Objectives */}
          <h3 style={{ fontSize: 13, color: 'var(--text-sec)', margin: '18px 0 10px 0' }}>Objectives</h3>
          {mission.objectives.map(obj => (
            <div key={obj.id} style={{
              background: 'var(--surface)', border: '1px solid var(--border)',
              borderRadius: 6, padding: '8px 12px', marginBottom: 6,
              display: 'flex', alignItems: 'center', gap: 10,
              opacity: obj.completed ? 0.6 : 1,
            }}>
              <span style={{ fontSize: 14 }}>{obj.completed ? '✅' : '⬜'}</span>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text)', fontWeight: 600 }}>
                  {obj.type.replace(/_/g, ' ')}
                </div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                  ({obj.target_x}, {obj.target_y}) · priority {obj.priority}
                </div>
              </div>
            </div>
          ))}

          {/* Anomalies sidebar — active only, newest first */}
          {(() => {
            const pending = [...anomalies]
              .filter(a => a.resolution === 'pending')
              .sort((a, b) => new Date(b.detected_at).getTime() - new Date(a.detected_at).getTime());
            return (
              <>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '18px 0 10px 0' }}>
                  <h3 style={{ fontSize: 13, color: 'var(--text-sec)', margin: 0 }}>Active Anomalies</h3>
                  {pending.length > 0 && (
                    <span style={{
                      background: '#dc262622', color: '#dc2626',
                      border: '1px solid #dc262655', borderRadius: 10,
                      fontSize: 10, padding: '1px 7px', fontWeight: 700,
                    }}>
                      {pending.length}
                    </span>
                  )}
                  {pending.length > 1 && (
                    <button
                      onClick={() => dismissAll.mutate()}
                      disabled={dismissAll.isPending}
                      style={{
                        marginLeft: 'auto', background: 'none', border: '1px solid var(--border)',
                        borderRadius: 4, color: 'var(--text-muted)', cursor: 'pointer',
                        fontSize: 10, padding: '1px 8px', fontFamily: 'inherit',
                      }}
                    >
                      {dismissAll.isPending ? 'Dismissing…' : 'Dismiss all'}
                    </button>
                  )}
                </div>

                {resolveError && (
                  <div style={{
                    background: '#dc262218', border: '1px solid #dc262255',
                    borderRadius: 6, padding: '6px 10px', marginBottom: 8,
                    fontSize: 11, color: '#dc2626',
                  }}>
                    {resolveError}
                  </div>
                )}

                <AnomalyAlert
                  anomalies={pending}
                  onResolve={id => resolveAnomaly.mutate(id)}
                />

                <button
                  onClick={() => setActiveTab('anomalies')}
                  style={{
                    marginTop: 8, width: '100%', background: 'none',
                    border: '1px solid var(--border)', borderRadius: 6,
                    color: 'var(--accent)', cursor: 'pointer',
                    fontSize: 11, padding: '5px 0', fontFamily: 'inherit',
                  }}
                >
                  View all anomaly history →
                </button>
              </>
            );
          })()}
        </div>
      </div>
    </div>
  );
}
