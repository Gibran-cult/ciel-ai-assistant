import vectors from "../src/shared/vectors/secrets.json";
import { findSecrets, redact } from "../src/content/redact";

test.each(vectors.map((item) => [item.text, item]))("same spans as Python: %s", (_text, item) => {
  expect(findSecrets(item.text)).toEqual(item.spans);
});

test.each(vectors.map((item) => [item.text, item]))("redacts like Python: %s", (_text, item) => {
  // Posisi dari Python dihitung per code point.
  const points = [...item.text];
  let expected = "";
  let at = 0;

  for (const [start, end] of item.spans as [number, number, string][]) {
    expected += points.slice(at, start).join("") + "[disaring]";
    at = end;
  }

  expect(redact(item.text)).toBe(expected + points.slice(at).join(""));
});

test("text without secrets is unchanged", () => {
  expect(redact("Kaos polos Rp49.000, kode pos 40115")).toBe("Kaos polos Rp49.000, kode pos 40115");
});
