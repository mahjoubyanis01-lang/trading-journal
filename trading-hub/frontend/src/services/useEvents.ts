import { useEffect, useRef } from 'react';
import type { WsMessage } from '../types';
import { getToken } from './token';

type Listener = (msg: WsMessage) => void;

// A single shared WebSocket connection to /ws, with auto-reconnect.
// Components subscribe to event types; a "*" pattern matches everything and a
// trailing ".*" (e.g. "robot.*") matches a namespace prefix.
class EventBus {
  private ws: WebSocket | null = null;
  private listeners = new Set<{ patterns: string[]; fn: Listener }>();
  private reconnectTimer: number | null = null;
  private connected = false;

  private matches(patterns: string[], type: string): boolean {
    return patterns.some((p) => {
      if (p === '*') return true;
      if (p.endsWith('.*')) return type.startsWith(p.slice(0, -1));
      return p === type;
    });
  }

  private ensure() {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }
    try {
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const tok = getToken();
      const q = tok ? `?token=${encodeURIComponent(tok)}` : '';
      this.ws = new WebSocket(`${proto}://${window.location.host}/ws${q}`);
    } catch {
      this.scheduleReconnect();
      return;
    }
    this.ws.onopen = () => {
      this.connected = true;
    };
    this.ws.onmessage = (ev) => {
      let msg: WsMessage;
      try {
        msg = JSON.parse(ev.data);
      } catch {
        return;
      }
      if (!msg || typeof msg.type !== 'string') return;
      for (const l of this.listeners) {
        if (this.matches(l.patterns, msg.type)) {
          try {
            l.fn(msg);
          } catch {
            /* ignore listener errors */
          }
        }
      }
    };
    this.ws.onclose = () => {
      this.connected = false;
      this.scheduleReconnect();
    };
    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  private scheduleReconnect() {
    if (this.reconnectTimer != null) return;
    if (this.listeners.size === 0) return;
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      if (this.listeners.size > 0) this.ensure();
    }, 2000);
  }

  subscribe(patterns: string[], fn: Listener): () => void {
    const entry = { patterns, fn };
    this.listeners.add(entry);
    this.ensure();
    return () => {
      this.listeners.delete(entry);
      if (this.listeners.size === 0 && this.ws) {
        this.ws.close();
        this.ws = null;
      }
    };
  }

  isConnected() {
    return this.connected;
  }
}

export const eventBus = new EventBus();

/**
 * Subscribe to WS event types. The callback is held in a ref so callers can
 * pass an inline function without re-subscribing every render.
 */
export function useEvents(patterns: string[], onEvent: Listener) {
  const cb = useRef(onEvent);
  cb.current = onEvent;
  const key = patterns.join('|');
  useEffect(() => {
    const unsub = eventBus.subscribe(patterns, (msg) => cb.current(msg));
    return unsub;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
}
