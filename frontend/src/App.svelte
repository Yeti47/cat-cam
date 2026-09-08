<script lang="ts">
  import { onMount } from "svelte";
  import { loadSettings, startStreams } from "./lib/stores";
  import DetectionAlert from "./components/DetectionAlert.svelte";
  import LiveView from "./views/LiveView.svelte";
  import ConfigView from "./views/ConfigView.svelte";
  import LogsView from "./views/LogsView.svelte";
  import SnapshotsView from "./views/SnapshotsView.svelte";

  type ViewId = "live" | "snapshots" | "config" | "logs";

  const views: { id: ViewId; label: string }[] = [
    { id: "live", label: "Live" },
    { id: "snapshots", label: "Snapshots" },
    { id: "config", label: "Config" },
    { id: "logs", label: "Logs" },
  ];

  function currentFromHash(): ViewId {
    const id = window.location.hash.replace(/^#\/?/, "") as ViewId;
    return views.some((v) => v.id === id) ? id : "live";
  }

  let view = $state<ViewId>(currentFromHash());
  let error = $state<string | null>(null);

  onMount(() => {
    const onHash = () => (view = currentFromHash());
    window.addEventListener("hashchange", onHash);

    loadSettings().catch((e) => (error = String(e)));
    const stop = startStreams();

    return () => {
      window.removeEventListener("hashchange", onHash);
      stop();
    };
  });
</script>

<!-- Plays the alert sound and drives the flash; lives at the app level so
     a detection still alerts while you're on the Config or Logs view. -->
<DetectionAlert />

<header>
  <h1>cat-cam</h1>
  <nav>
    {#each views as v (v.id)}
      <a href="#/{v.id}" class:active={view === v.id}>{v.label}</a>
    {/each}
  </nav>
</header>

{#if error}
  <p class="error">Could not reach the backend: {error}</p>
{/if}

<main>
  <!-- Kept mounted so the MJPEG connection isn't torn down and re-opened
       every time you visit another tab. -->
  <div class="view" class:hidden={view !== "live"}><LiveView /></div>
  {#if view === "snapshots"}<div class="view"><SnapshotsView /></div>{/if}
  {#if view === "config"}<div class="view"><ConfigView /></div>{/if}
  {#if view === "logs"}<div class="view"><LogsView /></div>{/if}
</main>

<style>
  header {
    display: flex;
    align-items: center;
    gap: 20px;
    padding: 10px 16px;
    border-bottom: 1px solid var(--border);
  }

  h1 {
    font-size: 16px;
    margin: 0;
  }

  nav {
    display: flex;
    gap: 4px;
  }

  nav a {
    color: var(--muted);
    text-decoration: none;
    padding: 5px 10px;
    border-radius: 5px;
    font-size: 13px;
  }

  nav a:hover {
    background: var(--panel);
    color: var(--text);
  }

  nav a.active {
    background: var(--panel);
    color: var(--text);
  }

  main {
    padding: 16px;
    /* Fills the space under the header; min-height:0 lets children shrink
       below their content size so a tall video can scale down to fit. */
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  .view {
    flex: 1;
    min-height: 0;
    overflow: auto;
  }

  .hidden {
    display: none;
  }

  .error {
    margin: 16px;
    padding: 10px 14px;
    border: 1px solid var(--error);
    border-radius: 6px;
    color: var(--error);
  }
</style>
