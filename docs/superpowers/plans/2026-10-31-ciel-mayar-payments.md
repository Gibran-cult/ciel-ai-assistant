# Ciel Pro via Mayar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users buy Ciel Pro (Rp79.000 = 30 days) through Mayar while Midtrans stays blocked, without removing the Midtrans path.

**Architecture:** `PAYMENT_PROVIDER` picks Midtrans or Mayar at checkout. Mayar checkout creates a Single Payment Request (`POST /hl/v2/payments/create`), and its ids are stored on the `pro_orders` row. A new Edge Function `mayar-notify` treats each webhook only as a hint about which order to check. It re-reads that payment from Mayar's API with our key, and only then calls the existing `ciel_settle_order`. That re-read is the security, because Mayar webhooks are unsigned. The Pricing "Cek lagi" button sends the same hint, which recovers a lost webhook.

**Tech Stack:** Python 3.14 / Streamlit (app.py, payments.py, chat_store.py), Supabase Postgres + Edge Functions (Deno, logic in plain JS tested with `node --test`), Mayar API v2.

**Spec:** No separate spec. This plan's Context section is the spec, written from Ciel's request of 2026-10-31.

## Context (findings, 2026-10-31)

- **Midtrans dashboard:** Business review has been "In progress" since 2026-10-19, and no payment method is active (every card still shows "Select").
- **Midtrans emails:**
  - 2026-10-29 "Need correction": GoPay QRIS Aggregator needs an NPWP.
  - 2026-10-30 "Hasil Pengajuan Aktivasi": GoPay QRIS Aggregator "tidak dapat kami lanjutkan, sesuai dengan regulasi penyedia jasa pembayaran".
  - 2026-10-30 "Payment Method Activation": the request was not granted. Ciel may re-apply for other methods, or ask support@midtrans.com.
- **Mayar** (docs.mayar.id):
  - An "Individual" account verifies with KTP + a selfie holding the KTP, with no NPWP or NIB.
  - Channel fees: QRIS 0,7%, VA Rp 4.000, e-wallet 1,5%.
  - Pay Request admin fee: 1,5% (Starter) / 1% / 0%.
  - Withdrawal: Rp 2.775 flat.
  - API v2: create `POST https://api.mayar.id/hl/v2/payments/create` (sandbox `https://api.mayar.io/...`), Bearer key; it returns `data.id`, `data.transactionId` and `data.link`.
  - Detail: `GET /hl/v2/payments/{id}` returns `data.status` (`unpaid`/`paid`/`closed`) and `data.amount`.
  - Webhook event `payment.received` carries **no signature**.
- **Tripay** (backup option): personal account needs a KTP only (third-party source; unverified). QRIS fee is Rp 750 + 0,7%. Callbacks are signed with HMAC-SHA256 (`X-Callback-Signature`). Tripay is not used in this plan.
- **Unconfirmed reason for the rejection.** The 2026-10-21 correction asked specifically about the product "Riset Skripsi". Any provider may read that name as a *joki* service. Every registration text must describe Ciel as it is: a research and citation tool that finds sources and checks citations. It does not write chapters for the user and does not evade AI detectors.

## Global Constraints

- Price stays `PRO_PRICE` from `pricing.PLANS` (Rp79.000). The buyer pays exactly that amount, and Mayar fees are borne by Ciel. `ciel_settle_order` compares the amount, so "pass fee to customer" in Mayar must stay **off**.
- A sandbox key must never reach the public app. `MAYAR_PRODUCTION = "true"` goes in app secrets and function secrets only together with a production key.
- The Midtrans code path, the `midtrans-notify` function and its secrets stay as they are. Rollback means setting `PAYMENT_PROVIDER = "midtrans"` (or removing `MAYAR_API_KEY`).
- User-facing copy is in Indonesian and follows [[ui-anti-slop-review-before-commit]]. No commit happens until Ciel has checked it in their own browser and said "commit".
- No Claude attribution lines in commits or PRs.
- Order ids stay 32 hex (`payments.new_order_id`). Mayar ids are UUIDs and are checked with `/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i` before they reach any PostgREST filter.

## Review Focus

