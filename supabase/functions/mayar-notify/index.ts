// Supabase Edge Function: webhook pembayaran Mayar untuk Ciel Pro.
// Deploy tanpa verifikasi JWT (Mayar tidak mengirim token Supabase); yang
// mengamankan adalah token di URL dan pengecekan ulang ke API Mayar di
// notification.js:
//
//   npx supabase functions deploy mayar-notify --project-ref <ref> --no-verify-jwt
//
// URL webhook di dashboard Mayar:
//   https://<ref>.supabase.co/functions/v1/mayar-notify?token=<MAYAR_WEBHOOK_TOKEN>
//
// Secrets function: MAYAR_API_KEY, MAYAR_PRODUCTION ("true" untuk produksi),
// MAYAR_WEBHOOK_TOKEN. SUPABASE_URL dan SUPABASE_SERVICE_ROLE_KEY sudah
// disediakan Supabase.

import { handleWebhook, paymentUrl } from "./notification.js";

const apiKey = Deno.env.get("MAYAR_API_KEY") ?? "";
const production = (Deno.env.get("MAYAR_PRODUCTION") ?? "").toLowerCase() === "true";
const webhookToken = Deno.env.get("MAYAR_WEBHOOK_TOKEN") ?? "";
const supabaseUrl = (Deno.env.get("SUPABASE_URL") ?? "").replace(/\/$/, "");
const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";

// Batas tiap panggilan keluar. Timeout dilempar sebagai error biasa, jadi
// notification.js menjawab 5xx dan Mayar (atau "Cek lagi") mencoba lagi;
// settle yang ternyata sudah tersimpan dijawab already_paid saat diulang.
const TIMEOUT_MS = 10_000;

const database = {
  apikey: serviceKey,
  Authorization: `Bearer ${serviceKey}`,
  "Content-Type": "application/json",
};

// ids sudah divalidasi sebagai UUID oleh notification.js sebelum sampai sini.
async function findOrder(ids: string[]) {
  const list = ids.join(",");
  const query = `select=id,amount,provider_ref&provider=eq.mayar` +
    `&or=(provider_ref.in.(${list}),provider_tx.in.(${list}))&limit=1`;
  const response = await fetch(`${supabaseUrl}/rest/v1/pro_orders?${query}`, {
    headers: database,
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
  if (!response.ok) {
    throw new Error(`find ${response.status}`);
  }
  const rows = await response.json();
  return rows[0] ?? null;
}

async function fetchPayment(ref: string) {
  const response = await fetch(paymentUrl(ref, production), {
    headers: { Accept: "application/json", Authorization: `Bearer ${apiKey}` },
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
  if (!response.ok) {
    throw new Error(`mayar api ${response.status}`);
  }
  return (await response.json()).data;
}

async function settle(orderId: string, amount: number, status: string) {
  const response = await fetch(`${supabaseUrl}/rest/v1/rpc/ciel_settle_order`, {
    method: "POST",
    headers: database,
    body: JSON.stringify({ p_order_id: orderId, p_gross_amount: amount, p_midtrans_status: status }),
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
  if (!response.ok) {
    throw new Error(`settle ${response.status}`);
  }
  return await response.json();
}

Deno.serve(async (request) => {
  if (request.method !== "POST") {
    return new Response("method not allowed", { status: 405 });
  }
  if (!apiKey || !webhookToken || !supabaseUrl || !serviceKey) {
    console.error("mayar_notify config missing");
    return new Response("not configured", { status: 503 });
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return new Response("bad request", { status: 400 });
  }

  const result = await handleWebhook(body, new URL(request.url).searchParams.get("token"), {
    token: webhookToken,
    findOrder,
    fetchPayment,
    settle,
    log: (...args: unknown[]) => console.log("mayar_notify", ...args),
  });

  return new Response(result.body, { status: result.status });
});
