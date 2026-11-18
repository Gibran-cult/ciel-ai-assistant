import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { pageRefs, readPage } from "../src/content/reader";

function load(name: string) {
  document.documentElement.innerHTML = readFileSync(resolve(__dirname, "pages", name), "utf8");
  return readPage(document);
}

function refOf(text: string, label: string): number {
  const match = new RegExp(`\\[ref (\\d+): [^\\]]*${label}`).exec(text);
  if (!match) throw new Error(`no control for ${label} in:\n${text}`);
  return Number(match[1]);
}

test("the observation has only the protocol keys", () => {
  const seen = load("shop.html");
  expect(Object.keys(seen).sort()).toEqual(["controls", "host", "ok", "source", "text"]);
  expect(seen).toMatchObject({ ok: true, source: "page", host: "localhost" });
  for (const [ref, control] of Object.entries(seen.controls)) {
    expect(ref).toMatch(/^\d{1,6}$/);
    expect(Object.keys(control).sort()).toEqual(["effect", "field_type", "submits"]);
  }
});

test("login: the password field is reported but never read", () => {
  const seen = load("login.html");
  expect(seen.text).not.toContain("rahasia123");
  expect(seen.text).not.toContain("lama456");
  expect(seen.controls[refOf(seen.text, "Kata sandi")]!.field_type).toBe("password");
  // Nama kolom "userPass" menandai kolom rahasia walau type="text".
  expect(seen.controls[refOf(seen.text, "Sandi lama")]!.field_type).toBe("password");
  expect(seen.controls[refOf(seen.text, "Email")]).toEqual({ field_type: "email", submits: false, effect: null });
  expect(seen.controls[refOf(seen.text, "Masuk")]!.submits).toBe(true);
});

test("checkout: card, OTP and PIN fields are secret, the pay button has an effect", () => {
  const seen = load("checkout.html");

  for (const label of ["Nomor kartu", "Nama di kartu", "Kode OTP", "PIN", "Kode verifikasi"]) {
    expect(seen.controls[refOf(seen.text, label)]!.field_type, label).toBe("password");
  }

  for (const value of ["4111", "BUDI SANTOSO", "482913", "9999", "771100", "5555"]) expect(seen.text).not.toContain(value);
  expect(seen.text).toContain("[disaring]");
  expect(seen.controls[refOf(seen.text, "Alamat pengiriman")]!.field_type).toBe("text");
  expect(seen.text).toContain("Jl. Mawar 12");
  expect(seen.controls[refOf(seen.text, "Bayar Sekarang")]!.effect).toBe("pay");
  expect(seen.controls[refOf(seen.text, "Batalkan pesanan")]!.effect).toBe("order_cancel");
});

test("shop: buttons, links, selects and hidden text", () => {
  const seen = load("shop.html");

  expect(seen.text).toContain("Harga Rp49.000");
  for (const hidden of ["display", "visibility", "atribut hidden", "aria hidden", "jangan dibaca", "tersembunyi"]) {
    expect(seen.text).not.toContain(hidden);
  }

  expect(seen.controls[refOf(seen.text, "Tambah ke Keranjang")]).toEqual({ field_type: null, submits: false, effect: "cart_add" });
  expect(seen.controls[refOf(seen.text, "Beli Sekarang")]!.effect).toBe("checkout_prepare");
  expect(seen.controls[refOf(seen.text, "Unduh katalog")]!.effect).toBe("download");
  expect(seen.controls[refOf(seen.text, "Hapus ulasan")]!.submits).toBe(true);
  expect(seen.controls[refOf(seen.text, "Kaos lain")]).toEqual({ field_type: null, submits: false, effect: null });
  expect(seen.controls[refOf(seen.text, "Ukuran")]!.field_type).toBe("select");
  expect(seen.text).toMatch(/Ukuran[^\]]*M/);
  expect(seen.controls[refOf(seen.text, "Jumlah")]!.field_type).toBe("number");
  // Kolom cari di formulir tanpa tombol lain: Enter mengirim formulir.
  expect(seen.controls[refOf(seen.text, "Cari produk")]).toEqual({ field_type: "search", submits: true, effect: null });
  // Tombol nonaktif tidak diberi nomor.
  expect(seen.text).not.toMatch(/\[ref \d+: [^\]]*Habis/);
  expect(seen.text).toContain("Habis");
});

