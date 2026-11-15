import { useState, useEffect, useRef } from 'react';
import { TelemetryWebSocketMessage } from '../types';

export type ConnectionState = 'CONNECTING' | 'CONNECTED' | 'RECONNECTING' | 'DISCONNECTED';
export type TelemetryHealthState = 'LIVE' | 'DEGRADED' | 'DISCONNECTED';

export function useWebSocket(
  url: string = 'ws://127.0.0.1:8000/ws/telemetry',
  tenantId?: string
) {
  const [data, setData] = useState<TelemetryWebSocketMessage | null>(null);
  const [lastEvent, setLastEvent] = useState<any | null>(null);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [connectionState, setConnectionState] = useState<ConnectionState>('CONNECTING');
  const [healthStatus, setHealthStatus] = useState<TelemetryHealthState>('DISCONNECTED');
  const [lastEventAt, setLastEventAt] = useState<number>(0);

  const wsRef = useRef<WebSocket | null>(null);
  const currentTenantRef = useRef<string>(tenantId || '*');
  const retryDelayRef = useRef<number>(1000);
  const lastActivityRef = useRef<number>(0);
  const lastTelemetryAtRef = useRef<number>(0);

  useEffect(() => {
    currentTenantRef.current = tenantId || '*';
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      try {
        wsRef.current.send(JSON.stringify({ action: 'subscribe', tenant_id: currentTenantRef.current }));
      } catch (e) {}
    }
  }, [tenantId]);

  useEffect(() => {
    let reconnectTimer: any = null;
    let pingTimer: any = null;
    let healthCheckTimer: any = null;
    let isUnmounted = false;

    function connect() {
      if (isUnmounted) return;
      setConnectionState((prev) => (prev === 'CONNECTED' ? 'RECONNECTING' : 'CONNECTING'));
      try {
        const ws = new WebSocket(url);
        wsRef.current = ws;

        ws.onopen = () => {
          if (isUnmounted) return;
          setIsConnected(true);
          setConnectionState('CONNECTED');
          retryDelayRef.current = 1000; // Reset exponential backoff
          lastActivityRef.current = Date.now();

          try {
            ws.send(JSON.stringify({ action: 'subscribe', tenant_id: currentTenantRef.current }));
          } catch (e) {}
        };

        ws.onmessage = (event) => {
          if (isUnmounted) return;
          const now = Date.now();
          lastActivityRef.current = now;

          try {
            const parsed = JSON.parse(event.data);
            if (parsed.type === 'TELEMETRY_UPDATE') {
              setData(parsed);
            } else if (parsed.type === 'HEARTBEAT' || parsed.type === 'pong' || parsed.type === 'CONNECTION_ESTABLISHED') {
              // WebSocket connection keepalive
            } else if (parsed.event_id || parsed.tenant_id || parsed.service || parsed.message) {
              const activeFilter = currentTenantRef.current;
              // Enforce client-side tenant isolation if specific tenant is requested
              if (activeFilter !== '*' && parsed.tenant_id && parsed.tenant_id !== activeFilter) {
                return;
              }
              lastTelemetryAtRef.current = now;
              setLastEventAt(now);
              setLastEvent(parsed);
              setHealthStatus('LIVE');
            }
          } catch (e) {
            console.error('Error parsing WS message', e);
          }
        };

        ws.onclose = () => {
          if (isUnmounted) return;
          setIsConnected(false);
          setConnectionState('RECONNECTING');
          scheduleReconnect();
        };

        ws.onerror = () => {
          if (isUnmounted) return;
          setIsConnected(false);
          setConnectionState('RECONNECTING');
          try {
            ws.close();
          } catch (e) {}
        };
      } catch (err) {
        if (isUnmounted) return;
        setIsConnected(false);
        setConnectionState('RECONNECTING');
        scheduleReconnect();
      }
    }

    function scheduleReconnect() {
      if (isUnmounted) return;
      const delay = retryDelayRef.current;
      // Exponential backoff: 1s -> 2s -> 4s -> max 8s
      retryDelayRef.current = Math.min(delay * 2, 8000);
      reconnectTimer = setTimeout(connect, delay);
    }

    // Ping-pong heartbeat: send ping every 10 seconds
    pingTimer = setInterval(() => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        try {
          wsRef.current.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }));
        } catch (e) {}
      }
    }, 10000);

    // Health freshness evaluation: check every 2 seconds
    healthCheckTimer = setInterval(() => {
      if (isUnmounted) return;
      if (!lastTelemetryAtRef.current) {
        setHealthStatus('DISCONNECTED');
      } else {
        const timeSinceLastEvent = Date.now() - lastTelemetryAtRef.current;
        if (timeSinceLastEvent < 15000) {
          setHealthStatus('LIVE');
        } else if (timeSinceLastEvent < 45000) {
          setHealthStatus('DEGRADED');
        } else {
          setHealthStatus('DISCONNECTED');
        }
      }
    }, 2000);

    connect();

    return () => {
      isUnmounted = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (pingTimer) clearInterval(pingTimer);
      if (healthCheckTimer) clearInterval(healthCheckTimer);
      if (wsRef.current) {
        try {
          wsRef.current.close();
        } catch (e) {}
      }
    };
  }, [url]);

  return { data, lastEvent, isConnected, connectionState, healthStatus, lastEventAt };
}