1. **Forged webhook** (anyone can POST to the function): Pro is granted only when `GET /payments/{provider_ref}` with our key says `paid` and the amount equals the order. A wrong or missing `?token=` gets 403 before any Mayar call. Pinned in Task 4.
2. **Lost or late webhook** (Mayar retry behaviour is undocumented): the "Cek lagi" button pokes the function with the order's `provider_ref`, so a paid buyer is never stuck pending. Pinned in Task 5.
3. **Webhook for something that is not a Ciel order** (Mayar membership events, dashboard test, unknown id): the function answers 200 "ignored" or "unknown", writes nothing, and puts no unvalidated id into a filter. Pinned in Task 4.
4. **Duplicate `payment.received`**: the second settle returns `already_paid`, and Pro is extended only once (this already holds in SQL). Pinned in Task 4 as a two-call test.
5. **Mayar create succeeds but saving the refs fails**: no payment link is shown, because a payment that cannot be matched could never be settled. Pinned in Task 5.

---

### Task 0: Accounts and keys (Ciel, manual, no code)

- [ ] **Step 1:** Register at mayar.id as **Individual** (KTP + selfie). For the business description, reuse the "Penjelasan Produk Riset Skripsi" text sent to Midtrans on 2026-10-27, and open it with: "Ciel adalah asisten riset dan pengecek kutipan; tidak menulis bab untuk pengguna."
- [ ] **Step 2:** In Mayar settings, keep channel fee and admin fee borne by the merchant.
- [ ] **Step 3:** Copy the **sandbox** API key (sandbox dashboard linked from docs.mayar.id/api-reference-v2/introduction) into `.streamlit/secrets.toml` as `MAYAR_API_KEY`, above `[auth]`. Generate the webhook token with `python -c "import secrets;print(secrets.token_urlsafe(32))"` and save it as `MAYAR_WEBHOOK_TOKEN`.
- [ ] **Step 4 (optional, parallel):** Claude drafts a short email to support@midtrans.com. It asks (a) whether the business review can continue for VA methods, which need only the owner's KTP, and (b) the exact reason GoPay QRIS Aggregator was refused. Ciel reviews it and sends it from Gmail.

### Task 1: Spike — capture a real sandbox webhook

**Files:** none committed. Notes go into this plan under "Spike result".

- [ ] **Step 1:** Create one sandbox payment request (`amount: 79000`, `name: "Ciel Pro 30 hari"`, `redirectUrl` = local Pricing, `expiredAt` = now + 60 min, ISO 8601 UTC).

```bash
python -c "import toml,requests,datetime as d; k=toml.load('.streamlit/secrets.toml')['MAYAR_API_KEY']; e=(d.datetime.now(d.timezone.utc)+d.timedelta(minutes=60)).isoformat(timespec='seconds').replace('+00:00','Z'); r=requests.post('https://api.mayar.io/hl/v2/payments/create',headers={'Authorization':'Bearer '+k},json={'name':'Ciel Pro 30 hari','amount':79000,'email':'test@example.com','redirectUrl':'http://localhost:8501/?page=pricing','expiredAt':e},timeout=20); print(r.status_code, r.json())"
```

Expected: `200` with `data.id`, `data.transactionId` and `data.link`.

- [ ] **Step 2:** Point a sandbox webhook at a request bin (Mayar "Register URL Hook" v2), pay the link in sandbox, and record the raw body. Record: the `event` field name, whether `data.id` equals the create response's `id` or its `transactionId`, and the paid `GET /payments/{id}` response (`status`, `amount`).
- [ ] **Step 3:** Write the three answers under "Spike result" at the end of this file. If `data.id` matches neither create id, stop and re-plan Task 4's matching.

### Task 2: Order table knows its provider

**Files:**
- Modify: `docs/chat_store.sql:76-140`
- Test: Supabase SQL via MCP `execute_sql` on project `nibbamicnqdxtmaacrio`

**Interfaces:**
- Produces: `pro_orders.provider text not null default 'midtrans'`, `pro_orders.provider_ref text`, `pro_orders.provider_tx text`; unique partial indexes on `provider_ref` and `provider_tx` (where not null); `ciel_settle_order` writes `pro_members.source = paid_order.provider`. The signature `(text, numeric, text)` is unchanged.

