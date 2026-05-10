import { useRef, useState, useCallback } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, PerspectiveCamera } from '@react-three/drei';
import * as THREE from 'three';
import type { Environment, Rover, TerrainType } from '@/types';

const ELEV_SCALE = 2.5;
const CELL_GAP   = 0.05;

const TERRAIN_COLORS_3D: Record<TerrainType, string> = {
  flat:     '#3a8aad',
  rocky:    '#9b7a5a',
  ice:      '#c8e8f0',
  crater:   '#7a5530',
  geyser:   '#9d5cf0',
  crevasse: '#1a1a2e',
};

const GEYSER_DORMANT_COLOR_3D = '#5c3880';   // muted purple for dormant geyser
const FROST_COLOR_3D          = '#6ab0d8';   // cooler blue tint for frosted flat/ice

const TERRAIN_DESCRIPTIONS: Record<TerrainType, string> = {
  flat:     'Flat terrain — easy traversal, standard movement cost',
  rocky:    'Rocky terrain — rough surface, higher movement cost',
  ice:      'Ice surface — slippery, moderate movement cost',
  crater:   'Impact crater — difficult terrain, high movement cost',
  geyser:   'Active geyser — hazardous, may halt rover',
  crevasse: 'Crevasse — impassable, rover cannot cross',
};

const ROVER_STATE_COLORS: Record<string, string> = {
  idle:      '#22c55e',
  moving:    '#3b82f6',
  sampling:  '#f59e0b',
  charging:  '#a855f7',
  stuck:     '#ef4444',
  comm_lost: '#f97316',
  error:     '#dc2626',
  safe_mode: '#06b6d4',  // cyan — standby / waiting for ground contact
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
  fog: boolean;
  rover?: Rover;
}

interface TerrainCanvasProps {
  environment: Environment;
  rovers?: Rover[];
  highlightPath?: [number, number][];
  targetCells?: [number, number][];
}

interface CellProps {
  x: number;
  z: number;
  gridX: number;
  gridY: number;
  elevation: number;
  hasSample: boolean;
  terrain: TerrainType;
  color: string;
  isPath: boolean;
  isTarget: boolean;
  fog: boolean;
  rover?: Rover;
  onHover: (info: TooltipInfo) => void;
  onHoverMove: (clientX: number, clientY: number) => void;
  onHoverEnd: () => void;
}

function TerrainCell({ x, z, gridX, gridY, elevation, hasSample, terrain, color, isPath, isTarget, fog, rover, onHover, onHoverMove, onHoverEnd }: CellProps) {
  const height = Math.max(0.2, 1 + elevation * ELEV_SCALE);
  const posY   = elevation * ELEV_SCALE * 0.5;

  return (
    <mesh
      position={[x, posY, z]}
      scale={[1, height, 1]}
      castShadow
      receiveShadow
      onPointerEnter={e => {
        e.stopPropagation();
        onHover({ clientX: e.nativeEvent.clientX, clientY: e.nativeEvent.clientY, gridX, gridY, terrain, elevation, hasSample, isPath, isTarget, fog, rover });
      }}
      onPointerMove={e => onHoverMove(e.nativeEvent.clientX, e.nativeEvent.clientY)}
      onPointerLeave={() => onHoverEnd()}
    >
      <boxGeometry args={[1 - CELL_GAP, 1, 1 - CELL_GAP]} />
      <meshStandardMaterial color={color} />
    </mesh>
  );
}

