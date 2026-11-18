// Pembaca halaman: teks yang terlihat dan kontrol bernomor (ref).
//
// Kolom rahasia (kata sandi, kartu, OTP, PIN) dilaporkan sebagai
// field_type "password" dan isinya tidak pernah dibaca. Seluruh teks lewat
// redact() sebelum keluar dari tab. Bingkai (iframe) tidak pernah dibaca.
import type { Control, Observation } from "../shared/protocol";
import { redact } from "./redact";

const SKIP = new Set(["SCRIPT", "STYLE", "NOSCRIPT", "TEMPLATE", "HEAD", "TITLE", "META", "LINK", "SVG", "CANVAS"]);
const FRAMES = new Set(["IFRAME", "FRAME", "OBJECT", "EMBED"]);
const BLOCK = new Set(["ADDRESS", "ARTICLE", "ASIDE", "BLOCKQUOTE", "BR", "DD", "DIV", "DL", "DT", "FIELDSET", "FIGCAPTION",
  "FIGURE", "FOOTER", "FORM", "H1", "H2", "H3", "H4", "H5", "H6", "HEADER", "HR", "LI", "MAIN", "NAV", "OL", "P", "PRE",
  "SECTION", "TABLE", "TR", "UL"]);
const BUTTON_INPUTS = new Set(["submit", "button", "reset", "image"]);
const SUBMIT_INPUTS = new Set(["submit", "image"]);
const MAX_LABEL = 100;
const MAX_VALUE = 200;
const MAX_HREF = 150;
// Lebih dari 20 node berubah sejak dibaca: halaman dianggap baru.
const BIG_CHANGE = 20;

// Kolom rahasia: autocomplete pembayaran dan kata sandi, atau nama/id yang
// memuat kata-kata ini. Dicocokkan per kata, supaya "shipping" tidak
// dianggap "pin".
const SECRET_AUTOCOMPLETE = /^(cc-.+|current-password|new-password|one-time-code)$/;
const SECRET_PREFIXES = ["pass", "pwd", "otp", "cvv", "cvc", "card", "sandi", "kartu"];
const SECRET_WORDS = new Set(["pin", "mpin"]);

// Efek tombol, diperiksa berurutan. "pay" tidak pernah dijalankan agent.
const EFFECTS: [string, RegExp][] = [
  ["pay", /\b(bayar|pay|place order|buat pesanan|konfirmasi pembayaran)\b/],
  ["order_cancel", /\b(batalkan|cancel order)\b/],
  ["checkout_prepare", /\b(checkout|check out|beli sekarang|buy now|lanjut ke pembayaran|proceed to checkout)\b/],
  ["cart_add", /(tambahkan ke keranjang|tambah ke keranjang|masukkan (ke )?keranjang|\+ ?keranjang|add to (cart|bag|basket))/],
  ["download", /\b(unduh|download)\b/],
];

class PageRefs {
  generation = 0;
  private refs = new Map<number, WeakRef<Element>>();
  private changed = 0;
  private url = "";
  private observer: MutationObserver | null = null;
  private watched: Document | null = null;

  /** Mulai bacaan baru: rujukan lama tidak berlaku lagi. */
  reset(doc: Document): void {
    this.invalidate();
    this.url = doc.location?.href ?? "";
    this.watch(doc);
  }

  add(element: Element): number {
    const ref = this.refs.size + 1;
    this.refs.set(ref, new WeakRef(element));
    return ref;
  }

  keep(refs: Set<number>): void {
    for (const ref of [...this.refs.keys()]) if (!refs.has(ref)) this.refs.delete(ref);
  }

  /** Elemen untuk nomor rujukan dari bacaan terakhir, atau null kalau halaman sudah berubah. */
  resolve(ref: number): Element | null {
    const doc = this.watched;
    if (doc && (doc.location?.href ?? "") !== this.url) this.invalidate();

    const element = this.refs.get(ref)?.deref();
    return element && element.isConnected ? element : null;
  }

  private invalidate(): void {
    this.generation += 1;
    this.refs.clear();
    this.changed = 0;
  }

  private watch(doc: Document): void {
    if (this.watched === doc) return;
    this.observer?.disconnect();
    this.watched = doc;
    const View = doc.defaultView?.MutationObserver ?? MutationObserver;

    this.observer = new View((records) => {
      for (const record of records) this.changed += record.addedNodes.length + record.removedNodes.length;
      if (this.changed > BIG_CHANGE && this.refs.size > 0) this.invalidate();
    });
    this.observer.observe(doc, { childList: true, subtree: true });
  }
}

export const pageRefs = new PageRefs();

export function squash(text: string): string {
  return text.replace(/\s+/g, " ").trim();
}

function clip(text: string, max: number): string {
  const points = [...text];
  return points.length <= max ? text : `${points.slice(0, max - 1).join("")}…`;
}

function words(value: string): string[] {
  return value.replace(/([a-z0-9])([A-Z])/g, "$1 $2").toLowerCase().split(/[^a-z0-9]+/).filter(Boolean);
}

