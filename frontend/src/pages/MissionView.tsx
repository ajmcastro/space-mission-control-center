import { useParams, useNavigate } from 'react-router-dom';
import {
  useMission, useMissionEnvironment, useMissionPlan, useRovers,
  useStartMission, useSpawnRover, useAutoPlan, useRunPlan,
  useUpdateMission, useDeleteMission,
} from '@/hooks/useMissions';
import { telemetryApi } from '@/services/api';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useTelemetrySocket } from '@/hooks/useTelemetry';
import { GridMap } from '@/components/GridMap';
import { RoverStatus } from '@/components/RoverStatus';
import { AnomalyAlert } from '@/components/AnomalyAlert';
import { useState } from 'react';

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

export function MissionView() {
  const { id: missionId = '' } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data: mission, isLoading } = useMission(missionId);
  const { data: env } = useMissionEnvironment(missionId);
  const { data: rovers = [] } = useRovers(missionId);
  const { data: plan } = useMissionPlan(missionId, mission?.plan_id);
  const { data: anomalies = [] } = useQuery({
    queryKey: ['anomalies', missionId],
    queryFn: () => telemetryApi.getAnomalies(missionId),
    refetchInterval: 3000,
  });
  const { data: telemetryEvents = [] } = useQuery({
    queryKey: ['telemetry', missionId],
    queryFn: () => telemetryApi.getEvents(missionId, 100),
    refetchInterval: 2000,
  });

  const startMission   = useStartMission();
  const spawnRover     = useSpawnRover();
  const autoPlan       = useAutoPlan();
  const runPlan        = useRunPlan();
  const updateMission  = useUpdateMission();
  const deleteMission  = useDeleteMission();

  const [resolveError, setResolveError]   = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [showAllAnomalies, setShowAllAnomalies] = useState(false);
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

  const [roverName, setRoverName]     = useState('Enc-Rover-1');
  const [activeTab, setActiveTab]     = useState<'map' | 'telemetry' | 'explain'>('map');
  const [showAllSteps, setShowAllSteps] = useState(false);

  // Inline edit state
  const [editing, setEditing]         = useState(false);
  const [editName, setEditName]       = useState('');
  const [editDesc, setEditDesc]       = useState('');

  useTelemetrySocket(missionId);

  if (isLoading) return <div style={{ padding: 32, color: 'var(--text-muted)' }}>Loading mission...</div>;
  if (!mission)  return <div style={{ padding: 32, color: 'var(--accent-red)' }}>Mission not found</div>;

  const firstRover = rovers[0];
  const canStart   = mission.status === 'draft' || mission.status === 'planned';
  const canSpawnRover = mission.status === 'active' && rovers.length < 4;
  const canPlan    = !!firstRover && !mission.plan_id;
  const canRun     = !!mission.plan_id && mission.status === 'active';

  const plannedWaypoints: [number, number][] = plan?.waypoints ?? [];
  const targetCells: [number, number][]       = mission.objectives.map(o => [o.target_x, o.target_y]);

  const completedCount = mission.objectives.filter(o => o.completed).length;
  const totalCount     = mission.objectives.length;
  const progressColor  = mission.progress_pct >= 100 ? '#a855f7'
    : mission.progress_pct > 0 ? '#22c55e' : 'var(--border)';

  const displayedSteps = showAllSteps ? (plan?.steps ?? []) : (plan?.steps ?? []).slice(0, 30);

  function startEdit() {
    setEditName(mission!.name);
    setEditDesc(mission!.description ?? '');
    setEditing(true);
  }

  function cancelEdit() {
    setEditing(false);
  }

  function saveEdit() {
    updateMission.mutate(
      { id: missionId, payload: { name: editName, description: editDesc } },
      { onSuccess: () => setEditing(false) }
    );
  }

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
                  onClick={saveEdit}
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
                  onClick={cancelEdit}
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
                  fontSize: 12, padding: '3px 8px', fontFamily: 'inherit',
                  flexShrink: 0,
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

        <div style={{ display: 'flex', gap: 6 }}>
          <input
            value={roverName}
            onChange={e => setRoverName(e.target.value)}
            style={{
              background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 6,
              padding: '6px 10px', color: 'var(--text)', fontSize: 12, width: 140,
            }}
          />
          <ActionBtn
            label="Spawn Rover"
            onClick={() => spawnRover.mutate({ mission_id: missionId, name: roverName })}
            disabled={!canSpawnRover}
            color="#7c3aed"
          />
        </div>

        <ActionBtn
          label="Auto Plan (A*)"
          onClick={() => firstRover && autoPlan.mutate({ mission_id: missionId, rover_id: firstRover.id })}
          disabled={!canPlan}
          color="#0369a1"
        />

        <ActionBtn
          label="Execute Plan"
          onClick={() => mission.plan_id && runPlan.mutate({ mission_id: missionId, plan_id: mission.plan_id })}
          disabled={!canRun}
          color="#b45309"
        />

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            {rovers.length} rover(s) · {completedCount}/{totalCount} objectives
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
                onClick={() =>
                  deleteMission.mutate(missionId, { onSuccess: () => navigate('/') })
                }
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
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 280px', gap: 20, alignItems: 'start' }}>

        {/* Left: tabs */}
        <div>
          <div style={{ display: 'flex', gap: 2, marginBottom: 14 }}>
            {(['map', 'telemetry', 'explain'] as const).map(tab => (
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
                }}
              >
                {tab.charAt(0).toUpperCase() + tab.slice(1)}
              </button>
            ))}
          </div>

          {activeTab === 'map' && (
            <div style={{ background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 10, padding: 16 }}>
              {env ? (
                <GridMap
                  environment={env}
                  rovers={rovers}
                  highlightPath={plannedWaypoints}
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

          {activeTab === 'explain' && plan && (
            <div style={{ background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 10, padding: 16 }}>
              <h3 style={{ fontSize: 13, color: 'var(--text-sec)', marginTop: 0 }}>Plan Explanation</h3>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>
                Planner: <span style={{ color: 'var(--accent)' }}>{plan.planner}</span> ·{' '}
                Steps: <span style={{ color: 'var(--text)' }}>{plan.total_commands}</span> ·{' '}
                Est. battery: <span style={{ color: 'var(--accent-amber)' }}>{plan.estimated_total_battery.toFixed(1)}</span>
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
              {plan.steps.length > 30 && (
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
                    : `Show all ${plan.steps.length} steps (${plan.steps.length - 30} more)`}
                </button>
              )}
            </div>
          )}
        </div>

        {/* Right sidebar */}
        <div>
          {/* Rovers */}
          <h3 style={{ fontSize: 13, color: 'var(--text-sec)', margin: '0 0 10px 0' }}>Rovers</h3>
          {rovers.length === 0 && (
            <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>No rovers spawned. Start mission then spawn a rover.</p>
          )}
          {rovers.map(r => <RoverStatus key={r.id} rover={r} />)}

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

          {/* Anomalies */}
          {(() => {
            const activeCount = anomalies.filter(a => a.resolution === 'pending').length;
            const visibleCount = showAllAnomalies ? anomalies.length : 10;
            return (
              <>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '18px 0 10px 0' }}>
                  <h3 style={{ fontSize: 13, color: 'var(--text-sec)', margin: 0 }}>Anomalies</h3>
                  {activeCount > 0 && (
                    <span style={{
                      background: '#dc262622', color: '#dc2626',
                      border: '1px solid #dc262655', borderRadius: 10,
                      fontSize: 10, padding: '1px 7px', fontWeight: 700,
                    }}>
                      {activeCount} active
                    </span>
                  )}
                  {activeCount > 1 && (
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
                  anomalies={anomalies}
                  maxVisible={visibleCount}
                  onResolve={(id) => resolveAnomaly.mutate(id)}
                />

                {anomalies.length > 10 && (
                  <button
                    onClick={() => setShowAllAnomalies(s => !s)}
                    style={{
                      marginTop: 6, background: 'none', border: 'none',
                      color: 'var(--accent)', cursor: 'pointer',
                      fontSize: 11, padding: '2px 0', fontFamily: 'inherit',
                    }}
                  >
                    {showAllAnomalies
                      ? 'Show fewer'
                      : `Show all ${anomalies.length} anomalies`}
                  </button>
                )}
              </>
            );
          })()}
        </div>
      </div>
    </div>
  );
}
