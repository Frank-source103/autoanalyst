import { useEffect, useRef, useState, useCallback } from 'react';
import { AgentEvent } from '../types';

interface UseWebSocketOptions {
  runId: string | null;
  lastSeq: number;
  onEvent: (event: AgentEvent) => void;
}

export function useWebSocket({ runId, lastSeq, onEvent }: UseWebSocketOptions) {
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const lastSeqRef = useRef<number>(lastSeq);

  useEffect(() => {
    lastSeqRef.current = lastSeq;
  }, [lastSeq]);

  const connect = useCallback(() => {
    if (!runId) return;

    // Connect directly to Railway WebSocket when deployed remotely, or use localhost in development
    const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
    const defaultRemoteHost = 'autoanalyst-production.up.railway.app';
    const host = (import.meta.env.VITE_WS_HOST as string) || (isLocal ? window.location.host : defaultRemoteHost);
    const protocol = (window.location.protocol === 'https:' || !isLocal) ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${host}/ws/runs/${runId}?last_seq=${lastSeqRef.current}`;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data && typeof data.seq === 'number') {
            onEvent(data as AgentEvent);
          }
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e);
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        // Automatic reconnection attempt with delay
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect();
        }, 2000);
      };

      ws.onerror = (err) => {
        console.warn('WebSocket encountered error:', err);
        ws.close();
      };
    } catch (err) {
      console.error('Failed to create WebSocket:', err);
    }
  }, [runId, onEvent]);

  useEffect(() => {
    connect();

    // Heartbeat ping interval
    const pingInterval = window.setInterval(() => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ping' }));
      }
    }, 15000);

    return () => {
      window.clearInterval(pingInterval);
      if (reconnectTimeoutRef.current) {
        window.clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  return { isConnected };
}
