import { useMemo, useState, useCallback } from 'react';
import type { Environment, Rover, TerrainType } from '@/types';

interface GridMapProps {
  environment: Environment;
  rovers?: Rover[];
  highlightPath?: [number, number][];
  targetCells?: [number, number][];
  cellSize?: number;
  showScienceOverlay?: boolean;
}

// Terrain colours intentionally stay fixed — they represent physical surface
// properties and must remain readable regardless of UI theme.
const TERRAIN_COLORS: Record<TerrainType, string> = {
  flat:     '#1e3a4a',
  rocky:    '#4a3728',
  ice:      '#c8e8f0',
  crater:   '#2d1f0e',
  geyser:   '#7c3aed',
  crevasse: '#0a0a0a',
};

// Dormant geysers are safe traversal targets — distinct muted colour.
const GEYSER_DORMANT_COLOR = '#4a3060';

// Science heatmap gradient: dark-teal (low) → gold (high), blended as rgba overlay.
function scienceOverlayColor(value: number): string {
  // value is 0–10; map to 0–1
  const t = Math.min(1, value / 10);
  // low=teal (#0d9488), mid=lime (#84cc16), high=amber (#f59e0b)
  let r: number, g: number, b: number;
  if (t < 0.5) {
    const s = t * 2;
    r = Math.round(13  + s * (132 - 13));
    g = Math.round(148 + s * (204 - 148));
    b = Math.round(136 + s * (22  - 136));
  } else {
    const s = (t - 0.5) * 2;
    r = Math.round(132 + s * (245 - 132));
    g = Math.round(204 + s * (158 - 204));
    b = Math.round(22  + s * (11  - 22));
  }
  const alpha = 0.15 + t * 0.45;  // 0.15 at low, 0.60 at max
  return `rgba(${r},${g},${b},${alpha})`;
}

// Surface frost — subtle blue tint during Enceladus night.
const FROST_OVERLAY_COLOR = 'rgba(120,180,255,0.18)';

const TERRAIN_LABELS: Record<TerrainType, string> = {
  flat: 'F', rocky: 'R', ice: 'I', crater: 'C', geyser: 'G', crevasse: '█',
};

const TERRAIN_DESCRIPTIONS: Record<TerrainType, string> = {
  flat:     'Flat terrain — easy traversal, standard movement cost',
  rocky:    'Rocky terrain — rough surface, higher movement cost',
  ice:      'Ice surface — slippery, moderate movement cost',
  crater:   'Impact crater — difficult terrain, high movement cost',
  geyser:   'Active geyser — hazardous, may halt rover',
  crevasse: 'Crevasse — impassable, rover cannot cross',
};

interface TooltipInfo {
  clientX: number;
  clientY: number;
  gridX: number;
  gridY: number;
  terrain: TerrainType;
  elevation: number;
  hasSample: boolean;
  isPath: boolean;
  isTarget: boolean;
  isHistory: boolean;
  fog: boolean;
  geyserActive: boolean;
  scienceValue: number;
  rover?: Rover;
}

