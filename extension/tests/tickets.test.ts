// @vitest-environment node
import { afterEach, vi } from "vitest";
import vectors from "../src/shared/vectors/tickets.json";
import { canonical, ed25519Verify, verifyTicket } from "../src/tickets";

type Case = (typeof vectors.cases)[number];

function run(item: Case) {
  const { task, device, last_seq, now } = item.context;
  return verifyTicket(item.signed, item.keys, { task, device, lastSeq: last_seq, now });
}

afterEach(() => vi.restoreAllMocks());

test("canonical bytes equal Python's json.dumps", () => {
  for (const item of vectors.canonical) {
    expect(new TextDecoder().decode(canonical(item.value))).toBe(item.canonical);
  }
});

test("numbers that are not safe integers are refused", () => {
  expect(() => canonical({ a: 1.5 })).toThrow();
  expect(() => canonical({ a: 2 ** 60 })).toThrow();
});

test.each(vectors.cases.map((item) => [item.name, item]))("WebCrypto: %s", async (_name, item) => {
  expect(await run(item as Case)).toBe(item.expect);
});

test.each(vectors.cases.map((item) => [item.name, item]))("fallback library: %s", async (_name, item) => {
  const importKey = vi.spyOn(crypto.subtle, "importKey").mockRejectedValue(
    new DOMException("Ed25519 is not supported", "NotSupportedError"));
  expect(await run(item as Case)).toBe(item.expect);
  if (item.expect === null) expect(importKey).toHaveBeenCalled();
});

test("other WebCrypto errors do not switch to the fallback", async () => {
  vi.spyOn(crypto.subtle, "importKey").mockRejectedValue(new DOMException("bad key", "DataError"));
  const valid = vectors.cases.find((item) => item.name === "valid")!;
  expect(await run(valid)).toBe("bad_signature");
});

test("ed25519Verify answers false for a wrong-length signature", async () => {
  expect(await ed25519Verify(new Uint8Array(32), new Uint8Array(10), new Uint8Array(1))).toBe(false);
});
