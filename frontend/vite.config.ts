import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/ws": {
        target: "ws://backend:8000",
        ws: true,
      },
      "/api": {
        target: "http://backend:8000",
      },
      "/health": {
        target: "http://backend:8000",
      },
    },
  },
});
