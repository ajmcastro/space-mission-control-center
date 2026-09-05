import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { Rover, AutonomyLevel, AegisProposal, UplinkResult } from '@/types';
import { simulationApi } from '@/services/api';

interface Props {
  rover: Rover;
  missionId?: string;
}

const STATE_COLORS: Record<string, string> = {
  idle: '#22c55e', moving: '#3b82f6', sampling: '#f59e0b',
  charging: '#a855f7', stuck: '#ef4444', comm_lost: '#f97316',
  error: '#dc2626', safe_mode: '#06b6d4',
};

const AUTONOMY_LABELS: Record<AutonomyLevel, string> = {
  supervised: 'Supervised',
  semi_autonomous: 'Semi-auto',
  fully_autonomous: 'Full auto',
};

const AUTONOMY_COLORS: Record<AutonomyLevel, string> = {
  supervised: '#6b7280',
  semi_autonomous: '#3b82f6',
  fully_autonomous: '#8b5cf6',
};

export function RoverStatus({ rover, missionId }: Props) {
  const qc = useQueryClient();
  const [queuedNotice, setQueuedNotice] = useState<string | null>(null);
  const batteryColor =
    rover.battery_pct > 50 ? 'var(--accent-green)' :
    rover.battery_pct > 20 ? 'var(--accent-amber)' : 'var(--accent-red)';

  function noteResult(result: UplinkResult, actionLabel: string) {
    setQueuedNotice(
      result.delivered ? null : `${actionLabel} queued — comm window closed, will send at next uplink`
    );
  }

  const setAutonomy = useMutation({
    mutationFn: (level: AutonomyLevel) => simulationApi.setAutonomy(rover.id, level),
    onSuccess: (result) => {
      noteResult(result, 'Autonomy change');
      qc.invalidateQueries({ queryKey: ['rovers'] });
      qc.invalidateQueries({ queryKey: ['simulation-status'] });
      qc.invalidateQueries({ queryKey: ['comm-queue', missionId] });
    },
  });

  // Poll for AEGIS proposals only in supervised mode
  const { data: proposal } = useQuery<AegisProposal>({
    queryKey: ['aegis-proposal', rover.id],
    queryFn: () => simulationApi.getAegisProposal(rover.id),
    enabled: rover.autonomy_level === 'supervised',
    refetchInterval: 3000,
  });

  const approveProposal = useMutation({
    mutationFn: () => simulationApi.approveAegisProposal(rover.id, missionId ?? ''),
    onSuccess: (result) => {
      noteResult(result, 'AEGIS approval');
      qc.invalidateQueries({ queryKey: ['aegis-proposal', rover.id] });
      qc.invalidateQueries({ queryKey: ['rovers'] });
      qc.invalidateQueries({ queryKey: ['mission'] });
      qc.invalidateQueries({ queryKey: ['comm-queue', missionId] });
    },
  });

  const rejectProposal = useMutation({
    mutationFn: () => simulationApi.rejectAegisProposal(rover.id),
    onSuccess: (result) => {
      noteResult(result, 'AEGIS rejection');
      qc.invalidateQueries({ queryKey: ['aegis-proposal', rover.id] });
      qc.invalidateQueries({ queryKey: ['comm-queue', missionId] });
    },
  });

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

      {queuedNotice && (
        <div style={{
          background: '#f59e0b22', border: '1px solid #f59e0b55',
          borderRadius: 5, padding: '5px 8px', marginBottom: 8,
          fontSize: 11, color: '#f59e0b',
        }}>
          📡 {queuedNotice}
        </div>
      )}

      {rover.state === 'safe_mode' && rover.safe_mode_reason && (
        <div style={{
          background: '#06b6d422', border: '1px solid #06b6d455',
          borderRadius: 5, padding: '5px 8px', marginBottom: 8,
          fontSize: 11, color: '#06b6d4',
        }}>
          🛡 Safe mode: {rover.safe_mode_reason}
          <div style={{ color: '#94a3b8', fontSize: 10, marginTop: 2 }}>
            Resolve the anomaly to restore operations
          </div>
        </div>
      )}

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

      {/* AEGIS autonomy level selector */}
      <div style={{ marginTop: 12, borderTop: '1px solid var(--border)', paddingTop: 10 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
          <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, letterSpacing: '0.04em' }}>
            AUTONOMY
          </span>
          {rover.aegis_objectives_generated > 0 && (
            <span style={{
              background: '#8b5cf622', color: '#8b5cf6',
              fontSize: 10, padding: '1px 6px', borderRadius: 10, fontWeight: 600,
            }}>
              {rover.aegis_objectives_generated} auto-obj
            </span>
          )}
        </div>
        <div style={{ display: 'flex', gap: 4 }}>
          {(['supervised', 'semi_autonomous', 'fully_autonomous'] as AutonomyLevel[]).map(lvl => {
            const active = rover.autonomy_level === lvl;
            const col = AUTONOMY_COLORS[lvl];
            return (
              <button
                key={lvl}
                onClick={() => setAutonomy.mutate(lvl)}
                disabled={setAutonomy.isPending}
                style={{
                  flex: 1, fontSize: 9, padding: '4px 2px', borderRadius: 5,
                  border: `1px solid ${active ? col : 'var(--border)'}`,
                  background: active ? col + '22' : 'transparent',
                  color: active ? col : 'var(--text-muted)',
                  cursor: 'pointer', fontWeight: active ? 700 : 400,
                  transition: 'all 0.15s',
                  textAlign: 'center', lineHeight: 1.2,
                }}
              >
                {AUTONOMY_LABELS[lvl]}
              </button>
            );
          })}
        </div>
        <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>
          {rover.autonomy_level === 'supervised' && 'Rover proposes targets; awaits approval'}
          {rover.autonomy_level === 'semi_autonomous' && 'Self-directs within explored terrain'}
          {rover.autonomy_level === 'fully_autonomous' && 'Full AEGIS: explores any reachable cell'}
        </div>
      </div>

      {/* AEGIS proposal panel (supervised mode only) */}
      {proposal?.pending && (
        <div style={{
          marginTop: 10,
          background: '#8b5cf611', border: '1px solid #8b5cf655',
          borderRadius: 6, padding: '8px 10px',
        }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: '#8b5cf6', marginBottom: 4 }}>
            🤖 AEGIS target proposal
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-sec)', marginBottom: 2 }}>
            ({proposal.x}, {proposal.y}) — score {proposal.score?.toFixed(3)}
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 8 }}>
            {proposal.reason}
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            <button
              onClick={() => approveProposal.mutate()}
              disabled={approveProposal.isPending || !missionId}
              style={{
                flex: 1, fontSize: 10, padding: '4px 0', borderRadius: 5,
                border: '1px solid #22c55e55', background: '#22c55e18',
                color: '#22c55e', cursor: 'pointer', fontWeight: 600,
              }}
            >
              {approveProposal.isPending ? 'Sending…' : '✓ Approve'}
            </button>
            <button
              onClick={() => rejectProposal.mutate()}
              disabled={rejectProposal.isPending}
              style={{
                flex: 1, fontSize: 10, padding: '4px 0', borderRadius: 5,
                border: '1px solid #ef444455', background: '#ef444418',
                color: '#ef4444', cursor: 'pointer', fontWeight: 600,
              }}
            >
              {rejectProposal.isPending ? '…' : '✕ Reject'}
            </button>
          </div>
        </div>
      )}
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
