<script lang="ts">
  import { settings, saveSettings, detectionTick, lastDetection } from "../lib/stores";
  import ZoneEditor from "../components/ZoneEditor.svelte";

  let showZone = $state(localStorage.getItem("catcam.showZone") !== "false");
  let flashing = $state(false);
  let status = $state("");
  let firstTick = true;

  // Flash the border on each detection.
  $effect(() => {
    $detectionTick;
    if (firstTick) {
      firstTick = false;
      return;
    }
    flashing = false;
    // Next frame, so the animation restarts even on back-to-back hits.
    requestAnimationFrame(() => (flashing = true));
    const timer = setTimeout(() => (flashing = false), 1800);
    return () => clearTimeout(timer);
  });

  function toggleZone() {
    showZone = !showZone;
    localStorage.setItem("catcam.showZone", String(showZone));
  }

  function flash(message: string) {
    status = message;
    setTimeout(() => (status = ""), 1500);
  }

  async function onZoneChange(zone: [number, number, number, number] | null) {
    if (!zone) return;
    await saveSettings({ zone });
    flash("zone saved");
  }

  async function clearZone() {
    await saveSettings({ clear_zone: true });
    flash("zone cleared");
  }
</script>

<div class="wrap">
  <div class="video" class:flashing>
    <img src="/stream.mjpg" alt="live feed" />
    <ZoneEditor zone={$settings?.zone ?? null} visible={showZone} onchange={onZoneChange} />
  </div>

  <div class="controls">
    <button class="secondary" onclick={toggleZone}>
      {showZone ? "Hide zone" : "Show zone"}
    </button>
    <button class="secondary" onclick={clearZone} disabled={!$settings?.zone}>Clear zone</button>
    <span class="muted">
      {#if status}
        {status}
      {:else if $settings?.zone}
        Detection limited to the marked area — drag to redraw, corners to resize.
      {:else}
        Drag on the feed to limit detection to part of the frame.
      {/if}
    </span>
  </div>

  {#if $lastDetection}
    <p class="muted last">
      Last detection: {($lastDetection.confidence * 100).toFixed(0)}% confidence{$lastDetection.is_night
        ? ", night mode"
        : ""}
    </p>
  {/if}
</div>

<style>
  .wrap {
    /* Centre the feed (and its controls) in whatever space is left. */
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 10px;
  }

  .video {
    position: relative;
    display: flex;
    border: 6px solid var(--border);
    border-radius: 6px;
    line-height: 0;
    max-width: 100%;
    /* Shrink to fit rather than overflow when the window is short --
       matters for a portrait phone stream. */
    min-height: 0;
    flex: 0 1 auto;
  }

  .video.flashing {
    animation: pulse 900ms ease-in-out 2;
  }

  @keyframes pulse {
    0%,
    100% {
      border-color: var(--border);
      box-shadow: none;
    }
    50% {
      border-color: var(--flash);
      box-shadow: 0 0 24px 4px var(--flash);
    }
  }

  img {
    display: block;
    max-width: 100%;
    /* Bounded in both axes so the frame always fits; object-fit keeps the
       aspect ratio, which the zone overlay depends on to stay aligned. */
    max-height: 100%;
    object-fit: contain;
    user-select: none;
  }

  .controls {
    display: flex;
    gap: 8px;
    align-items: center;
    font-size: 12px;
    flex-wrap: wrap;
    justify-content: center;
  }

  .last {
    margin: 0;
    font-size: 12px;
  }
</style>