function RoverMarker({ rover, elevation, gridHeight, onHover, onHoverMove, onHoverEnd }: {
  rover: Rover;
  elevation: number;
  gridHeight: number;
  onHover: (info: TooltipInfo) => void;
  onHoverMove: (clientX: number, clientY: number) => void;
  onHoverEnd: () => void;
}) {
  const groupRef = useRef<THREE.Group>(null);
  const cell_z   = gridHeight - 1 - rover.y;
  const color    = ROVER_STATE_COLORS[rover.state] ?? '#22c55e';

  // y of the top surface of this cell
  const cellH    = Math.max(0.2, 1 + elevation * ELEV_SCALE);
  const cellTopY = elevation * ELEV_SCALE * 0.5 + cellH * 0.5;
  const baseY    = cellTopY + 1.8;

  // Bob up and down; offset phase per rover so multiple rovers don't sync
  const phase = rover.x * 1.3 + rover.y * 0.7;
  useFrame(({ clock }) => {
    if (groupRef.current) {
      groupRef.current.position.y = baseY + Math.sin(clock.elapsedTime * 2.5 + phase) * 0.22;
    }
  });

  const pointerProps = {
    onPointerEnter: (e: { stopPropagation(): void; nativeEvent: MouseEvent }) => {
      e.stopPropagation();
      onHover({
        clientX: e.nativeEvent.clientX, clientY: e.nativeEvent.clientY,
        gridX: rover.x, gridY: rover.y,
        terrain: 'flat', elevation,
        hasSample: false, isPath: false, isTarget: false,
        fog: false,   // rover position is always revealed
        rover,
      });
    },
    onPointerMove: (e: { nativeEvent: MouseEvent }) =>
      onHoverMove(e.nativeEvent.clientX, e.nativeEvent.clientY),
    onPointerLeave: () => onHoverEnd(),
  };

  return (
    <group ref={groupRef} position={[rover.x, baseY, cell_z]}>
      {/* Sphere head */}
      <mesh position={[0, 0.6, 0]} castShadow {...pointerProps}>
        <sphereGeometry args={[0.5, 16, 16]} />
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.55} />
      </mesh>
      {/* Cone body pointing down */}
      <mesh position={[0, -0.2, 0]} rotation-x={Math.PI} castShadow {...pointerProps}>
        <coneGeometry args={[0.42, 1.1, 16]} />
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.35} />
      </mesh>
      {/* Shadow ring on terrain surface for positional clarity */}
      <mesh position={[0, -baseY + cellTopY + 0.02, 0]} rotation-x={-Math.PI / 2}>
        <ringGeometry args={[0.45, 0.7, 32]} />
        <meshBasicMaterial color={color} transparent opacity={0.35} />
      </mesh>
    </group>
  );
}

