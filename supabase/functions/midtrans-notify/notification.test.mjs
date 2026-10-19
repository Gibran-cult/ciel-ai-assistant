// node --test supabase/functions/midtrans-notify/notification.test.mjs
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { test } from "node:test";

import { decide, handleNotification, sameText, sha512Hex, statusUrl } from "./notification.js";

const SERVER_KEY = "SB-Mid-server-test-key";
const ORDER = "0123456789abcdef0123456789abcdef";

function signed(fields) {
  const body = { order_id: ORDER, status_code: "200", gross_amount: "79000.00", ...fields };
  body.signature_key = createHash("sha512")
    .update(`${body.order_id}${body.status_code}${body.gross_amount}${SERVER_KEY}`)
    .digest("hex");
  return body;
}

function deps(status, overrides = {}) {
  const calls = { settle: [], mark: [], reversal: [], fetch: [] };
  return {
    calls,
    deps: {
      serverKey: SERVER_KEY,
      fetchStatus: async (orderId) => {
        calls.fetch.push(orderId);
        return { order_id: orderId, gross_amount: "79000.00", ...status };
      },
      settle: async (...args) => {
        calls.settle.push(args);
        return calls.settle.length === 1 ? "paid" : "already_paid";
      },
      mark: async (...args) => calls.mark.push(args),
      noteReversal: async (...args) => calls.reversal.push(args),
      ...overrides,
    },
  };
}

test("sha512 matches Node's implementation", async () => {
  assert.equal(await sha512Hex("abc"), createHash("sha512").update("abc").digest("hex"));
  assert.ok(sameText("abc", "abc"));
  assert.ok(!sameText("abc", "abd"));
  assert.ok(!sameText("abc", "ab"));
});

test("settlement settles once, re-sent notifications are idempotent", async () => {
  const { calls, deps: d } = deps({ transaction_status: "settlement" });
  const first = await handleNotification(signed({ transaction_status: "settlement" }), d);
  const again = await handleNotification(signed({ transaction_status: "settlement" }), d);

  assert.deepEqual([first.status, first.body], [200, "paid"]);
  assert.deepEqual([again.status, again.body], [200, "already_paid"]);
  // The amount comes from the Status API, as a number for the SQL function.
  assert.deepEqual(calls.settle[0], [ORDER, 79000, "settlement"]);
});

test("the Status API decides, not the notification body", async () => {
  // Notification claims settlement, Midtrans says pending: nothing is settled.
  const { calls, deps: d } = deps({ transaction_status: "pending" });
  const result = await handleNotification(signed({ transaction_status: "settlement" }), d);
  assert.deepEqual([result.status, result.body], [200, "pending"]);
  assert.equal(calls.settle.length, 0);
  assert.deepEqual(calls.fetch, [ORDER]);
});

test("forged or tampered notifications are refused before any lookup", async () => {
  const { calls, deps: d } = deps({ transaction_status: "settlement" });
  const forged = signed({ transaction_status: "settlement" });
  forged.gross_amount = "1.00"; // signature no longer matches
  assert.equal((await handleNotification(forged, d)).status, 403);

  const wrongKey = { ...signed({}), signature_key: "00".repeat(64) };
  assert.equal((await handleNotification(wrongKey, d)).status, 403);
  assert.equal(calls.fetch.length, 0);
  assert.equal(calls.settle.length, 0);
});

test("malformed bodies are 400 and foreign order ids are ignored", async () => {
  const { calls, deps: d } = deps({ transaction_status: "settlement" });
  assert.equal((await handleNotification(null, d)).status, 400);
  assert.equal((await handleNotification({ order_id: ORDER }, d)).status, 400);

  const foreign = signed({ order_id: "payment_notif_test_G123" });
  assert.deepEqual(await handleNotification(foreign, d), { status: 200, body: "ignored" });
  assert.equal(calls.fetch.length, 0);
});

test("failed payments are recorded, never settled", async () => {
  for (const status of ["expire", "cancel", "deny", "failure"]) {
    const { calls, deps: d } = deps({ transaction_status: status });
    const result = await handleNotification(signed({ transaction_status: status }), d);
    assert.deepEqual([result.status, result.body], [200, status]);
    assert.deepEqual(calls.mark, [[ORDER, status]]);
    assert.equal(calls.settle.length, 0);
  }
});

test("card capture needs fraud_status accept", () => {
  assert.equal(decide({ transaction_status: "capture", fraud_status: "accept" }).action, "settle");
  assert.equal(decide({ transaction_status: "capture", fraud_status: "challenge" }).action, "wait");
  assert.equal(decide({ transaction_status: "refund" }).action, "reversed");
  assert.equal(decide({}).action, "wait");
});

test("temporary failures ask Midtrans to retry; amount mismatch does not", async () => {
  const down = deps({}, { fetchStatus: async () => { throw new Error("timeout"); } });
  assert.equal((await handleNotification(signed({}), down.deps)).status, 502);

  const other = deps({ transaction_status: "settlement", order_id: "f".repeat(32) });
  other.deps.fetchStatus = async () => ({ order_id: "f".repeat(32), transaction_status: "settlement" });
  assert.equal((await handleNotification(signed({}), other.deps)).status, 502);

  const dbDown = deps({ transaction_status: "settlement" }, { settle: async () => { throw new Error("503"); } });
  assert.equal((await handleNotification(signed({}), dbDown.deps)).status, 500);

  const mismatch = deps({ transaction_status: "settlement" }, { settle: async () => "amount_mismatch" });
  assert.deepEqual(await handleNotification(signed({}), mismatch.deps), { status: 200, body: "amount mismatch" });
});

test("status URL follows the environment", () => {
  assert.equal(statusUrl(ORDER, false), `https://api.sandbox.midtrans.com/v2/${ORDER}/status`);
  assert.equal(statusUrl(ORDER, true), `https://api.midtrans.com/v2/${ORDER}/status`);
});
