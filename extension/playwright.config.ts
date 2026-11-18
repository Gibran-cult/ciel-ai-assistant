import { readFileSync } from "node:fs";
import { defineConfig } from "@playwright/test";

const { id } = JSON.parse(readFileSync(new URL("./tests/e2e/key.json", import.meta.url), "utf8"));
const python = process.env.E2E_PYTHON ?? "python";

// Uji ujung ke ujung: ekstensi build e2e (npm run build:e2e) melawan layanan
// agent sungguhan di 127.0.0.1 dengan model bernaskah (tools/agent_e2e_server.py).
export default defineConfig({
  testDir: "tests/e2e",
  timeout: 90_000,
  workers: 1,
  reporter: [["list"]],
  webServer: {
    command: `"${python}" ../tools/agent_e2e_server.py --origin chrome-extension://${id}`,
    url: "http://127.0.0.1:8611/healthz",
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
    stdout: "pipe",
  },
});
