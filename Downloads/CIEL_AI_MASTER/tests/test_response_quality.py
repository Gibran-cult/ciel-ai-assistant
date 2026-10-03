import json
import base64
import re
import os

from pathlib import Path

import requests
from dotenv import load_dotenv


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

NGROK_URL = os.getenv("NGROK_URL")
NGROK_USER = os.getenv("NGROK_USER")
NGROK_PASSWORD = os.getenv("NGROK_PASSWORD")
LANGFLOW_API_KEY = os.getenv("LANGFLOW_API_KEY")
FLOW_ID = os.getenv("FLOW_ID")

NGROK_URL = (
    NGROK_URL.strip().rstrip("/")
    if NGROK_URL
    else None
)


# ============================================================
# PATH
# ============================================================

TEST_DIR = Path(__file__).parent

CASES_FILE = (
    TEST_DIR / "evaluation_cases.json"
)


# ============================================================
# VALIDATE CONFIG
# ============================================================

required_config = {
    "NGROK_URL": NGROK_URL,
    "NGROK_USER": NGROK_USER,
    "NGROK_PASSWORD": NGROK_PASSWORD,
    "LANGFLOW_API_KEY": LANGFLOW_API_KEY,
    "FLOW_ID": FLOW_ID,
}

missing = [
    name
    for name, value in required_config.items()
    if not value
]

if missing:
    raise RuntimeError(
        "Config belum lengkap: "
        + ", ".join(missing)
    )


# ============================================================
# LOAD CASES
# ============================================================

def load_cases():

    if not CASES_FILE.exists():
        raise FileNotFoundError(
            f"File evaluasi tidak ditemukan: "
            f"{CASES_FILE}"
        )

    with CASES_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:

        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError(
            "evaluation_cases.json harus "
            "berisi JSON array."
        )

    return data


# ============================================================
# API — TEXT
# ============================================================

def ask_ciel(
    question,
    timeout=120
):

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

    return (
        data["outputs"][0]
        ["outputs"][0]
        ["results"]["message"]
        ["data"]["text"]
    )


# ============================================================
# API — IMAGE
# ============================================================

def ask_ciel_with_image(
    question,
    image_path,
    timeout=120
):

    image_path = Path(image_path).resolve()

    if not image_path.exists():
        raise FileNotFoundError(
            f"Image tidak ditemukan: {image_path}"
        )

    print(
        f"   Vision image: {image_path.name}"
    )

    print(
        f"   Image size: {image_path.stat().st_size} bytes"
    )

    # ========================================================
    # 1. UPLOAD IMAGE
    # ========================================================

    upload_url = (
        f"{NGROK_URL}"
        f"/api/v1/files/upload/{FLOW_ID}"
    )

    upload_headers = {
        "Accept": "application/json",
        "x-api-key": LANGFLOW_API_KEY,
    }

    with image_path.open("rb") as image_file:

        upload_response = requests.post(
            upload_url,
            headers=upload_headers,
            auth=(
                NGROK_USER,
                NGROK_PASSWORD
            ),
            files={
                "file": (
                    image_path.name,
                    image_file,
                    "image/png"
                )
            },
            timeout=30,
        )

    upload_response.raise_for_status()

    upload_data = upload_response.json()

    file_path = upload_data.get("file_path")

    if not file_path:
        raise RuntimeError(
            "Langflow tidak mengembalikan file_path.\n"
            f"Response:\n{upload_data}"
        )

    print(
        f"   Uploaded file: {file_path}"
    )

    # ========================================================
    # 2. RUN FLOW
    # ========================================================

    run_url = (
        f"{NGROK_URL}"
        f"/api/v1/run/{FLOW_ID}"
    )

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "x-api-key": LANGFLOW_API_KEY,
    }

    payload = {
        "output_type": "chat",
        "input_type": "chat",

        "tweaks": {
            "ChatInput-X8W7I": {
                "files": file_path,
                "input_value": question
            }
        }
    }

    response = requests.post(
        run_url,
        headers=headers,
        auth=(
            NGROK_USER,
            NGROK_PASSWORD
        ),
        json=payload,
        params={
            "stream": "false"
        },
        timeout=120,
    )

    response.raise_for_status()

    data = response.json()

    return (
        data["outputs"][0]
        ["outputs"][0]
        ["results"]["message"]
        ["data"]["text"]
    )


# ============================================================
# QUALITY CHECKS
# ============================================================