export function isSecretField(element: Element): boolean {
  if (element.tagName === "INPUT" && (element as HTMLInputElement).type === "password") return true;

  const autocomplete = (element.getAttribute("autocomplete") ?? "").toLowerCase().split(/\s+/);
  if (autocomplete.some((token) => SECRET_AUTOCOMPLETE.test(token))) return true;

  const named = words(`${element.getAttribute("name") ?? ""} ${element.id}`);
  return named.some((word) => SECRET_WORDS.has(word) || SECRET_PREFIXES.some((prefix) => word.startsWith(prefix)));
}

// Teks di dalam elemen, tanpa isi kontrol lain (opsi pilihan, nilai kolom).
function plainText(element: Element): string {
  let out = "";

  for (const node of element.childNodes) {
    if (node.nodeType === Node.TEXT_NODE) out += ` ${node.textContent ?? ""}`;
    else if (node.nodeType === Node.ELEMENT_NODE && !["SELECT", "TEXTAREA", "INPUT", "SCRIPT", "STYLE"].includes((node as Element).tagName)) {
      out += ` ${plainText(node as Element)}`;
    }
  }

  return squash(out);
}

function labelOf(element: Element): string {
  const doc = element.ownerDocument;
  const aria = element.getAttribute("aria-label");
  if (aria && squash(aria)) return squash(aria);

  const labelledBy = element.getAttribute("aria-labelledby");
  if (labelledBy) {
    const text = squash(labelledBy.split(/\s+/).map((id) => doc.getElementById(id)?.textContent ?? "").join(" "));
    if (text) return text;
  }

  const labels = (element as HTMLInputElement).labels;
  if (labels && labels.length > 0) {
    const text = squash([...labels].map(plainText).join(" "));
    if (text) return text;
  }

  if (element.tagName === "INPUT" && BUTTON_INPUTS.has((element as HTMLInputElement).type)) {
    return squash((element as HTMLInputElement).value || element.getAttribute("alt") || "");
  }

  const own = ["A", "BUTTON"].includes(element.tagName) || element.hasAttribute("role") ? plainText(element) : "";
  if (own) return own;

  const image = element.querySelector("img[alt]");
  return squash(image?.getAttribute("alt") || element.getAttribute("placeholder") || element.getAttribute("title")
    || element.getAttribute("name") || "");
}

function effectOf(element: Element, label: string): string | null {
  if (element.tagName === "A" && element.hasAttribute("download")) return "download";

  const said = [label, element.getAttribute("name"), element.id, element.getAttribute("title")]
    .join(" ").toLowerCase().replace(/[_-]+/g, " ");
  return EFFECTS.find(([, pattern]) => pattern.test(said))?.[0] ?? null;
}

function formHasSubmitButton(form: HTMLFormElement): boolean {
  return form.querySelector("button:not([type]), button[type=submit], input[type=submit], input[type=image]") !== null;
}

export type Kind = "link" | "button" | "field" | "select" | "check" | "textarea";

export function kindOf(element: Element): Kind | null {
  const tag = element.tagName;
  if (tag === "A") return element.hasAttribute("href") ? "link" : null;
  if (tag === "BUTTON") return "button";
  if (tag === "SELECT") return "select";
  if (tag === "TEXTAREA") return "textarea";

  if (tag === "INPUT") {
    const type = (element as HTMLInputElement).type;
    if (type === "hidden") return null;
    if (BUTTON_INPUTS.has(type)) return "button";
    if (type === "checkbox" || type === "radio") return "check";
    return "field";
  }

  const role = element.getAttribute("role");
  if (role === "button") return "button";
  if (role === "link") return "link";
  return null;
}

interface Described {
  marker: string;
  control: Control;
}

function describe(element: Element, kind: Kind): Described {
  const label = clip(labelOf(element), MAX_LABEL);
  const quoted = `"${label}"`;

  if (kind === "link") {
    const href = clip((element as HTMLAnchorElement).href ?? "", MAX_HREF);
    const method = (element.getAttribute("data-method") ?? "").toLowerCase();
    return {
      marker: `tautan ${quoted} → ${href}`,
      control: { field_type: null, submits: ["post", "put", "patch", "delete"].includes(method), effect: effectOf(element, label) },
    };
  }

  if (kind === "button") {
    const form = (element as HTMLButtonElement).form ?? null;
    const type = (element as HTMLButtonElement).type;
    const submits = form !== null && (element.tagName === "BUTTON" ? type === "submit" : SUBMIT_INPUTS.has(type));
    return { marker: `tombol ${quoted}`, control: { field_type: null, submits, effect: effectOf(element, label) } };
  }

  if (isSecretField(element)) {
    return { marker: `kolom rahasia ${quoted}`, control: { field_type: "password", submits: false, effect: null } };
  }

  if (kind === "select") {
    const select = element as HTMLSelectElement;
    const options = [...select.options].slice(0, 20).map((option) => squash(option.text));
    const chosen = squash(select.selectedOptions[0]?.text ?? "");
    return {
      marker: `pilihan ${quoted} = "${clip(chosen, MAX_VALUE)}" (opsi: ${clip(options.join(", "), MAX_VALUE)})`,
      control: { field_type: "select", submits: false, effect: null },
    };
  }

  if (kind === "check") {
    const input = element as HTMLInputElement;
    const state = input.checked ? "dicentang" : "tidak dicentang";
    return {
      marker: `${input.type === "radio" ? "pilihan radio" : "kotak centang"} ${quoted} (${state})`,
      control: { field_type: input.type, submits: false, effect: null },
    };
  }

  const field = element as HTMLInputElement | HTMLTextAreaElement;
  const fieldType = kind === "textarea" ? "textarea" : (field as HTMLInputElement).type;
  const form = field.form;
  const value = squash(field.value ?? "");
  return {
    marker: `kolom ${fieldType} ${quoted}${value ? ` = "${clip(value, MAX_VALUE)}"` : ""}`,
    control: { field_type: fieldType, submits: form !== null && !formHasSubmitButton(form), effect: null },
  };
}

