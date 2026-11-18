import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";

const here = (path: string) => fileURLToPath(new URL(path, import.meta.url));

// Content script disuntikkan dengan chrome.scripting.executeScript ke tab
// tugas saja, jadi harus satu berkas skrip biasa (IIFE) tanpa import.
export default defineConfig({
  publicDir: false,
  build: {
    outDir: here("dist"),
    emptyOutDir: false,
    sourcemap: false,
    lib: {
      entry: here("src/content/index.ts"),
      formats: ["iife"],
      name: "CielContent",
      fileName: () => "content.js",
    },
  },
});
