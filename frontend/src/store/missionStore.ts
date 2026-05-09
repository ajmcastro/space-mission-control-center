import { create } from 'zustand';
import type { Rover, Anomaly, TelemetryEvent, Environment } from '@/types';

interface MissionState {
  // Selected mission context
  activeMissionId: string | null;
  setActiveMissionId: (id: string | null) => void;

  // Cached environment per mission
  environments: Record<string, Environment>;
  setEnvironment: (missionId: string, env: Environment) => void;

  // Live rover state (updated by WebSocket)
  liveRovers: Record<string, Rover>;
  updateRover: (rover: Rover) => void;

  // Anomaly feed (last N)
  anomalies: Anomaly[];
  addAnomaly: (a: Anomaly) => void;

  // Telemetry ring buffer per rover
  telemetryBuffer: Record<string, TelemetryEvent[]>;
  appendTelemetry: (roverId: string, event: TelemetryEvent) => void;

  // UI state
  sidebarOpen: boolean;
  toggleSidebar: () => void;
}

const MAX_TELEMETRY_BUFFER = 200;
const MAX_ANOMALIES = 50;

export const useMissionStore = create<MissionState>((set) => ({
  activeMissionId: null,
  setActiveMissionId: (id) => set({ activeMissionId: id }),

  environments: {},
  setEnvironment: (missionId, env) =>
    set((s) => ({ environments: { ...s.environments, [missionId]: env } })),

  liveRovers: {},
  updateRover: (rover) =>
    set((s) => ({ liveRovers: { ...s.liveRovers, [rover.id]: rover } })),

  anomalies: [],
  addAnomaly: (a) =>
    set((s) => ({
      anomalies: [a, ...s.anomalies].slice(0, MAX_ANOMALIES),
    })),

  telemetryBuffer: {},
  appendTelemetry: (roverId, event) =>
    set((s) => {
      const existing = s.telemetryBuffer[roverId] ?? [];
      return {
        telemetryBuffer: {
          ...s.telemetryBuffer,
          [roverId]: [...existing, event].slice(-MAX_TELEMETRY_BUFFER),
        },
      };
    }),

  sidebarOpen: true,
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
}));
