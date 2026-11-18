import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { vi } from "vitest";
import { act } from "../src/content/act";
import { observe } from "../src/content/reader";

function load(name: string) {
  document.documentElement.innerHTML = readFileSync(resolve(__dirname, "pages", name), "utf8");
  return observe(document);
}

function refOf(text: string, label: string): number {
  const match = new RegExp(`\\[ref (\\d+): [^\\]]*${label}`).exec(text);
  if (!match) throw new Error(`no control for ${label}`);
  return Number(match[1]);
}

const now = { settleMs: 0 };

test("clicking the cart button runs it and returns a fresh reading", async () => {
  const { observation, generation } = load("shop.html");
  const ref = refOf(observation.text, "Tambah ke Keranjang");
  expect(observation.controls[ref]!.effect).toBe("cart_add");
  const clicked = vi.fn();
  [...document.querySelectorAll("button")].find((b) => b.textContent === "Tambah ke Keranjang")!.addEventListener("click", clicked);

  const after = await act("tab_click", { ref }, generation, now);
  expect(clicked).toHaveBeenCalledTimes(1);
  expect(after.observation.ok).toBe(true);
  expect(after.observation.text).toContain("Harga Rp49.000");
  expect(after.generation).toBeGreaterThan(generation);
});

test("typing into a password field is refused even with a valid ticket", async () => {
  const { observation, generation } = load("login.html");
  const ref = refOf(observation.text, "Kata sandi");
  const result = await act("tab_type", { ref, text: "tebakan" }, generation, now);
  expect(result.observation.ok).toBe(false);
  expect((document.getElementById("pw") as HTMLInputElement).value).toBe("rahasia123");
});

test("a field that turned secret after reading is refused", async () => {
  const { observation, generation } = load("login.html");
  const ref = refOf(observation.text, "Email");
  document.getElementById("email")!.setAttribute("type", "password");
  expect((await act("tab_type", { ref, text: "x" }, generation, now)).observation.ok).toBe(false);
});

test("typing sets the value and fires input and change", async () => {
  const { observation, generation } = load("login.html");
  const ref = refOf(observation.text, "Email");
  const field = document.getElementById("email") as HTMLInputElement;
  const events: string[] = [];
  for (const type of ["input", "change"]) field.addEventListener(type, () => events.push(type));

  const result = await act("tab_type", { ref, text: "sari@example.com" }, generation, now);
  expect(result.observation.ok).toBe(true);
  expect(field.value).toBe("sari@example.com");
  expect(events).toEqual(["input", "change"]);
});

test("text that holds a card number is never typed", async () => {
  const { observation, generation } = load("login.html");
  const ref = refOf(observation.text, "Email");
  expect((await act("tab_type", { ref, text: "4111 1111 1111 1111" }, generation, now)).observation.ok).toBe(false);
  expect((document.getElementById("email") as HTMLInputElement).value).toBe("budi@example.com");
});

test("an old ref after the page was replaced does not hit another element", async () => {
  const { observation, generation } = load("shop.html");
  const ref = refOf(observation.text, "Tambah ke Keranjang");
  document.body.innerHTML = "<button>Hapus akun</button>".repeat(30);
  await new Promise((done) => setTimeout(done, 0));
  const clicked = vi.fn();
  for (const button of document.querySelectorAll("button")) button.addEventListener("click", clicked);

  expect((await act("tab_click", { ref }, generation, now)).observation.ok).toBe(false);
  expect(clicked).not.toHaveBeenCalled();
});

test("a ref from an older generation is refused", async () => {
  const { observation, generation } = load("shop.html");
  const ref = refOf(observation.text, "Tambah ke Keranjang");
  observe(document);
  expect((await act("tab_click", { ref }, generation, now)).observation.ok).toBe(false);
});

test("tab_select only takes a listed option", async () => {
  const { observation, generation } = load("shop.html");
  const ref = refOf(observation.text, "Ukuran");
  const select = document.querySelector("select")!;

  expect((await act("tab_select", { ref, value: "XL" }, generation, now)).observation.ok).toBe(false);
  expect(select.value).toBe("M");

  const fresh = observe(document);
  const again = refOf(fresh.observation.text, "Ukuran");
  expect((await act("tab_select", { ref: again, value: "L" }, fresh.generation, now)).observation.ok).toBe(true);
  expect(select.value).toBe("L");
});

test("form_submit submits the field's form", async () => {
  const { observation, generation } = load("shop.html");
  const ref = refOf(observation.text, "Cari produk");
  const submitted = vi.fn((event: Event) => event.preventDefault());
  document.querySelector("form")!.addEventListener("submit", submitted);
  expect((await act("form_submit", { ref }, generation, now)).observation.ok).toBe(true);
  expect(submitted).toHaveBeenCalledTimes(1);
});

test("form_submit on a control outside a form is refused", async () => {
  const { observation, generation } = load("shop.html");
  const ref = refOf(observation.text, "Jumlah");
  expect((await act("form_submit", { ref }, generation, now)).observation.ok).toBe(false);
});

test("scrolling moves the window and reads again", async () => {
  const { generation } = load("shop.html");
  const scrollBy = vi.spyOn(window, "scrollBy").mockImplementation(() => undefined);
  expect((await act("tab_scroll", { direction: "down" }, generation, now)).observation.ok).toBe(true);
  expect((scrollBy.mock.calls[0] as unknown as [number, number])[1]).toBeGreaterThan(0);
  scrollBy.mockRestore();
});

test("unknown tools and bad arguments are refused", async () => {
  const { generation } = load("shop.html");
  expect((await act("pay", {}, generation, now)).observation.ok).toBe(false);
  expect((await act("tab_click", { ref: "1" }, generation, now)).observation.ok).toBe(false);
  expect((await act("tab_scroll", { direction: "left" }, generation, now)).observation.ok).toBe(false);
});

test("the reading after a click waits for the page to update", async () => {
  const { observation, generation } = load("shop.html");
  const ref = refOf(observation.text, "Tambah ke Keranjang");
  [...document.querySelectorAll("button")].find((b) => b.textContent === "Tambah ke Keranjang")!.addEventListener("click", () => {
    setTimeout(() => document.body.append(Object.assign(document.createElement("p"), { textContent: "Masuk keranjang: 1 barang" })), 30);
  });

  const after = await act("tab_click", { ref }, generation, { settleMs: 400 });
  expect(after.observation.text).toContain("Masuk keranjang: 1 barang");
});
