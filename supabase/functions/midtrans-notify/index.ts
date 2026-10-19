// Supabase Edge Function: notifikasi pembayaran Midtrans untuk Ciel Pro.
// Deploy tanpa verifikasi JWT (Midtrans tidak mengirim token Supabase); yang
// mengamankan adalah signature dan Status API di notification.js:
//
//   npx supabase functions deploy midtrans-notify --project-ref <ref> --no-verify-jwt
//
// Secrets function: MIDTRANS_SERVER_KEY, MIDTRANS_PRODUCTION ("true" untuk
// produksi). SUPABASE_URL dan SUPABASE_SERVICE_ROLE_KEY sudah disediakan Supabase.

import { handleNotification, statusUrl } from "./notification.js";

const serverKey = Deno.env.get("MIDTRANS_SERVER_KEY") ?? "";
const production = (Deno.env.get("MIDTRANS_PRODUCTION") ?? "").toLowerCase() === "true";
const supabaseUrl = (Deno.env.get("SUPABASE_URL") ?? "").replace(/\/$/, "");
const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";

const database = {
  apikey: serviceKey,
  Authorization: `Bearer ${serviceKey}`,
  "Content-Type": "application/json",
};

async function fetchStatus(orderId: string) {
  const response = await fetch(statusUrl(orderId, production), {
    headers: { Accept: "application/json", Authorization: `Basic ${btoa(`${serverKey}:`)}` },
  });
  if (!response.ok) {
    throw new Error(`status api ${response.status}`);
  }
  return await response.json();
}

async function settle(orderId: string, gross: number, status: string) {
  const response = await fetch(`${supabaseUrl}/rest/v1/rpc/ciel_settle_order`, {
    method: "POST",
    headers: database,
    body: JSON.stringify({ p_order_id: orderId, p_gross_amount: gross, p_midtrans_status: status }),
  });
  if (!response.ok) {
    throw new Error(`settle ${response.status}`);
  }
  return await response.json();
}

async function patchOrder(orderId: string, filter: string, fields: Record<string, string>) {
  const response = await fetch(`${supabaseUrl}/rest/v1/pro_orders?id=eq.${orderId}${filter}`, {
    method: "PATCH",
    headers: { ...database, Prefer: "return=minimal" },
    body: JSON.stringify({ ...fields, updated_at: new Date().toISOString() }),
  });
  if (!response.ok) {
    throw new Error(`patch ${response.status}`);
  }
}

Deno.serve(async (request) => {
  if (request.method !== "POST") {
    return new Response("method not allowed", { status: 405 });
  }
  if (!serverKey || !supabaseUrl || !serviceKey) {
    console.error("midtrans_notify config missing");
    return new Response("not configured", { status: 503 });
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return new Response("bad request", { status: 400 });
  }

  const result = await handleNotification(body, {
    serverKey,
    fetchStatus,
    settle,
    // Order yang sudah lunas tidak pernah diturunkan statusnya.
    mark: (orderId: string, status: string) =>
      patchOrder(orderId, "&status=neq.paid", { status, midtrans_status: status }),
    noteReversal: (orderId: string, status: string) =>
      patchOrder(orderId, "", { midtrans_status: status }),
    log: (...args: unknown[]) => console.log("midtrans_notify", ...args),
  });

  return new Response(result.body, { status: result.status });
});