function Tooltip({ info }: { info: TooltipInfo }) {
  const roverColor = info.rover ? (ROVER_STATE_COLORS[info.rover.state] ?? '#6b7280') : null;
  return (
    <div style={{
      position: 'fixed',
      left: info.clientX + 14,
      top:  info.clientY + 14,
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
        ({info.gridX}, {info.gridY})
      </div>

      {info.rover && (
        <div style={{ marginBottom: 6, paddingBottom: 6, borderBottom: '1px solid #1e293b' }}>
          <div style={{ fontWeight: 600, color: roverColor ?? '#22c55e' }}>
            {info.rover.name}
          </div>
          <div style={{ color: '#94a3b8', fontSize: 11 }}>
            State: {info.rover.state.replace('_', ' ')} · Battery: {info.rover.battery_pct.toFixed(1)}%
          </div>
          <div style={{ color: '#94a3b8', fontSize: 11 }}>
            Steps: {info.rover.steps_taken} · Samples: {info.rover.samples_collected}
          </div>
        </div>
      )}

      {!info.rover && (
        info.fog ? (
          <>
            <div style={{ color: '#475569', fontSize: 11, fontStyle: 'italic', marginBottom: 4 }}>
              Unknown territory — deploy a rover to reveal
            </div>
            {info.isTarget && <Tag color="#92400e">objective (uncharted)</Tag>}
          </>
        ) : (
          <>
            <div style={{ color: '#94a3b8', fontSize: 11, marginBottom: 2 }}>
              Terrain: <span style={{ color: '#e2e8f0', fontWeight: 600 }}>{info.terrain}</span>
            </div>
            {info.elevation !== 0 && (
              <div style={{ color: '#94a3b8', fontSize: 11, marginBottom: 2 }}>
                Elevation: <span style={{ color: '#e2e8f0' }}>{info.elevation.toFixed(2)}</span>
                <span style={{ color: '#64748b' }}> ({info.elevation > 0 ? 'ridge' : 'depression'})</span>
              </div>
            )}
            <div style={{ color: '#64748b', fontSize: 10, marginBottom: 4 }}>
              {TERRAIN_DESCRIPTIONS[info.terrain]}
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
              {info.hasSample && <Tag color="#f59e0b">sample</Tag>}
              {info.isTarget  && <Tag color="#f59e0b">objective</Tag>}
              {info.isPath    && <Tag color="#4ade80">planned path</Tag>}
            </div>
          </>
        )
      )}
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

export function TerrainCanvas({
  environment,
  rovers = [],
  highlightPath = [],
  targetCells = [],
}: TerrainCanvasProps) {
  const { grid } = environment;
  const [tooltip, setTooltip] = useState<TooltipInfo | null>(null);

  const handleHover    = useCallback((info: TooltipInfo) => setTooltip(info), []);
  const handleHoverMove = useCallback((clientX: number, clientY: number) => {
    setTooltip(t => t ? { ...t, clientX, clientY } : null);
  }, []);
  const handleHoverEnd = useCallback(() => setTooltip(null), []);

  const pathSet   = new Set(highlightPath.map(([x, y]) => `${x},${y}`));
  const targetSet = new Set(targetCells.map(([x, y])  => `${x},${y}`));
  const roverMap  = new Map(rovers.map(r => [`${r.x},${r.y}`, r]));

  const centerX = (grid.width  - 1) / 2;
  const centerZ = (grid.height - 1) / 2;
  const camDist = Math.max(grid.width, grid.height) * 1.1;

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <Canvas shadows camera={{ position: [centerX, camDist * 0.8, centerZ + camDist], fov: 45 }}>
        <color attach="background" args={['#060d1a']} />
        <PerspectiveCamera makeDefault position={[centerX, camDist * 0.8, centerZ + camDist]} fov={45} />
        <OrbitControls target={[centerX, 0, centerZ]} maxPolarAngle={Math.PI / 2.1} enableDamping dampingFactor={0.08} />
        <ambientLight intensity={0.8} />
        <directionalLight position={[centerX + 10, 20, centerZ + 10]} intensity={1.5} castShadow shadow-mapSize={[1024, 1024]} />
        <directionalLight position={[centerX - 10, 15, centerZ - 5]} intensity={0.4} />

        {grid.cells.map((row, y) =>
          row.map((cell, x) => {
            const key      = `${x},${y}`;
            const isPath   = pathSet.has(key);
            const isTarget = targetSet.has(key);
            const rover    = roverMap.get(key);
            const fog      = !cell.revealed;
            const cell_z   = grid.height - 1 - y;
            // Fogged cells: flat dark block, no elevation extrusion, no terrain colour.
            // Dynamic terrain: dormant geysers and frost get distinct colours.
            let color = fog ? '#0d1117' : (TERRAIN_COLORS_3D[cell.terrain] ?? '#3a8aad');
            if (!fog && cell.terrain === 'geyser' && !cell.geyser_active) color = GEYSER_DORMANT_COLOR_3D;
            if (!fog && environment.is_night && (cell.terrain === 'flat' || cell.terrain === 'ice')) color = FROST_COLOR_3D;
            if (!fog && isTarget) color = '#d97706';
            if (!fog && isPath)   color = '#16a34a';
            return (
              <TerrainCell
                key={key}
                x={x} z={cell_z}
                gridX={x} gridY={y}
                elevation={fog ? 0 : (cell.elevation ?? 0)}
                hasSample={!fog && cell.has_sample}
                terrain={cell.terrain}
                color={color}
                isPath={!fog && isPath}
                isTarget={isTarget}
                fog={fog}
                rover={rover}
                onHover={handleHover}
                onHoverMove={handleHoverMove}
                onHoverEnd={handleHoverEnd}
              />
            );
          })
        )}

        {rovers.map(r => (
          <RoverMarker
            key={r.id}
            rover={r}
            elevation={grid.cells[r.y]?.[r.x]?.elevation ?? 0}
            gridHeight={grid.height}
            onHover={handleHover}
            onHoverMove={handleHoverMove}
            onHoverEnd={handleHoverEnd}
          />
        ))}
      </Canvas>

      {tooltip && <Tooltip info={tooltip} />}

      <div style={{
        position: 'absolute', bottom: 10, left: 12,
        fontSize: 11, color: 'rgba(255,255,255,0.5)',
        pointerEvents: 'none',
      }}>
        Left-drag to orbit · Scroll to zoom · Right-drag to pan
      </div>
    </div>
  );
}
