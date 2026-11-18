import { copyFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const here = (path: string) => fileURLToPath(new URL(path, import.meta.url));

// Service worker dan side panel. Content script dibangun terpisah
// (vite.content.config.ts) karena harus satu berkas tanpa import.
export default defineConfig({
  root: here("src"),
  publicDir: here("public"),
  plugins: [
    react(),
    {
      name: "ciel-manifest",
      writeBundle() {
        // Manifest ditulis tangan (keputusan D17) dan disalin apa adanya.
        copyFileSync(here("manifest.json"), here("dist/manifest.json"));
      },
    },
  ],
  build: {
    outDir: here("dist"),
    emptyOutDir: true,
    sourcemap: false,
    modulePreload: false,
    rollupOptions: {
      input: {
        background: here("src/background.ts"),
        panel: here("src/panel/index.html"),
      },
      output: {
        entryFileNames: "[name].js",
        chunkFileNames: "chunks/[name]-[hash].js",
        assetFileNames: "assets/[name]-[hash][extname]",
      },
    },
  },
});
