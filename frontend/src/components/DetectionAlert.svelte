<script lang="ts">
  import { onMount } from "svelte";
  import { detectionTick } from "../lib/stores";
  import detectSound from "../assets/detect.mp3";

  // Browsers block audio until the page has been interacted with, which
  // is exactly this app's situation: a tab opened on a second monitor and
  // left alone. Prime on the first gesture and surface a hint if a real
  // alert gets blocked before that happens.
  let audio: HTMLAudioElement;
  let blocked = $state(false);
  let muted = $state(localStorage.getItem("catcam.muted") === "true");

  function toggleMute() {
    muted = !muted;
    localStorage.setItem("catcam.muted", String(muted));
  }

  export function play() {
    if (muted) return;
    audio.currentTime = 0;
    audio.play().catch(() => (blocked = true));
  }

  onMount(() => {
    const prime = () => {
      audio
        .play()
        .then(() => {
          audio.pause();
          audio.currentTime = 0;
          blocked = false;
        })
        .catch(() => {
          /* still blocked; a later gesture may clear it */
        });
    };
    window.addEventListener("click", prime, { once: true });
    window.addEventListener("keydown", prime, { once: true });

    // Skip the initial store value; only react to genuine new detections.
    let first = true;
    const unsubscribe = detectionTick.subscribe(() => {
      if (first) {
        first = false;
        return;
      }
      play();
    });

    return () => {
      window.removeEventListener("click", prime);
      window.removeEventListener("keydown", prime);
      unsubscribe();
    };
  });
</script>

<audio bind:this={audio} src={detectSound} preload="auto"></audio>

<div class="controls">
  <button class="secondary" onclick={toggleMute} title="Toggle alert sound">
    {muted ? "🔇" : "🔊"}
  </button>
  {#if blocked && !muted}
    <span class="hint">Click the page once to enable sound</span>
  {/if}
</div>

<style>
  .controls {
    position: fixed;
    top: 8px;
    right: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
    z-index: 10;
  }

  .hint {
    color: var(--warn);
    font-size: 12px;
  }
</style>
