"""Vektor uji bersama untuk ekstensi Ciel Agent.

Ekstensi memeriksa tiket, menyaring rahasia, dan menulis log dengan aturan
yang sama dengan layanan Python. Skrip ini menulis hasil kode Python ke
extension/src/shared/vectors/, lalu uji TypeScript membaca berkas itu.
tests/test_extension_vectors.py memastikan berkas di repo sama dengan hasil
skrip ini, jadi aturan Python yang berubah tanpa memperbarui vektor membuat
CI gagal.

    python tools/export_extension_vectors.py            # tulis ke folder ekstensi
    python tools/export_extension_vectors.py FOLDER     # tulis ke folder lain

Seed di sini hanya untuk uji. Tidak pernah dipakai layanan sungguhan.
"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import agent_log  # noqa: E402
from agent_api.tickets import TicketSigner, make_ticket, verify_ticket  # noqa: E402
from guard.risk import BLOCKED_APPS, BLOCKED_HOSTS, find_secrets  # noqa: E402

DEFAULT_OUT = ROOT / "extension" / "src" / "shared" / "vectors"
NOW = 1_795_000_000
CONTEXT = {"task": "t1", "device": "d1", "last_seq": 2, "now": NOW}


def seed(name):
    return hashlib.sha256(f"ciel-extension-vectors:{name}".encode()).digest()


def ticket_vectors():
    signer = TicketSigner((seed("a"),))
    rotated = TicketSigner((seed("b"), seed("a")))
    keys_a = signer.public_keys()
    keys_both = rotated.public_keys()

    def ticket(seq=3, tool="tab_click", args=None, host="shopee.co.id"):
        return make_ticket("t1", "d1", seq, tool, {"ref": 5} if args is None else args, host, NOW)

    good = signer.sign(ticket())
    text = signer.sign(ticket(tool="tab_type", args={"ref": 4, "text": "Kaos ✓ ukuran L, café 😀 baris\x1f\n\"kutip\" \\ /"}))
    nested = signer.sign(ticket(tool="tab_select", args={"value": "Merah", "ref": 2, "Zeta": 1, "alpha": "a", "é": 1, "😀": 2, "ｗ": 3}))
    cases = [
        ("valid", good, keys_a, {}),
        ("valid at the last second", good, keys_a, {"now": NOW + 60}),
        ("expired one second later", good, keys_a, {"now": NOW + 61}),
        ("args changed", {**good, "ticket": {**good["ticket"], "args": {"ref": 6}}}, keys_a, {}),
        ("host changed", {**good, "ticket": {**good["ticket"], "host": "evil.example"}}, keys_a, {}),
        ("tool changed", {**good, "ticket": {**good["ticket"], "tool": "form_submit"}}, keys_a, {}),
        ("signature changed", {**good, "sig": good["sig"][:-2] + "AA"}, keys_a, {}),
        ("signature not base64", {**good, "sig": "%%%"}, keys_a, {}),
        ("signature empty", {**good, "sig": ""}, keys_a, {}),
        ("same seq again", good, keys_a, {"last_seq": 3}),
        ("other task", good, keys_a, {"task": "t2"}),
        ("other device", good, keys_a, {"device": "d2"}),
        ("unknown key", good, rotated.public_keys()[:1], {}),
        ("key with another algorithm", good, [{**keys_a[0], "alg": "RS256"}], {}),
        ("broken public key", good, [{**keys_a[0], "key": "AAAA"}], {}),
        ("rotation: new key signs, both listed", rotated.sign(ticket()), keys_both, {}),
        ("rotation: old key still listed", good, keys_both, {}),
        ("rotation: new key, old list", rotated.sign(ticket()), keys_a, {}),
        ("non-ASCII and control text", text, keys_a, {}),
        ("keys sorted by code point", nested, keys_a, {}),
        ("seq as boolean", signer.sign({**ticket(), "seq": True}), keys_a, {}),
        ("missing exp", signer.sign({key: value for key, value in ticket().items() if key != "exp"}), keys_a, {}),
        ("null", None, keys_a, {}),
        ("list", [], keys_a, {}),
        ("empty object", {}, keys_a, {}),
        ("extra field", {**good, "extra": 1}, keys_a, {}),
        ("kid not a string", {**good, "kid": 7}, keys_a, {}),
        ("sig not a string", {**good, "sig": 7}, keys_a, {}),
        ("ticket not an object", {**good, "ticket": "x"}, keys_a, {}),
    ]

    out = []

    for name, signed, keys, override in cases:
        context = {**CONTEXT, **override}
        expect = verify_ticket(signed, keys, task=context["task"], device=context["device"],
                               last_seq=context["last_seq"], now=context["now"])
        out.append({"name": name, "signed": signed, "keys": keys, "context": context, "expect": expect})

    canonical = [{"value": value, "canonical": json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)}
                 for value in (good["ticket"], text["ticket"], nested["ticket"], {"b": [1, {"d": None, "c": True}], "a": ""})]
    return {"cases": out, "canonical": canonical}


def secret_vectors():
    texts = [
        "Kirim ke Jl. Mawar 12, kode pos 40115, tahun 2026",
        "Kartu 4111 1111 1111 1111 berlaku 12/30",
        "4111-1111-1111-1111",
        "4111111111111111123",
        "Nomor 4111 1111 1111 1112 salah Luhn",
        "NIK 3273012345678901",
        "😀 4111 1111 1111 1111",
        "Kunci sk-abcdefghijklmnop",
        "token ghp_0123456789abcdefghijABCDEFGHIJ",
        "aB3dE5gH7jK9mN1pQ3sT5vW7yZ9bC1dE3fG5",
        "Kaos_polos_lengan_pendek_warna_hitam_ukuran_XL",
        "angka ٤١١١ ١١١١ ١١١١ ١١١١ arab",
        "lebar ４１１１ １１１１ １１１１ １１１１",
        "dua kartu 5555 5555 5555 4444 dan 4111 1111 1111 1111",
        "",
    ]
    return [{"text": text, "spans": [list(span) for span in find_secrets(text)]} for text in texts]


def blocked_vectors():
    return {"apps": sorted(BLOCKED_APPS), "host_suffixes": sorted(BLOCKED_HOSTS)}


def log_text_vectors():
    decisions = ("allow", "confirm", "block", "handover", None)
    results = ("ok", "failed", "declined", "expired", "widened", "handed_over", None)
    return {
        "actions": agent_log.ACTION_TEXT,
        "reasons": agent_log.REASON_TEXT,
        "chain": {("unchecked" if key is None else key): value for key, value in agent_log.CHAIN_TEXT.items()},
        "results": [{"decision": decision, "result": result, "text": agent_log.result_text(decision, result)}
                    for decision in decisions for result in results],
        "unknown_action": "Aksi lain ({kind})",
        "unknown_reason": "Diblokir aturan keamanan ({reason}).",
        "explained_decisions": ["block", "confirm", "handover"],
        "max_target": agent_log.MAX_TARGET,
        "months": list(agent_log.MONTHS),
    }


VECTORS = {
    "tickets.json": ticket_vectors,
    "secrets.json": secret_vectors,
    "blocked.json": blocked_vectors,
    "log_text.json": log_text_vectors,
}


def render(build):
    return json.dumps(build(), ensure_ascii=False, indent=2) + "\n"


def main(out):
    out.mkdir(parents=True, exist_ok=True)

    for name, build in VECTORS.items():
        (out / name).write_bytes(render(build).encode("utf-8"))


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT)