def evaluate_answer(
    answer,
    checks
):

    failures = []

    if not isinstance(answer, str):
        return [
            "Output bukan string."
        ]

    normalized = answer.lower()

    # Normalisasi simbol matematika dan whitespace
    normalized = (
        normalized
        .replace("−", "-")
        .replace("–", "-")
        .replace("—", "-")
        .replace("＋", "+")
    )

    normalized = re.sub(
        r"\s*([+\-])\s*",
        r"\1",
        normalized
    )   

    # --------------------------------------------------------
    # MIN LENGTH
    # --------------------------------------------------------

    min_length = checks.get(
        "min_length"
    )

    if min_length is not None:

        if len(answer.strip()) < int(
            min_length
        ):

            failures.append(
                f"Output terlalu pendek: "
                f"{len(answer.strip())} "
                f"< {min_length}"
            )

    # --------------------------------------------------------
    # EXPECTED CONTAINS
    # Semua item harus ada
    # --------------------------------------------------------

    expected_contains = checks.get(
        "expected_contains",
        []
    )

    for expected in expected_contains:

        if str(expected).lower() not in normalized:

            failures.append(
                f"Tidak menemukan: "
                f"'{expected}'"
            )

    # --------------------------------------------------------
    # EXPECTED ANY
    # Minimal satu item harus ada
    # --------------------------------------------------------

    expected_any = checks.get(
        "expected_any",
        []
    )

    if expected_any:

        found_any = any(
            str(expected).lower()
            in normalized
            for expected in expected_any
        )

        if not found_any:

            failures.append(
                "Tidak ada satupun nilai "
                "expected_any yang ditemukan."
            )

    # --------------------------------------------------------
    # REQUIRED ABSENT
    # Semua item harus TIDAK ada
    # --------------------------------------------------------

    required_absent = checks.get(
        "required_absent",
        []
    )

    for forbidden in required_absent:

        if str(forbidden).lower() in normalized:

            failures.append(
                f"Menemukan forbidden phrase: "
                f"'{forbidden}'"
            )

    return failures


# ============================================================
# RUN ONE CASE
# ============================================================

def run_case(case):

    case_id = case.get(
        "id",
        "unknown"
    )

    category = case.get(
        "category",
        "unknown"
    )

    question = case.get(
        "question",
        ""
    )

    checks = case.get(
        "checks",
        {}
    )

    try:

        # ----------------------------------------------------
        # IMAGE CASE
        # ----------------------------------------------------

        image_relative = case.get(
            "image"
        )

        if image_relative:

            image_path = (
                TEST_DIR / image_relative
            )

            answer = ask_ciel_with_image(
                question,
                image_path
            )

        # ----------------------------------------------------
        # TEXT CASE
        # ----------------------------------------------------

        else:

            answer = ask_ciel(
                question
            )

        # ----------------------------------------------------
        # QUALITY CHECK
        # ----------------------------------------------------

        failures = evaluate_answer(
            answer,
            checks
        )

        passed = (
            len(failures) == 0
        )

        return {
            "id": case_id,
            "category": category,
            "passed": passed,
            "answer": answer,
            "failures": failures,
        }

    except Exception as error:

        return {
            "id": case_id,
            "category": category,
            "passed": False,
            "answer": "",
            "failures": [
                f"Execution error: {error}"
            ],
        }


# ============================================================
# MAIN
# ============================================================

def main():

    cases = load_cases()

    print()
    print("=" * 70)
    print("CIEL AI MASTER — RESPONSE QUALITY EVALUATION")
    print("=" * 70)
    print()

    results = []

    for case in cases:

        result = run_case(
            case
        )

        results.append(
            result
        )

        symbol = (
            "✅"
            if result["passed"]
            else "❌"
        )

        status = (
            "PASS"
            if result["passed"]
            else "FAIL"
        )

        print(
            f"{symbol} "
            f"{result['id']:<30} "
            f"{status}"
        )

        if not result["passed"]:

            for failure in result[
                "failures"
            ]:

                print(
                    f"   └─ {failure}"
                )

        # Jangan print seluruh response
        # supaya output terminal tidak terlalu panjang.
        if result["answer"]:

            preview = (
                result["answer"]
                .replace("\n", " ")
                .strip()
            )

            print(
                f"   Output: "
                f"{preview[:160]}"
            )

        print()

    # ========================================================
    # SUMMARY
    # ========================================================

    total = len(results)

    passed = sum(
        1
        for result in results
        if result["passed"]
    )

    failed = (
        total - passed
    )

    print("=" * 70)

    print(
        f"RESULT: "
        f"{passed}/{total} PASSED"
    )

    print(
        f"PASSED: {passed}"
    )

    print(
        f"FAILED: {failed}"
    )

    print("=" * 70)

    if failed == 0:

        print(
            "✅ RESPONSE QUALITY EVALUATION PASSED"
        )

    else:

        print(
            "❌ RESPONSE QUALITY EVALUATION FAILED"
        )

        raise SystemExit(1)


if __name__ == "__main__":
    main()