- [ ] **Step 1:** Check that `pro_members.source` has no check constraint: `select conname, pg_get_constraintdef(oid) from pg_constraint where conrelid = 'public.pro_members'::regclass;`. Expected: no constraint on `source`. If one exists, extend it to allow `'mayar'` in Step 2.
- [ ] **Step 2:** Add the `alter table ... add column if not exists` lines and the two `create unique index if not exists` lines after the `pro_orders` table. In `ciel_settle_order`, replace both `'midtrans'` literals with `paid_order.provider`. Update the comment to say that `midtrans_status` holds the gateway status for either provider (kept to avoid renaming a live column).
- [ ] **Step 3:** Apply it to production with MCP `apply_migration` (name `pro_orders_provider`). Ciel approves the migration call.
- [ ] **Step 4:** Verify by inserting a throwaway order and settling it inside one transaction, then rolling back:

```sql
begin;
insert into pro_orders (id, owner, amount, provider) values ('ffffffffffffffffffffffffffffffff', 'test0000test0000', 79000, 'mayar');
select ciel_settle_order('ffffffffffffffffffffffffffffffff', 79000, 'paid');            -- expect 'paid'
select source from pro_members where owner = 'test0000test0000';                          -- expect 'mayar'
select ciel_settle_order('ffffffffffffffffffffffffffffffff', 79000, 'paid');            -- expect 'already_paid'
rollback;
```

- [ ] **Step 5:** Commit `docs/chat_store.sql` with "Record the payment provider on Pro orders".

### Task 3: Mayar client and order refs

**Files:**
- Modify: `payments.py`, `chat_store.py:290-324`
- Test: `tests/test_payments.py`

**Interfaces:**
- Produces in `payments.py`:
  - `MAYAR_URLS = {False: "https://api.mayar.io/hl/v2", True: "https://api.mayar.id/hl/v2"}`
  - `mayar_payload(order_id: str, amount: int, redirect_url: str, email: str | None = None, now: float | None = None) -> dict`
  - `create_mayar_payment(api_key: str, production: bool, payload: dict) -> dict | None`, which returns `{"ref": data.id, "tx": data.transactionId, "url": data.link}`
  - `poke_mayar_notify(supabase_url: str, token: str, ref: str) -> bool`
- Produces in `chat_store.ChatStore`:
  - `create_order(owner, order_id, amount, provider="midtrans")`
  - `attach_order_ref(owner, order_id, ref, tx) -> bool`
  - `load_latest_order(owner)` now also returns `"provider"` and `"ref"`

- [ ] **Step 1: Write the failing tests** in a new `MayarTest` class:

```python
def test_mayar_payload_is_pro_30_days_with_a_60_minute_expiry(self):
    p = payments.mayar_payload(ORDER, 79_000, "https://ciel.example/?page=pricing", email="a@example.com", now=0)
    self.assertEqual(p["name"], "Ciel Pro 30 hari")
    self.assertEqual(p["amount"], 79_000)
    self.assertEqual(p["redirectUrl"], "https://ciel.example/?page=pricing")
    self.assertEqual(p["expiredAt"], "1970-01-01T01:00:00Z")
    self.assertIn(ORDER, p["description"])
    self.assertEqual(p["email"], "a@example.com")
    self.assertNotIn("email", payments.mayar_payload(ORDER, 79_000, "u", now=0))

def test_mayar_create_uses_bearer_key_and_environment(self):
    body = {"statusCode": 200, "data": {"id": "R", "transactionId": "T", "link": "https://pay.example/x"}}
    with patch("requests.post", return_value=Response(body)) as post:
        self.assertEqual(payments.create_mayar_payment("k", False, {}), {"ref": "R", "tx": "T", "url": "https://pay.example/x"})
        payments.create_mayar_payment("k", True, {})
    sandbox, production = post.call_args_list
    self.assertEqual(sandbox.args[0], "https://api.mayar.io/hl/v2/payments/create")
    self.assertEqual(production.args[0], "https://api.mayar.id/hl/v2/payments/create")
    self.assertEqual(sandbox.kwargs["headers"]["Authorization"], "Bearer k")

def test_mayar_create_failure_returns_none(self):
    with patch("requests.post", side_effect=requests.exceptions.Timeout()):
        self.assertIsNone(payments.create_mayar_payment("k", True, {}))
    with patch("requests.post", return_value=Response({"data": {}})):
        self.assertIsNone(payments.create_mayar_payment("k", True, {}))

def test_poke_posts_the_ref_to_the_function_with_the_token(self):
    with patch("requests.post", return_value=Response({})) as post:
        self.assertTrue(payments.poke_mayar_notify("https://db.example", "tok", "R"))
    self.assertEqual(post.call_args.args[0], "https://db.example/functions/v1/mayar-notify")
    self.assertEqual(post.call_args.kwargs["params"], {"token": "tok"})
    self.assertEqual(post.call_args.kwargs["json"], {"event": "payment.received", "data": {"id": "R"}})
```

