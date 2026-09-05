import { useQuery } from '@tanstack/react-query';
import { commApi } from '@/services/api';

export function useCommStatus() {
  return useQuery({
    queryKey: ['comm-status'],
    queryFn: commApi.status,
    refetchInterval: 1000,   // windows can be as short as a few seconds
  });
}

export function useUplinkQueue(missionId: string) {
  return useQuery({
    queryKey: ['comm-queue', missionId],
    queryFn: () => commApi.queue(missionId),
    enabled: !!missionId,
    refetchInterval: 1500,
  });
}
