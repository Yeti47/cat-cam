<script lang="ts">
  import { onMount } from "svelte";
  import { api, type Snapshot } from "../lib/api";
  import { detectionTick } from "../lib/stores";

  const PAGE = 60;

  let items = $state<Snapshot[]>([]);
  let total = $state(0);
  let loading = $state(true);
  let error = $state("");
  let selected = $state<Snapshot | null>(null);

  async function load(reset = true) {
    try {
      const page = await api.listSnapshots(PAGE, reset ? 0 : items.length);
      items = reset ? page.items : [...items, ...page.items];
      total = page.total;
      error = "";
    } catch (e) {
      error = String(e);
    } finally {
      loading = false;
    }
  }

  onMount(() => load());

  // A new detection means a new snapshot; refresh so the gallery stays current.
  let first = true;
  $effect(() => {
    $detectionTick;
    if (first) {
      first = false;
      return;
    }
    load();
  });

  async function remove(snapshot: Snapshot) {
    try {
      await api.deleteSnapshot(snapshot.id);
      items = items.filter((i) => i.id !== snapshot.id);
      total -= 1;
      if (selected?.id === snapshot.id) selected = null;
    } catch (e) {
      error = String(e);
    }
  }

  const when = (iso: string) => new Date(iso).toLocaleString();
</script>

{#if error}
  <p class="err">{error}</p>
{/if}

{#if loading}
  <p class="muted">Loading snapshots…</p>
{:else if items.length === 0}
  <p class="muted">No snapshots yet. They appear here when a cat is detected.</p>
{:else}
  <p class="muted count">{items.length} of {total}</p>

  <div class="grid">
    {#each items as item (item.id)}
      <figure class="card">
        <button class="thumb" onclick={() => (selected = item)} title="View full size">
          <img src={api.snapshotUrl(item.id)} alt="Detection at {when(item.taken_at)}" loading="lazy" />
        </button>
        <figcaption>
          <span>{when(item.taken_at)}</span>
          <span class="meta">
            {#if item.confidence !== null}
              {(item.confidence * 100).toFixed(0)}%{item.is_night ? " · night" : ""}
            {:else}
              <span class="muted">—</span>
            {/if}
            <button class="danger del" onclick={() => remove(item)} title="Delete">✕</button>
          </span>
        </figcaption>
      </figure>
    {/each}
  </div>

  {#if items.length < total}
    <button class="secondary more" onclick={() => load(false)}>Load more</button>
  {/if}
{/if}

{#if selected}
  <div
    class="lightbox"
    onclick={() => (selected = null)}
    onkeydown={(e) => e.key === "Escape" && (selected = null)}
    role="button"
    tabindex="-1"
  >
    <img src={api.snapshotUrl(selected.id)} alt="Detection at {when(selected.taken_at)}" />
    <p>{when(selected.taken_at)}</p>
  </div>
{/if}

<style>
  .count {
    font-size: 12px;
    margin: 0 0 10px;
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 12px;
  }

  .card {
    margin: 0;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
  }

  .thumb {
    display: block;
    width: 100%;
    padding: 0;
    border: none;
    background: none;
    cursor: zoom-in;
    line-height: 0;
  }

  .thumb img {
    width: 100%;
    aspect-ratio: 4 / 3;
    object-fit: cover;
  }

  figcaption {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    padding: 7px 9px;
    font-size: 12px;
  }

  .meta {
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--muted);
  }

  .del {
    padding: 1px 6px;
    font-size: 11px;
    line-height: 1.4;
  }

  .more {
    margin-top: 14px;
  }

  .lightbox {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.85);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 10px;
    cursor: zoom-out;
    z-index: 20;
    border: none;
  }

  .lightbox img {
    max-width: 92vw;
    max-height: 82vh;
    object-fit: contain;
  }

  .lightbox p {
    color: var(--muted);
    font-size: 12px;
    margin: 0;
  }

  .err {
    color: var(--error);
  }
</style>
