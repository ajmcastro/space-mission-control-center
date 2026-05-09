import { useMemo, useState, useCallback } from 'react';
import type { Environment, Rover, TerrainType } from '@/types';

interface GridMapProps {
  environment: Environment;
  rovers?: Rover[];
  highlightPath?: [number, number][];
  targetCells?: [number, number][];
  cellSize?: number;
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
  rover?: Rover;
}

export function GridMap({
  environment,
  rovers = [],
  highlightPath = [],
  targetCells = [],
  cellSize = 28,
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
    rover?: Rover,
  ) => {
    setTooltip({ clientX: e.clientX, clientY: e.clientY, gridX: x, gridY: y, terrain, elevation, hasSample, isPath, isTarget, isHistory, rover });
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
            const px = x * cellSize;
            const py = y * cellSize;

            return (
              <g
                key={key}
                style={{ cursor: 'crosshair' }}
                onMouseEnter={e => handleMouseEnter(e, x, y, cell.terrain, cell.elevation ?? 0, cell.has_sample, isPath, isTgt, isHist, rover)}
              >
                <rect x={px} y={py} width={cellSize} height={cellSize}
                  fill={TERRAIN_COLORS[cell.terrain]} stroke="#0d1b2a" strokeWidth={0.5} />

                {isHist && !rover && (
                  <rect x={px} y={py} width={cellSize} height={cellSize}
                    fill="rgba(56, 189, 248, 0.18)" />
                )}

                {isPath && !rover && (
                  <rect x={px + 4} y={py + 4} width={cellSize - 8} height={cellSize - 8}
                    rx={3} fill="rgba(99, 210, 130, 0.35)" stroke="#4ade80" strokeWidth={1} />
                )}

                {isTgt && (
                  <rect x={px + 2} y={py + 2} width={cellSize - 4} height={cellSize - 4}
                    rx={3} fill="none" stroke="#f59e0b" strokeWidth={2} strokeDasharray="4 2" />
                )}

                {cell.has_sample && !rover && (
                  <circle cx={px + cellSize / 2} cy={py + cellSize / 2} r={3} fill="#f59e0b" />
                )}

                {!rover && (
                  <text x={px + cellSize / 2} y={py + cellSize / 2 + 3}
                    textAnchor="middle"
                    fill={cell.terrain === 'crevasse' ? '#333' : 'rgba(255,255,255,0.3)'}
                    fontSize={9}>
                    {TERRAIN_LABELS[cell.terrain]}
                  </text>
                )}

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

          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
            {tooltip.hasSample && <Tag color="#f59e0b">sample</Tag>}
            {tooltip.isTarget && <Tag color="#f59e0b">objective</Tag>}
            {tooltip.isPath && <Tag color="#4ade80">planned path</Tag>}
            {tooltip.isHistory && !tooltip.rover && <Tag color="#38bdf8">traversed</Tag>}
          </div>
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
    default:          return '#6b7280';
  }
}
