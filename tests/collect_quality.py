import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import os

ROOT = Path(__file__).resolve().parents[1]

RESULT_FILE = (
    ROOT
    / "tests"
    / "results"
    / "quality_latest.json"
)


# ============================================================
# SUBPROCESS RUNNER
# ============================================================

def run_script(path):
    process = subprocess.run(
        [
            sys.executable,
            "-u",
            str(path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={
            **os.environ,
            "PYTHONUNBUFFERED": "1",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
        },
    )

    stdout = process.stdout or ""
    stderr = process.stderr or ""

    combined = stdout + "\n" + stderr

    return {
        "passed": process.returncode == 0,
        "return_code": process.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "output": combined,
    }


# ============================================================
# RESPONSE QUALITY PARSER
# ============================================================

def parse_response_quality(output):
    if not output:
        return {
            "passed": 0,
            "failed": 0,
            "total": 0,
            "pass_rate": None,
            "status": "not_collected",
        }

    # Primary format:
    # RESULT: 7/9 PASSED
    match = re.search(
        r"RESULT\s*:\s*(\d+)\s*/\s*(\d+)\s*PASSED",
        output,
        re.IGNORECASE,
    )

    if match:
        passed = int(match.group(1))
        total = int(match.group(2))
        failed = total - passed

        return {
            "passed": passed,
            "failed": failed,
            "total": total,
            "pass_rate": (
                passed / total
                if total > 0
                else None
            ),
            "status": (
                "healthy"
                if failed == 0
                else "degraded"
            ),
        }

    # Fallback:
    # PASSED: 7
    # FAILED: 2
    passed_match = re.search(
        r"PASSED\s*:\s*(\d+)",
        output,
        re.IGNORECASE,
    )

    failed_match = re.search(
        r"FAILED\s*:\s*(\d+)",
        output,
        re.IGNORECASE,
    )

    if passed_match and failed_match:
        passed = int(passed_match.group(1))
        failed = int(failed_match.group(1))
        total = passed + failed

        return {
            "passed": passed,
            "failed": failed,
            "total": total,
            "pass_rate": (
                passed / total
                if total > 0
                else None
            ),
            "status": (
                "healthy"
                if failed == 0
                else "degraded"
            ),
        }

    return {
        "passed": 0,
        "failed": 0,
        "total": 0,
        "pass_rate": None,
        "status": "not_collected",
    }


# ============================================================
# MEMORY BENCHMARK PARSER
# ============================================================

def parse_memory_benchmark(output):
    recall = {
        1: [],
        3: [],
        5: [],
    }

    for line in output.splitlines():

        match = re.search(
            r"^\s*"
            r"(education|python|project|career|preference|goal)"
            r"\s*:\s*"
            r"K1=(YES|NO)"
            r"\s*\|\s*"
            r"K3=(YES|NO)"
            r"\s*\|\s*"
            r"K5=(YES|NO)",
            line,
            re.IGNORECASE,
        )

        if not match:
            continue

        values = {
            1: match.group(2).upper() == "YES",
            3: match.group(3).upper() == "YES",
            5: match.group(4).upper() == "YES",
        }

        for k, value in values.items():
            recall[k].append(value)

    recall_percent = {}

    for k in (1, 3, 5):

        values = recall[k]

        if not values:
            recall_percent[k] = None
        else:
            recall_percent[k] = (
                sum(values) / len(values)
            )

    reduction_match = re.search(
        r"K=5:\s*\d+\s*->\s*\d+\s*chars\s*"
        r"\(([\d.]+)%\s*reduction\)",
        output,
        re.IGNORECASE,
    )

    reduction = (
        float(reduction_match.group(1))
        if reduction_match
        else None
    )

    return {
        "recall_k1": recall_percent[1],
        "recall_k3": recall_percent[3],
        "recall_k5": recall_percent[5],
        "context_reduction_k5_percent": reduction,
    }


# ============================================================
# PERFORMANCE PARSER
# ============================================================

def parse_performance(output):
    match = re.search(
        r"PERFORMANCE_RESULT\s*=\s*(\{.*\})",
        output,
        re.IGNORECASE,
    )

    if not match:
        return {
            "first_request_s": None,
            "warm_median_s": None,
            "overall_median_s": None,
            "p95_s": None,
            "runs": None,
            "latencies_s": [],
            "status": "not_collected",
        }

    try:
        result = json.loads(match.group(1))
    except json.JSONDecodeError:
        return {
            "first_request_s": None,
            "warm_median_s": None,
            "overall_median_s": None,
            "p95_s": None,
            "runs": None,
            "latencies_s": [],
            "status": "invalid_result",
        }

    return {
        "first_request_s": result.get("first_request_s"),
        "warm_median_s": result.get("warm_median_s"),
        "overall_median_s": result.get("overall_median_s"),
        "p95_s": result.get("p95_s"),
        "runs": result.get("runs"),
        "latencies_s": result.get(
            "latencies_s",
            [],
        ),
        "status": "collected",
    }


# ============================================================
# MAIN
# ============================================================

def main():

    if not RESULT_FILE.exists():
        raise FileNotFoundError(
            f"Result file tidak ditemukan: {RESULT_FILE}"
        )

    with RESULT_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    checks = {}

    # ========================================================
    # RESILIENCE
    # ========================================================

    resilience_test = (
        ROOT
        / "tests"
        / "test_resilience.py"
    )

    checks["resilience"] = run_script(
        resilience_test
    )

    # ========================================================
    # MEMORY CONTRACT
    # ========================================================

    memory_contract_test = (
        ROOT
        / "tests"
        / "test_memory_v110_contract.py"
    )

    checks["memory_v110_contract"] = run_script(
        memory_contract_test
    )

    # ========================================================
    # RESPONSE QUALITY
    # ========================================================

    response_quality_test = (
        ROOT
        / "tests"
        / "test_response_quality.py"
    )

    response_quality_result = run_script(
        response_quality_test
    )

    checks["response_quality"] = (
        response_quality_result
    )

    response_quality = parse_response_quality(
        response_quality_result["output"]
    )

    # DEBUG OUTPUT ONLY WHEN PARSER FAILS
    if response_quality["total"] == 0:

        print()
        print(
            "[DEBUG] Response quality output "
            "tidak memiliki RESULT yang terbaca."
        )
        print(
            "[DEBUG] Last 3000 characters:"
        )
        print(
            response_quality_result["output"][-3000:]
        )
        print()

    # ========================================================
    # MEMORY MULTI-QUERY
    # ========================================================

    memory_benchmark_test = (
        ROOT
        / "tests"
        / "test_memory_multi_query.py"
    )

    memory_benchmark_result = run_script(
        memory_benchmark_test
    )

    checks["memory_multi_query"] = (
        memory_benchmark_result
    )

    memory = parse_memory_benchmark(
        memory_benchmark_result["output"]
    )

    # ========================================================
    # PERFORMANCE SNAPSHOT
    # ========================================================

    performance_test = (
        ROOT
        / "tests"
        / "test_performance_snapshot.py"
    )

    performance_result = run_script(
        performance_test
    )

    checks["performance"] = (
        performance_result
    )

    performance = parse_performance(
        performance_result["output"]
    )

    # ========================================================
    # AUTOMATED CHECK SUMMARY
    # ========================================================

    passed_checks = sum(
        1
        for result in checks.values()
        if result.get("passed")
    )

    total_checks = len(checks)

    if total_checks == 0:

        status = "unknown"
        score = None

    elif passed_checks == total_checks:

        status = "healthy"
        score = 1.0

    else:

        status = "degraded"
        score = (
            passed_checks
            / total_checks
        )

    # ========================================================
    # WRITE RESULT
    # ========================================================

    data["project"] = (
        data.get(
            "project",
            "Ciel AI Master",
        )
    )

    data["version"] = (
        data.get(
            "version",
            "v1.1.0",
        )
    )

    data["generated_at"] = (
        datetime.now(
            timezone.utc
        ).isoformat()
    )

    data["overall"] = {
        "status": status,
        "score": score,
    }

    data["response_quality"] = (
        response_quality
    )

    data["memory"] = memory

    data["performance"] = {
        "first_request_s": performance[
            "first_request_s"
        ],
        "warm_median_s": performance[
            "warm_median_s"
        ],
        "overall_median_s": performance[
            "overall_median_s"
        ],
        "p95_s": performance[
            "p95_s"
        ],
    }

    data["resilience"] = {
        "passed": 1
        if checks["resilience"]["passed"]
        else 0,
        "failed": 0
        if checks["resilience"]["passed"]
        else 1,
        "total": 1,
        "pass_rate": (
            1.0
            if checks["resilience"]["passed"]
            else 0.0
        ),
    }

    data["automated_checks"] = {
        "passed": passed_checks,
        "failed": (
            total_checks
            - passed_checks
        ),
        "total": total_checks,
        "details": {
            name: {
                "passed": result["passed"],
                "return_code": result[
                    "return_code"
                ],
            }
            for name, result in checks.items()
        },
    }

    with RESULT_FILE.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as file:

        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )

        file.write("\n")

    # ========================================================
    # TERMINAL SUMMARY
    # ========================================================

    print("=" * 70)
    print(
        "CIEL AI MASTER - "
        "PRODUCTION QUALITY COLLECTOR"
    )
    print("=" * 70)
    print()

    for name, result in checks.items():

        status_text = (
            "PASS"
            if result["passed"]
            else "FAIL"
        )

        print(
            f"{name:<30} "
            f"{status_text}"
        )

    print()

    print(
        f"Automated checks: "
        f"{passed_checks}/{total_checks}"
    )

    print(
        f"Response quality: "
        f"{response_quality['passed']}/"
        f"{response_quality['total']}"
    )

    recall_k5 = memory.get(
        "recall_k5"
    )

    if recall_k5 is None:
        print(
            "Memory recall K=5: N/A"
        )
    else:
        print(
            "Memory recall K=5: "
            f"{recall_k5 * 100:.1f}%"
        )

    context_reduction = memory.get(
        "context_reduction_k5_percent"
    )

    if context_reduction is None:
        print(
            "Context reduction K=5: N/A"
        )
    else:
        print(
            "Context reduction K=5: "
            f"{context_reduction:.1f}%"
        )

    if performance["overall_median_s"] is None:

        print(
            "Performance: N/A"
        )

    else:

        print(
            "Performance:"
        )
        print(
            f"  First request : "
            f"{performance['first_request_s']:.3f}s"
        )
        print(
            f"  Warm median   : "
            f"{performance['warm_median_s']:.3f}s"
        )
        print(
            f"  Overall median: "
            f"{performance['overall_median_s']:.3f}s"
        )
        print(
            f"  P95           : "
            f"{performance['p95_s']:.3f}s"
        )

    print(
        f"Overall status: {status}"
    )

    print()
    print(
        f"Result file: {RESULT_FILE}"
    )


if __name__ == "__main__":
    main()