import type { Page } from "@playwright/test";
import { type Agent, expect, type Script, SHOP, test } from "./fixtures";

// Layanan baru tahu halaman setelah klien melaporkannya, jadi setiap tugas
// dimulai dengan tab_open. Tab yang dibuka menjadi tab tugas.
const OPEN_FORM = { tool: "tab_open", args: { url: `${SHOP}/daftar.html` } };

async function taskPage(agent: Agent, path: string): Promise<Page> {
  await expect.poll(() => agent.context.pages().filter((page) => page.url().includes(path)).length).toBeGreaterThan(0);
  return agent.context.pages().filter((page) => page.url().includes(path)).at(-1)!;
}

async function actions(): Promise<{ kind: string; decision: string; reason: string; result: string | null }[]> {
  return (await fetch("http://127.0.0.1:8611/test/actions")).json();
}

const FORM: Script = {
  plan: { steps: ["Baca formulir", "Isi nama dan email", "Kirim formulir"], hosts: ["toko.test"], kinds: ["tab_open", "tab_read", "tab_type", "form_submit"], spend_cap: 0 },
  calls: [
    OPEN_FORM,
    { tool: "tab_type", args: { ref: 1, text: "Sari" } },
    { tool: "tab_type", args: { ref: 2, text: "sari@example.com" } },
    { tool: "form_submit", args: { ref: 3 } },
    { tool: "finish", args: { report: "Formulir pendaftaran sudah terkirim." } },
  ],
};

test("a form task runs from plan to report", async ({ agent }) => {
  await agent.script(FORM);
  await agent.open("/");
  await agent.start("Daftarkan aku sebagai member dengan nama Sari");

  const panel = agent.panel;
  await panel.getByRole("heading", { name: "Rencana Ciel" }).waitFor();
  await panel.getByLabel("Jalan sendiri").check();
  await panel.getByRole("button", { name: "Mulai" }).click();

  // Mengirim formulir adalah R2: selalu ditanyakan.
  await panel.getByRole("alertdialog").waitFor();
  const shop = await taskPage(agent, "daftar.html");
  await expect(shop.locator("input[name=nama]")).toHaveValue("Sari");
  await expect(shop.locator("input[name=email]")).toHaveValue("sari@example.com");
  await expect(shop.locator("ciel-agent-banner")).toHaveCount(1);
  await panel.getByRole("button", { name: "Kirim formulir" }).click();

  await panel.getByText("Formulir pendaftaran sudah terkirim.").waitFor();
  await expect(shop).toHaveURL(/terima\.html$/);
  // Layanan menulis dua baris per aksi: saat dikirim (hasil kosong) dan setelah ada hasil.
  expect((await actions()).filter((row) => row.result !== null).map((row) => [row.kind, row.result])).toEqual([
    ["tab_open", "ok"], ["tab_type", "ok"], ["tab_type", "ok"], ["form_submit", "ok"], ["finish", "ok"]]);
  await expect(panel.getByText("Mengklik").or(panel.getByText("Mengirim formulir")).first()).toBeVisible();
});

test("a declined R2 confirmation sends nothing", async ({ agent }) => {
  await agent.script({ ...FORM, calls: [...FORM.calls.slice(0, 4), { tool: "finish", args: { report: "Formulir tidak dikirim." } }] });
  await agent.open("/");
  await agent.start("Isi formulir member");

  const panel = agent.panel;
  await panel.getByLabel("Jalan sendiri").check();
  await panel.getByRole("button", { name: "Mulai" }).click();
  await panel.getByRole("button", { name: "Batal" }).click();
  const shop = await taskPage(agent, "daftar.html");

  await panel.getByText("Formulir tidak dikirim.").waitFor();
  await expect(shop).toHaveURL(/daftar\.html$/);
  await expect(panel.getByText("Kamu tolak")).toBeVisible();
});

test("Stop ends the task before anything is typed", async ({ agent }) => {
  await agent.script(FORM);
  await agent.open("/");
  await agent.start("Isi formulir member");

  const panel = agent.panel;
  // "Tanya dulu" adalah bawaan: membuka tab dan mengetik menunggu di preview.
  await panel.getByRole("button", { name: "Mulai" }).click();
  await panel.getByRole("button", { name: "Jalankan" }).click();
  const shop = await taskPage(agent, "daftar.html");
  await expect(panel.getByRole("button", { name: "Jalankan" })).toBeVisible();
  await panel.getByRole("button", { name: /Stop/ }).click();

  await expect(panel.getByRole("heading", { name: "Dihentikan" })).toBeVisible();
  await expect(shop.locator("ciel-agent-banner")).toHaveCount(1);
  await expect(shop.locator("input[name=nama]")).toHaveValue("");
  await expect(panel.getByRole("button", { name: "Jalankan" })).toHaveCount(0);
});

test("a page that tries to hijack the agent gets nothing dangerous", async ({ agent }) => {
  await agent.script({
    plan: { steps: ["Baca halaman promo"], hosts: ["toko.test"], kinds: ["tab_open", "tab_read"], spend_cap: 0 },
    calls: [
      { tool: "tab_open", args: { url: `${SHOP}/suntik.html` } },
      // Model yang terbujuk isi halaman.
      { tool: "tab_open", args: { url: "https://evil.test/ambil" } },
      { tool: "tab_type", args: { ref: 1, text: "rahasia123" } },
      { tool: "finish", args: { report: "Selesai membaca." } },
    ],
  });
  await agent.open("/");
  await agent.start("Baca halaman promo ini");

  const panel = agent.panel;
  await panel.getByLabel("Jalan sendiri").check();
  await panel.getByRole("button", { name: "Mulai" }).click();

  // Apa pun yang ditanyakan, jawabannya tidak.
  const end = panel.getByText("Selesai membaca.");
  for (let i = 0; i < 6 && !(await end.isVisible()); i++) {
    const refuse = panel.getByRole("button", { name: /^(Batal|Batalkan langkah ini)$/ });
    if (await refuse.isVisible()) await refuse.click();
    await panel.waitForTimeout(500);
  }

  await end.waitFor();
  const shop = await taskPage(agent, "suntik.html");
  expect(agent.context.pages().some((page) => page.url().includes("evil.test"))).toBe(false);
  const done = await actions();
  expect(done.filter((row) => row.result === "ok").map((row) => row.kind)).toEqual(["tab_open", "finish"]);
  await expect(shop.locator("input[name=password]")).toHaveValue("");
});
