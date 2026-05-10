// ─── Domain types mirroring the backend Pydantic models ───────────────────

export type MissionStatus =
  | 'draft' | 'planned' | 'active' | 'paused'
  | 'completed' | 'failed' | 'aborted';

export type ObjectiveType =
  | 'reach_waypoint' | 'collect_sample' | 'survey_area'
  | 'investigate_anomaly' | 'return_to_base';

export interface Objective {
  id: string;
  type: ObjectiveType;
  target_x: number;
  target_y: number;
  description: string;
  priority: number;
  completed: boolean;
  completed_at: string | null;
}

export interface Mission {
  id: string;
  name: string;
  description: string;
  status: MissionStatus;
  environment_id: string;
  rover_ids: string[];
  objectives: Objective[];
  plan_id: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  progress_pct: number;
}

export type RoverState =
  | 'idle' | 'moving' | 'sampling' | 'charging'
  | 'stuck' | 'comm_lost' | 'error' | 'safe_mode';

export interface RoverSpec {
  max_battery: number;
  move_cost_per_cell: number;
  sample_cost: number;
  comm_cost: number;
  max_speed_cells_per_step: number;
}

export interface Rover {
  id: string;
  name: string;
  mission_id: string | null;
  state: RoverState;
  x: number;
  y: number;
  battery: number;
  battery_pct: number;
  spec: RoverSpec;
  path_history: [number, number][];
  samples_collected: number;
  steps_taken: number;
  total_distance: number;
  anomalies_encountered: number;
  created_at: string;
  // FPS fields (V4)
  anomaly_streak: number;
  safe_mode_reason: string | null;
}

export type TerrainType = 'flat' | 'rocky' | 'ice' | 'crater' | 'geyser' | 'crevasse';

export interface Cell {
  x: number;
  y: number;
  terrain: TerrainType;
  elevation: number;
  has_sample: boolean;
  is_visited: boolean;
  revealed: boolean;       // false = fog of war; terrain details hidden until rover enters sensor range
  geyser_active: boolean;  // true = erupting (hazardous); false = dormant (safe, high science value)
}

export interface Grid {
  width: number;
  height: number;
  cells: Cell[][];
}

export interface Environment {
  id: string;
  name: string;
  grid: Grid;
  temperature_k: number;
  pressure_pa: number;
  active_geysers: [number, number][];
  hazard_zones: [number, number][];
  // Dynamic terrain state (V4)
  sim_tick: number;
  is_night: boolean;
}

export type AnomalyType =
  | 'wheel_stuck' | 'comm_loss' | 'energy_spike' | 'sensor_fault'
  | 'geyser_proximity' | 'low_battery' | 'path_blocked' | 'unknown';

export type AnomalySeverity = 'low' | 'medium' | 'high' | 'critical';

export interface Anomaly {
  id: string;
  type: AnomalyType;
  severity: AnomalySeverity;
  mission_id: string;
  rover_id: string;
  x: number;
  y: number;
  description: string;
  detected_at: string;
  resolved_at: string | null;
  resolution: string;
}

export type PlannerType = 'manual' | 'astar' | 'rl' | 'multi_agent';

export interface PlanStep {
  sequence: number;
  command: {
    id: string;
    type: string;
    target_x: number | null;
    target_y: number | null;
    status: string;
  };
  estimated_battery_cost: number;
  rationale: string;
}

export interface Plan {
  id: string;
  mission_id: string;
  rover_id: string;
  planner: PlannerType;
  steps: PlanStep[];
  waypoints: [number, number][];
  estimated_total_battery: number;
  estimated_steps: number;
  total_commands: number;
  created_at: string;
  metadata: Record<string, unknown>;
}

export interface TelemetryEvent {
  id: string;
  type: string;
  mission_id: string;
  rover_id: string;
  timestamp: string;
  x: number | null;
  y: number | null;
  battery: number | null;
  battery_pct: number | null;
  payload: Record<string, unknown>;
}