function isDisabled(element: Element): boolean {
  return (element as HTMLButtonElement).disabled === true || element.getAttribute("aria-disabled") === "true";
}

function isHidden(element: Element, view: Window): boolean {
  if (element.hasAttribute("hidden") || element.hasAttribute("inert") || element.getAttribute("aria-hidden") === "true") return true;
  return view.getComputedStyle(element).display === "none";
}

function isInvisible(element: Element, view: Window): boolean {
  const visibility = view.getComputedStyle(element).visibility;
  return visibility === "hidden" || visibility === "collapse";
}

class Reader {
  parts: string[] = [];
  length = 0;
  controls = new Map<number, Control>();

  constructor(private view: Window, private budget: number) {}

  get full(): boolean {
    return this.length > this.budget;
  }

  emit(text: string): void {
    this.parts.push(text);
    this.length += text.length;
  }

  walk(node: Node): void {
    if (this.full) return;

    if (node.nodeType === Node.TEXT_NODE) {
      const parent = node.parentElement;
      if (parent && !isInvisible(parent, this.view)) this.emit(node.textContent ?? "");
      return;
    }

    if (node.nodeType !== Node.ELEMENT_NODE && node.nodeType !== Node.DOCUMENT_FRAGMENT_NODE) return;

    if (node.nodeType === Node.DOCUMENT_FRAGMENT_NODE) {
      for (const child of node.childNodes) this.walk(child);
      return;
    }

    const element = node as Element;
    const tag = element.tagName.toUpperCase();
    if (SKIP.has(tag) || isHidden(element, this.view)) return;

    if (FRAMES.has(tag)) {
      this.emit(" [bingkai tidak dibaca] ");
      return;
    }

    const kind = kindOf(element);

    if (kind !== null) {
      if (!isInvisible(element, this.view)) this.control(element, kind);
      return;
    }

    const block = BLOCK.has(tag);
    if (block) this.emit("\n");

    if (tag === "SLOT") {
      for (const child of (element as HTMLSlotElement).assignedNodes({ flatten: true })) this.walk(child);
    } else {
      const root = element.shadowRoot;
      for (const child of (root ?? element).childNodes) this.walk(child);
    }

    if (block) this.emit("\n");
  }

  control(element: Element, kind: Kind): void {
    const { marker, control } = describe(element, kind);

    if (isDisabled(element)) {
      this.emit(` [${marker} nonaktif] `);
      return;
    }

    const ref = pageRefs.add(element);
    this.controls.set(ref, control);
    this.emit(` [ref ${ref}: ${marker}] `);
  }
}

function tidy(text: string): string {
  return text
    .split("\n")
    .map((line) => line.replace(/[ \t ]+/g, " ").trim())
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

const CUT = "\n[terpotong]";

/** Isi halaman sebagai observation. Rujukan lama tidak berlaku lagi setelah ini. */
export function readPage(doc: Document = document, maxChars = 20_000): Observation {
  const view = doc.defaultView ?? window;
  pageRefs.reset(doc);

  const reader = new Reader(view, maxChars * 2);
  reader.walk(doc.body ?? doc.documentElement);

  let text = redact(tidy(reader.parts.join("")));
  const points = [...text];

  if (points.length > maxChars) {
    text = tidy(points.slice(0, maxChars - CUT.length).join("")) + CUT;
  }

  // Kontrol yang tidak ikut terbaca (terpotong atau tersaring) tidak dikirim.
  const present = new Set([...text.matchAll(/\[ref (\d+): /g)].map((match) => Number(match[1])));
  pageRefs.keep(present);
  const controls: Record<string, Control> = {};
  for (const [ref, control] of reader.controls) if (present.has(ref)) controls[String(ref)] = control;

  return { ok: true, source: "page", text, host: doc.location?.hostname || null, controls };
}

export interface Reading {
  observation: Observation;
  generation: number;
}

/** Bacaan halaman beserta generation-nya. Generation tidak dikirim ke server (kunci di luar protokol). */
export function observe(doc: Document = document, maxChars = 20_000): Reading {
  const observation = readPage(doc, maxChars);
  return { observation, generation: pageRefs.generation };
}
