import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// `npm run dev` serves the site; `npm run dev:api` runs the Worker that answers /api.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://localhost:8787" } },
});
