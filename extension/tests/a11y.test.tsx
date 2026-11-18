import axe from "axe-core";
import { cleanup } from "@testing-library/react";
import type { PanelState } from "../src/controller";
import { BASE, show } from "./panel_helpers";

const PROMPT = { tool: "tab_open", target: "shopee-promo.co.id", level: "R2", reason: "lookalike_domain", widens: "shopee-promo.co.id",
  from_page: true, url: "https://shopee-promo.co.id/", ref: null, text: null, lookalike: "shopee.co.id" };

const STATES: [string, Partial<PanelState>][] = [
  ["signed out", { auth: "signed_out" }],
  ["consent required", { auth: "consent_required" }],
  ["idle", {}],
  ["running", { phase: "running", log: [{ time: "10.42", action: "Mengklik", target: "toko.test", result: "Selesai" }] }],
  ["offline", { phase: "running", connection: "closed" }],
  ["plan", { phase: "running", dialog: { kind: "plan", id: 1, steps: ["Buka toko"], scope: { hosts: ["toko.test"], kinds: ["tab_open"], spend_cap: null } } }],
  ["confirm", { phase: "running", dialog: { kind: "confirm", id: 2, prompt: PROMPT } }],
  ["preview", { phase: "running", dialog: { kind: "confirm", id: 2, prompt: { ...PROMPT, reason: "ask_mode" } } }],
  ["handover", { phase: "handover", dialog: { kind: "handover", id: 3, prompt: PROMPT } }],
  ["ask", { phase: "running", dialog: { kind: "ask", id: 4, question: "Ukuran?" } }],
  ["paused", { phase: "paused" }],
  ["permission", { phase: "running", needPermission: "toko.test" }],
  ["ended", { ended: { status: "stopped", reason: "user", steps: 2, report: "Berhenti." } }],
];

describe.each(["light", "dark"])("%s theme", (theme) => {
  test.each(STATES)("%s has no axe findings", async (_name, over) => {
    document.documentElement.setAttribute("data-theme", theme);
    document.documentElement.lang = "id";
    show({ ...BASE, ...over });
    const result = await axe.run(document.body);
    expect(result.violations.map((item) => `${item.id}: ${item.nodes.map((node) => node.html).join(" | ")}`)).toEqual([]);
    cleanup();
  });
});
