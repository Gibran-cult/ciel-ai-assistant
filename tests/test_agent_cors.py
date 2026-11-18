import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.test_agent_devices import Service  # noqa: E402

EXTENSION = "chrome-extension://abcdefghijklmnop"


def preflight(service, origin, path="/v1/device/refresh", method="POST"):
    return service.client.options(path, headers={"origin": origin, "access-control-request-method": method,
                                                 "access-control-request-headers": "content-type"})


class CorsTest(unittest.TestCase):
    """Ekstensi memanggil layanan dari origin chrome-extension:// tanpa izin host tetap."""

    def test_the_extension_origin_may_call_the_api(self):
        service = Service()
        response = preflight(service, EXTENSION)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("access-control-allow-origin"), EXTENSION)
        self.assertNotIn("access-control-allow-credentials", response.headers)

        keys = service.client.get("/v1/ticket-keys", headers={"origin": EXTENSION})
        self.assertEqual(keys.headers.get("access-control-allow-origin"), EXTENSION)

    def test_other_origins_get_no_cors_headers(self):
        service = Service()

        for origin in ("https://evil.example", "chrome-extension://otherextensionid", "null"):
            with self.subTest(origin=origin):
                self.assertNotIn("access-control-allow-origin", preflight(service, origin).headers)
                keys = service.client.get("/v1/ticket-keys", headers={"origin": origin})
                self.assertNotIn("access-control-allow-origin", keys.headers)

    def test_only_the_methods_and_headers_the_extension_uses(self):
        response = preflight(Service(), EXTENSION, method="PUT")
        self.assertNotIn("PUT", response.headers.get("access-control-allow-methods", ""))


if __name__ == "__main__":
    unittest.main()
