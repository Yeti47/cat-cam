// SSE subscriptions with automatic reconnect.
//
// Both streams are opened once for the whole app rather than per-view, so
// switching tabs doesn't drop the detection alert or lose log lines.

export interface DetectionEvent {
  type: "detection";
  confidence: number;
  is_night: boolean;
  snapshot: string | null;
}

const RECONNECT_MS = 3000;

function connect(url: string, onMessage: (data: string) => void): () => void {
  let source: EventSource | null = null;
  let timer: number | undefined;
  let closed = false;

  const open = () => {
    if (closed) return;
    source = new EventSource(url);
    source.onmessage = (e) => onMessage(e.data);
    source.onerror = () => {
      source?.close();
      source = null;
      // The server sends keep-alives, so an error here means a real drop.
      timer = window.setTimeout(open, RECONNECT_MS);
    };
  };

  open();

  return () => {
    closed = true;
    window.clearTimeout(timer);
    source?.close();
  };
}

export function subscribeDetections(handler: (event: DetectionEvent) => void): () => void {
  return connect("/events", (data) => {
    try {
      handler(JSON.parse(data) as DetectionEvent);
    } catch {
      /* ignore malformed frame */
    }
  });
}

export function subscribeLogs(handler: (line: string) => void): () => void {
  return connect("/logs/stream", (data) => {
    try {
      handler(JSON.parse(data) as string);
    } catch {
      /* ignore malformed frame */
    }
  });
}
