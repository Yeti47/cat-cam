import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";

// In dev, `npm run dev` serves the UI on :5173 and proxies everything the
// backend owns to the running container on :8090 -- including the MJPEG
// stream and the two SSE endpoints, which must not be buffered.
const backend = process.env.CATCAM_BACKEND ?? "http://127.0.0.1:8090";

export default defineConfig({
  plugins: [svelte()],
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": backend,
      "/stream.mjpg": backend,
      "/events": backend,
      "/logs/stream": backend,
    },
  },
});