Add to `OrderStoreTest`: `create_order(..., provider="mayar")` sends `"provider": "mayar"`. `attach_order_ref` sends PATCH with `params` `owner=eq.<owner>` and `id=eq.<order>`, and body `{"provider_ref": "R", "provider_tx": "T"}`. `load_latest_order` selects `id,status,created_at,provider,provider_ref` and returns `"provider"` and `"ref"`.

- [ ] **Step 2:** Run `python -m pytest tests/test_payments.py -q`. Expected: the new tests FAIL with AttributeError.
- [ ] **Step 3:** Implement the payments functions:
  - `create_mayar_payment` mirrors `create_snap_transaction`'s error handling and logging (type and status only).
  - `poke_mayar_notify` uses `TIMEOUT`, returns `response.ok`, and returns False on `RequestException`.
- [ ] **Step 4:** Implement the store changes:
  - `attach_order_ref` uses `self._request("PATCH", "attach_order_ref", owner, "pro_orders", row_id=order_id, json=..., headers={"Prefer": "return=minimal"})`.
  - Update the docstrings that say "Midtrans" to say "penyedia pembayaran".
- [ ] **Step 5:** Run `python -m pytest tests/test_payments.py tests/test_chat_store.py -q`. Expected: all PASS.
- [ ] **Step 6:** Commit with "Add a Mayar payment client and order refs".

### Task 4: `mayar-notify` Edge Function

**Files:**
- Create: `supabase/functions/mayar-notify/notification.js`, `supabase/functions/mayar-notify/index.ts`, `supabase/functions/mayar-notify/notification.test.mjs`
- Modify: `.github/workflows/ci.yml:123` (add a second `node --test` line)

**Interfaces:**
- Consumes: `sameText` from `../midtrans-notify/notification.js`; `pro_orders.provider_ref` and `provider_tx` (Task 2); RPC `ciel_settle_order`.
- Produces from `notification.js`:
  - `PAYMENT_ID` (the UUID regex in Global Constraints)
  - `paymentUrl(id, production) -> string`
  - `candidateIds(body) -> string[]`: the unique UUIDs from `body.data.id` and `body.data.transactionId`
  - `handleWebhook(body, token, deps) -> {status, body}`, where `deps = { token, findOrder(ids) -> {id, amount, provider_ref} | null, fetchPayment(ref) -> data, settle(orderId, amount, status), log }`

Decision order in `handleWebhook`:
1. `token` must match `deps.token` (`sameText`); otherwise 403.
2. Non-object body → 400.
3. `body.event` present and not `payment.received` → 200 `ignored`.
4. No candidate ids → 200 `ignored`.
5. `findOrder` null → 200 `unknown`.
6. `fetchPayment(order.provider_ref)` throws → 502.
7. `data.id !== order.provider_ref` → 502.
8. `data.status === "paid"` → `settle(order.id, Number(data.amount), "paid")`. If that returns `amount_mismatch`, answer 200 `amount mismatch`; otherwise answer 200 with the settle result. A settle throw → 500.
9. Anything else → 200 with `data.status`.

