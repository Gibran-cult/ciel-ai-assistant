import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(__dirname, "..");
const manifest = JSON.parse(readFileSync(resolve(root, "manifest.json"), "utf8"));

test("only the approved permissions", () => {
  expect([...manifest.permissions].sort()).toEqual(["activeTab", "alarms", "identity", "scripting", "sidePanel", "storage"]);
  expect(manifest.optional_host_permissions).toEqual(["https://*/*"]);
  for (const banned of ["host_permissions", "externally_connectable", "web_accessible_resources"]) {
    expect(manifest).not.toHaveProperty(banned);
  }
});

test("content script is not injected everywhere", () => {
  expect(manifest).not.toHaveProperty("content_scripts");
});

test("the CSP forbids eval and inline script", () => {
  expect(manifest.content_security_policy.extension_pages).toBe("script-src 'self'; object-src 'none'; base-uri 'none'");
});

test("every file the manifest names exists in the build", () => {
  const dist = resolve(root, "dist");

  // CI membangun sebelum menguji; di laptop uji ini menunggu `npm run build`.
  if (!existsSync(dist)) {
    expect(process.env.CI ?? "").toBe("");
    return;
  }

  expect(JSON.parse(readFileSync(resolve(dist, "manifest.json"), "utf8"))).toEqual(manifest);
  const named = [manifest.background.service_worker, manifest.side_panel.default_path, "content.js",
    ...Object.values(manifest.icons as Record<string, string>)];

  for (const file of named) expect(existsSync(resolve(dist, file)), file).toBe(true);
});
