// Logika webhook pembayaran Mayar untuk Ciel Pro, tanpa API khusus Deno,
// supaya bisa dites dengan Node (notification.test.mjs). index.ts hanya
// menyambungkannya ke Deno.serve, Mayar, dan Supabase.
//
// Webhook Mayar tidak ditandatangani, jadi isinya hanya petunjuk order mana
// yang perlu dicek. Urutan pengecekan:
// 1. Token di URL webhook sama dengan MAYAR_WEBHOOK_TOKEN (menyaring kiriman
//    sembarangan sebelum memanggil API Mayar).
// 2. Event payment.received (atau tanpa event: "Cek lagi" dari app) dan id
//    berbentuk UUID; hanya UUID yang masuk ke filter database.
// 3. Order Ciel dicari lewat provider_ref atau provider_tx.
// 4. Payment request order itu diambil ulang dari API Mayar dengan API key;
//    hanya status "paid" dari sana yang melunasi, dengan nominal dari sana.
// 5. Lunas -> ciel_settle_order (idempoten, cek nominal, tambah Pro 30 hari).
//
// Kode respons: 2xx berarti selesai; 403 untuk token salah; 5xx untuk
// gangguan sementara (API Mayar, database) supaya bisa dicoba lagi.

import { sameText } from "../midtrans-notify/notification.js";

export const PAYMENT_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function paymentUrl(id, production) {
  const host = production ? "https://api.mayar.id" : "https://api.mayar.io";
  return `${host}/hl/v2/payments/${id}`;
}

// UUID unik dari data.id, data.transactionId, dan data.productId (huruf kecil).
// Webhook payment.received asli (sandbox 2026-10-31): id = transactionId =
// transaksi baru yang dibuat saat membayar, productId = id payment request
// (provider_ref). "Cek lagi" dari app mengirim provider_ref sebagai data.id.
export function candidateIds(body) {
  const data = (body && typeof body.data === "object" && body.data) || {};
  const ids = [data.id, data.transactionId, data.productId]
    .filter((value) => typeof value === "string" && PAYMENT_ID.test(value))
    .map((value) => value.toLowerCase());
  return [...new Set(ids)];
}

const reply = (status, text) => ({ status, body: text });

// deps: { token, findOrder(ids), fetchPayment(ref), settle(orderId, amount, status), log(...args) }
export async function handleWebhook(body, token, deps) {
  const log = deps.log || (() => {});

  if (!sameText(String(token ?? ""), deps.token) || !deps.token) {
    log("bad_token");
    return reply(403, "forbidden");
  }
  if (!body || typeof body !== "object") {
    return reply(400, "bad request");
  }
  if (body.event !== undefined && body.event !== "payment.received") {
    return reply(200, "ignored");
  }

  const ids = candidateIds(body);
  if (ids.length === 0) {
    log("ignored_payment_id");
    return reply(200, "ignored");
  }

  let order;
  try {
    order = await deps.findOrder(ids);
  } catch (error) {
    log("database_error", String(error));
    return reply(500, "database error");
  }
  if (!order) {
    log("unknown_payment", ids.join(","));
    return reply(200, "unknown");
  }

  let payment;
  try {
    payment = await deps.fetchPayment(order.provider_ref);
  } catch (error) {
    log("mayar_api_error", order.id, String(error));
    return reply(502, "payment unavailable");
  }

  if (String(payment?.id || "").toLowerCase() !== String(order.provider_ref).toLowerCase()) {
    log("payment_mismatch", order.id);
    return reply(502, "payment mismatch");
  }

  if (payment.status !== "paid") {
    log("wait", order.id, payment.status);
    return reply(200, String(payment.status || "unknown"));
  }

  try {
    const result = await deps.settle(order.id, Number(payment.amount), "paid");
    log("settle", order.id, result);
    if (result === "amount_mismatch") {
      // Jangan diulang: perlu dicek manual (nominal di Mayar beda dengan order).
      return reply(200, "amount mismatch");
    }
    return reply(200, String(result));
  } catch (error) {
    log("database_error", order.id, String(error));
    return reply(500, "database error");
  }
}
