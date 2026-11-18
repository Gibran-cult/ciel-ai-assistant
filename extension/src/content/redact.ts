// Penyaring rahasia. Salinan find_secrets di guard/risk.py, diuji dengan
// vektor yang dibuat dari kode Python itu (src/shared/vectors/secrets.json).
//
// Python menghitung posisi per code point dan \d-nya mencakup semua angka
// Unicode. Di sini teks diubah ke daftar code point dulu, dan regex memakai
// flag u dengan \p{Nd}, supaya hasilnya sama persis.

export type SecretKind = "card" | "api_key" | "token";
export type SecretSpan = [start: number, end: number, kind: SecretKind];

const DIGIT_RUN = /\p{Nd}+(?:[^A-Za-z0-9]{1,2}\p{Nd}+)*/gu;
const DIGITS = /\p{Nd}+/gu;
const TOKEN = /(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{19,}(?![A-Za-z0-9_-])/gu;
const KEY_PREFIXES = ["sk-", "ghp_", "gho_", "github_pat_", "xoxb-", "xoxp-", "AKIA", "AIza"];
const ND = /\p{Nd}/u;

// Angka Unicode (kategori Nd) selalu berupa blok 0 sampai 9 yang berurutan,
// jadi nilainya adalah jarak dari awal deretan, modulo 10.
function digitValue(char: string): number {
  const code = char.codePointAt(0)!;
  let start = code;
  while (ND.test(String.fromCodePoint(start - 1))) start -= 1;
  return (code - start) % 10;
}

function luhnOk(digits: string[]): boolean {
  let total = 0;

  digits.slice().reverse().forEach((char, index) => {
    let value = digitValue(char);
    if (index % 2) value = value * 2 - (value > 4 ? 9 : 0);
    total += value;
  });

  return total % 10 === 0;
}

// Posisi UTF-16 dari regex menjadi posisi code point.
function pointIndex(text: string): (utf16: number) => number {
  const map = new Map<number, number>();
  let point = 0;

  for (let unit = 0; unit < text.length; point++) {
    map.set(unit, point);
    unit += text.codePointAt(unit)! > 0xffff ? 2 : 1;
  }

  map.set(text.length, point);
  return (utf16) => map.get(utf16)!;
}

function cardSpans(text: string, at: (utf16: number) => number): SecretSpan[] {
  const spans: SecretSpan[] = [];

  for (const run of text.matchAll(DIGIT_RUN)) {
    const groups = [...run[0].matchAll(DIGITS)].map((match) => ({
      start: at(run.index + match.index),
      end: at(run.index + match.index + match[0].length),
      digits: [...match[0]],
    }));
    let index = 0;

    while (index < groups.length) {
      let hit: number | null = null;

      // Paling banyak 19 kelompok, karena kartu paling panjang 19 digit.
      for (let end = Math.min(groups.length, index + 19); end > index; end--) {
        const digits = groups.slice(index, end).flatMap((group) => group.digits);

        if (digits.length >= 13 && digits.length <= 19 && luhnOk(digits)) {
          hit = end;
          break;
        }
      }

      if (hit === null) {
        index += 1;
      } else {
        spans.push([groups[index]!.start, groups[hit - 1]!.end, "card"]);
        index = hit;
      }
    }
  }

  return spans;
}

function keyKind(token: string): SecretKind | null {
  if (KEY_PREFIXES.some((prefix) => token.startsWith(prefix))) return "api_key";

  const count = (pattern: RegExp) => (token.match(pattern) ?? []).length;

  if (token.length >= 32 && count(/[0-9]/g) >= 6 && count(/[A-Z]/g) >= 4 && count(/[a-z]/g) >= 4) return "token";
  return null;
}

function compare(a: SecretSpan, b: SecretSpan): number {
  return a[0] - b[0] || a[1] - b[1] || (a[2] < b[2] ? -1 : a[2] > b[2] ? 1 : 0);
}

/** Letak rahasia di dalam teks, per code point, urut dari kiri, tanpa tumpang tindih. */
export function findSecrets(text: string): SecretSpan[] {
  if (typeof text !== "string") return [];

  const at = pointIndex(text);
  const found = cardSpans(text, at);

  for (const match of text.matchAll(TOKEN)) {
    const kind = keyKind(match[0]);
    if (kind) found.push([at(match.index), at(match.index + match[0].length), kind]);
  }

  const spans: SecretSpan[] = [];

  for (const span of found.sort(compare)) {
    if (spans.length === 0 || span[0] >= spans[spans.length - 1]![1]) spans.push(span);
  }

  return spans;
}

/** Teks dengan setiap rahasia diganti "[disaring]". Dipanggil sebelum teks apa pun keluar dari tab. */
export function redact(text: string): string {
  const points = [...text];
  let out = "";
  let at = 0;

  for (const [start, end] of findSecrets(text)) {
    out += points.slice(at, start).join("") + "[disaring]";
    at = end;
  }

  return out + points.slice(at).join("");
}
