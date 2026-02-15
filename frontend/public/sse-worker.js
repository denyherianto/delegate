/**
 * SharedWorker: maintains a single SSE connection to /stream and
 * broadcasts events to all connected tabs via MessagePort.
 *
 * Protocol:
 *   Tab → Worker:  { type: "init" }           — register this tab
 *   Worker → Tab:  { type: "sse", data: ... }  — SSE event payload
 *   Worker → Tab:  { type: "status", connected: bool } — connection status
 *
 * Cleanup: dead ports are pruned on every broadcast (postMessage throws
 * on closed ports). When the last tab closes, the browser GCs the worker
 * and all its resources (including the EventSource).
 */

const ports = new Set();
let es = null;
let reconnectTimer = null;

function broadcast(msg) {
  for (const port of ports) {
    try {
      port.postMessage(msg);
    } catch (_) {
      // Port is dead (tab closed / navigated away) — remove it
      ports.delete(port);
    }
  }
}

function connect() {
  if (es) { try { es.close(); } catch (_) {} }
  es = new EventSource("/stream");

  es.onopen = () => {
    broadcast({ type: "status", connected: true });
  };

  es.onmessage = (evt) => {
    try {
      const data = JSON.parse(evt.data);
      broadcast({ type: "sse", data });
    } catch (_) {}
  };

  es.onerror = () => {
    broadcast({ type: "status", connected: false });
    // EventSource auto-reconnects, but if it closes permanently
    // we reconnect after a delay
    if (es.readyState === EventSource.CLOSED) {
      es = null;
      if (!reconnectTimer) {
        reconnectTimer = setTimeout(() => {
          reconnectTimer = null;
          if (ports.size > 0) connect();
        }, 3000);
      }
    }
  };
}

// Called when a new tab connects to this SharedWorker
self.onconnect = (e) => {
  const port = e.ports[0];
  ports.add(port);

  port.onmessage = (evt) => {
    if (evt.data && evt.data.type === "init") {
      // Start the SSE connection on first tab
      if (!es || es.readyState === EventSource.CLOSED) connect();
      port.postMessage({
        type: "status",
        connected: es && es.readyState === EventSource.OPEN,
      });
    }
  };

  port.start();
};
