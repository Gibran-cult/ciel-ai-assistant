import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { renderTheme } from "../scripts/tokens.mjs";

const repo = resolve(__dirname, "..", "..");
const tokens = JSON.parse(readFileSync(resolve(repo, "design/tokens.json"), "utf8"));
const doc = readFileSync(resolve(repo, "docs/design-system.md"), "utf8");

type Theme = Record<string, string>;

function value(theme: Theme, name: string): string {
  const raw = theme[name];
  if (raw === undefined) throw new Error(`no token ${name}`);
  const alias = /^\{([a-z-]+)\}$/.exec(raw);
  return alias ? value(theme, alias[1]!) : raw;
}

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map(
    (c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r! + 0.7152 * g! + 0.0722 * b!;
}

function ratio(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi! + 0.05) / (lo! + 0.05);
}

// Baris tabel: | `text` di atas `bg` | 16,13 | 17,63 | Ya |
const rows = [...doc.matchAll(/^\| `([a-z-]+)` di atas `([a-z-]+)`([^|]*)\| ([\d,]+) \| ([\d,]+) \|/gm)];

test("the design system table has the pairs", () => {
  expect(rows.length).toBe(21);
});

test.each(rows.map((m) => [m[1]!, m[2]!, m[3]!, m[4]!, m[5]!]))(
  "%s on %s meets AA and matches the table", (fg, bg, note, light, dark) => {
    const min = note.includes("garis tepi") ? 3 : 4.5;

    for (const [mode, written] of [["light", light], ["dark", dark]] as const) {
      const got = ratio(value(tokens[mode], fg), value(tokens[mode], bg));
      expect(got).toBeGreaterThanOrEqual(min);
      expect(Math.abs(got - Number(written.replace(",", ".")))).toBeLessThan(0.006);
    }
  });

test("agent tokens have readable text", () => {
  for (const mode of ["light", "dark"] as const) {
    const theme = tokens[mode];
    expect(ratio(value(theme, "stop-ink"), value(theme, "stop-bg"))).toBeGreaterThanOrEqual(4.5);
    expect(ratio(value(theme, "official-ink"), value(theme, "official-bg"))).toBeGreaterThanOrEqual(4.5);
    for (const name of ["agent-active", "agent-wait", "rejected"]) expect(value(theme, name)).toMatch(/^#[0-9a-f]{6}$/);
  }
});

test("theme.css is generated from tokens.json", () => {
  const css = readFileSync(resolve(__dirname, "..", "src", "theme.css"), "utf8").replace(/\r\n/g, "\n");
  expect(css).toBe(renderTheme(tokens));
  expect(css).toContain("--c-stop-bg: #a33b2c;");
  expect(css).toContain("--c-agent-active: var(--c-accent);");
  expect(css).toContain('@media (prefers-color-scheme: dark)');
  expect(css).toContain(':root[data-theme="dark"]');
});
