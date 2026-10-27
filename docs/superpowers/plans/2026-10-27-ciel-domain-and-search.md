# Ciel Domain and Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ciel gets its own address, `ciel-ai.web.id`, and people can find it by searching "Ciel AI" on Google and Bing, so nobody needs the long Streamlit link.

**Architecture:** The landing page stays on GitHub Pages and gets `ciel-ai.web.id` as its custom domain, so the old `github.io` address redirects to it automatically. Cloudflare's free plan hosts the DNS and runs a redirect from `app.ciel-ai.web.id` to the Streamlit app, because Streamlit Community Cloud does not support custom domains. Search engines index the landing page (static HTML), not the Streamlit app (a JavaScript page with nothing to crawl). The page gets the tags, structured data, sitemap and share image that search engines and link previews read.

**Tech Stack:** static HTML on GitHub Pages, Cloudflare DNS and Redirect Rules (free plan), Python 3 `unittest`, Google Search Console (through the HyperGSC connector), Bing Webmaster Tools.

**Spec:** the "Decisions" section below (no separate spec; Ciel asked on 2026-10-27 for Ciel to be searchable, with a nice free domain that is not Streamlit or GitHub).

## Decisions (2026-10-27)

| Question | Decision | Why |
|---|---|---|
| Domain | `ciel-ai.web.id` (Ciel's pick; registered 2026-10-27 as `.web.id`, not the `.my.id` this research priced) | Registrars sold `.my.id` at about Rp9.000–12.000 a year in 2024–2026. Truly free options were weaker: DigitalPlat (`dpdns.org`) has an unusual ending, the Student Pack domain is free only for year 1, and `*.pages.dev` is a hosting address. |
| App address | `app.ciel-ai.web.id` → 302 redirect to the Streamlit URL, keeping path and query | Streamlit Community Cloud allows only `*.streamlit.app` subdomains. An iframe would hide the URL but breaks Google login and page links. A 302 (not 301) lets the target change later without browsers caching the old one. |
| Landing host | Keep GitHub Pages, add the custom domain | Already deployed by `pages.yml`. GitHub redirects `gibran-cult.github.io/ciel-ai-assistant/` to the custom domain, so links already shared keep working. Vercel (connected, Hobby plan) was ruled out because Hobby forbids commercial use and Ciel sells Pro. |
| DNS | Cloudflare free plan | Free redirect rules with HTTPS for `app.`; registrar URL forwarding is usually HTTP-only. |
| What gets indexed | Landing page only | The Streamlit app renders in JavaScript over a websocket, so crawlers see an empty shell. |

**Expectations to tell Ciel:** Google usually indexes a new verified site within days to a couple of weeks. A search for "Ciel AI" should find it after that. A search for just "Ciel" competes with the French word and the *Tensura* character, so it may never rank first. Links from Ciel's Instagram, TikTok and the GitHub repo help the most.

## Global Constraints

- Domain: `ciel-ai.web.id`. Canonical page URL: `https://ciel-ai.web.id/` (https, no `www`, trailing slash).
- App base: `https://app.ciel-ai.web.id/`. Allowed app links stay `/`, `/?page=login`, `/?page=pricing`, `/?page=privacy`.
- Streamlit URL (redirect target only): `https://ciel-ai-assistant-hywsyrnfpyhxc5e9pjgaho.streamlit.app`.
- Brand name for search: `Ciel AI` (title, `og:site_name`, `WebSite.name`); `Ciel` is the alternate name.
- Everything stays free except the `.web.id` registration. Ciel pays for it and must turn on auto-renew. A lapsed domain can be re-registered by anyone and used to impersonate Ciel.
- Purchases, account sign-ups, DNS changes in Cloudflare, and Search Console or Bing verification are Ciel's to do in the browser. The agent gives the exact values and checks the result. The agent never enters Ciel's passwords, KTP data or payment details.
- Visual changes (`og.png`, the title in the browser tab) wait for Ciel's own browser check and an explicit "commit" (Ciel's standing rule).
- Commits and PRs have no Claude attribution lines (Ciel's standing rule).
- Keep the landing CSP strict: no new `<script>` that runs, no third-party origins. A `<script type="application/ld+json">` block is data, not code, so the CSP does not block it and `test_csp_hash_matches_inline_script` (which matches only bare `<script>`) still sees one script.
- Run tests as CI does: `python -m unittest -v tests.test_landing`.

## Review Focus

1. **Login link loses its query string through the redirect.** `app.ciel-ai.web.id/?page=login` must land on the Streamlit login page, not the home page. Task 1 Step 6 checks the `Location` header for `?page=login`.
2. **Cloudflare proxy on the apex or `www` records.** Proxied ("orange cloud") records stop GitHub from issuing the Pages certificate, and the site shows an HTTPS error. Apex and `www` must be DNS only. Only `app` is proxied. Task 1 Step 4 sets this and Task 4 Step 3 checks the certificate.
3. **Old links shared before today.** `https://gibran-cult.github.io/ciel-ai-assistant/` (Instagram bio, chats) must answer with a 301 to `https://ciel-ai.web.id/`, not a 404. Task 4 Step 4.
4. **Duplicate URLs split the ranking.** `http://`, `www.` and the github.io URL must all redirect to the one canonical URL, and `canonical`, `og:url` and the sitemap must name exactly that URL. `test_canonical_url_is_consistent` (Task 3) plus the curl checks in Task 4.
5. **Prices in search results drift from the app.** The JSON-LD offers must come from `pricing.py`, or Google shows a stale Pro price. `test_structured_data_prices_match_pricing_py` (Task 3).

---

### Task 1: Register the domain and set up DNS (Ciel in the browser, agent checks)

**Files:** none (account and DNS work).

**Interfaces:**
- Produces: `ciel-ai.web.id` on Cloudflare nameservers; `https://app.ciel-ai.web.id/<path>?<query>` → 302 → `https://ciel-ai-assistant-hywsyrnfpyhxc5e9pjgaho.streamlit.app/<path>?<query>`; GitHub Pages domain verification for `ciel-ai.web.id` on the `Gibran-cult` account.

- [ ] **Step 1: Ciel registers `ciel-ai.web.id`**

Use an Indonesian registrar that sells PANDI domains (for example Domainesia or Rumahweb); PANDI asks for a KTP. Turn on auto-renew. The plan first priced `.my.id`; Ciel registered `ciel-ai.web.id` on 2026-10-27 (PANDI RDAP shows it on Cloudflare nameservers). If a chosen name is taken, stop and ask Ciel for another; every later value depends on it.

- [ ] **Step 2: Ciel adds the domain to Cloudflare (free plan)**

dash.cloudflare.com → Add a domain → `ciel-ai.web.id` → Free plan. Cloudflare shows two nameservers. At the registrar, replace the default nameservers with those two. If Cloudflare refuses the `.web.id` zone, stop and tell Ciel. The fallback is registrar DNS for the apex and `www`, plus Task 2 keeping the direct Streamlit links, because the `app.` redirect then has no free HTTPS host.

- [ ] **Step 3: Verify the domain for GitHub Pages first (takeover protection)**

Ciel: github.com/settings/pages → Add a domain → `ciel-ai.web.id`. GitHub shows a TXT record named `_github-pages-challenge-Gibran-cult.ciel-ai.web.id`. Add it in Cloudflare DNS, then click Verify. This must happen before Task 4. Otherwise another GitHub account could claim the domain for its own Pages site.

- [ ] **Step 4: Ciel adds the DNS records in Cloudflare**

| Type | Name | Content | Proxy |
|---|---|---|---|
| A | `@` | `185.199.108.153` | DNS only |
| A | `@` | `185.199.109.153` | DNS only |
| A | `@` | `185.199.110.153` | DNS only |
| A | `@` | `185.199.111.153` | DNS only |
| AAAA | `@` | `2606:50c0:8000::153` | DNS only |
| AAAA | `@` | `2606:50c0:8001::153` | DNS only |
| AAAA | `@` | `2606:50c0:8002::153` | DNS only |
| AAAA | `@` | `2606:50c0:8003::153` | DNS only |
| CNAME | `www` | `gibran-cult.github.io` | DNS only |
| AAAA | `app` | `100::` | Proxied |

`100::` is a discard address. The `app` record exists only so Cloudflare's proxy can answer it with the redirect rule.

- [ ] **Step 5: Ciel creates the redirect rule**

Cloudflare → Rules → Redirect Rules → Create rule, named `app to Streamlit`:
- If: Custom filter expression, Hostname equals `app.ciel-ai.web.id`.
- Then: Dynamic. Expression: `concat("https://ciel-ai-assistant-hywsyrnfpyhxc5e9pjgaho.streamlit.app", http.request.uri.path)`. Status code `302`. Preserve query string: on.

- [ ] **Step 6: Agent checks DNS and the redirect**

Run:
```bash
nslookup -type=NS ciel-ai.web.id 1.1.1.1
curl -sI "https://app.ciel-ai.web.id/?page=login"
curl -sI "https://app.ciel-ai.web.id/"
```
Expected: two `*.ns.cloudflare.com` nameservers. The first curl returns `302` with `location: https://ciel-ai-assistant-hywsyrnfpyhxc5e9pjgaho.streamlit.app/?page=login`, and the second returns `location: …streamlit.app/`. Nameserver changes can take up to 24 h. Re-check instead of changing records.

---

### Task 2: Share image and icons for search results and link previews

**Files:**
- Create: `assets/brand/og-card.html` (source for the image; not published)
- Create: `landing/og.png` (1200×630)
- Create: `landing/ciel-icon-192.png`, `landing/ciel-icon-512.png` (copies of `assets/brand/` files)
- Test: `tests/test_landing.py`

**Interfaces:**
- Produces: files served at `https://ciel-ai.web.id/og.png`, `/ciel-icon-192.png`, `/ciel-icon-512.png`, used by Task 3.

- [ ] **Step 1: Write the failing test**

```python
def png_size(path):
    data = path.read_bytes()[:24]
    assert data[:8] == b"\x89PNG\r\n\x1a\n", path
    return struct.unpack(">II", data[16:24])

class LandingAssetsTest(unittest.TestCase):

    def test_share_image_is_1200_by_630(self):
        self.assertEqual(png_size(LANDING.parent / "og.png"), (1200, 630))
        self.assertLess((LANDING.parent / "og.png").stat().st_size, 300_000)

    def test_png_icons_match_brand_files(self):
        for size in (192, 512):
            with self.subTest(size=size):
                name = f"ciel-icon-{size}.png"
                self.assertEqual((LANDING.parent / name).read_bytes(), (ROOT / "assets" / "brand" / name).read_bytes())
```
(add `import struct`.)

- [ ] **Step 2: Run it and see it fail**

Run: `python -m unittest -v tests.test_landing.LandingAssetsTest`
Expected: FAIL with `FileNotFoundError` for `og.png`.

- [ ] **Step 3: Build `assets/brand/og-card.html` and render `landing/og.png`**

A 1200×630 card in the landing's own style: night ground `#141311`, the Ciel mark from `assets/brand/ciel-mark-dark.svg`, "Ciel AI" in Fraunces 500, the line "Riset yang nggak ngarang." in Geist, and `ciel-ai.web.id` small at the bottom. Keep text inside the middle 1000×520 so square crops still read. Render it with the Playwright plugin or the built-in browser at a 1200×630 viewport, take a full-viewport PNG screenshot, and save it as `landing/og.png`. Copy the two icon PNGs from `assets/brand/`.

- [ ] **Step 4: Run the tests and see them pass**

Run: `python -m unittest -v tests.test_landing`
Expected: all PASS.

- [ ] **Step 5: Ciel checks the image**

Send `landing/og.png` to Ciel (SendUserFile). Wait for Ciel's own check and an explicit "commit".

- [ ] **Step 6: Commit**

```bash
git add assets/brand/og-card.html landing/og.png landing/ciel-icon-192.png landing/ciel-icon-512.png tests/test_landing.py
git commit -m "Add a share image and PNG icons for the landing page"
```

---

### Task 3: Search tags, structured data, robots.txt and sitemap

**Files:**
- Modify: `landing/index.html` (`<head>`, lines 1–16)
- Create: `landing/robots.txt`, `landing/sitemap.xml`
- Test: `tests/test_landing.py`

**Interfaces:**
- Consumes: `og.png`, `ciel-icon-192.png`, `ciel-icon-512.png` from Task 2; `pricing.PLANS`, `pricing.format_idr` (existing).
- Produces: module constant `SITE = "https://ciel-ai.web.id/"` in `tests/test_landing.py`, and helper `structured_data(source) -> list[dict]` (parses every `<script type="application/ld+json">` block with `json.loads`, and flattens `@graph`).

- [ ] **Step 1: Write the failing tests**

```python
SITE = "https://ciel-ai.web.id/"

def meta(source, key):
    match = re.search(rf'<meta (?:name|property)="{re.escape(key)}" content="([^"]*)">', source)
    return unescape(match.group(1)) if match else None

class SearchTagsTest(unittest.TestCase):

    def test_title_names_ciel_ai(self):
        self.assertIn("<title>Ciel AI: riset yang nggak ngarang</title>", page())

    def test_canonical_url_is_consistent(self):
        source = page()
        self.assertIn(f'<link rel="canonical" href="{SITE}">', source)
        self.assertEqual(meta(source, "og:url"), SITE)
        self.assertIn(f"<loc>{SITE}</loc>", (LANDING.parent / "sitemap.xml").read_text(encoding="utf-8"))
        self.assertIn(f"Sitemap: {SITE}sitemap.xml", (LANDING.parent / "robots.txt").read_text(encoding="utf-8"))

    def test_open_graph_and_twitter_tags(self):
        source = page()
        expected = {
            "og:type": "website", "og:site_name": "Ciel AI", "og:locale": "id_ID",
            "og:title": "Ciel AI: riset yang nggak ngarang",
            "og:image": f"{SITE}og.png", "og:image:width": "1200", "og:image:height": "630",
            "twitter:card": "summary_large_image",
        }
        for key, value in expected.items():
            with self.subTest(key=key):
                self.assertEqual(meta(source, key), value)
        self.assertEqual(meta(source, "og:description"), meta(source, "description"))
        self.assertTrue(meta(source, "og:image:alt"))

    def test_robots_allow_everything(self):
        robots = (LANDING.parent / "robots.txt").read_text(encoding="utf-8")
        self.assertIn("User-agent: *", robots)
        self.assertNotRegex(robots, r"(?m)^Disallow:\s*/\s*$")
        self.assertNotIn('name="robots"', page())

    def test_site_name_for_google(self):
        site = next(item for item in structured_data(page()) if item["@type"] == "WebSite")
        self.assertEqual((site["name"], site["url"]), ("Ciel AI", SITE))
        self.assertIn("Ciel", site["alternateName"])

    def test_structured_data_prices_match_pricing_py(self):
        app = next(item for item in structured_data(page()) if item["@type"] == "WebApplication")
        self.assertEqual(app["url"], SITE)
        offers = {offer["name"]: offer for offer in app["offers"]}
        for plan in pricing.PLANS:
            if plan["id"] in ("free", "pro"):
                with self.subTest(plan=plan["id"]):
                    self.assertEqual(offers[plan["name"]]["price"], str(plan["monthly"]))
                    self.assertEqual(offers[plan["name"]]["priceCurrency"], "IDR")

    def test_organization_links_ciels_accounts(self):
        org = next(item for item in structured_data(page()) if item["@type"] == "Organization")
        self.assertEqual(org["logo"], f"{SITE}ciel-icon-512.png")
        self.assertEqual(set(org["sameAs"]), {"https://www.instagram.com/ciel_ai.1/", "https://www.tiktok.com/@ciel_ai.1"})
```

`test_no_third_party_scripts_or_styles` already requires local `<link>` files to exist, which covers the PNG icon links. `meta()` expects each tag written as `<meta name|property="…" content="…">` in that attribute order: `name` for `description` and `twitter:*`, `property` for `og:*`.

- [ ] **Step 2: Run them and see them fail**

Run: `python -m unittest -v tests.test_landing.SearchTagsTest`
Expected: FAIL on the title, missing canonical, and `NameError: structured_data`.

- [ ] **Step 3: Add the head tags and the two files**

In `landing/index.html` `<head>`:
- `<title>Ciel AI: riset yang nggak ngarang</title>`; the description meta stays as is.
- `<link rel="canonical" href="https://ciel-ai.web.id/">`
- Open Graph and Twitter metas with the values in the test. `og:image:alt`: `Logo Ciel AI dan tulisan Riset yang nggak ngarang`.
- `<link rel="icon" type="image/png" sizes="192x192" href="ciel-icon-192.png">` and `<link rel="apple-touch-icon" href="ciel-icon-192.png">`, after the SVG icon.
- One `<script type="application/ld+json">` with an `@graph` of three nodes: `WebSite` (`name` "Ciel AI", `alternateName` ["Ciel"], `url`, `inLanguage` "id"); `Organization` (`name` "Ciel AI", `url`, `logo`, `sameAs`); `WebApplication` (`name` "Ciel AI", `url`, `description` = the meta description, `applicationCategory` "EducationalApplication", `operatingSystem` "Web", `inLanguage` "id", `offers`: one `Offer` per Free and Pro plan, with `name` = plan name, `price` = `str(plan["monthly"])`, `priceCurrency` "IDR").

`landing/robots.txt`:
```
User-agent: *
Allow: /

Sitemap: https://ciel-ai.web.id/sitemap.xml
```
`landing/sitemap.xml`: a standard `urlset` with one `<url>` whose `<loc>` is `https://ciel-ai.web.id/` and `<lastmod>` is the commit date.

Add `structured_data(source)` and `meta(source, key)` to `tests/test_landing.py` next to `csp()`.

- [ ] **Step 4: Run all landing tests and see them pass**

Run: `python -m unittest -v tests.test_landing`
Expected: all PASS, including `test_csp_hash_matches_inline_script` (the JSON-LD block is not a bare `<script>`).

- [ ] **Step 5: Ciel checks the tab title**

Open `landing/index.html` in the built-in browser and show Ciel the tab title. Wait for an explicit "commit".

- [ ] **Step 6: Commit**

```bash
git add landing/index.html landing/robots.txt landing/sitemap.xml tests/test_landing.py
git commit -m "Add search tags, structured data, robots.txt and sitemap to the landing page"
```

---

### Task 4: Point app links at `app.ciel-ai.web.id` and switch Pages to the domain

**Files:**
- Modify: `landing/index.html` (every `href` that starts with the Streamlit URL: lines 493, 512, 526, 527, 609, 709, 724, 738, 758, 759, 766, 775)
- Modify: `tests/test_landing.py:18` (`APP`), `.github/workflows/pages.yml:3` (comment URL)
- Modify: `README.md` (add the site and app addresses at the top)

**Interfaces:**
- Consumes: the redirect from Task 1 (must pass Task 1 Step 6 before this merges).
- Produces: production site at `https://ciel-ai.web.id/`.

- [ ] **Step 1: Write the failing test**

Set `APP = "https://app.ciel-ai.web.id/"` in `tests/test_landing.py`, and add to `test_app_links_use_known_pages`:
```python
        self.assertNotIn("streamlit.app", page())
```

- [ ] **Step 2: Run it and see it fail**

Run: `python -m unittest -v tests.test_landing.LandingContentTest.test_app_links_use_known_pages`
Expected: FAIL (`app_links` is empty).

- [ ] **Step 3: Replace the Streamlit base URL**

In `landing/index.html`, replace `https://ciel-ai-assistant-hywsyrnfpyhxc5e9pjgaho.streamlit.app/` with `https://app.ciel-ai.web.id/` everywhere. Update the URL in the `pages.yml` comment to `https://ciel-ai.web.id/`. In `README.md`, add a line near the top: site `https://ciel-ai.web.id/`, app `https://app.ciel-ai.web.id/`.

- [ ] **Step 4: Run all tests and see them pass**

Run: `python -m unittest -v tests.test_landing`
Expected: all PASS.

- [ ] **Step 5: Commit, open the PR, merge after Ciel's go-ahead**

```bash
git add landing/index.html tests/test_landing.py .github/workflows/pages.yml README.md
git commit -m "Send landing links through app.ciel-ai.web.id"
```
Open the PR (with Tasks 2–3 on the same branch). Merge only when Ciel says so. The merge triggers `pages.yml`.

- [ ] **Step 6: Set the custom domain on GitHub Pages**

After Task 1 Step 3 (domain verified) and the deploy:
```bash
gh api -X PUT repos/Gibran-cult/ciel-ai-assistant/pages -f cname=ciel-ai.web.id
```
Wait for the certificate (GitHub shows it under Settings → Pages; usually under an hour), then:
```bash
gh api -X PUT repos/Gibran-cult/ciel-ai-assistant/pages -F https_enforced=true
gh repo edit Gibran-cult/ciel-ai-assistant --homepage https://ciel-ai.web.id/
```

- [ ] **Step 7: Check every address resolves to the one URL**

Run:
```bash
curl -sI https://ciel-ai.web.id/
curl -sI http://ciel-ai.web.id/
curl -sI https://www.ciel-ai.web.id/
curl -sI https://gibran-cult.github.io/ciel-ai-assistant/
curl -s https://ciel-ai.web.id/robots.txt
curl -sI https://ciel-ai.web.id/og.png
```
Expected: `200` for the first; `301` to `https://ciel-ai.web.id/` for the next three; robots.txt as committed; `og.png` `200` with `content-type: image/png`. Then click every "Masuk" and "Buka aplikasi" link on the live page in the built-in browser and confirm it opens the right Streamlit page, including Google login.

---

### Task 5: Register with Google and Bing, and check indexing

**Files:** none.

**Interfaces:**
- Consumes: the live site from Task 4.
- Produces: a verified Search Console Domain property `ciel-ai.web.id`, visible to the HyperGSC connector.

- [ ] **Step 1: Ciel verifies the domain in Google Search Console**

search.google.com/search-console → Add property → **Domain** → `ciel-ai.web.id`. Google offers to add the TXT record through Cloudflare automatically, or shows a `google-site-verification=…` TXT to add at `@`. Use the same Google account that HyperGSC is connected to (gibranahmadn6@gmail.com). A Domain property covers `www`, `app` and both protocols.

- [ ] **Step 2: Ciel submits the sitemap and requests indexing**

In Search Console: Sitemaps → `https://ciel-ai.web.id/sitemap.xml` → Submit. URL Inspection → `https://ciel-ai.web.id/` → Request indexing.

- [ ] **Step 3: Ciel adds the site to Bing**

bing.com/webmasters → Import from Google Search Console. This also covers DuckDuckGo and Yahoo, which use Bing's index.

- [ ] **Step 4: Agent checks through the HyperGSC connector**

Ciel refreshes properties at hypergsc.com/connections. Then call `list_properties`, then `inspect_url_enhanced` for `https://ciel-ai.web.id/`, `indexability_detective` and `sitemap_health`. Expected: the property is listed, the page is indexable with the canonical set to itself, and the sitemap has one URL. "Discovered – currently not indexed" in the first days is normal. Re-check after a few days instead of changing anything.

- [ ] **Step 5: Ciel updates the links people follow**

Put `ciel-ai.web.id` in the Instagram (@ciel_ai.1) and TikTok bios. These links, plus the GitHub homepage set in Task 4, are how Google first connects "Ciel AI" to the site.

- [ ] **Step 6: Record the result in memory**

Save a project memory: domain, registrar renewal date, Cloudflare redirect rule, Pages custom domain, and Search Console status, with the date.
