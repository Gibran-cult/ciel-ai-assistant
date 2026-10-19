// Logika notifikasi pembayaran Midtrans untuk Ciel Pro, tanpa API khusus Deno,
// supaya bisa dites dengan Node (notification.test.mjs). index.ts hanya
// menyambungkannya ke Deno.serve, Midtrans, dan Supabase.
//
// Urutan pengecekan:
// 1. Badan permintaan lengkap dan order_id berbentuk ID Ciel (32 hex).
// 2. signature_key = sha512(order_id + status_code + gross_amount + server key).
// 3. Status diambil ulang dari Status API Midtrans; isi notifikasi tidak
//    dipakai untuk memutuskan lunas.
// 4. Lunas -> ciel_settle_order (database: idempoten, cek nominal, tambah
//    Pro 30 hari). Gagal/kedaluwarsa -> status order dicatat.
//
// Kode respons: 2xx berarti Midtrans berhenti mengirim ulang. Notifikasi
// palsu atau rusak dijawab 4xx; gangguan sementara (Status API, database)
// dijawab 5xx supaya Midtrans mencoba lagi.

export const ORDER_ID = /^[0-9a-f]{32}$/;
const FAILED = new Set(["deny", "cancel", "expire", "failure"]);
const REVERSED = new Set(["refund", "partial_refund", "chargeback", "partial_chargeback"]);

export async function sha512Hex(text) {
  const digest = await crypto.subtle.digest("SHA-512", new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

// Perbandingan dengan waktu tetap, supaya signature tidak bisa ditebak per karakter.
export function sameText(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) {
    return false;
  }
  let diff = 0;
  for (let i = 0; i < a.length; i += 1) {
    diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return diff === 0;
}

export async function validSignature(body, serverKey) {
  const expected = await sha512Hex(
    `${body.order_id}${body.status_code}${body.gross_amount}${serverKey}`,
  );
  return sameText(String(body.signature_key || "").toLowerCase(), expected);
}

// Status dari Status API -> apa yang dilakukan.
export function decide(status) {
  const transaction = String(status.transaction_status || "");
  const fraud = String(status.fraud_status || "accept");

  if (transaction === "settlement" || (transaction === "capture" && fraud === "accept")) {
    return { action: "settle", status: transaction };
  }
  if (FAILED.has(transaction)) {
    return { action: "mark", status: transaction };
  }
  if (REVERSED.has(transaction)) {
    return { action: "reversed", status: transaction };
  }
  // pending, authorize, capture dengan challenge: tunggu notifikasi berikutnya.
  return { action: "wait", status: transaction || "unknown" };
}

export function statusUrl(orderId, production) {
  const host = production ? "https://api.midtrans.com" : "https://api.sandbox.midtrans.com";
  return `${host}/v2/${orderId}/status`;
}

const reply = (status, text) => ({ status, body: text });

// deps: { serverKey, fetchStatus(orderId), settle(orderId, gross, status),
//         mark(orderId, status), noteReversal(orderId, status), log(...args) }
export async function handleNotification(body, deps) {
  const log = deps.log || (() => {});

  if (!body || typeof body !== "object") {
    return reply(400, "bad request");
  }
  for (const field of ["order_id", "status_code", "gross_amount", "signature_key"]) {
    if (body[field] === undefined || body[field] === null || body[field] === "") {
      return reply(400, "bad request");
    }
  }
  if (!ORDER_ID.test(String(body.order_id))) {
    // Bukan order Ciel (mis. tes dari dashboard Midtrans): terima tanpa tindakan.
    log("ignored_order_id");
    return reply(200, "ignored");
  }
  if (!(await validSignature(body, deps.serverKey))) {
    log("bad_signature", body.order_id);
    return reply(403, "invalid signature");
  }

  let status;
  try {
    status = await deps.fetchStatus(body.order_id);
  } catch (error) {
    log("status_api_error", body.order_id, String(error));
    return reply(502, "status unavailable");
  }

  if (String(status.order_id || "") !== body.order_id) {
    log("status_order_mismatch", body.order_id);
    return reply(502, "status mismatch");
  }

  const decision = decide(status);

  try {
    if (decision.action === "settle") {
      const result = await deps.settle(body.order_id, Number(status.gross_amount), decision.status);
      log("settle", body.order_id, result);
      if (result === "amount_mismatch") {
        // Jangan diulang: perlu dicek manual (nominal di Midtrans beda dengan order).
        return reply(200, "amount mismatch");
      }
      return reply(200, String(result));
    }
    if (decision.action === "mark") {
      await deps.mark(body.order_id, decision.status);
      log("mark", body.order_id, decision.status);
      return reply(200, decision.status);
    }
    if (decision.action === "reversed") {
      // Refund/chargeback: dicatat; pencabutan Pro diputuskan pengelola.
      await deps.noteReversal(body.order_id, decision.status);
      log("reversed", body.order_id, decision.status);
      return reply(200, decision.status);
    }
  } catch (error) {
    log("database_error", body.order_id, String(error));
    return reply(500, "database error");
  }

  log("wait", body.order_id, decision.status);
  return reply(200, decision.status);
}
