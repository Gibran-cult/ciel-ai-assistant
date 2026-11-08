// Adds a strict Content-Security-Policy to the static export. Next.js writes a different set of
// inline scripts on every build, so their SHA-256 hashes can only be known after `next build`.
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";

const file = new URL("../out/index.html", import.meta.url);
let html = readFileSync(file, "utf8");

const hashes = new Set();
const inline = /<script(?![^>]*\bsrc=)([^>]*)>([\s\S]*?)<\/script>/g;
for (const [, attrs, body] of html.matchAll(inline)) {
  // JSON-LD is a data block, never executed, so CSP does not apply to it.
  if (/application\/ld\+json/.test(attrs) || body.length === 0) continue;
  hashes.add(`'sha256-${createHash("sha256").update(body, "utf8").digest("base64")}'`);
}

const policy = [
  "default-src 'none'",
  `script-src 'self' ${[...hashes].join(" ")}`,
  "style-src 'self' 'unsafe-inline'",
  "font-src 'self'",
  "img-src 'self' data:",
  "connect-src 'self'",
  "manifest-src 'self'",
  "base-uri 'none'",
  "form-action 'none'",
  "object-src 'none'",
].join("; ");

html = html.replace(/<meta http-equiv="Content-Security-Policy"[^>]*>/, "");
html = html.replace(/<head>/, `<head><meta http-equiv="Content-Security-Policy" content="${policy}">`);
writeFileSync(file, html);
console.log(`CSP: ${hashes.size} inline script hashes`);
