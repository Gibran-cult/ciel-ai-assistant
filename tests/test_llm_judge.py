import json
import re
from pathlib import Path

import requests


# ============================================================
# CONFIGURATION
# ============================================================

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
JUDGE_MODEL = "qwen2.5vl:3b"

TEST_DIR = Path(__file__).parent

CASES_FILE = (
    TEST_DIR / "evaluation_cases.json"
)

RUBRIC_FILE = (
    TEST_DIR / "quality_rubric.json"
)


# ============================================================
# LOAD JSON
# ============================================================

def load_json(path):

    if not path.exists():
        raise FileNotFoundError(
            f"File tidak ditemukan: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


def load_cases():
    return load_json(
        CASES_FILE
    )


def load_rubric():
    return load_json(
        RUBRIC_FILE
    )


# ============================================================
# JUDGE PROMPT
# ============================================================

def build_judge_prompt(
    category,
    question,
    answer,
    criteria,
    judge_context,
):

    criterion_ids = [
        item["id"]
        for item in criteria
    ]

    criteria_text = "\n".join(
        f"- {item['id']}: {item['description']}"
        for item in criteria
    )

    ground_truth = judge_context.get(
        "ground_truth"
    )

    important_facts = (
        judge_context.get(
            "important_facts",
            []
        )
    )

    verification_requirements = (
        judge_context.get(
            "verification_requirements",
            []
        )
    )

    limitations = judge_context.get(
        "limitations",
        ""
    )

    important_facts_text = (
        "\n".join(
            f"- {fact}"
            for fact in important_facts
        )
        if important_facts
        else "Tidak ada."
    )

    verification_text = (
        "\n".join(
            f"- {item}"
            for item in verification_requirements
        )
        if verification_requirements
        else "Tidak ada."
    )

    if ground_truth is None:
        ground_truth_text = (
            "TIDAK TERSEDIA. "
            "Jangan mengarang ground truth."
        )
    else:
        ground_truth_text = ground_truth

    example_scores = {
        criterion_id: None
        for criterion_id in criterion_ids
    }

    example_json = json.dumps(
        {
            "scores": example_scores,
            "summary": (
                "ringkasan singkat"
            )
        },
        ensure_ascii=False,
        indent=2
    )

    return f"""
Anda adalah evaluator kualitas jawaban AI.

Tugas Anda HANYA mengevaluasi jawaban AI.
Jangan menjawab pertanyaan pengguna.

========================
KATEGORI
========================

{category}

========================
PERTANYAAN
========================

{question}

========================
JAWABAN AI
========================

{answer}

========================
REFERENSI EVALUASI
========================

Ground truth:
{ground_truth_text}

Important facts:
{important_facts_text}

Verification requirements:
{verification_text}

Limitations:
{limitations}

========================
KRITERIA
========================

{criteria_text}

========================
SKALA
========================

4 = sangat baik
3 = baik
2 = cukup
1 = buruk
0 = gagal
null = tidak dapat dinilai dengan bukti yang tersedia

ATURAN PENTING:

1. Nilai SETIAP criterion yang tersedia.
2. Jangan membuat criterion baru.
3. Jangan mengubah nama criterion.
4. Gunakan HANYA informasi dari:
   - pertanyaan
   - jawaban AI
   - referensi evaluasi di atas
5. Jangan mengarang fakta tambahan.
6. Jika suatu criterion tidak dapat dibuktikan
   dari informasi yang tersedia, gunakan null.
7. null BUKAN kegagalan.
8. Nilai 0 hanya jika terdapat bukti kuat
   bahwa jawaban gagal pada criterion tersebut.
9. Untuk research freshness/evidence:
   jika tidak tersedia tanggal atau bukti yang cukup,
   gunakan null, bukan 0.
10. Grounding harus dinilai berdasarkan referensi
    evaluasi yang diberikan, bukan asumsi pribadi.

ID CRITERION YANG VALID:

{", ".join(criterion_ids)}

Contoh JSON yang BENAR:

{example_json}

Kembalikan HANYA JSON valid.
Jangan gunakan markdown.
Jangan gunakan code fence.
""".strip()


# ============================================================
# OLLAMA JUDGE
# ============================================================

def run_judge(prompt):

    payload = {
        "model": JUDGE_MODEL,
        "stream": False,
        "format": "json",

        "options": {
            "temperature": 0
        },

        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
    }

    response = requests.post(
        OLLAMA_URL,
        json=payload,
        timeout=120,
    )

    response.raise_for_status()

    data = response.json()

    return data["message"]["content"]


# ============================================================
# PARSE JSON
# ============================================================

def parse_json_response(text):

    text = text.strip()

    try:
        return json.loads(text)

    except json.JSONDecodeError:
        pass

    match = re.search(
        r"\{.*\}",
        text,
        re.DOTALL,
    )

    if not match:
        raise ValueError(
            "Judge tidak mengembalikan JSON valid."
        )

    return json.loads(
        match.group(0)
    )


# ============================================================
# VALIDATE JUDGE OUTPUT
# ============================================================

def validate_judge_output(
    result,
    criteria
):

    if not isinstance(
        result,
        dict
    ):
        raise ValueError(
            "Output Judge harus JSON object."
        )

    scores = result.get(
        "scores"
    )

    if not isinstance(
        scores,
        dict
    ):
        raise ValueError(
            "Field 'scores' harus object."
        )

    expected_ids = {
        item["id"]
        for item in criteria
    }

    actual_ids = set(
        scores.keys()
    )

    if expected_ids != actual_ids:

        raise ValueError(
            "Criterion dari judge tidak sesuai.\n"
            f"Expected: {sorted(expected_ids)}\n"
            f"Actual: {sorted(actual_ids)}"
        )

    normalized_scores = {}

    for criterion_id, score in scores.items():

        # N/A
        if score is None:
            normalized_scores[
                criterion_id
            ] = None
            continue

        # Model kadang mengembalikan angka
        # sebagai string.
        if isinstance(
            score,
            str
        ):

            score = score.strip()

            if score.lower() in {
                "null",
                "n/a",
                "na",
            }:

                normalized_scores[
                    criterion_id
                ] = None

                continue

            if score.isdigit():
                score = int(score)

        if not isinstance(
            score,
            int
        ):

            raise ValueError(
                f"Score {criterion_id} "
                f"tidak valid: {score}"
            )

        if not 0 <= score <= 4:

            raise ValueError(
                f"Score {criterion_id} "
                "harus 0-4."
            )

        normalized_scores[
            criterion_id
        ] = score

    result["scores"] = (
        normalized_scores
    )

    return result


# ============================================================
# CALCULATE CASE SCORE
# ============================================================

def calculate_case_score(scores):

    valid_scores = [
        score
        for score in scores.values()
        if score is not None
    ]

    if not valid_scores:

        return {
            "earned": 0,
            "maximum": 0,
            "average": None,
            "percentage": None,
            "na_count": len(scores),
        }

    earned = sum(
        valid_scores
    )

    maximum = (
        len(valid_scores) * 4
    )

    average = (
        earned / len(valid_scores)
    )

    percentage = (
        earned / maximum * 100
    )

    return {
        "earned": earned,
        "maximum": maximum,
        "average": average,
        "percentage": percentage,
        "na_count": (
            len(scores)
            - len(valid_scores)
        ),
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print(
        "CIEL AI MASTER — "
        "REFERENCE-AWARE LLM-AS-A-JUDGE"
    )
    print("=" * 70)
    print()

    cases = load_cases()
    rubric = load_rubric()

    # Vision belum ikut LLM Judge.
    # Vision tetap dievaluasi melalui deterministic test.
    cases = [
        case
        for case in cases
        if case.get("category")
        != "vision"
    ]

    # Import evaluator yang sudah ada
    # agar mekanisme pemanggilan Ciel tetap konsisten.
    from test_response_quality import (
        run_case,
    )

    total_earned = 0
    total_maximum = 0

    total_na = 0

    successful_cases = 0

    for case in cases:

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

        if not criteria:

            print(
                "  ❌ Rubric tidak ditemukan."
            )
            print()
            continue

        # ====================================================
        # RUN CIEL
        # ====================================================

        try:

            result = run_case(
                case
            )

            answer = result.get(
                "answer",
                ""
            )

        except Exception as error:

            print(
                f"  ❌ Ciel execution error: "
                f"{error}"
            )

            print()
            continue

        # ====================================================
        # BUILD PROMPT
        # ====================================================

        prompt = build_judge_prompt(
            category=category,
            question=question,
            answer=answer,
            criteria=criteria,
            judge_context=judge_context,
        )

        # ====================================================
        # RUN JUDGE
        # ====================================================

        try:

            raw_judge = run_judge(
                prompt
            )

            judged = parse_json_response(
                raw_judge
            )

            judged = validate_judge_output(
                judged,
                criteria
            )

        except Exception as error:

            print(
                f"  ❌ Judge error: "
                f"{error}"
            )

            print()
            continue

        # ====================================================
        # SCORE
        # ====================================================

        scores = judged[
            "scores"
        ]

        case_score = (
            calculate_case_score(
                scores
            )
        )

        for criterion_id in (
            scores
        ):

            score = scores[
                criterion_id
            ]

            if score is None:

                print(
                    f"  {criterion_id:<25}"
                    f"N/A"
                )

            else:

                print(
                    f"  {criterion_id:<25}"
                    f"{score}/4"
                )

        print(
            f"  Overall{'':<18}"
            f"{case_score['average']:.2f}/4"
            if case_score["average"]
            is not None
            else
            "  Overall                  N/A"
        )

        if case_score[
            "percentage"
        ] is not None:

            print(
                f"  Quality{'':<18}"
                f"{case_score['percentage']:.2f}%"
            )

        if case_score[
            "na_count"
        ]:

            print(
                f"  N/A criteria{'':<14}"
                f"{case_score['na_count']}"
            )

        summary = judged.get(
            "summary",
            ""
        )

        if summary:

            print(
                f"  Summary: {summary}"
            )

        # ====================================================
        # TOTALS
        # ====================================================

        total_earned += (
            case_score["earned"]
        )

        total_maximum += (
            case_score["maximum"]
        )

        total_na += (
            case_score["na_count"]
        )

        successful_cases += 1

        print()

    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    print("=" * 70)

    print(
        f"Cases evaluated: "
        f"{successful_cases}/{len(cases)}"
    )

    print(
        f"N/A criteria: "
        f"{total_na}"
    )

    if total_maximum:

        overall_percentage = (
            total_earned
            / total_maximum
            * 100
        )

        print(
            f"LLM Judge Score: "
            f"{total_earned}/{total_maximum}"
        )

        print(
            f"LLM Judge Quality: "
            f"{overall_percentage:.2f}%"
        )

    else:

        print(
            "LLM Judge Score: N/A"
        )

        print(
            "LLM Judge Quality: N/A"
        )

    print("=" * 70)


if __name__ == "__main__":
    main()