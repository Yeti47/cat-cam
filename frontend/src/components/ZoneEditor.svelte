<script lang="ts">
  // Draggable / resizable rectangle overlaid on the live feed.
  //
  // Everything is kept in normalized 0..1 coordinates -- the same space
  // the backend stores -- and rendered as percentages. Nothing measures
  // the element to draw, which matters because the MJPEG image has no
  // size until its first frame arrives: a pixel-based render computed at
  // mount would come out zero-sized and never correct itself (the zone
  // would look "reset" after every page reload). Percentages are also
  // automatically right after a window resize.
  //
  // Pixels appear only while dragging, where layout is necessarily settled.

  type Rect = { x: number; y: number; w: number; h: number };
  type Handle = "nw" | "ne" | "sw" | "se";
  type DragMode = "draw" | "move" | Handle;

  interface Props {
    zone: [number, number, number, number] | null;
    visible?: boolean;
    onchange: (zone: [number, number, number, number] | null) => void;
  }

  let { zone, visible = true, onchange }: Props = $props();

  // Ignore drags that are really just a click: 4px, as a fraction.
  const MIN_SIZE_PX = 4;

  let layer: HTMLDivElement;
  let dragMode: DragMode | null = null;
  let dragStart = { x: 0, y: 0 };
  let rectAtDragStart: Rect | null = null;
  // In-progress rectangle; null means "show whatever is saved".
  let draft = $state<Rect | null>(null);

  const clamp01 = (v: number) => Math.max(0, Math.min(1, v));

  let display = $derived.by((): Rect | null => {
    if (draft) return draft;
    if (!zone) return null;
    return { x: zone[0], y: zone[1], w: zone[2], h: zone[3] };
  });

  function bounds() {
    return layer.getBoundingClientRect();
  }

  /** Client coordinates -> normalized position within the layer. */
  function toNormalized(clientX: number, clientY: number) {
    const b = bounds();
    return {
      x: clamp01((clientX - b.left) / b.width),
      y: clamp01((clientY - b.top) / b.height),
    };
  }

  function commit(rect: Rect | null) {
    const b = bounds();
    if (!rect || rect.w * b.width < MIN_SIZE_PX || rect.h * b.height < MIN_SIZE_PX) {
      draft = null;
      return;
    }
    onchange([rect.x, rect.y, rect.w, rect.h]);
    draft = null;
  }

  function startDrag(event: MouseEvent, mode: DragMode) {
    event.preventDefault();
    event.stopPropagation();
    dragMode = mode;
    dragStart = { x: event.clientX, y: event.clientY };
    rectAtDragStart = display ? { ...display } : null;
    draft = rectAtDragStart;
  }

  function onLayerMouseDown(event: MouseEvent) {
    const start = toNormalized(event.clientX, event.clientY);
    dragMode = "draw";
    dragStart = { x: event.clientX, y: event.clientY };
    draft = { x: start.x, y: start.y, w: 0, h: 0 };
  }

  function onMouseMove(event: MouseEvent) {
    if (!dragMode) return;
    const b = bounds();
    // Deltas as fractions of the displayed size, so dragging tracks the
    // cursor regardless of how the feed is scaled.
    const dx = (event.clientX - dragStart.x) / b.width;
    const dy = (event.clientY - dragStart.y) / b.height;

    if (dragMode === "draw") {
      const from = toNormalized(dragStart.x, dragStart.y);
      const to = toNormalized(event.clientX, event.clientY);
      draft = {
        x: Math.min(from.x, to.x),
        y: Math.min(from.y, to.y),
        w: Math.abs(to.x - from.x),
        h: Math.abs(to.y - from.y),
      };
      return;
    }

    const s = rectAtDragStart;
    if (!s) return;

    if (dragMode === "move") {
      draft = {
        x: Math.max(0, Math.min(s.x + dx, 1 - s.w)),
        y: Math.max(0, Math.min(s.y + dy, 1 - s.h)),
        w: s.w,
        h: s.h,
      };
      return;
    }

    let { x, y, w, h } = s;
    if (dragMode.includes("n")) {
      y = s.y + dy;
      h = s.h - dy;
    }
    if (dragMode.includes("s")) h = s.h + dy;
    if (dragMode.includes("w")) {
      x = s.x + dx;
      w = s.w - dx;
    }
    if (dragMode.includes("e")) w = s.w + dx;
    // Dragging a handle past the opposite edge flips the rectangle.
    if (w < 0) {
      x += w;
      w = -w;
    }
    if (h < 0) {
      y += h;
      h = -h;
    }
    const nx = clamp01(x);
    const ny = clamp01(y);
    draft = { x: nx, y: ny, w: Math.min(w, 1 - nx), h: Math.min(h, 1 - ny) };
  }

  function onMouseUp() {
    if (!dragMode) return;
    dragMode = null;
    commit(draft);
  }
</script>

<svelte:window onmousemove={onMouseMove} onmouseup={onMouseUp} />

<div
  class="layer"
  class:hidden={!visible}
  bind:this={layer}
  onmousedown={onLayerMouseDown}
  role="presentation"
>
  {#if display}
    <div
      class="rect"
      style:left="{display.x * 100}%"
      style:top="{display.y * 100}%"
      style:width="{display.w * 100}%"
      style:height="{display.h * 100}%"
    >
      <div class="body" onmousedown={(e) => startDrag(e, "move")} role="presentation"></div>
      {#each ["nw", "ne", "sw", "se"] as const as handle (handle)}
        <div
          class="handle {handle}"
          onmousedown={(e) => startDrag(e, handle)}
          role="presentation"
        ></div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .layer {
    position: absolute;
    inset: 0;
    cursor: crosshair;
  }

  .layer.hidden {
    visibility: hidden;
    pointer-events: none;
  }

  .rect {
    position: absolute;
    border: 2px dashed var(--accent);
    background: rgba(77, 163, 255, 0.12);
  }

  .body {
    position: absolute;
    inset: 0;
    cursor: move;
  }

  .handle {
    position: absolute;
    width: 12px;
    height: 12px;
    margin: -6px;
    background: var(--accent);
    border-radius: 2px;
  }

  .handle.nw {
    top: 0;
    left: 0;
    cursor: nwse-resize;
  }
  .handle.ne {
    top: 0;
    left: 100%;
    cursor: nesw-resize;
  }
  .handle.sw {
    top: 100%;
    left: 0;
    cursor: nesw-resize;
  }
  .handle.se {
    top: 100%;
    left: 100%;
    cursor: nwse-resize;
  }
</style>
