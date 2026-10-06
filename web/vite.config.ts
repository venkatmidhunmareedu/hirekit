import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The browser only talks to this origin: /v1 is proxied to the API, so the
// session cookie is same-origin and the API needs no CORS (api-lld section 7).
// 8080 is the backend's default PORT (backend/Makefile `dev`).
const apiTarget = process.env.API_PROXY_TARGET ?? "http://localhost:8080";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true, proxy: { "/v1": apiTarget } },
  preview: { port: 4173, strictPort: true, proxy: { "/v1": apiTarget } },
});
