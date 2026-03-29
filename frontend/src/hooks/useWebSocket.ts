import { useEffect, useRef } from "react";
import { useSimulationStore } from "../stores/simulationStore";

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const store = useSimulationStore;

  useEffect(() => {
    let cancelled = false;

    const connect = () => {
      if (cancelled) return;
      const wsUrl =
        import.meta.env.VITE_WS_URL ||
        `ws://${window.location.hostname}:8000/ws`;

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        store.getState().setConnected(true);
      };

      ws.onclose = () => {
        store.getState().setConnected(false);
        if (!cancelled) {
          reconnectTimerRef.current = window.setTimeout(connect, 2000);
        }
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);

          if (msg.type === "world_state") {
            store.getState().initFromWorldState(msg.data);
          } else if (msg.type === "tick") {
            store.getState().updateFromTick(msg.data);
          } else if (msg.type === "agent_detail") {
            store.getState().setAgentDetail(msg.data);
          } else if (msg.type === "dashboard_data") {
            store.getState().setDashboardData(msg.data);
          } else if (msg.type === "autobiography") {
            store.getState().setAutobiography(msg.data);
          } else if (msg.type === "world_object_delta") {
            const delta = msg.data;
            if (delta.created && delta.created.length > 0) {
              store.getState().addWorldObjects(delta.created);
            }
            if (delta.destroyed && delta.destroyed.length > 0) {
              store.getState().removeWorldObjects(delta.destroyed);
            }
            if (delta.updated) {
              for (const obj of delta.updated) {
                store.getState().updateWorldObject(obj);
              }
            }
          } else if (msg.type === "action_result") {
            store.getState().addActionResult(msg.data);
          } else if (msg.type === "innovation_event") {
            store.getState().addInnovation(msg.data);
          } else if (msg.type === "pattern_event") {
            store.getState().addPattern(msg.data);
          } else if (msg.type === "timeline_event") {
            store.getState().addTimelineEvent(msg.data);
          }
        } catch (e) {
          console.error("Failed to parse WS message:", e);
        }
      };
    };

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
      }
      wsRef.current?.close();
    };
  }, []);

  return {
    send: (msg: object) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify(msg));
      }
    },
    ws: wsRef,
  };
}
