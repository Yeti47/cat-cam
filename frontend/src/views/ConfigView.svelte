<script lang="ts">
  import { onMount } from "svelte";
  import { settings, saveSettings } from "../lib/stores";
  import { api, type DeployInfo, type RuntimeSettings } from "../lib/api";

  let deploy = $state<DeployInfo | null>(null);
  let status = $state("");
  let error = $state("");

  onMount(() => {
    api.getDeployInfo().then((d) => (deploy = d)).catch(() => {});
  });

  async function update<K extends keyof RuntimeSettings>(key: K, value: RuntimeSettings[K]) {
    error = "";
    try {
      await saveSettings({ [key]: value } as never);
      status = "saved";
      setTimeout(() => (status = ""), 1200);
    } catch (e) {
      error = String(e);
    }
  }

  // Commit on change/blur rather than on every keystroke, so a half-typed
  // number never reaches the detector.
  const num = (e: Event) => Number((e.currentTarget as HTMLInputElement).value);
  const checked = (e: Event) => (e.currentTarget as HTMLInputElement).checked;
</script>

{#if $settings}
  <div class="grid">
    <section class="panel">
      <h2>Detection</h2>

      <label class="field">
        <span class="name">Confidence — day <b>{$settings.confidence_day.toFixed(2)}</b></span>
        <input
          type="range"
          min="0"
          max="1"
          step="0.01"
          value={$settings.confidence_day}
          onchange={(e) => update("confidence_day", num(e))}
        />
        <span class="help">Threshold used in normal, bright conditions.</span>
      </label>

      <label class="field">
        <span class="name">Confidence — night <b>{$settings.confidence_night.toFixed(2)}</b></span>
        <input
          type="range"
          min="0"
          max="1"
          step="0.01"
          value={$settings.confidence_night}
          onchange={(e) => update("confidence_night", num(e))}
        />
        <span class="help">
          Used once the scene is judged dark. Lower is more sensitive but more prone to false
          positives — worth lowering if a dark-coloured cat gets missed at night.
        </span>
      </label>

      <label class="field">
        <span class="name">Night brightness threshold</span>
        <input
          type="number"
          min="0"
          max="255"
          step="1"
          value={$settings.night_brightness_threshold}
          onchange={(e) => update("night_brightness_threshold", num(e))}
        />
        <span class="help">
          Mean pixel brightness (0–255) below which night mode kicks in: contrast enhancement plus
          the night threshold above. The average is taken <em>over the detection zone</em>, so a
          tight zone around the door stops a bright indoor floor from skewing it upward and keeping
          night mode from ever triggering.
        </span>
      </label>

      <label class="field">
        <span class="name">Detection interval (s)</span>
        <input
          type="number"
          min="0.1"
          max="60"
          step="0.1"
          value={$settings.interval_seconds}
          onchange={(e) => update("interval_seconds", num(e))}
        />
        <span class="help">
          How often inference runs. The live feed is captured faster than this regardless.
        </span>
      </label>

      <label class="field">
        <span class="name">Consecutive frames required</span>
        <input
          type="number"
          min="1"
          max="30"
          step="1"
          value={$settings.consecutive_frames_required}
          onchange={(e) => update("consecutive_frames_required", num(e))}
        />
        <span class="help">
          Detections in a row before alerting. Raise if single bad frames trigger false alarms;
          lower for faster alerts.
        </span>
      </label>

      <label class="field">
        <span class="name">Absence reset (s)</span>
        <input
          type="number"
          min="0"
          step="1"
          value={$settings.absence_reset_seconds}
          onchange={(e) => update("absence_reset_seconds", num(e))}
        />
        <span class="help">
          Quiet period with no detection before re-arming, so a fresh arrival notifies again. There
          is no other cooldown.
        </span>
      </label>
    </section>

    <div class="column">
      <section class="panel">
        <h2>Notifications &amp; snapshots</h2>

        <label class="row">
          <input
            type="checkbox"
            checked={$settings.notifications_enabled}
            onchange={(e) => update("notifications_enabled", checked(e))}
          />
          <span>Send push notifications</span>
        </label>

        <label class="row">
          <input
            type="checkbox"
            checked={$settings.snapshots_enabled}
            onchange={(e) => update("snapshots_enabled", checked(e))}
          />
          <span>Save snapshots</span>
        </label>

        <label class="field">
          <span class="name">Snapshot retention (days)</span>
          <input
            type="number"
            min="1"
            max="365"
            step="1"
            value={$settings.snapshot_retention_days}
            onchange={(e) => update("snapshot_retention_days", num(e))}
          />
          <span class="help">Older snapshots are deleted automatically.</span>
        </label>
      </section>

      {#if deploy}
        <section class="panel">
          <h2>Deployment (read-only)</h2>
          <p class="help">
            Set from the environment at startup — change these in <code>.env</code> and restart.
          </p>
          <dl>
            <dt>Camera</dt>
            <dd>{deploy.camera_device}</dd>
            <dt>Crop</dt>
            <dd>{deploy.camera_crop ? deploy.camera_crop.join(", ") : "none"}</dd>
            <dt>Model</dt>
            <dd>{deploy.yolo_model} ({deploy.class_name})</dd>
            <dt>ntfy</dt>
            <dd>{deploy.ntfy_enabled ? `${deploy.ntfy_server} → ${deploy.ntfy_topic}` : "disabled"}</dd>
          </dl>
        </section>
      {/if}
    </div>
  </div>

  <p class="status" class:error={!!error}>{error || status}</p>
{:else}
  <p class="muted">Loading settings…</p>
{/if}

<style>
  .grid {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    gap: 16px;
    align-items: start;
    max-width: 1100px;
  }

  @media (max-width: 860px) {
    .grid {
      grid-template-columns: 1fr;
    }
  }

  .column {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .field {
    display: block;
    margin-bottom: 16px;
  }

  .name {
    display: block;
    margin-bottom: 4px;
  }

  .help {
    display: block;
    color: var(--muted);
    font-size: 12px;
    margin-top: 4px;
  }

  input[type="range"] {
    width: 100%;
  }

  .row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 10px;
  }

  dl {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 4px 12px;
    margin: 0;
    font-size: 13px;
  }

  dt {
    color: var(--muted);
  }

  dd {
    margin: 0;
    word-break: break-all;
  }

  .status {
    height: 1em;
    color: var(--ok);
    font-size: 12px;
  }

  .status.error {
    color: var(--error);
  }
</style>
