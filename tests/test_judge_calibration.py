import json
from pathlib import Path

from test_llm_judge import (
    build_judge_prompt,
    run_judge,
    parse_json_response,
    validate_judge_output,
)
from test_llm_judge import load_rubric


# ============================================================
# PATH
# ============================================================

TEST_DIR = Path(__file__).parent

CASES_FILE = (
    TEST_DIR / "adversarial_cases.json"
)


# ============================================================
# LOAD CASES
# ============================================================

def load_cases():

    with CASES_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(file)


# ============================================================
# ASSERTIONS
# ============================================================

def validate_assertions(
    judged,
    assertions,
):

    scores = judged["scores"]

    overall_scores = [
        score
        for score in scores.values()
        if score is not None
    ]

    if not overall_scores:
        raise ValueError(
            "Judge tidak memberikan score yang dapat dinilai."
        )

    overall = (
        sum(overall_scores)
        / len(overall_scores)
    )

    failures = []

    # --------------------------------------------------------
    # OVERALL MIN
    # --------------------------------------------------------

    overall_min = assertions.get(
        "overall_min"
    )

    if (
        overall_min is not None
        and overall < overall_min
    ):

        failures.append(
            f"Overall {overall:.2f} "
            f"< minimum {overall_min}"
        )

    # --------------------------------------------------------
    # OVERALL MAX
    # --------------------------------------------------------

    overall_max = assertions.get(
        "overall_max"
    )

    if (
        overall_max is not None
        and overall > overall_max
    ):

        failures.append(
            f"Overall {overall:.2f} "
            f"> maximum {overall_max}"
        )

    # --------------------------------------------------------
    # CRITERION MIN
    # --------------------------------------------------------

    criterion_min = assertions.get(
        "criterion_min",
        {}
    )

    for criterion_id, minimum in criterion_min.items():

        score = scores.get(
            criterion_id
        )

        if score is None:

            failures.append(
                f"{criterion_id}: N/A "
                f"padahal minimum {minimum}"
            )

        elif score < minimum:

            failures.append(
                f"{criterion_id}: {score} "
                f"< minimum {minimum}"
            )

    # --------------------------------------------------------
    # CRITERION MAX
    # --------------------------------------------------------

    criterion_max = assertions.get(
        "criterion_max",
        {}
    )

    for criterion_id, maximum in criterion_max.items():

        score = scores.get(
            criterion_id
        )

        if score is None:

            failures.append(
                f"{criterion_id}: N/A "
                f"padahal maximum {maximum}"
            )

        elif score > maximum:

            failures.append(
                f"{criterion_id}: {score} "
                f"> maximum {maximum}"
            )

    return failures, overall


# ============================================================
# MAIN
# ============================================================

def main():

    cases = load_cases()
    rubric = load_rubric()

    print()
    print("=" * 75)
    print(
        "CIEL AI MASTER — ADVERSARIAL JUDGE CALIBRATION"
    )
    print("=" * 75)
    print()

    passed = 0
    failed = 0

    for case in cases:

        case_id = case["id"]
        category = case["category"]
        question = case["question"]
        answer = case["answer"]
        judge_context = case.get(
            "judge_context",
            {}
        )

        criteria = rubric.get(
            category,
            {}
        ).get(
            "criteria",
            []
        )

        print(
            f"CASE: {case_id}"
        )

        prompt = build_judge_prompt(
            category=category,
            question=question,
            answer=answer,
            criteria=criteria,
            judge_context=judge_context,
        )

        try:

            raw = run_judge(
                prompt
            )

            judged = parse_json_response(
                raw
            )

            judged = validate_judge_output(
                judged,
                criteria
            )

            failures, overall = (
                validate_assertions(
                    judged,
                    case.get(
                        "assertions",
                        {}
                    )
                )
            )

            if failures:

                failed += 1

                print(
                    "  ❌ CALIBRATION FAIL"
                )

                print(
                    f"  Overall: {overall:.2f}/4"
                )

                for failure in failures:

                    print(
                        f"  └─ {failure}"
                    )

            else:

                passed += 1

                print(
                    "  ✅ CALIBRATION PASS"
                )

                print(
                    f"  Overall: {overall:.2f}/4"
                )

        except Exception as error:

            failed += 1

            print(
                "  ❌ EXECUTION ERROR"
            )

            print(
                f"  └─ {error}"
            )

        print()

    # ========================================================
    # SUMMARY
    # ========================================================

    print("=" * 75)

    print(
        f"Calibration result: "
        f"{passed}/{len(cases)} PASSED"
    )

    print(
        f"Passed: {passed}"
    )

    print(
        f"Failed: {failed}"
    )

    print("=" * 75)

    if failed:

        raise SystemExit(1)

    print(
        "✅ LLM JUDGE CALIBRATION PASSED"
    )


if __name__ == "__main__":
    main()