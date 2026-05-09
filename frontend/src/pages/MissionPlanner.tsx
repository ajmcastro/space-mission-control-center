import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCreateMission } from '@/hooks/useMissions';
import type { ObjectiveType } from '@/types';

interface ObjectiveDraft {
  type: ObjectiveType;
  target_x: number;
  target_y: number;
  description: string;
  priority: number;
}

const OBJECTIVE_TYPES: ObjectiveType[] = [
  'reach_waypoint', 'collect_sample', 'survey_area',
  'investigate_anomaly', 'return_to_base',
];

const OBJECTIVE_ICONS: Record<ObjectiveType, string> = {
  reach_waypoint:      '📍',
  collect_sample:      '🧪',
  survey_area:         '🔭',
  investigate_anomaly: '⚠️',
  return_to_base:      '🏠',
};

// ─── Auto-generation ─────────────────────────────────────────────────────────

/**
 * Generate a realistic-feeling objective sequence for an Enceladus mission.
 * Spreads waypoints across grid quadrants, mixes science and navigation types,
 * and always closes with return_to_base at the origin.
 */
function generateObjectives(gridW: number, gridH: number, count: number): ObjectiveDraft[] {
  const margin = 2;
  const w = Math.max(gridW - margin * 2, 1);
  const h = Math.max(gridH - margin * 2, 1);

  const anchors = [
    [0.6, 0.3],
    [0.7, 0.7],
    [0.3, 0.6],
    [0.5, 0.15],
    [0.15, 0.35],
    [0.8, 0.45],
  ];

  const typeSequence: ObjectiveType[] = [
    'reach_waypoint',
    'collect_sample',
    'survey_area',
    'investigate_anomaly',
    'collect_sample',
    'reach_waypoint',
  ];

  const descriptions: Record<ObjectiveType, string[]> = {
    reach_waypoint:      ['Navigate to survey staging area', 'Advance to observation point', 'Reach grid sector checkpoint'],
    collect_sample:      ['Collect subsurface ice core sample', 'Retrieve mineral deposit specimen', 'Gather geyser ejecta sample'],
    survey_area:         ['Wide-angle terrain survey', 'Spectroscopic surface analysis', 'Thermal emission mapping'],
    investigate_anomaly: ['Investigate magnetic field anomaly', 'Assess unexpected heat signature', 'Examine surface fracture pattern'],
    return_to_base:      ['Return to landing site for data uplink'],
  };

  const pick = <T,>(arr: T[], seed: number): T => arr[seed % arr.length];

  const nonReturnCount = Math.max(1, count - 1);
  const result: ObjectiveDraft[] = [];

  for (let i = 0; i < nonReturnCount; i++) {
    const [ax, ay] = anchors[i % anchors.length];
    const jitterX = ((i * 7 + 3) % 5) - 2;
    const jitterY = ((i * 11 + 5) % 5) - 2;
    const x = Math.min(gridW - 1, Math.max(0, Math.round(ax * w + margin + jitterX)));
    const y = Math.min(gridH - 1, Math.max(0, Math.round(ay * h + margin + jitterY)));
    const type = typeSequence[i % typeSequence.length];

    result.push({
      type,
      target_x: x,
      target_y: y,
      description: pick(descriptions[type], i),
      priority: i + 1,
    });
  }

  result.push({
    type: 'return_to_base',
    target_x: 0,
    target_y: 0,
    description: descriptions.return_to_base[0],
    priority: result.length + 1,
  });

  return result;
}

// ─── Shared UI primitives ─────────────────────────────────────────────────────

function Input({ label, ...props }: { label: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div style={{ marginBottom: 14 }}>
      <label style={{ display: 'block', fontSize: 12, color: 'var(--text-sec)', marginBottom: 4 }}>{label}</label>
      <input
        {...props}
        style={{
          width: '100%',
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          borderRadius: 6,
          padding: '8px 12px',
          color: 'var(--text)',
          fontSize: 13,
          fontFamily: 'inherit',
          boxSizing: 'border-box',
        }}
      />
    </div>
  );
}

function Select({ label, children, ...props }: { label: string } & React.SelectHTMLAttributes<HTMLSelectElement> & { children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <label style={{ display: 'block', fontSize: 12, color: 'var(--text-sec)', marginBottom: 4 }}>{label}</label>
      <select
        {...props}
        style={{
          width: '100%',
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          borderRadius: 6,
          padding: '8px 12px',
          color: 'var(--text)',
          fontSize: 13,
          fontFamily: 'inherit',
        }}
      >
        {children}
      </select>
    </div>
  );
}

