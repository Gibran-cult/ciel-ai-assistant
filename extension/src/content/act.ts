// Pelaksana aksi di tab tugas. Dipanggil hanya setelah tiketnya lolos
// pemeriksaan di service worker (runner.ts). Semua aturan keselamatan di
// sini dicek ulang pada elemen yang hidup saat aksi dijalankan, bukan pada
// hasil bacaan sebelumnya: halaman bisa berubah di antara keduanya.
import type { Observation } from "../shared/protocol";
import { isSecretField, kindOf, observe, pageRefs, type Reading, squash } from "./reader";
import { findSecrets } from "./redact";

// Jenis kolom yang boleh diketik. Sama dengan HARMLESS_FIELDS di guard/risk.py
// untuk kolom teks.
const TYPABLE = new Set(["text", "search", "email", "tel", "url", "number"]);

export interface ActOptions {
  /** Lama menunggu halaman tenang setelah aksi, dalam milidetik. */
  settleMs?: number;
}

type Args = Record<string, unknown>;

function refused(text: string, doc: Document): Reading {
  const observation: Observation = { ok: false, source: "page", text, host: doc.location?.hostname || null, controls: {} };
  return { observation, generation: pageRefs.generation };
}

// Tunggu sampai tidak ada perubahan DOM selama sepertiga waktu tunggu, paling lama settleMs.
function settle(doc: Document, settleMs: number): Promise<void> {
  if (settleMs <= 0) return Promise.resolve();

  return new Promise((done) => {
    const quiet = Math.max(50, Math.floor(settleMs / 3));
    let timer = setTimeout(finish, quiet);
    const limit = setTimeout(finish, settleMs);
    const View = doc.defaultView?.MutationObserver ?? MutationObserver;
    const observer = new View(() => {
      clearTimeout(timer);
      timer = setTimeout(finish, quiet);
    });
    observer.observe(doc, { childList: true, subtree: true, attributes: true, characterData: true });

    function finish() {
      clearTimeout(timer);
      clearTimeout(limit);
      observer.disconnect();
      done();
    }
  });
}

function element(args: Args, generation: number): Element | string {
  if (typeof args.ref !== "number" || !Number.isInteger(args.ref)) return "Nomor rujukan tidak sah.";
  if (generation !== pageRefs.generation) return "Halaman sudah berubah sejak dibaca. Baca ulang dulu.";
  const found = pageRefs.resolve(args.ref);
  return found ?? "Kontrol itu sudah tidak ada di halaman. Baca ulang dulu.";
}

function show(target: Element): void {
  if (typeof target.scrollIntoView === "function") target.scrollIntoView({ block: "center", inline: "nearest" });
}

function setValue(field: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement, value: string): void {
  // Pakai setter bawaan, supaya kolom yang dikendalikan React ikut tahu nilainya berubah.
  const proto = Object.getPrototypeOf(field) as object;
  const setter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
  if (setter) setter.call(field, value);
  else field.value = value;
  field.dispatchEvent(new Event("input", { bubbles: true }));
  field.dispatchEvent(new Event("change", { bubbles: true }));
}

function run(tool: string, args: Args, generation: number, doc: Document): string | null {
  if (tool === "tab_read") return null;

  if (tool === "tab_scroll") {
    if (args.direction !== "up" && args.direction !== "down") return "Arah gulir tidak sah.";
    const view = doc.defaultView ?? window;
    view.scrollBy(0, (args.direction === "down" ? 1 : -1) * Math.round((view.innerHeight || 800) * 0.8));
    return null;
  }

  if (!["tab_click", "form_submit", "tab_type", "tab_select"].includes(tool)) return "Aksi ini tidak dikenal ekstensi.";

  const target = element(args, generation);
  if (typeof target === "string") return target;

  const kind = kindOf(target);
  if (kind === null) return "Elemen itu bukan kontrol.";
  // Kolom rahasia diisi sendiri oleh pengguna, apa pun isi tiketnya.
  if ((kind === "field" || kind === "select" || kind === "textarea") && isSecretField(target)) {
    return "Kolom ini meminta data rahasia, jadi kamu yang mengisinya sendiri.";
  }
  if ((target as HTMLButtonElement).disabled === true) return "Kontrol itu nonaktif.";

  show(target);

  if (tool === "tab_click") {
    (target as HTMLElement).click();
    return null;
  }

  if (tool === "form_submit") {
    if (kind === "button") {
      if ((target as HTMLButtonElement).form == null) return "Tombol itu tidak ada di dalam formulir.";
      (target as HTMLElement).click();
      return null;
    }

    const form = (target as HTMLInputElement).form;
    if (!form) return "Kontrol itu tidak ada di dalam formulir.";
    form.requestSubmit();
    return null;
  }

  if (tool === "tab_type") {
    if (typeof args.text !== "string") return "Teks tidak sah.";
    if (findSecrets(args.text).length > 0) return "Teks ini tampak berisi data rahasia, jadi tidak diketik.";

    const field = target as HTMLInputElement | HTMLTextAreaElement;
    const typable = kind === "textarea" || (kind === "field" && TYPABLE.has((field as HTMLInputElement).type));
    if (!typable || field.readOnly) return "Kolom itu tidak bisa diketik agent.";
    field.focus();
    setValue(field, args.text);
    return null;
  }

  // tab_select
  if (kind !== "select" || typeof args.value !== "string") return "Kontrol itu bukan daftar pilihan.";
  const select = target as HTMLSelectElement;
  const wanted = squash(args.value);
  const option = [...select.options].find((item) => !item.disabled && (squash(item.text) === wanted || item.value === args.value));
  if (!option) return "Pilihan itu tidak ada di daftar.";
  setValue(select, option.value);
  return null;
}

/** Jalankan satu aksi lalu baca ulang halaman. Penolakan menjadi observation ok: false. */
export async function act(tool: string, args: Args, generation: number, options: ActOptions = {},
  doc: Document = document): Promise<Reading> {
  let problem: string | null;

  try {
    problem = run(tool, args, generation, doc);
  } catch {
    problem = "Aksi gagal dijalankan di halaman.";
  }

  if (problem !== null) return refused(problem, doc);
  await settle(doc, options.settleMs ?? 600);
  return observe(doc);
}
