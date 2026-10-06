import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

RESULT_FILE = (
    ROOT
    / "tests"
    / "results"
    / "quality_latest.json"
)


TESTS = [
    {
        "name": "resilience",
        "path": ROOT / "tests" / "test_resilience.py",
    },
    {
        "name": "memory_v110_contract",
        "path": ROOT / "tests" / "test_memory_v110_contract.py",
    },
]


def run_test(path):
    process = subprocess.run(
        [
            sys.executable,
            str(path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    return {
        "passed": process.returncode == 0,
        "return_code": process.returncode,
        "stdout": process.stdout[-4000:],
        "stderr": process.stderr[-2000:],
    }


def main():

    with RESULT_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    checks = {}

    for test in TESTS:

        name = test["name"]
        path = test["path"]

        if not path.exists():
            checks[name] = {
                "passed": False,
                "return_code": None,
                "error": "Test file tidak ditemukan.",
            }
            continue

        result = run_test(path)

        checks[name] = {
            "passed": result["passed"],
            "return_code": result["return_code"],
            "output": result["stdout"],
            "error": result["stderr"],
        }

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
            passed_checks / total_checks
        )

    data["generated_at"] = (
        datetime.now(timezone.utc).isoformat()
    )

    data["overall"] = {
        "status": status,
        "score": score,
    }

    data["automated_checks"] = {
        "passed": passed_checks,
        "failed": total_checks - passed_checks,
        "total": total_checks,
        "details": checks,
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

    print("=" * 60)
    print("CIEL AI MASTER - RESULT COLLECTOR")
    print("=" * 60)
    print()

    for name, result in checks.items():

        status_text = (
            "PASS"
            if result.get("passed")
            else "FAIL"
        )

        print(
            f"{name:<30} {status_text}"
        )

    print()
    print(
        f"Automated checks: "
        f"{passed_checks}/{total_checks}"
    )

    print(
        f"Overall status: {status}"
    )

    print(
        f"Result file: {RESULT_FILE}"
    )


if __name__ == "__main__":
    main()