- [ ] **Step 1: Write the failing tests** (`node:test`, styled like `midtrans-notify/notification.test.mjs`):
  - `wrong or missing token is 403 and calls nothing`
  - `membership events and bodies without a uuid are ignored without lookups`
  - `a non-uuid id never reaches findOrder` (body `data.id = "x) or (1=1"`)
  - `unknown payment id answers unknown`
  - `paid payment settles the order with Mayar's amount, not the webhook's` (webhook `data.amount = 1`, fetched amount 79000 → settle args `[ORDER, 79000, "paid"]`)
  - `unpaid or closed payment does not settle`
  - `mayar api error is 502 so Mayar retries`
  - `fetched id different from the order's ref is 502`
  - `second delivery returns already_paid` (settle stub returns `already_paid`)
  - `amount mismatch answers 200 and is logged`
  - `paymentUrl picks sandbox or production host`
- [ ] **Step 2:** Run `node --test supabase/functions/mayar-notify/notification.test.mjs`. Expected: FAIL, module not found.
- [ ] **Step 3:** Implement `notification.js` following the decision order above.
- [ ] **Step 4:** Implement `index.ts`. Copy `midtrans-notify/index.ts`'s structure with these changes:
  - Secrets: `MAYAR_API_KEY`, `MAYAR_PRODUCTION`, `MAYAR_WEBHOOK_TOKEN`.
  - Read the token from `new URL(request.url).searchParams.get("token")`.
  - `findOrder` runs `GET /rest/v1/pro_orders?select=id,amount,provider_ref&provider=eq.mayar&or=(provider_ref.in.(<ids>),provider_tx.in.(<ids>))&limit=1`. The ids are already validated by `PAYMENT_ID`.
  - `fetchPayment` calls `GET paymentUrl(ref)` with `Authorization: Bearer <key>` and returns `json.data`.
  - Write the header comment in the same style, with the deploy command `npx supabase functions deploy mayar-notify --project-ref <ref> --no-verify-jwt`.
- [ ] **Step 5:** Run the node tests for both functions. Expected: all PASS. Add `node --test supabase/functions/mayar-notify/notification.test.mjs` to CI next to the Midtrans line.
- [ ] **Step 6:** Commit with "Add the mayar-notify webhook".

### Task 5: Checkout, Pricing, Privacy and landing use the active provider

**Files:**
- Modify: `app.py:1597-1604` (config), `app.py:1924-2002` (checkout and Pricing action), `pricing.py:112`, `privacy.py:53,160-165`, `landing/index.html:785`
- Test: `tests/test_payments.py` (`CheckoutAppTest`, `PricingCheckoutTest`)

**Interfaces:**
- Consumes: everything from Task 3.
- Produces config in app.py:
  - `PAYMENT_PROVIDER = (get_config("PAYMENT_PROVIDER") or "midtrans").lower()`
  - `MAYAR_API_KEY`, `MAYAR_PRODUCTION`, `MAYAR_WEBHOOK_TOKEN`
  - `PAYMENTS_ENABLED`, true when the active provider's key is set and `CHAT_STORE` exists
  - `PAYMENT_PROVIDER_NAME` ("Mayar" or "Midtrans") for copy
- `privacy_sections(..., payments=False | str)`: a provider name turns the payments paragraph on and names that provider.

- [ ] **Step 1: Write the failing tests:**
  - `test_mayar_checkout_creates_order_attaches_refs_and_shows_the_link`: with secrets `PAYMENT_PROVIDER="mayar"`, `MAYAR_API_KEY="k"` and `MAYAR_WEBHOOK_TOKEN="tok"`, clicking `pro_buy` posts to `https://api.mayar.io/hl/v2/payments/create`. The database mock receives a POST to `pro_orders` with `"provider": "mayar"`, then a PATCH with `provider_ref`. The page shows a link button labelled `Lanjut ke pembayaran`.
  - `test_mayar_checkout_hides_the_link_when_refs_cannot_be_saved`: the PATCH returns 500 → no link button, and the error reads `Halaman pembayaran belum bisa dibuka. Silakan coba lagi.`
  - `test_recheck_pokes_mayar_notify_for_a_pending_mayar_order`: latest order is `{"status": "pending", "provider": "mayar", "provider_ref": "<uuid>"}`. Clicking `pro_recheck` posts to `https://db.example.invalid/functions/v1/mayar-notify` with `params={"token": "tok"}`.
  - Change `test_privacy_names_midtrans_only_when_payments_are_on`. `payments="Mayar"` puts "Mayar" in the text, and so does `payments="Midtrans"` for "Midtrans". `payments=False` mentions neither.
  - Existing Midtrans checkout tests stay green without setting `PAYMENT_PROVIDER` (the default).
