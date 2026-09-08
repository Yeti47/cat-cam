<script lang="ts">
  import { logs } from "../lib/stores";

  let container: HTMLDivElement;
  let follow = $state(true);
  let filter = $state("");

  let visible = $derived(
    filter ? $logs.filter((l) => l.toLowerCase().includes(filter.toLowerCase())) : $logs,
  );

  function levelOf(line: string): string {
    const match = line.match(/\s(DEBUG|INFO|WARNING|ERROR|CRITICAL)\s/);
    return match ? match[1].toLowerCase() : "";
  }

  // Stick to the bottom as lines arrive, unless the user scrolled away.
  $effect(() => {
    visible;
    if (follow && container) {
      requestAnimationFrame(() => (container.scrollTop = container.scrollHeight));
    }
  });

  function onScroll() {
    const gap = container.scrollHeight - container.scrollTop - container.clientHeight;
    follow = gap < 40;
  }
</script>

<div class="panel">
  <div class="bar">
    <input type="text" placeholder="Filter…" bind:value={filter} />
    <label class="follow">
      <input type="checkbox" bind:checked={follow} />
      <span>Follow</span>
    </label>
    <span class="muted">{visible.length} / {$logs.length} lines</span>
  </div>

  <div class="lines" bind:this={container} onscroll={onScroll}>
    {#each visible as line, i (i)}
      <div class="line {levelOf(line)}">{line}</div>
    {:else}
      <div class="muted">No log lines yet.</div>
    {/each}
  </div>
</div>

<style>
  .bar {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 10px;
    font-size: 12px;
  }

  .bar input[type="text"] {
    flex: 1;
    max-width: 320px;
  }

  .follow {
    display: flex;
    align-items: center;
    gap: 5px;
  }

  .lines {
    height: min(65vh, 620px);
    overflow-y: auto;
    font: 12px/1.5 ui-monospace, monospace;
    white-space: pre-wrap;
    word-break: break-word;
  }

  .line.warning {
    color: var(--warn);
  }

  .line.error,
  .line.critical {
    color: var(--error);
  }
</style>
