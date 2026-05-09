import { useEffect, useRef } from 'react';
import { useMissionStore } from '@/store/missionStore';

const WS_BASE = `ws://${window.location.host}/api/v1/telemetry/ws`;

export function useTelemetrySocket(missionId: string | null) {
  const wsRef = useRef<WebSocket | null>(null);
  const { appendTelemetry, updateRover, addAnomaly } = useMissionStore();

  useEffect(() => {
    if (!missionId) return;

    const ws = new WebSocket(`${WS_BASE}/${missionId}`);
    wsRef.current = ws;

    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data as string);
        if (msg.type === 'ping') return;

        if (msg.type === 'telemetry' || msg.type === 'history') {
          const data = msg.data;
          if (data?.rover_id) {
            appendTelemetry(data.rover_id, data);
          }
        }
        if (msg.type === 'anomaly' && msg.data) {
          addAnomaly(msg.data);
        }
      } catch {
        // ignore parse errors
      }
    };

    ws.onerror = () => { /* silently reconnect */ };

    ws.onclose = () => {
      // Simple reconnect after 3s
      setTimeout(() => {
        if (wsRef.current === ws) {
          wsRef.current = null;
        }
      }, 3000);
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [missionId, appendTelemetry, updateRover, addAnomaly]);

  return wsRef;
}
