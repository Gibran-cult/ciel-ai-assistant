import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const here = (path: string) => fileURLToPath(new URL(path, import.meta.url));

// Service worker dan side panel. Content script dibangun terpisah
// (vite.content.config.ts) karena harus satu berkas tanpa import.
// Build uji ujung ke ujung (npm run build:e2e): ID ekstensi tetap dan izin
// untuk situs tiruan toko.test, di folder terpisah. Build rilis tidak pernah
// memuat keduanya.
function manifestFor(mode: string): string {
  const manifest = JSON.parse(readFileSync(here("manifest.json"), "utf8"));
  if (mode === "e2e") {
    manifest.key = JSON.parse(readFileSync(here("tests/e2e/key.json"), "utf8")).key;
    manifest.host_permissions = ["https://toko.test/*"];
  }
  return `${JSON.stringify(manifest, null, 2)}\n`;
}

export default defineConfig(({ mode }) => ({
  root: here("src"),
  publicDir: here("public"),
  plugins: [
    react(),
    {
      name: "ciel-manifest",
      writeBundle() {
        // Manifest ditulis tangan (keputusan D17) dan disalin apa adanya.
        writeFileSync(here(`${mode === "e2e" ? "dist-e2e" : "dist"}/manifest.json`), manifestFor(mode));
      },
    },
  ],
  build: {
    outDir: here(mode === "e2e" ? "dist-e2e" : "dist"),
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
}));
