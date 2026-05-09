import axios from 'axios';
import type {
  Mission, Rover, Environment, Plan, Anomaly, TelemetryEvent,
} from '@/types';

const http = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
});

// ─── Missions ────────────────────────────────────────────────────────────────

export interface CreateMissionPayload {
  name: string;
  description?: string;
  environment_id?: string;
  grid_width?: number;
  grid_height?: number;
  objectives?: {
    type: string;
    target_x: number;
    target_y: number;
    description?: string;
    priority?: number;
  }[];
}

export const missionsApi = {
  list: () => http.get<Mission[]>('/missions/').then(r => r.data),
  get: (id: string) => http.get<Mission>(`/missions/${id}`).then(r => r.data),
  create: (payload: CreateMissionPayload) =>
    http.post<Mission>('/missions/', payload).then(r => r.data),
  update: (id: string, payload: Partial<Pick<Mission, 'name' | 'description' | 'status'>>) =>
    http.patch<Mission>(`/missions/${id}`, payload).then(r => r.data),
  delete: (id: string) => http.delete(`/missions/${id}`),
  start: (id: string) => http.post<Mission>(`/missions/${id}/start`).then(r => r.data),
  complete: (id: string) => http.post<Mission>(`/missions/${id}/complete`).then(r => r.data),
  getEnvironment: (id: string) =>
    http.get<Environment>(`/missions/${id}/environment`).then(r => r.data),
};

// ─── Planning ────────────────────────────────────────────────────────────────

export const planningApi = {
  autoPlan: (payload: { mission_id: string; rover_id: string; start_x?: number; start_y?: number }) =>
    http.post<Plan>('/planning/auto', payload).then(r => r.data),
  manualPlan: (payload: { mission_id: string; rover_id: string; waypoints: [number, number][] }) =>
    http.post<Plan>('/planning/manual', payload).then(r => r.data),
  getPlan: (id: string) => http.get<Plan>(`/planning/${id}`).then(r => r.data),
  getMissionPlan: (missionId: string) =>
    http.get<Plan>(`/planning/mission/${missionId}`).then(r => r.data),
};

// ─── Simulation ──────────────────────────────────────────────────────────────

export const simulationApi = {
  spawnRover: (payload: { mission_id: string; name: string; start_x?: number; start_y?: number }) =>
    http.post<Rover>('/simulation/rovers', payload).then(r => r.data),
  listRovers: (mission_id?: string) =>
    http.get<Rover[]>('/simulation/rovers', { params: { mission_id } }).then(r => r.data),
  getRover: (id: string) => http.get<Rover>(`/simulation/rovers/${id}`).then(r => r.data),
  runPlan: (payload: { mission_id: string; plan_id: string }) =>
    http.post('/simulation/run', payload).then(r => r.data),
  stop: (missionId: string) =>
    http.post(`/simulation/${missionId}/stop`).then(r => r.data),
  status: (missionId: string) =>
    http.get(`/simulation/${missionId}/status`).then(r => r.data),
};

// ─── Telemetry ───────────────────────────────────────────────────────────────

export const telemetryApi = {
  getEvents: (missionId: string, limit = 100) =>
    http.get<TelemetryEvent[]>(`/telemetry/events/${missionId}`, { params: { limit } }).then(r => r.data),
  getAnomalies: (missionId?: string) => {
    const url = missionId ? `/telemetry/anomalies/${missionId}` : '/telemetry/anomalies';
    return http.get<Anomaly[]>(url).then(r => r.data);
  },
  resolveAnomaly: (anomalyId: string, resolution = 'ignored') =>
    http.patch<Anomaly>(`/telemetry/anomalies/${anomalyId}/resolve`, { resolution }).then(r => r.data),
  dismissAll: (missionId: string) =>
    http.post<Anomaly[]>(`/telemetry/anomalies/${missionId}/dismiss-all`).then(r => r.data),
};

// ─── Explainability ──────────────────────────────────────────────────────────

export const explainApi = {
  plan: (planId: string) => http.get(`/explain/plan/${planId}`).then(r => r.data),
  mission: (missionId: string) => http.get(`/explain/mission/${missionId}`).then(r => r.data),
  anomaly: (anomalyId: string) => http.get(`/explain/anomaly/${anomalyId}`).then(r => r.data),
};