function Btn({ children, onClick, variant = 'primary', disabled, title }: {
  children: React.ReactNode;
  onClick?: () => void;
  variant?: 'primary' | 'secondary' | 'accent' | 'danger';
  disabled?: boolean;
  title?: string;
}) {
  const colors = {
    primary:   { bg: 'var(--btn-primary)', text: '#fff' },
    secondary: { bg: 'var(--border)', text: 'var(--text-sec)' },
    accent:    { bg: 'var(--btn-accent)', text: 'var(--accent-green)' },
    danger:    { bg: 'var(--btn-danger, #7f1d1d)', text: 'var(--accent-red)' },
  };
  const c = colors[variant];
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={title}
      style={{
        background: disabled ? 'var(--border)' : c.bg,
        color: disabled ? 'var(--text-muted)' : c.text,
        border: 'none',
        borderRadius: 6,
        padding: '8px 16px',
        fontSize: 13,
        cursor: disabled ? 'not-allowed' : 'pointer',
        fontFamily: 'inherit',
        fontWeight: 600,
      }}
    >
      {children}
    </button>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export function MissionPlanner() {
  const navigate = useNavigate();
  const createMission = useCreateMission();

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [gridW, setGridW] = useState(20);
  const [gridH, setGridH] = useState(20);

  const [objectives, setObjectives] = useState<ObjectiveDraft[]>([]);

  const [objType, setObjType] = useState<ObjectiveType>('reach_waypoint');
  const [objX, setObjX] = useState(5);
  const [objY, setObjY] = useState(5);
  const [objDesc, setObjDesc] = useState('');
  const [objPriority, setObjPriority] = useState(1);

  const [autoCount, setAutoCount] = useState(4);

  const addObjective = () => {
    const next = [...objectives, {
      type: objType,
      target_x: objX,
      target_y: objY,
      description: objDesc,
      priority: objPriority,
    }];
    setObjectives(next);
    setObjPriority(objPriority + 1);
    setObjDesc('');
  };

  const removeObjective = (i: number) => {
    const next = objectives.filter((_, idx) => idx !== i)
      .map((o, idx) => ({ ...o, priority: idx + 1 }));
    setObjectives(next);
    setObjPriority(next.length + 1);
  };

  const handleAutoGenerate = () => {
    const generated = generateObjectives(gridW, gridH, autoCount);
    setObjectives(generated);
    setObjPriority(generated.length + 1);
  };

  const handleCreate = async () => {
    if (!name.trim()) return;
    const mission = await createMission.mutateAsync({
      name: name.trim(),
      description,
      grid_width: gridW,
      grid_height: gridH,
      objectives,
    });
    navigate(`/missions/${mission.id}`);
  };

  return (
    <div style={{ padding: '24px 32px', maxWidth: 960, margin: '0 auto' }}>
      <h1 style={{ fontSize: 20, fontWeight: 800, color: 'var(--text)', marginBottom: 24 }}>
        Mission Planner
      </h1>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 32, alignItems: 'start' }}>

        {/* ── Left: Mission config ─────────────────────────────────────────── */}
        <div>
          <h2 style={{ fontSize: 14, color: 'var(--text-sec)', marginBottom: 16, fontWeight: 600 }}>
            Mission Config
          </h2>
          <Input
            label="Mission Name *"
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="e.g. Alpha Geyser Survey"
          />
          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'block', fontSize: 12, color: 'var(--text-sec)', marginBottom: 4 }}>Description</label>
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              rows={3}
              placeholder="Mission objectives and context..."
              style={{
                width: '100%',
                background: 'var(--surface)',
                border: '1px solid var(--border)',
                borderRadius: 6,
                padding: '8px 12px',
                color: 'var(--text)',
                fontSize: 13,
                fontFamily: 'inherit',
                resize: 'vertical',
                boxSizing: 'border-box',
              }}
            />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <Input label="Grid Width"  type="number" value={gridW} onChange={e => setGridW(+e.target.value)} min={5} max={50} />
            <Input label="Grid Height" type="number" value={gridH} onChange={e => setGridH(+e.target.value)} min={5} max={50} />
          </div>

          <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 8 }}>
            <Btn
              onClick={handleCreate}
              disabled={!name.trim() || objectives.length === 0 || createMission.isPending}
              title={objectives.length === 0 ? 'Add at least one objective before creating' : undefined}
            >
              {createMission.isPending ? 'Creating...' : `Create Mission (${objectives.length} objective${objectives.length !== 1 ? 's' : ''})`}
            </Btn>
            {objectives.length === 0 && (
              <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: 0 }}>
                Add at least one objective on the right, or use Auto-generate.
              </p>
            )}
            {createMission.isError && (
              <p style={{ color: 'var(--accent-red)', fontSize: 12, margin: 0 }}>
                Error creating mission. Check backend connection.
              </p>
            )}
          </div>
        </div>

        {/* ── Right: Objectives ────────────────────────────────────────────── */}
        <div>
          <h2 style={{ fontSize: 14, color: 'var(--text-sec)', marginBottom: 16, fontWeight: 600 }}>
            Objectives
          </h2>

          {/* Auto-generate panel */}
          <div style={{
            background: 'var(--surface-alt)',
            border: '1px solid var(--border-strong)',
            borderRadius: 8,
            padding: '12px 14px',
            marginBottom: 20,
          }}>
            <div style={{ fontSize: 12, color: 'var(--accent)', fontWeight: 700, marginBottom: 10 }}>
              Auto-generate
            </div>
            <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end' }}>
              <div style={{ flex: 1 }}>
                <label style={{ display: 'block', fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>
                  Number of objectives
                </label>
                <input
                  type="number"
                  value={autoCount}
                  onChange={e => setAutoCount(Math.max(2, Math.min(8, +e.target.value)))}
                  min={2}
                  max={8}
                  style={{
                    width: '100%',
                    background: 'var(--surface)',
                    border: '1px solid var(--border)',
                    borderRadius: 6,
                    padding: '7px 10px',
                    color: 'var(--text)',
                    fontSize: 13,
                    fontFamily: 'inherit',
                    boxSizing: 'border-box',
                  }}
                />
              </div>
              <Btn variant="accent" onClick={handleAutoGenerate}>
                ✦ Generate
              </Btn>
            </div>
            <p style={{ fontSize: 13, color: 'var(--text-faint)', margin: '8px 0 0 0' }}>
              Spreads waypoints, samples, and a science task across the grid.
              Always ends with return-to-base. You can edit or add more below.
            </p>
          </div>

          {/* Divider */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
            <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
            <span style={{ fontSize: 11, color: 'var(--text-faint)' }}>or add manually</span>
            <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
          </div>

          {/* Manual-add form */}
          <Select label="Type" value={objType} onChange={e => setObjType(e.target.value as ObjectiveType)}>
            {OBJECTIVE_TYPES.map(t => (
              <option key={t} value={t}>{OBJECTIVE_ICONS[t]} {t.replace(/_/g, ' ')}</option>
            ))}
          </Select>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
            <Input label="Target X"  type="number" value={objX}        onChange={e => setObjX(+e.target.value)}        min={0} max={gridW - 1} />
            <Input label="Target Y"  type="number" value={objY}        onChange={e => setObjY(+e.target.value)}        min={0} max={gridH - 1} />
            <Input label="Priority"  type="number" value={objPriority} onChange={e => setObjPriority(+e.target.value)} min={1} />
          </div>
          <Input label="Description (optional)" value={objDesc} onChange={e => setObjDesc(e.target.value)} placeholder="e.g. Collect ice core near geyser" />
          <Btn variant="secondary" onClick={addObjective}>+ Add Objective</Btn>

          {/* Objective list */}
          <div style={{ marginTop: 16 }}>
            {objectives.length === 0 && (
              <p style={{ color: 'var(--text-faint)', fontSize: 12, fontStyle: 'italic' }}>
                No objectives yet — auto-generate or add one above.
              </p>
            )}
            {objectives.map((o, i) => (
              <div
                key={i}
                style={{
                  background: 'var(--surface)',
                  border: '1px solid var(--border)',
                  borderRadius: 6,
                  padding: '8px 12px',
                  marginBottom: 6,
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: 8,
                }}
              >
                <div style={{ minWidth: 0 }}>
                  <span style={{ fontSize: 12, color: 'var(--accent)', fontWeight: 600 }}>
                    {OBJECTIVE_ICONS[o.type]} #{o.priority} {o.type.replace(/_/g, ' ')}
                  </span>
                  <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 8 }}>
                    ({o.target_x}, {o.target_y})
                  </span>
                  {o.description && (
                    <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {o.description}
                    </div>
                  )}
                </div>
                <button
                  onClick={() => removeObjective(i)}
                  title="Remove objective"
                  style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 16, lineHeight: 1, flexShrink: 0 }}
                >
                  ×
                </button>
              </div>
            ))}
            {objectives.length > 0 && (
              <button
                onClick={() => { setObjectives([]); setObjPriority(1); }}
                style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 11, marginTop: 4, padding: 0 }}
              >
                Clear all
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
