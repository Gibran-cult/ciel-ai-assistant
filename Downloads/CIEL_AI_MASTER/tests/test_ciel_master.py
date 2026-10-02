import os
import re
import requests
from dotenv import load_dotenv


# ============================================================
# LOAD CONFIG
# ============================================================

load_dotenv()

NGROK_URL = os.getenv("NGROK_URL")
NGROK_USER = os.getenv("NGROK_USER")
NGROK_PASSWORD = os.getenv("NGROK_PASSWORD")
LANGFLOW_API_KEY = os.getenv("LANGFLOW_API_KEY")
FLOW_ID = os.getenv("FLOW_ID")


# ============================================================
# VALIDATION
# ============================================================

required = {
    "NGROK_URL": NGROK_URL,
    "NGROK_USER": NGROK_USER,
    "NGROK_PASSWORD": NGROK_PASSWORD,
    "LANGFLOW_API_KEY": LANGFLOW_API_KEY,
    "FLOW_ID": FLOW_ID,
}

missing = [
    name
    for name, value in required.items()
    if not value
]

if missing:
    raise RuntimeError(
        "Config belum lengkap: "
        + ", ".join(missing)
    )


NGROK_URL = NGROK_URL.strip().rstrip("/")


# ============================================================
# API CALL
# ============================================================

def ask_ciel(question, timeout=120):

    url = (
        f"{NGROK_URL}"
        f"/api/v1/run/{FLOW_ID}"
    )

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "x-api-key": LANGFLOW_API_KEY,
    }

    payload = {
        "input_value": question,
        "input_type": "chat",
        "output_type": "chat",
    }

    response = requests.post(
        url,
        headers=headers,
        auth=(
            NGROK_USER,
            NGROK_PASSWORD
        ),
        json=payload,
        params={
            "stream": "false"
        },
        timeout=timeout,
    )

    response.raise_for_status()

    data = response.json()

    answer = (
        data["outputs"][0]
        ["outputs"][0]
        ["results"]["message"]
        ["data"]["text"]
    )

    return answer


# ============================================================
# HELPERS
# ============================================================

def check_contains(text, candidates):

    normalized = text.lower()

    return any(
        candidate.lower() in normalized
        for candidate in candidates
    )


def print_result(
    name,
    passed,
    detail=""
):

    if passed:
        symbol = "✅"
        status = "PASS"
    else:
        symbol = "❌"
        status = "FAIL"

    print(
        f"{symbol} {name:<25} {status}"
    )

    if detail:
        print(
            f"   {detail}"
        )


# ============================================================
# TEST 1 — BASIC CHAT
# ============================================================

def test_chat():

    answer = ask_ciel(
        "Halo Ciel, jawab singkat."
    )

    passed = bool(
        answer
        and len(answer.strip()) > 0
    )

    print_result(
        "Basic Chat",
        passed
    )

    return passed


# ============================================================
# TEST 2 — MATH
# ============================================================

def test_math():

    answer = ask_ciel(
        "Hitung limit "
        "(x² - 9)/(x - 3) "
        "saat x mendekati 3."
    )

    passed = (
        "6" in answer
        and len(answer.strip()) > 0
    )

    print_result(
        "Math Tutor",
        passed,
        answer.replace("\n", " ")[:120]
    )

    return passed


# ============================================================
# TEST 3 — DATA ANALYST
# ============================================================

def test_data():

    answer = ask_ciel(
        "Berapa total Sales_Amount "
        "pada dataset?"
    )

    normalized = answer.replace(
        ",", ""
    )

    passed = (
        "1065600.71" in normalized
    )

    print_result(
        "Data Analyst",
        passed,
        answer.replace("\n", " ")[:150]
    )

    return passed


# ============================================================
# TEST 4 — KNOWLEDGE
# ============================================================

def test_knowledge():

    answer = ask_ciel(
        "Apa itu overfitting?"
    )

    passed = (
        len(answer.strip()) > 0
        and check_contains(
            answer,
            [
                "model",
                "training",
                "data",
                "general"
            ]
        )
    )

    print_result(
        "Knowledge Agent",
        passed,
        answer.replace("\n", " ")[:150]
    )

    return passed


# ============================================================
# TEST 5 — RESEARCH
# ============================================================

def test_research():

    answer = ask_ciel(
        "Cari informasi terbaru "
        "tentang Python."
    )

    passed = (
        len(answer.strip()) > 0
    )

    print_result(
        "Research Agent",
        passed,
        answer.replace("\n", " ")[:150]
    )

    return passed


# ============================================================
# TEST 6 — HEALTH
# ============================================================

def test_health():

    url = f"{NGROK_URL}/health_check"

    response = requests.get(
        url,
        auth=(
            NGROK_USER,
            NGROK_PASSWORD
        ),
        timeout=10,
    )

    response.raise_for_status()

    data = response.json()

    passed = (
        data.get("status") == "ok"
        and data.get("chat") == "ok"
        and data.get("db") == "ok"
    )

    print_result(
        "Backend Health",
        passed
    )

    return passed


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 55)
    print("CIEL AI MASTER — REGRESSION TEST")
    print("=" * 55)
    print()

    tests = [
        test_health,
        test_chat,
        test_math,
        test_data,
        test_knowledge,
        test_research,
    ]

    results = []

    for test in tests:

        try:

            results.append(
                test()
            )

        except Exception as error:

            print_result(
                test.__name__,
                False,
                str(error)
            )

            results.append(False)

    print()
    print("=" * 55)

    passed_count = sum(
        results
    )

    total_count = len(
        results
    )

    print(
        f"RESULT: "
        f"{passed_count}/{total_count} PASSED"
    )

    print("=" * 55)

    if passed_count == total_count:

        print(
            "✅ REGRESSION TEST PASSED"
        )

    else:

        print(
            "❌ REGRESSION TEST FAILED"
        )

        raise SystemExit(1)


if __name__ == "__main__":
    main()