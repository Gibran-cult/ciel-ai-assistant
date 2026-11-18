import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from account_ids import owner_from_subject  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


class OwnerIdTest(unittest.TestCase):
    def test_service_and_app_compute_the_same_owner(self):
        self.assertEqual(owner_from_subject("1234567890"), hashlib.sha256(b"ciel-memory:1234567890").hexdigest()[:16])
        self.assertEqual(owner_from_subject("budi@contoh.test"), hashlib.sha256(b"ciel-memory:budi@contoh.test").hexdigest()[:16])

    def test_empty_or_odd_subjects_have_no_owner(self):
        for subject in ("", None, 7, b"123"):
            self.assertEqual(owner_from_subject(subject), "")

    def test_the_app_uses_the_shared_function(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("return owner_from_subject(subject)", source)
        self.assertNotIn('f"ciel-memory:{subject}"', source)


if __name__ == "__main__":
    unittest.main()
