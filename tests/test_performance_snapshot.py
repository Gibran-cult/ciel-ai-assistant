import json
import os
import statistics
import time
from pathlib import Path

import requests
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]

load_dotenv(
    ROOT / ".env"
)

NGROK_URL = os.getenv(
    "NGROK_URL"
)

NGROK_USER = os.getenv(
    "NGROK_USER"
)

NGROK_PASSWORD = os.getenv(
    "NGROK_PASSWORD"
)

LANGFLOW_API_KEY = os.getenv(
    "LANGFLOW_API_KEY"
)

FLOW_ID = os.getenv(
    "FLOW_ID"
)

RUNS = 7

QUESTION = (
    "Jelaskan apa itu Data Science "
    "dalam satu atau dua kalimat."
)


def validate_config():

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


def ask_once():

    url = (
        NGROK_URL.rstrip("/")
        + f"/api/v1/run/{FLOW_ID}"
    )

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "x-api-key": LANGFLOW_API_KEY,
    }

    payload = {
        "input_value": QUESTION,
        "input_type": "chat",
        "output_type": "chat",
    }

    start = time.perf_counter()

    response = requests.post(
        url,
        headers=headers,
        auth=(
            NGROK_USER,
            NGROK_PASSWORD,
        ),
        json=payload,
        params={
            "stream": "false"
        },
        timeout=120,
    )

    elapsed = (
        time.perf_counter()
        - start
    )

    response.raise_for_status()

    data = response.json()

    answer = (
        data["outputs"][0]
        ["outputs"][0]
        ["results"]["message"]
        ["data"]["text"]
    )

    if not answer.strip():
        raise RuntimeError(
            "Backend mengembalikan "
            "jawaban kosong."
        )

    return elapsed


def percentile_95(values):

    ordered = sorted(values)

    if len(ordered) == 1:
        return ordered[0]

    index = 0.95 * (
        len(ordered) - 1
    )

    lower = int(index)
    upper = min(
        lower + 1,
        len(ordered) - 1,
    )

    weight = index - lower

    return (
        ordered[lower]
        + (
            ordered[upper]
            - ordered[lower]
        )
        * weight
    )


def main():

    validate_config()

    print()
    print("=" * 70)
    print(
        "CIEL AI MASTER - "
        "PERFORMANCE SNAPSHOT"
    )
    print("=" * 70)
    print()

    latencies = []

    for i in range(1, RUNS + 1):

        elapsed = ask_once()

        latencies.append(
            elapsed
        )

        label = (
            "first"
            if i == 1
            else "warm"
        )

        print(
            f"Run {i}: "
            f"{elapsed:.3f}s "
            f"({label})"
        )

    first_request = latencies[0]

    warm_values = latencies[1:]

    warm_median = statistics.median(
        warm_values
    )

    overall_median = statistics.median(
        latencies
    )

    p95 = percentile_95(
        latencies
    )

    result = {
        "runs": RUNS,
        "first_request_s": round(
            first_request,
            3,
        ),
        "warm_median_s": round(
            warm_median,
            3,
        ),
        "overall_median_s": round(
            overall_median,
            3,
        ),
        "p95_s": round(
            p95,
            3,
        ),
        "latencies_s": [
            round(
                value,
                3,
            )
            for value in latencies
        ],
    }

    print()
    print("=" * 70)
    print("PERFORMANCE SUMMARY")
    print("=" * 70)

    print(
        f"First request : "
        f"{first_request:.3f}s"
    )

    print(
        f"Warm median   : "
        f"{warm_median:.3f}s"
    )

    print(
        f"Overall median: "
        f"{overall_median:.3f}s"
    )

    print(
        f"P95           : "
        f"{p95:.3f}s"
    )

    print(
        f"Runs          : "
        f"{RUNS}"
    )

    print()
    print(
        "PERFORMANCE_RESULT="
        + json.dumps(
            result,
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
