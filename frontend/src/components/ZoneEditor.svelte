<script lang="ts">
  // Draggable / resizable rectangle overlaid on the live feed.
  //
  // Works in normalized 0..1 coordinates so the saved zone is independent
  // of the displayed image size, and converts to/from pixels only for
  // rendering and mouse math.

  type Rect = { x: number; y: number; w: number; h: number };
  type Handle = "nw" | "ne" | "sw" | "se";
  type DragMode = "draw" | "move" | Handle;

  interface Props {
    zone: [number, number, number, number] | null;
    visible?: boolean;
    onchange: (zone: [number, number, number, number] | null) => void;
  }

  let { zone, visible = true, onchange }: Props = $props();

  let layer: HTMLDivElement;
  let dragMode: DragMode | null = null;
  let dragStart = { x: 0, y: 0 };
  let rectAtDragStart: Rect | null = null;
  // Pixel rect during a drag; null means "show the saved zone".
  let draft = $state<Rect | null>(null);

  const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));

  function bounds() {
    return layer.getBoundingClientRect();
  }

  // What to render: the in-progress draft, else the saved zone scaled up.
  let display = $derived.by((): Rect | null => {
    if (draft) return draft;
    if (!zone || !layer) return null;
    const b = layer.getBoundingClientRect();
    return { x: zone[0] * b.width, y: zone[1] * b.height, w: zone[2] * b.width, h: zone[3] * b.height };
  });

  function commit(rect: Rect | null) {
    if (!rect || rect.w < 4 || rect.h < 4) {
      draft = null;
      return;
    }
    const b = bounds();
    onchange([rect.x / b.width, rect.y / b.height, rect.w / b.width, rect.h / b.height]);
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
    const b = bounds();
    const x = clamp(event.clientX - b.left, 0, b.width);
    const y = clamp(event.clientY - b.top, 0, b.height);
    dragMode = "draw";
    dragStart = { x: event.clientX, y: event.clientY };
    draft = { x, y, w: 0, h: 0 };
  }

  function onMouseMove(event: MouseEvent) {
    if (!dragMode) return;
    const b = bounds();
    const dx = event.clientX - dragStart.x;
    const dy = event.clientY - dragStart.y;

    if (dragMode === "draw") {
      const x0 = clamp(dragStart.x - b.left, 0, b.width);
      const y0 = clamp(dragStart.y - b.top, 0, b.height);
      const x1 = clamp(event.clientX - b.left, 0, b.width);
      const y1 = clamp(event.clientY - b.top, 0, b.height);
      draft = { x: Math.min(x0, x1), y: Math.min(y0, y1), w: Math.abs(x1 - x0), h: Math.abs(y1 - y0) };
      return;
    }

    const s = rectAtDragStart;
    if (!s) return;

    if (dragMode === "move") {
      draft = {
        x: clamp(s.x + dx, 0, b.width - s.w),
        y: clamp(s.y + dy, 0, b.height - s.h),
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
    if (w < 0) {
      x += w;
      w = -w;
    }
    if (h < 0) {
      y += h;
      h = -h;
    }
    draft = { x: clamp(x, 0, b.width), y: clamp(y, 0, b.height), w, h };
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
      style:left="{display.x}px"
      style:top="{display.y}px"
      style:width="{display.w}px"
      style:height="{display.h}px"
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
