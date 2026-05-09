import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { missionsApi, planningApi, simulationApi, type CreateMissionPayload } from '@/services/api';
import type { Mission } from '@/types';

export const MISSIONS_KEY = ['missions'];
export const missionKey = (id: string) => ['missions', id];
export const envKey = (id: string) => ['missions', id, 'environment'];
export const planKey = (id: string) => ['plans', id];

// ─── Queries ─────────────────────────────────────────────────────────────────

export function useMissions() {
  return useQuery({ queryKey: MISSIONS_KEY, queryFn: missionsApi.list, refetchInterval: 5000 });
}

export function useMission(id: string) {
  return useQuery({
    queryKey: missionKey(id),
    queryFn: () => missionsApi.get(id),
    enabled: !!id,
    refetchInterval: 3000,
  });
}

export function useMissionEnvironment(missionId: string) {
  return useQuery({
    queryKey: envKey(missionId),
    queryFn: () => missionsApi.getEnvironment(missionId),
    enabled: !!missionId,
    staleTime: Infinity, // environment is static per mission
  });
}

export function useMissionPlan(missionId: string, planId?: string | null) {
  return useQuery({
    queryKey: planKey(planId ?? missionId),
    queryFn: () =>
      planId ? planningApi.getPlan(planId) : planningApi.getMissionPlan(missionId),
    enabled: !!planId,
  });
}

export function useRovers(missionId?: string) {
  return useQuery({
    queryKey: ['rovers', missionId],
    queryFn: () => simulationApi.listRovers(missionId),
    refetchInterval: 2000,
  });
}

// ─── Mutations ───────────────────────────────────────────────────────────────

export function useCreateMission() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateMissionPayload) => missionsApi.create(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: MISSIONS_KEY }),
  });
}

export function useDeleteMission() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => missionsApi.delete(id),
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: MISSIONS_KEY });
      qc.removeQueries({ queryKey: missionKey(id) });
    },
  });
}

export function useUpdateMission() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<Pick<Mission, 'name' | 'description'>> }) =>
      missionsApi.update(id, payload),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: MISSIONS_KEY });
      qc.setQueryData(missionKey(data.id), data);
    },
  });
}

export function useStartMission() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => missionsApi.start(id),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: MISSIONS_KEY });
      qc.invalidateQueries({ queryKey: missionKey(data.id) });
    },
  });
}

export function useSpawnRover() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { mission_id: string; name: string; start_x?: number; start_y?: number }) =>
      simulationApi.spawnRover(payload),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['rovers', vars.mission_id] });
    },
  });
}

export function useAutoPlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { mission_id: string; rover_id: string }) =>
      planningApi.autoPlan(payload),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: missionKey(data.mission_id) });
      qc.invalidateQueries({ queryKey: planKey(data.id) });
    },
  });
}

export function useRunPlan() {
  return useMutation({
    mutationFn: (payload: { mission_id: string; plan_id: string }) =>
      simulationApi.runPlan(payload),
  });
}
