// Demo untuk pemeriksaan tampilan oleh pemilik, bukan uji. Jalankan:
//   DEMO=1 HEADED=1 npx playwright test demo
// Browser terbuka dengan ekstensi yang sudah masuk ke layanan uji lokal, di
// beranda toko tiruan. Klik ikon Ciel untuk membuka side panel. Apa pun
// perintahnya, model bernaskah memutar alur isi formulir ini. Tutup browser
// untuk selesai.
import { SHOP, test } from "./fixtures";

test.skip(!process.env.DEMO, "hanya untuk demo");
test.setTimeout(0);

test("demo", async ({ agent }) => {
  await agent.script({
    plan: { steps: ["Buka halaman daftar member", "Isi nama dan email", "Kirim formulir"], hosts: ["toko.test"],
      kinds: ["tab_open", "tab_read", "tab_type", "form_submit"], spend_cap: 0 },
    calls: [
      { tool: "tab_open", args: { url: `${SHOP}/daftar.html` } },
      { tool: "tab_type", args: { ref: 1, text: "Sari" } },
      { tool: "tab_type", args: { ref: 2, text: "sari@example.com" } },
      { tool: "form_submit", args: { ref: 3 } },
      { tool: "finish", args: { report: "Formulir pendaftaran sudah terkirim atas nama Sari." } },
    ],
  });
  await agent.panel.close();
  const home = await agent.open("/");
  await home.bringToFront();
  await new Promise<void>((done) => agent.context.on("close", () => done()));
});
