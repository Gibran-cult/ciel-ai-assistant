"""Check that the DeepSeek account can still pay for requests.

Calls GET https://api.deepseek.com/user/balance with DEEPSEEK_API_KEY (from the
environment, then the repository's .env). Prints one PASS/FAIL line and exits
with 1 when the account is unavailable, the USD balance is below --min-usd,
or the balance cannot be read. The key is never printed.
"""

import argparse
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_ngrok_policy import ROOT, load_settings  # noqa: E402

URL = "https://api.deepseek.com/user/balance"
TIMEOUT = 20
DEFAULT_MIN_USD = 3.0


def balance_ok(payload, min_usd):
    """(ok, message) for the payload of GET /user/balance. The message never holds the key."""
    infos = payload.get("balance_infos") or []
    if not payload.get("is_available"):
        return False, "akun DeepSeek tidak tersedia (is_available false)"
    usd = next((info for info in infos if info.get("currency") == "USD"), None)
    if usd is None:
        currencies = ", ".join(str(info.get("currency")) for info in infos) or "tidak ada"
        return False, f"tidak ada saldo USD; mata uang yang ada: {currencies}"
    raw = usd.get("total_balance")
    try:
        total = float(raw)
    except (TypeError, ValueError):
        return False, f"saldo USD tidak terbaca: {raw!r}"
    if total < min_usd:
        return False, f"saldo USD {raw} di bawah batas {min_usd:.2f}"
    return True, f"saldo USD {raw} (batas {min_usd:.2f})"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-usd", type=float, default=DEFAULT_MIN_USD)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    args = parser.parse_args(argv)

    key = load_settings(args.env_file).get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        print("Belum diisi: DEEPSEEK_API_KEY", file=sys.stderr)
        return 1

    try:
        response = requests.get(URL, headers={"Authorization": f"Bearer {key}"}, timeout=TIMEOUT)
    except requests.exceptions.RequestException as error:
        # Only the exception class: its text could echo request details.
        print(f"FAIL  GET /user/balance {type(error).__name__}")
        return 1
    if response.status_code != 200:
        print(f"FAIL  GET /user/balance {response.status_code} (harus 200)")
        return 1
    try:
        ok, message = balance_ok(response.json(), args.min_usd)
    except (ValueError, AttributeError):
        print("FAIL  GET /user/balance jawaban bukan JSON yang dikenal")
        return 1

    print(f"{'PASS' if ok else 'FAIL'}  {message}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