test("frames are never read", () => {
  const seen = load("shop.html");
  expect(seen.text).not.toContain("pay.example");
  expect(seen.text).toContain("[bingkai tidak dibaca]");
});

test("open shadow roots are read", () => {
  document.documentElement.innerHTML = "<body><div id=host></div></body>";
  const root = document.getElementById("host")!.attachShadow({ mode: "open" });
  root.innerHTML = "<p>Dalam bayangan</p><button>Tambah ke keranjang</button>";
  const seen = readPage(document);
  expect(seen.text).toContain("Dalam bayangan");
  expect(seen.controls[refOf(seen.text, "Tambah ke keranjang")]!.effect).toBe("cart_add");
});

test("long pages are cut and only the visible controls keep a number", () => {
  document.documentElement.innerHTML = `<body>${"<p>baris panjang sekali</p>".repeat(400)}<button>Akhir</button></body>`;
  const seen = readPage(document, 1000);
  expect(seen.text.length).toBeLessThanOrEqual(1000);
  expect(Object.keys(seen.controls)).toEqual([]);
});

test("refs point at the read element until the page changes", async () => {
  const seen = load("shop.html");
  const cart = refOf(seen.text, "Tambah ke Keranjang");
  expect(pageRefs.resolve(cart)?.textContent).toBe("Tambah ke Keranjang");
  expect(pageRefs.resolve(9999)).toBeNull();

  // Perubahan kecil tidak membatalkan rujukan.
  document.body.append(document.createElement("span"));
  await new Promise((done) => setTimeout(done, 0));
  expect(pageRefs.resolve(cart)).not.toBeNull();

  // Perubahan besar membatalkan semuanya.
  for (let i = 0; i < 25; i++) document.body.append(document.createElement("div"));
  await new Promise((done) => setTimeout(done, 0));
  expect(pageRefs.resolve(cart)).toBeNull();
});

test("a removed element is not resolved, and a new read starts a new generation", () => {
  const seen = load("shop.html");
  const generation = pageRefs.generation;
  const cart = refOf(seen.text, "Tambah ke Keranjang");
  pageRefs.resolve(cart)!.remove();
  expect(pageRefs.resolve(cart)).toBeNull();
  readPage(document);
  expect(pageRefs.generation).toBeGreaterThan(generation);
});

test("review: a field that is secret only by its label, aria-label or placeholder is never read", () => {
  document.documentElement.innerHTML = `<body>
    <label>Kode OTP <input type="tel" name="code" value="482913"></label>
    <input type="text" name="security_code" placeholder="CVV" value="123">
    <input type="text" aria-label="Kata sandi" name="field1" value="tebakku99">
    <label>Nomor kartu <input type="text" name="nomor" value="5555"></label>
    <input type="text" inputmode="numeric" maxlength="6" name="kode" value="771100">
    <label>Jumlah <input type="number" name="qty" value="2"></label>
    <label>Kode pos <input type="text" name="zip" value="40115"></label>
  </body>`;
  const seen = readPage(document);
  for (const value of ["482913", "123", "tebakku99", "5555", "771100"]) expect(seen.text).not.toContain(value);
  expect(Object.values(seen.controls).filter((control) => control.field_type === "password")).toHaveLength(5);
  expect(seen.text).toContain("40115");
  expect(seen.controls[refOf(seen.text, "Jumlah")]!.field_type).toBe("number");
});

test("review: each page starts its generations at its own random number", async () => {
  const { PageRefs } = await import("../src/content/reader");
  const a = new PageRefs();
  const b = new PageRefs();
  expect(a.generation).not.toBe(b.generation);
  expect(Number.isSafeInteger(a.generation)).toBe(true);
});

test("review: a page restored from the back-forward cache drops its refs", () => {
  const seen = load("shop.html");
  const cart = refOf(seen.text, "Tambah ke Keranjang");
  const event = new Event("pageshow");
  Object.defineProperty(event, "persisted", { value: true });
  window.dispatchEvent(event);
  expect(pageRefs.resolve(cart)).toBeNull();
});

test("review: common final-order buttons are pay buttons", () => {
  const labels = ["Pesan sekarang", "Selesaikan pesanan", "Place your order", "Complete purchase", "Confirm order"];
  document.documentElement.innerHTML = `<body>${labels.map((label) => `<button>${label}</button>`).join("")}</body>`;
  const seen = readPage(document);
  for (const label of labels) expect(seen.controls[refOf(seen.text, label)]!.effect, label).toBe("pay");
});
