import base64
import hashlib
import json
import secrets
import sys
import unittest
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from account_ids import owner_from_subject  # noqa: E402
from agent_api.google import GoogleClient  # noqa: E402
from agent_api.main import create_app  # noqa: E402
from agent_api.settings import load_settings  # noqa: E402
from tests.agent_fakes import MemoryStore  # noqa: E402
from tests.agent_service_fakes import ENV, NOW, Clock  # noqa: E402

SETTINGS = load_settings(ENV)[0]
EXT_REDIRECT = "https://abcdefghijklmnop.chromiumapp.org/"
ALICE = owner_from_subject("alice")


def b64url(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def pkce_pair():
    verifier = secrets.token_urlsafe(48)
    return verifier, b64url(hashlib.sha256(verifier.encode()).digest())


def id_token(claims):
    header = b64url(json.dumps({"alg": "RS256", "kid": "uji"}).encode())
    return f"{header}.{b64url(json.dumps(claims).encode())}.tanda-tangan-tidak-diperiksa"


def query(location):
    return {key: values[0] for key, values in parse_qs(urlsplit(location).query).items()}


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status_code = status

    def json(self):
        return self.payload


class FakeSession:
    """Endpoint token Google tiruan. `claims` diisi uji, `nonce` dari URL login."""

    def __init__(self):
        self.claims = {}
        self.posts = []
        self.status = 200

    def post(self, url, data=None, timeout=None):
        self.posts.append((url, data, timeout))
        return FakeResponse({"id_token": id_token(self.claims), "access_token": "abaikan"}, self.status)


class Service:
    """Satu aplikasi uji dengan store, Google, dan jam tiruan."""

    def __init__(self, models=None, settings=SETTINGS):
        self.store = MemoryStore()
        self.session = FakeSession()
        self.clock = Clock()
        google = GoogleClient(self.session, settings.google_client_id, settings.google_client_secret, settings.google_redirect_uri)
        self.client = TestClient(create_app(settings, store=self.store, models=models, google=google, clock=self.clock))

    def good_claims(self, nonce, sub="alice"):
        return {"iss": "https://accounts.google.com", "aud": SETTINGS.google_client_id, "sub": sub, "nonce": nonce,
                "exp": int(NOW.timestamp()) + 3600, "email": f"{sub}@contoh.test", "email_verified": True}

    def start(self, challenge, redirect=EXT_REDIRECT, state="s1"):
        return self.client.get("/v1/device/login", params={"challenge": challenge, "redirect": redirect, "state": state},
                               follow_redirects=False)

    def callback(self, state, code="g1"):
        return self.client.get("/v1/device/callback", params={"code": code, "state": state}, follow_redirects=False)

    def device_code(self, sub="alice", challenge=None, claims=None):
        """Jalankan login sampai kode perangkat. Mengembalikan (verifier, response callback)."""

        verifier, made = pkce_pair()
        login = self.start(challenge or made)
        google = query(login.headers["location"])
        self.session.claims = {**self.good_claims(google["nonce"], sub), **(claims or {})}
        return verifier, self.callback(google["state"])

    def login(self, sub="alice", name="Chrome", platform="extension"):
        verifier, back = self.device_code(sub)
        code = query(back.headers["location"])["code"]
        return self.client.post("/v1/device/token", json={"code": code, "verifier": verifier, "name": name, "platform": platform}).json()


class DeviceLoginTest(unittest.TestCase):
    def setUp(self):
        self.service = Service()

    def test_login_redirects_to_google_with_state_and_nonce(self):
        _, challenge = pkce_pair()
        response = self.service.start(challenge)
        self.assertEqual(response.status_code, 302)
        location = response.headers["location"]
        self.assertTrue(location.startswith("https://accounts.google.com/o/oauth2/v2/auth?"))
        params = query(location)
        self.assertEqual((params["client_id"], params["redirect_uri"], params["response_type"], params["scope"], params["prompt"]),
                         (SETTINGS.google_client_id, SETTINGS.google_redirect_uri, "code", "openid email", "select_account"))
        self.assertTrue(params["state"] and params["nonce"])
        self.assertNotIn(SETTINGS.google_client_secret, location)

    def test_a_full_login_creates_one_device(self):
        verifier, back = self.service.device_code()
        self.assertEqual(back.status_code, 302)
        self.assertTrue(back.headers["location"].startswith(EXT_REDIRECT + "?"))
        params = query(back.headers["location"])
        self.assertEqual(params["state"], "s1")
        self.assertTrue(params["code"].startswith("cdc1." + ALICE + "."))

        tokens = self.service.client.post("/v1/device/token", json={
            "code": params["code"], "verifier": verifier, "name": "Chrome", "platform": "extension",
        }).json()
        self.assertEqual(set(tokens), {"device", "access_token", "refresh_token", "expires_in"})
        self.assertTrue(tokens["access_token"].startswith("cat1." + ALICE + "."))
        self.assertTrue(tokens["refresh_token"].startswith("crt1." + ALICE + "."))
        self.assertEqual(tokens["expires_in"], 900)
        self.assertEqual([device["id"] for device in self.service.store.load_devices(ALICE)], [tokens["device"]])
        self.assertRegex(tokens["device"], r"^[0-9a-f]{16}$")

        # Yang disimpan hanya hash, tidak pernah token mentahnya.
        stored = repr(self.service.store.tokens)
        for token in (params["code"], tokens["access_token"], tokens["refresh_token"]):
            self.assertNotIn(token, stored)
            self.assertIn(hashlib.sha256(token.encode()).hexdigest(), stored)

    def test_google_gets_the_code_with_the_client_secret_in_the_body(self):
        self.service.device_code()
        url, data, timeout = self.service.session.posts[-1]
        self.assertEqual(url, "https://oauth2.googleapis.com/token")
        self.assertEqual((data["code"], data["grant_type"], data["client_secret"], data["redirect_uri"]),
                         ("g1", "authorization_code", SETTINGS.google_client_secret, SETTINGS.google_redirect_uri))
        self.assertEqual(timeout, 10)

    def test_bad_google_tokens_create_nothing(self):
        cases = ({"aud": "aplikasi-lain"}, {"nonce": "lain"}, {"exp": int(NOW.timestamp()) - 1}, {"iss": "https://evil.example"},
                 {"sub": ""}, {"sub": 7}, {"email_verified": False})
        for claims in cases:
            with self.subTest(claims=claims):
                service = Service()
                _, back = service.device_code(claims=claims)
                self.assertEqual(back.status_code, 400)
                self.assertNotIn("location", back.headers)
                self.assertEqual(service.store.tokens, {})

        service = Service()
        service.session.status = 400
        _, back = service.device_code()
        self.assertEqual((back.status_code, service.store.tokens), (400, {}))

    def test_a_code_works_once_and_only_with_its_verifier(self):
        verifier, back = self.service.device_code()
        code = query(back.headers["location"])["code"]
        body = {"code": code, "verifier": "x" * 43, "name": "Chrome", "platform": "extension"}
        self.assertEqual(self.service.client.post("/v1/device/token", json=body).status_code, 400)
        # Percobaan yang salah tetap menghabiskan kodenya.
        self.assertEqual(self.service.client.post("/v1/device/token", json={**body, "verifier": verifier}).status_code, 400)
        self.assertEqual(self.service.store.load_devices(ALICE), [])

    def test_a_code_expires_after_60_seconds(self):
        verifier, back = self.service.device_code()
        code = query(back.headers["location"])["code"]
        self.service.clock.time = NOW + timedelta(seconds=61)
        body = {"code": code, "verifier": verifier, "name": "Chrome", "platform": "extension"}
        self.assertEqual(self.service.client.post("/v1/device/token", json=body).status_code, 400)

    def test_bad_token_requests_are_refused(self):
        verifier, back = self.service.device_code()
        code = query(back.headers["location"])["code"]
        good = {"code": code, "verifier": verifier, "name": "Chrome", "platform": "extension"}
        for body in ({**good, "platform": "ponsel"}, {**good, "name": ""}, {**good, "name": "n" * 61}, {**good, "owner": "lain"},
                     {k: v for k, v in good.items() if k != "verifier"}, {**good, "code": "cat1." + code[5:]}, {**good, "verifier": "pendek"}):
            with self.subTest(body=body):
                self.assertIn(self.service.client.post("/v1/device/token", json=body).status_code, (400, 422))
        self.assertEqual(self.service.client.post("/v1/device/token", json=good).status_code, 200)

    def test_unknown_redirects_and_bad_challenges_are_refused(self):
        _, challenge = pkce_pair()
        for params in ({"redirect": "https://evil.example/"}, {"redirect": EXT_REDIRECT + "x"}, {"challenge": "pendek"},
                       {"state": "a b"}, {"state": "s" * 129}):
            with self.subTest(params=params):
                response = self.service.client.get("/v1/device/login", params={"challenge": challenge, "redirect": EXT_REDIRECT,
                                                                              "state": "s1", **params}, follow_redirects=False)
                self.assertEqual(response.status_code, 400)
                self.assertNotIn("location", response.headers)

    def test_a_tampered_or_old_state_is_refused(self):
        _, challenge = pkce_pair()
        state = query(self.service.start(challenge).headers["location"])["state"]
        flipped = state[:-1] + ("A" if state[-1] != "A" else "B")
        self.assertEqual(self.service.callback(flipped).status_code, 400)
        self.service.clock.time = NOW + timedelta(seconds=601)
        self.assertEqual(self.service.callback(state).status_code, 400)
        self.assertEqual(self.service.session.posts, [])

    def test_a_desktop_redirect_with_a_custom_scheme_works(self):
        verifier, made = pkce_pair()
        login = self.service.start(made, redirect="ciel://auth", state="d9")
        google = query(login.headers["location"])
        self.service.session.claims = self.service.good_claims(google["nonce"])
        back = self.service.callback(google["state"])
        self.assertTrue(back.headers["location"].startswith("ciel://auth?"))

    def test_secrets_never_appear_in_logs(self):
        with self.assertLogs("ciel", level="INFO") as logs:
            tokens = self.service.login()
        text = "\n".join(logs.output)
        for prefix in ("cat1.", "crt1.", "cdc1."):
            self.assertNotIn(prefix, text)
        self.assertNotIn(SETTINGS.google_client_secret, text)
        self.assertIn(tokens["device"], text)

    def test_login_endpoints_are_rate_limited_per_address(self):
        _, challenge = pkce_pair()
        self.service.store.full = "agent-ip:testclient"
        self.assertEqual(self.service.start(challenge).status_code, 429)
        self.assertEqual(self.service.store.hits[-1], {"agent-ip:testclient": (10, 600)})
        self.assertEqual(self.service.callback("x").status_code, 429)
        self.assertEqual(self.service.client.post("/v1/device/token", json={}).status_code, 429)

        self.service.store.full = None
        self.service.store.fail.add("rate_limit_hit")
        self.assertEqual(self.service.start(challenge).status_code, 503)



def bearer(tokens):
    return {"Authorization": "Bearer " + tokens["access_token"]}


class DeviceTokenTest(unittest.TestCase):
    """Token akses, rotasi token pembaruan, dan pencabutan (Task 6)."""

    def setUp(self):
        self.service = Service()
        self.client = self.service.client

    def at(self, seconds):
        self.service.clock.time = NOW + timedelta(seconds=seconds)

    def devices(self, tokens):
        return self.client.get("/v1/devices", headers=bearer(tokens))

    def refresh(self, token):
        return self.client.post("/v1/device/refresh", json={"refresh_token": token})

    def test_access_tokens_expire_after_15_minutes(self):
        tokens = self.service.login()
        self.at(899)
        self.assertEqual(self.devices(tokens).status_code, 200)
        self.at(901)
        self.assertEqual(self.devices(tokens).status_code, 401)

    def test_requests_without_a_good_bearer_token_are_refused(self):
        tokens = self.service.login()
        for headers in ({}, {"Authorization": tokens["access_token"]}, {"Authorization": "Bearer " + tokens["refresh_token"]},
                        {"Authorization": "Bearer cat1.x.y"}, {"Authorization": "Basic abc"}):
            with self.subTest(headers=headers):
                self.assertEqual(self.client.get("/v1/devices", headers=headers).status_code, 401)

    def test_a_refresh_gives_a_new_pair_and_uses_up_the_old_token(self):
        first = self.service.login()
        self.at(1000)
        response = self.refresh(first["refresh_token"])
        self.assertEqual(response.status_code, 200)
        second = response.json()
        self.assertEqual(second["device"], first["device"])
        self.assertNotEqual(second["refresh_token"], first["refresh_token"])
        self.assertEqual(self.devices(second).status_code, 200)

    def test_reusing_an_old_refresh_token_revokes_the_device(self):
        first = self.service.login()
        second = self.refresh(first["refresh_token"]).json()
        self.assertEqual(self.refresh(first["refresh_token"]).status_code, 401)
        self.assertEqual(self.devices(second).status_code, 401)
        self.assertEqual(self.refresh(second["refresh_token"]).status_code, 401)
        self.assertIs(self.service.store.device_active(ALICE, first["device"]), False)

    def test_refresh_tokens_last_30_days(self):
        tokens = self.service.login()
        self.at(30 * 86400 + 1)
        self.assertEqual(self.refresh(tokens["refresh_token"]).status_code, 401)

    def test_bad_refresh_requests_are_refused(self):
        tokens = self.service.login()
        for body in ({}, {"refresh_token": tokens["access_token"]}, {"refresh_token": tokens["refresh_token"], "device": "x"},
                     {"refresh_token": 7}):
            with self.subTest(body=body):
                self.assertIn(self.client.post("/v1/device/refresh", json=body).status_code, (400, 401))
        self.assertEqual(self.refresh(tokens["refresh_token"]).status_code, 200)

    def test_the_device_list_belongs_to_the_token_owner(self):
        tokens = self.service.login(name="Chrome kantor")
        listed = self.devices(tokens).json()["devices"]
        self.assertEqual([(d["id"], d["name"], d["platform"], d["revoked"]) for d in listed],
                         [(tokens["device"], "Chrome kantor", "extension", False)])
        self.assertEqual(set(listed[0]), {"id", "name", "platform", "created_at", "last_seen_at", "revoked"})

    def test_a_revoked_device_is_refused_on_the_next_request(self):
        tokens = self.service.login()
        other = self.service.login(name="Laptop", platform="desktop")
        self.assertEqual(self.client.delete(f"/v1/devices/{tokens['device']}", headers=bearer(other)).status_code, 204)
        self.assertEqual(self.devices(tokens).status_code, 401)
        self.assertEqual(self.refresh(tokens["refresh_token"]).status_code, 401)
        self.assertEqual([d["revoked"] for d in self.devices(other).json()["devices"]], [True, False])

    def test_an_account_cannot_see_or_revoke_another_accounts_device(self):
        alice, bob = self.service.login(sub="alice"), self.service.login(sub="bob")
        self.assertEqual([d["id"] for d in self.devices(bob).json()["devices"]], [bob["device"]])
        self.assertEqual(self.client.delete(f"/v1/devices/{alice['device']}", headers=bearer(bob)).status_code, 404)
        self.assertEqual(self.client.delete("/v1/devices/tidak..ada", headers=bearer(bob)).status_code, 404)
        self.assertIs(self.service.store.device_active(ALICE, alice["device"]), True)

    def test_a_token_with_another_owner_inside_is_refused(self):
        alice = self.service.login(sub="alice")
        forged = "cat1." + owner_from_subject("bob") + "." + alice["access_token"].split(".", 2)[2]
        self.assertEqual(self.devices({"access_token": forged}).status_code, 401)

    def test_a_store_outage_refuses_instead_of_letting_through(self):
        tokens = self.service.login()
        self.service.store.fail.add("device_active")
        self.assertEqual(self.devices(tokens).status_code, 401)


if __name__ == "__main__":
    unittest.main()
