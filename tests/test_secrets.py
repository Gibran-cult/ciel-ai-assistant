"""No tracked file may hold a key-shaped string.

GitHub secret scanning has no pattern for Langflow keys; one sat in flow
v1.0.0/v1.1.0 of this public repo until 2026-10-26. Fixtures below are built
by concatenation so this file never matches its own patterns.
"""

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SECRET_PATTERNS = {
    "langflow": re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    "jwt": re.compile(r"eyJhbGciOi[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\."),
    "google_api": re.compile(r"AIza[0-9A-Za-z_-]{35}"),
    "google_oauth": re.compile(r"GOCSPX-[A-Za-z0-9_-]{20,}"),
    "github": re.compile(r"gh[pousr]_[A-Za-z0-9]{36}"),
    "midtrans": re.compile(r"(?:SB-)?Mid-server-[A-Za-z0-9_-]{16,}"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}


def find_secrets(text):
    return [name for name, pattern in SECRET_PATTERNS.items() if pattern.search(text)]


def file_text(path):
    """Text of a file, or None for binary. UTF-16 (with BOM) is read too, not skipped."""
    data = path.read_bytes()
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="ignore")
    if b"\0" in data:
        return None
    return data.decode("utf-8", errors="ignore")


def tracked_files():
    output = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
    return [ROOT / name for name in output.decode("utf-8").split("\0") if name]


class SecretScanTest(unittest.TestCase):
    def test_tracked_files_have_no_secrets(self):
        found = []

        for path in tracked_files():
            text = file_text(path) if path.is_file() else None
            if text is None:
                continue

            names = find_secrets(text)
            if names:
                found.append(f"{path.relative_to(ROOT).as_posix()}: {', '.join(names)}")

        self.assertEqual(found, [], "Key-shaped strings in tracked files (rotate, then remove)")

    def test_patterns_catch_known_secret_shapes(self):
        langflow = "sk-" + "Ab3_" * 6
        samples = {
            "langflow": [langflow, 'API_KEY = \\"' + langflow + '\\"'],
            "jwt": ["eyJhbGciOi" + "JIUzI1NiIs" + "." + "eyJyb2xlIjoi" + "." + "sig"],
            "google_api": ["AIza" + "B" * 35],
            "google_oauth": ["GOCSPX-" + "c" * 24],
            "github": ["ghp_" + "d" * 36],
            "midtrans": ["Mid-server-" + "e" * 20, "SB-Mid-server-" + "f" * 20],
            "private_key": ["-----BEGIN " + "PRIVATE KEY-----", "-----BEGIN RSA " + "PRIVATE KEY-----"],
        }

        self.assertEqual(set(samples), set(SECRET_PATTERNS))
        for name, texts in samples.items():
            for text in texts:
                self.assertIn(name, find_secrets(text), text)

    def test_utf16_files_are_scanned(self):
        # PowerShell 5.1 `>` and Out-File write UTF-16LE; such a file must not be skipped.
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "out.txt"
            path.write_bytes(("API_KEY=" + "sk-" + "Ab3_" * 6).encode("utf-16"))
            self.assertIn("langflow", find_secrets(file_text(path)))

    def test_placeholders_are_not_secrets(self):
        example = (ROOT / ".streamlit" / "secrets.toml.example").read_text(encoding="utf-8")

        for text in ("DEEPSEEK_API_KEY", "sk-REVOKED", 'api_key = "your-langflow-key"', example):
            self.assertEqual(find_secrets(text), [], text[:60])


if __name__ == "__main__":
    unittest.main()
