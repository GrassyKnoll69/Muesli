import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: { outDir: "dist" },
  server: {
    proxy: {
      "/meetings": "http://localhost:8731",
      "/recordings": "http://localhost:8731",
      "/templates": "http://localhost:8731",
      "/settings": "http://localhost:8731",
      "/ollama": "http://localhost:8731",
    },
  },
});