- [ ] **Step 2:** Run `python -m pytest tests/test_payments.py -q`. Expected: the new tests FAIL.
- [ ] **Step 3:** Branch `start_pro_checkout` on `PAYMENT_PROVIDER`:
  - Mayar path: `create_order(..., provider="mayar")` → `create_mayar_payment(MAYAR_API_KEY, MAYAR_PRODUCTION, mayar_payload(order_id, PRO_PRICE, finish_url(APP_URL or st.context.url), email=st.user.get("email")))` → `attach_order_ref`. Show the link only if all three succeed.
  - Keep the Midtrans path byte-for-byte.
- [ ] **Step 4:** Give the "Cek lagi" button an `on_click` that calls `poke_mayar_notify(SUPABASE_URL, MAYAR_WEBHOOK_TOKEN, order["ref"])` when the order's provider is `mayar`.
- [ ] **Step 5:** Make the copy provider-neutral:
  - Link button: `Lanjut ke pembayaran`.
  - Pay note: "Pro aktif begitu pembayaran terkonfirmasi."
  - `pricing.py:112`: "Sekali bayar Rp79.000 (QRIS, e-wallet, atau virtual account)…".
  - Landing: "Sekali bayar, tanpa tagihan otomatis."
  - Privacy names `PAYMENT_PROVIDER_NAME`, and app.py:5120 passes it.
- [ ] **Step 6:** Run `python -m pytest -q` and both node tests. Expected: all PASS.
- [ ] **Step 7:** Run the app locally with sandbox Mayar secrets. Ciel checks Pricing in light and dark mode in their own browser (see [[ciel-dark-mode-checks]]). Commit only after Ciel says "commit": "Sell Pro through Mayar behind PAYMENT_PROVIDER".

### Task 6: Sandbox end-to-end, docs, then production

**Files:**
- Modify: `docs/PRO.md` (add a "Pembelian lewat Mayar" section with the secrets table rows, deploy, webhook URL and rollback), `SECURITY.md:19` (key-shaped string list, if the Mayar key has a recognizable prefix)
- Test: `tests/test_secrets.py`. Add a pattern only if Task 1 shows a fixed Mayar key prefix.

- [ ] **Step 1:** Deploy with `npx supabase functions deploy mayar-notify --project-ref nibbamicnqdxtmaacrio --no-verify-jwt`. Set the function secrets from `secrets.toml` the same way docs/PRO.md does for Midtrans (`MAYAR_API_KEY`, `MAYAR_WEBHOOK_TOKEN`, `MAYAR_PRODUCTION=false`), then compare sha256 digests.
- [ ] **Step 2:** In Mayar sandbox, register the webhook `https://nibbamicnqdxtmaacrio.supabase.co/functions/v1/mayar-notify?token=<MAYAR_WEBHOOK_TOKEN>` and run "Test URL Hook". Expected: 200 `ignored`.
- [ ] **Step 3:** Buy Pro locally with a test account and pay in sandbox. Expected: Pricing shows "Pembayaran diterima. Ciel Pro aktif sampai …", and `select status, provider, provider_ref from pro_orders order by created_at desc limit 1` gives `paid | mayar | <uuid>`.
- [ ] **Step 4:** Write the docs/PRO.md section, open a PR, and merge it after Ciel's review.
- [ ] **Step 5 (Ciel + Claude, after Mayar KYC is approved):**
  - Put the production key and `MAYAR_PRODUCTION=true` into the function secrets and redeploy.
  - Register the production webhook URL.
  - Then set Streamlit Cloud secrets `PAYMENT_PROVIDER="mayar"`, `MAYAR_API_KEY`, `MAYAR_PRODUCTION="true"` and `MAYAR_WEBHOOK_TOKEN`.
  - Run one real Rp79.000 purchase with Ciel's own account and confirm `paid`.

## Spike result

(filled in by Task 1)
