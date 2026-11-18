// Membuat src/theme.css dari design/tokens.json. Jalankan: npm run tokens
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

function block(selector, theme, indent = "") {
  const lines = Object.entries(theme).map(([name, raw]) => {
    const alias = /^\{([a-z-]+)\}$/.exec(raw);
    return `${indent}  --c-${name}: ${alias ? `var(--c-${alias[1]})` : raw};`;
  });
  return `${indent}${selector} {\n${lines.join("\n")}\n${indent}}`;
}

/** Isi theme.css untuk token yang diberikan. */
export function renderTheme(tokens) {
  return [
    "/* Dibuat oleh scripts/tokens.mjs dari design/tokens.json. Jangan diubah tangan. */",
    "",
    block(":root", tokens.light),
    "",
    "@media (prefers-color-scheme: dark) {",
    block(':root:not([data-theme="light"])', tokens.dark, "  "),
    "}",
    "",
    block(':root[data-theme="dark"]', tokens.dark),
    "",
  ].join("\n");
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const tokens = JSON.parse(readFileSync(new URL("../../design/tokens.json", import.meta.url), "utf8"));
  writeFileSync(new URL("../src/theme.css", import.meta.url), renderTheme(tokens));
}