export function GridMap({
  environment,
  rovers = [],
  highlightPath = [],
  targetCells = [],
  cellSize = 28,
  showScienceOverlay = false,
}: GridMapProps) {
  const { grid } = environment;
  const [tooltip, setTooltip] = useState<TooltipInfo | null>(null);

  const pathSet = useMemo(
    () => new Set(highlightPath.map(([x, y]) => `${x},${y}`)),
    [highlightPath],
  );
  const targetSet = useMemo(
    () => new Set(targetCells.map(([x, y]) => `${x},${y}`)),
    [targetCells],
  );
  const roverMap = useMemo(() => {
    const m: Record<string, Rover> = {};
    rovers.forEach(r => { m[`${r.x},${r.y}`] = r; });
    return m;
  }, [rovers]);
  const historySet = useMemo(() => {
    const s = new Set<string>();
    rovers.forEach(r => r.path_history.forEach(([hx, hy]) => s.add(`${hx},${hy}`)));
    return s;
  }, [rovers]);

  const svgW = grid.width  * cellSize;
  const svgH = grid.height * cellSize;

  const handleMouseEnter = useCallback((
    e: React.MouseEvent,
    x: number, y: number,
    terrain: TerrainType,
    elevation: number,
    hasSample: boolean,
    isPath: boolean,
    isTarget: boolean,
    isHistory: boolean,
    rover: Rover | undefined,
    fog: boolean,
    geyserActive: boolean,
    scienceValue: number,
  ) => {
    setTooltip({ clientX: e.clientX, clientY: e.clientY, gridX: x, gridY: y, terrain, elevation, hasSample, isPath, isTarget, isHistory, fog, geyserActive, scienceValue, rover });
  }, []);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    setTooltip(t => t ? { ...t, clientX: e.clientX, clientY: e.clientY } : null);
  }, []);

  return (
    <div style={{ overflowX: 'auto', overflowY: 'auto', position: 'relative' }}>
      <svg
        width={svgW} height={svgH}
        style={{ display: 'block', fontFamily: 'monospace', fontSize: 10 }}
        onMouseLeave={() => setTooltip(null)}
        onMouseMove={handleMouseMove}
      >
        {grid.cells.map((row, y) =>
          row.map((cell, x) => {
            const key    = `${x},${y}`;
            const isPath = pathSet.has(key);
            const isTgt  = targetSet.has(key);
            const isHist = historySet.has(key);
            const rover  = roverMap[key];
            const fog    = !cell.revealed;
            const px = x * cellSize;
            const py = y * cellSize;

            // Dynamic terrain colours
            const isDormantGeyser = !fog && cell.terrain === 'geyser' && !cell.geyser_active;
            const baseFill = fog ? '#0d1117'
              : isDormantGeyser ? GEYSER_DORMANT_COLOR
              : TERRAIN_COLORS[cell.terrain];
            const isFrosty = !fog && environment.is_night &&
              (cell.terrain === 'flat' || cell.terrain === 'ice');

            return (
              <g
                key={key}
                style={{ cursor: 'crosshair' }}
                onMouseEnter={e => handleMouseEnter(e, x, y, cell.terrain, cell.elevation ?? 0, cell.has_sample, isPath, isTgt, isHist, rover, fog, cell.geyser_active ?? true, cell.science_value ?? 0)}
              >
                {/* Base fill — fog cells render as uniform near-black */}
                <rect x={px} y={py} width={cellSize} height={cellSize}
                  fill={baseFill}
                  stroke={fog ? '#111827' : '#0d1b2a'}
                  strokeWidth={0.5} />

                {/* Subtle inner border gives fogged cells a tiled texture */}
                {fog && (
                  <rect x={px + 1} y={py + 1} width={cellSize - 2} height={cellSize - 2}
                    fill="none" stroke="#1a2332" strokeWidth={0.3} />
                )}

                {/* Surface frost overlay during Enceladus night */}
                {isFrosty && (
                  <rect x={px} y={py} width={cellSize} height={cellSize}
                    fill={FROST_OVERLAY_COLOR} />
                )}

                {/* Science value heatmap overlay — shown on revealed cells only */}
                {showScienceOverlay && !fog && (cell.science_value ?? 0) > 0 && (
                  <rect x={px} y={py} width={cellSize} height={cellSize}
                    fill={scienceOverlayColor(cell.science_value ?? 0)} />
                )}

                {/* Dormant geyser indicator — small pulsing dot */}
                {isDormantGeyser && !rover && (
                  <circle cx={px + cellSize / 2} cy={py + cellSize / 2} r={2.5}
                    fill="#c4b5fd" opacity={0.7} />
                )}

                {/* Revealed-only overlays */}
                {!fog && isHist && !rover && (
                  <rect x={px} y={py} width={cellSize} height={cellSize}
                    fill="rgba(56, 189, 248, 0.18)" />
                )}
                {!fog && isPath && !rover && (
                  <rect x={px + 4} y={py + 4} width={cellSize - 8} height={cellSize - 8}
                    rx={3} fill="rgba(99, 210, 130, 0.35)" stroke="#4ade80" strokeWidth={1} />
                )}
                {!fog && cell.has_sample && !rover && (
                  <circle cx={px + cellSize / 2} cy={py + cellSize / 2} r={3} fill="#f59e0b" />
                )}
                {!fog && !rover && (
                  <text x={px + cellSize / 2} y={py + cellSize / 2 + 3}
                    textAnchor="middle"
                    fill={cell.terrain === 'crevasse' ? '#333' : 'rgba(255,255,255,0.3)'}
                    fontSize={9}>
                    {TERRAIN_LABELS[cell.terrain]}
                  </text>
                )}

                {/* Objectives visible even in fog — known from orbital survey data */}
                {isTgt && (
                  <rect x={px + 2} y={py + 2} width={cellSize - 4} height={cellSize - 4}
                    rx={3} fill="none"
                    stroke={fog ? '#92400e' : '#f59e0b'}
                    strokeWidth={2} strokeDasharray="4 2" />
                )}

                {/* Rover always visible */}
                {rover && (
                  <g>
                    <circle cx={px + cellSize / 2} cy={py + cellSize / 2}
                      r={cellSize / 2 - 3} fill={roverStateColor(rover.state)}
                      stroke="#fff" strokeWidth={1.5} />
                    <text x={px + cellSize / 2} y={py + cellSize / 2 + 4}
                      textAnchor="middle" fill="white" fontSize={10} fontWeight="bold">
                      R
                    </text>
                  </g>
                )}
              </g>
            );
          }),
        )}

        {Array.from({ length: grid.width }, (_, x) => (
          <text key={`xl-${x}`} x={x * cellSize + cellSize / 2} y={grid.height * cellSize + 12}
            textAnchor="middle" fill="#475569" fontSize={8}>{x}</text>
        ))}
        {Array.from({ length: grid.height }, (_, y) => (
          <text key={`yl-${y}`} x={-8} y={y * cellSize + cellSize / 2 + 3}
            textAnchor="middle" fill="#475569" fontSize={8}>{y}</text>
        ))}
      </svg>

      {/* Hover tooltip */}
      {tooltip && (
        <div style={{
          position: 'fixed',
          left: tooltip.clientX + 14,
          top: tooltip.clientY + 14,
          background: '#0f172a',
          border: '1px solid #1e3a5f',
          borderRadius: 8,
          padding: '8px 12px',
          fontSize: 12,
          color: '#e2e8f0',
          pointerEvents: 'none',
          zIndex: 9999,
          minWidth: 180,
          maxWidth: 240,
          boxShadow: '0 4px 16px rgba(0,0,0,0.5)',
        }}>
          <div style={{ fontWeight: 700, marginBottom: 4, color: '#38bdf8' }}>
            ({tooltip.gridX}, {tooltip.gridY})
          </div>

          {tooltip.fog && !tooltip.rover ? (
            <>
              <div style={{ color: '#475569', fontSize: 11, fontStyle: 'italic', marginBottom: 4 }}>
                Unknown territory — deploy a rover to reveal
              </div>
              {tooltip.isTarget && <Tag color="#92400e">objective (uncharted)</Tag>}
            </>
          ) : (
            <>
              {tooltip.rover && (
                <div style={{ marginBottom: 6, paddingBottom: 6, borderBottom: '1px solid #1e293b' }}>
                  <div style={{ fontWeight: 600, color: roverStateColor(tooltip.rover.state) }}>
                    {tooltip.rover.name}
                  </div>
                  <div style={{ color: '#94a3b8', fontSize: 11 }}>
                    State: {tooltip.rover.state.replace('_', ' ')} · Battery: {tooltip.rover.battery_pct.toFixed(1)}%
                  </div>
                  <div style={{ color: '#94a3b8', fontSize: 11 }}>
                    Steps: {tooltip.rover.steps_taken} · Samples: {tooltip.rover.samples_collected}
                  </div>
                </div>
              )}

              <div style={{ color: '#94a3b8', fontSize: 11, marginBottom: 2 }}>
                Terrain: <span style={{ color: '#e2e8f0', fontWeight: 600 }}>{tooltip.terrain}</span>
              </div>
              {tooltip.elevation !== 0 && (
                <div style={{ color: '#94a3b8', fontSize: 11, marginBottom: 2 }}>
                  Elevation: <span style={{ color: '#e2e8f0' }}>{tooltip.elevation.toFixed(2)}</span>
                  <span style={{ color: '#64748b' }}> ({tooltip.elevation > 0 ? 'ridge' : 'depression'})</span>
                </div>
              )}
              <div style={{ color: '#64748b', fontSize: 10, marginBottom: 4 }}>
                {TERRAIN_DESCRIPTIONS[tooltip.terrain]}
              </div>

              {tooltip.terrain === 'geyser' && (
                <div style={{ fontSize: 10, color: tooltip.geyserActive ? '#c084fc' : '#86efac', marginBottom: 4 }}>
                  {tooltip.geyserActive
                    ? '🌋 Erupting — hazardous traversal'
                    : '💤 Dormant — safe, high science value'}
                </div>
              )}
              {tooltip.scienceValue > 0 && (
                <div style={{ fontSize: 10, color: '#fbbf24', marginBottom: 4 }}>
                  Science value:{' '}
                  <span style={{ fontWeight: 700 }}>{tooltip.scienceValue.toFixed(1)}</span>
                  <span style={{ color: '#64748b' }}> / 10</span>
                </div>
              )}
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
                {tooltip.hasSample && <Tag color="#f59e0b">sample</Tag>}
                {tooltip.isTarget && <Tag color="#f59e0b">objective</Tag>}
                {tooltip.isPath && <Tag color="#4ade80">planned path</Tag>}
                {tooltip.isHistory && !tooltip.rover && <Tag color="#38bdf8">traversed</Tag>}
                {environment.is_night && (tooltip.terrain === 'flat' || tooltip.terrain === 'ice') && (
                  <Tag color="#93c5fd">frost active</Tag>
                )}
              </div>
            </>
          )}
        </div>
      )}

      {/* Legend */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 8, fontSize: 11, color: 'var(--text-muted)' }}>
        {(Object.entries(TERRAIN_COLORS) as [TerrainType, string][]).map(([t, c]) => (
          <span key={t} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 12, height: 12, background: c, border: '1px solid #333', display: 'inline-block' }} />
            {t}
          </span>
        ))}
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 12, height: 12, background: GEYSER_DORMANT_COLOR, border: '1px solid #333', display: 'inline-block' }} />
          geyser (dormant)
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 12, height: 12, background: 'rgba(99,210,130,0.35)', border: '1px solid #4ade80', display: 'inline-block' }} />
          planned path
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 12, height: 12, background: 'rgba(56,189,248,0.18)', border: '1px solid #38bdf8', display: 'inline-block' }} />
          traversed
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 12, height: 12, border: '2px dashed #f59e0b', display: 'inline-block' }} />
          objective
        </span>
        {environment.is_night && (
          <span style={{
            display: 'flex', alignItems: 'center', gap: 4,
            background: 'rgba(120,180,255,0.15)', border: '1px solid rgba(120,180,255,0.4)',
            borderRadius: 4, padding: '1px 6px', color: '#93c5fd', fontWeight: 600,
          }}>
            🌙 Night frost active — movement costs ↑
          </span>
        )}
        {showScienceOverlay && (
          <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{
              width: 40, height: 12, display: 'inline-block', borderRadius: 2,
              background: 'linear-gradient(to right, rgba(13,148,136,0.6), rgba(132,204,22,0.6), rgba(245,158,11,0.75))',
              border: '1px solid #44444466',
            }} />
            science value (low → high)
          </span>
        )}
      </div>
    </div>
  );
}

function Tag({ color, children }: { color: string; children: React.ReactNode }) {
  return (
    <span style={{
      background: color + '22',
      color,
      border: `1px solid ${color}55`,
      borderRadius: 4,
      padding: '1px 6px',
      fontSize: 10,
      fontWeight: 600,
    }}>
      {children}
    </span>
  );
}

function roverStateColor(state: string): string {
  switch (state) {
    case 'idle':      return '#22c55e';
    case 'moving':    return '#3b82f6';
    case 'sampling':  return '#f59e0b';
    case 'charging':  return '#a855f7';
    case 'stuck':     return '#ef4444';
    case 'comm_lost': return '#f97316';
    case 'error':     return '#dc2626';
    case 'safe_mode': return '#06b6d4';  // cyan — standby / waiting for ground contact
    default:          return '#6b7280';
  }
}
