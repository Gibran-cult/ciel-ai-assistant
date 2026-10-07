import json
from pathlib import Path

import streamlit as st


ROOT = Path(__file__).resolve().parent

RESULT_FILE = (
    ROOT
    / "tests"
    / "results"
    / "quality_latest.json"
)


st.set_page_config(
    page_title="Ciel AI Master Quality",
    page_icon="🤖",
    layout="wide",
)


def load_results():
    if not RESULT_FILE.exists():
        return None

    with RESULT_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


data = load_results()


st.title("Ciel AI Master")
st.caption("Production Quality Dashboard")


if data is None:

    st.error(
        "Quality result belum tersedia."
    )

    st.stop()


project = data.get(
    "project",
    "Ciel AI Master",
)

version = data.get(
    "version",
    "unknown",
)

overall = data.get(
    "overall",
    {},
)

response_quality = data.get(
    "response_quality",
    {},
)

performance = data.get(
    "performance",
    {},
)

resilience = data.get(
    "resilience",
    {},
)

memory = data.get(
    "memory",
    {},
)

automated = data.get(
    "automated_checks",
    {},
)


# ============================================================
# HEADER
# ============================================================

st.subheader(
    f"{project} — {version}"
)

status = overall.get(
    "status",
    "unknown",
)

score = overall.get(
    "score"
)


if status == "healthy":
    st.success(
        f"Overall status: {status.upper()}"
    )

elif status == "degraded":
    st.warning(
        f"Overall status: {status.upper()}"
    )

else:
    st.info(
        f"Overall status: {status.upper()}"
    )


# ============================================================
# KPI
# ============================================================

col1, col2, col3, col4 = st.columns(4)


with col1:
    st.metric(
        "Overall Score",
        (
            f"{score * 100:.0f}%"
            if score is not None
            else "N/A"
        ),
    )


with col2:
    st.metric(
        "Automated Checks",
        (
            f"{automated.get('passed', 0)}"
            f"/"
            f"{automated.get('total', 0)}"
        ),
    )


with col3:
    st.metric(
        "Response Quality",
        (
            f"{response_quality.get('pass_rate') * 100:.1f}%"
            if response_quality.get("pass_rate")
            is not None
            else "N/A"
        ),
    )


with col4:
    st.metric(
        "Resilience",
        (
            f"{resilience.get('pass_rate') * 100:.1f}%"
            if resilience.get("pass_rate")
            is not None
            else "N/A"
        ),
    )


st.divider()


# ============================================================
# SECTIONS
# ============================================================

left, right = st.columns(2)


with left:

    st.subheader(
        "Response Quality"
    )

    st.write(
        f"Passed: "
        f"{response_quality.get('passed', 0)}"
    )

    st.write(
        f"Failed: "
        f"{response_quality.get('failed', 0)}"
    )

    st.write(
        f"Total: "
        f"{response_quality.get('total', 0)}"
    )


    st.subheader(
        "Resilience"
    )

    st.write(
        f"Passed: "
        f"{resilience.get('passed', 0)}"
    )

    st.write(
        f"Failed: "
        f"{resilience.get('failed', 0)}"
    )

    st.write(
        f"Total: "
        f"{resilience.get('total', 0)}"
    )


with right:

    st.subheader(
        "Performance"
    )

    first_request = performance.get(
        "first_request_s"
    )

    warm = performance.get(
        "warm_median_s"
    )

    overall_latency = performance.get(
        "overall_median_s"
    )

    p95 = performance.get(
        "p95_s"
    )

    st.write(
        "First request:",
        "N/A"
        if first_request is None
        else f"{first_request:.2f}s",
    )

    st.write(
        "Warm median:",
        "N/A"
        if warm is None
        else f"{warm:.2f}s",
    )

    st.write(
        "Overall median:",
        "N/A"
        if overall_latency is None
        else f"{overall_latency:.2f}s",
    )

    st.write(
        "P95:",
        "N/A"
        if p95 is None
        else f"{p95:.2f}s",
    )


    st.subheader(
        "Memory"
    )

    k1 = memory.get(
        "recall_k1"
    )

    k3 = memory.get(
        "recall_k3"
    )

    k5 = memory.get(
        "recall_k5"
    )

    reduction = memory.get(
        "context_reduction_k5_percent"
    )

    st.write(
        "Recall K=1:",
        "N/A"
        if k1 is None
        else f"{k1 * 100:.1f}%",
    )

    st.write(
        "Recall K=3:",
        "N/A"
        if k3 is None
        else f"{k3 * 100:.1f}%",
    )

    st.write(
        "Recall K=5:",
        "N/A"
        if k5 is None
        else f"{k5 * 100:.1f}%",
    )

    st.write(
        "Context reduction K=5:",
        "N/A"
        if reduction is None
        else f"{reduction:.1f}%",
    )


st.divider()


# ============================================================
# AUTOMATED CHECK DETAILS
# ============================================================

st.subheader(
    "Automated Checks"
)

details = automated.get(
    "details",
    {},
)

for name, result in details.items():

    if result.get("passed"):
        st.success(
            f"{name}: PASS"
        )
    else:
        st.error(
            f"{name}: FAIL"
        )


# ============================================================
# METADATA
# ============================================================

st.divider()

st.caption(
    f"Result file: {RESULT_FILE}"
)

st.caption(
    f"Generated at: "
    f"{data.get('generated_at', 'unknown')}"
)
