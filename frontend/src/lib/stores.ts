import { writable, type Writable } from "svelte/store";
import { api, type RuntimeSettings } from "./api";
import { subscribeDetections, subscribeLogs, type DetectionEvent } from "./events";

const MAX_LOG_LINES = 1000;

/** Current runtime settings, kept in sync with the backend. */
export const settings: Writable<RuntimeSettings | null> = writable(null);

/** Rolling log buffer, seeded from the backend's ring buffer then tailed. */
export const logs: Writable<string[]> = writable([]);

/** Most recent detection, used to drive the alert flash and sound. */
export const lastDetection: Writable<DetectionEvent | null> = writable(null);

/** Bumped on every detection so views can react even to repeat events. */
export const detectionTick: Writable<number> = writable(0);

export async function loadSettings(): Promise<void> {
  settings.set(await api.getConfig());
}

export async function saveSettings(patch: Parameters<typeof api.patchConfig>[0]): Promise<void> {
  settings.set(await api.patchConfig(patch));
}

/** Opens the app-wide SSE subscriptions. Returns a teardown function. */
export function startStreams(): () => void {
  api
    .getLogs()
    .then(({ lines }) => logs.set(lines.slice(-MAX_LOG_LINES)))
    .catch(() => {
      /* logs are best-effort */
    });

  const stopLogs = subscribeLogs((line) => {
    logs.update((current) => {
      const next = [...current, line];
      return next.length > MAX_LOG_LINES ? next.slice(-MAX_LOG_LINES) : next;
    });
  });

  const stopDetections = subscribeDetections((event) => {
    lastDetection.set(event);
    detectionTick.update((n) => n + 1);
  });

  return () => {
    stopLogs();
    stopDetections();
  };
}
