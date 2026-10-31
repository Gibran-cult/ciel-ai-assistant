// node --test supabase/functions/mayar-notify/notification.test.mjs
import assert from "node:assert/strict";
import { test } from "node:test";

import { candidateIds, handleWebhook, paymentUrl } from "./notification.js";

const TOKEN = "webhook-token";
const ORDER = "0123456789abcdef0123456789abcdef";
const REF = "6f8c19ff-5b97-4792-aa89-d2a12797b356";
const TX = "0b7d2a3c-1111-4222-8333-944455556666";

function received(data = { id: REF }) {
  return { event: "payment.received", data };
}

function deps(payment, overrides = {}) {
  const calls = { find: [], fetch: [], settle: [], log: [] };
  return {
    calls,
    deps: {
      token: TOKEN,
      findOrder: async (ids) => {
        calls.find.push(ids);
        return { id: ORDER, amount: 79000, provider_ref: REF };
      },
      fetchPayment: async (ref) => {
        calls.fetch.push(ref);
        return { id: ref, amount: 79000, status: "paid", ...payment };
      },
      settle: async (...args) => {
        calls.settle.push(args);
        return calls.settle.length === 1 ? "paid" : "already_paid";
      },
      log: (...args) => calls.log.push(args),
      ...overrides,
    },
  };
}

test("wrong or missing token is 403 and calls nothing", async () => {
  const { calls, deps: d } = deps({});
  for (const token of ["nope", "", null, undefined]) {
    const result = await handleWebhook(received(), token, d);
    assert.equal(result.status, 403);
  }
  assert.deepEqual([calls.find, calls.fetch, calls.settle], [[], [], []]);
});

test("membership events and bodies without a uuid are ignored without lookups", async () => {
  const { calls, deps: d } = deps({});
  for (const body of [
    { event: "membership.newMemberRegistered", data: { id: REF } },
    received({ id: "not-a-uuid" }),
    received({}),
    { event: "payment.received" },
  ]) {
    assert.deepEqual(await handleWebhook(body, TOKEN, d), { status: 200, body: "ignored" });
  }
  assert.equal(calls.find.length, 0);
  for (const body of [null, "text", 5]) {
    assert.equal((await handleWebhook(body, TOKEN, d)).status, 400);
  }
});

test("a non-uuid id never reaches findOrder", async () => {
  assert.deepEqual(candidateIds(received({ id: "x) or (1=1", transactionId: TX })), [TX]);
  assert.deepEqual(candidateIds(received({ id: REF.toUpperCase(), transactionId: REF })), [REF]);
  assert.deepEqual(candidateIds(received({ id: REF, transactionId: TX })), [REF, TX]);
  assert.deepEqual(candidateIds({}), []);
});

test("unknown payment id answers unknown", async () => {
  const { calls, deps: d } = deps({}, { findOrder: async () => null });
  assert.deepEqual(await handleWebhook(received(), TOKEN, d), { status: 200, body: "unknown" });
  assert.equal(calls.fetch.length, 0);
});

test("paid payment settles the order with Mayar's amount, not the webhook's", async () => {
  const { calls, deps: d } = deps({});
  const result = await handleWebhook(received({ id: TX, amount: 1, status: true }), TOKEN, d);
  assert.deepEqual(result, { status: 200, body: "paid" });
  assert.deepEqual(calls.find, [[TX]]);
  // The order's own ref is fetched, whichever id the webhook carried.
  assert.deepEqual(calls.fetch, [REF]);
  assert.deepEqual(calls.settle, [[ORDER, 79000, "paid"]]);
});

test("unpaid or closed payment does not settle", async () => {
  for (const status of ["unpaid", "closed", ""]) {
    const { calls, deps: d } = deps({ status });
    const result = await handleWebhook(received(), TOKEN, d);
    assert.equal(result.status, 200);
    assert.equal(calls.settle.length, 0);
  }
});

test("mayar api error is 502 so Mayar retries", async () => {
  const { calls, deps: d } = deps({}, {
    fetchPayment: async () => {
      throw new Error("mayar 500");
    },
  });
  assert.equal((await handleWebhook(received(), TOKEN, d)).status, 502);
  assert.equal(calls.settle.length, 0);
});

test("fetched id different from the order's ref is 502", async () => {
  const { calls, deps: d } = deps({ id: TX });
  assert.equal((await handleWebhook(received(), TOKEN, d)).status, 502);
  assert.equal(calls.settle.length, 0);
});

test("second delivery returns already_paid", async () => {
  const { calls, deps: d } = deps({});
  await handleWebhook(received(), TOKEN, d);
  assert.deepEqual(await handleWebhook(received(), TOKEN, d), { status: 200, body: "already_paid" });
  assert.equal(calls.settle.length, 2);
});

test("amount mismatch answers 200 and is logged", async () => {
  const { calls, deps: d } = deps({ amount: 1000 }, { settle: async () => "amount_mismatch" });
  assert.deepEqual(await handleWebhook(received(), TOKEN, d), { status: 200, body: "amount mismatch" });
  assert.ok(calls.log.some((entry) => entry[0] === "settle" && entry[2] === "amount_mismatch"));
});

test("a database error while settling is 500", async () => {
  const { deps: d } = deps({}, {
    settle: async () => {
      throw new Error("settle 503");
    },
  });
  assert.equal((await handleWebhook(received(), TOKEN, d)).status, 500);
});

test("paymentUrl picks sandbox or production host", () => {
  assert.equal(paymentUrl(REF, false), `https://api.mayar.io/hl/v2/payments/${REF}`);
  assert.equal(paymentUrl(REF, true), `https://api.mayar.id/hl/v2/payments/${REF}`);
});
