// Typed wrappers around the backend API. Shapes mirror the Pydantic
// models in cat_cam/api/, so drift shows up as a type error here.

export interface RuntimeSettings {
  confidence_day: number;
  confidence_night: number;
  night_brightness_threshold: number;
  interval_seconds: number;
  consecutive_frames_required: number;
  absence_reset_seconds: number;
  zone: [number, number, number, number] | null;
  snapshots_enabled: boolean;
  snapshot_retention_days: number;
  notifications_enabled: boolean;
}

export type SettingsPatch = Partial<Omit<RuntimeSettings, "zone">> & {
  zone?: [number, number, number, number];
  clear_zone?: boolean;
};

export interface DeployInfo {
  camera_device: string;
  camera_crop: [number, number, number, number] | null;
  yolo_model: string;
  class_name: string;
  ntfy_enabled: boolean;
  ntfy_server: string;
  ntfy_topic: string;
}

export interface Snapshot {
  id: string;
  taken_at: string;
  confidence: number | null;
  is_night: boolean | null;
}

export interface SnapshotPage {
  items: Snapshot[];
  total: number;
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = JSON.stringify((await res.json()).detail ?? detail);
    } catch {
      /* non-JSON error body */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  getConfig: () => request<RuntimeSettings>("/api/config"),

  patchConfig: (patch: SettingsPatch) =>
    request<RuntimeSettings>("/api/config", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    }),

  getDeployInfo: () => request<DeployInfo>("/api/deploy-info"),

  getLogs: () => request<{ lines: string[] }>("/api/logs"),

  listSnapshots: (limit = 60, offset = 0) =>
    request<SnapshotPage>(`/api/snapshots?limit=${limit}&offset=${offset}`),

  snapshotUrl: (id: string) => `/api/snapshots/${encodeURIComponent(id)}`,

  deleteSnapshot: (id: string) =>
    request<{ deleted: string }>(`/api/snapshots/${encodeURIComponent(id)}`, {
      method: "DELETE",
    }),
};
