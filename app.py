import html
import logging
import os
import re
import time
import uuid

import requests
import streamlit as st
from dotenv import load_dotenv

# ============================================================
# LOGGING
# ============================================================

logger = logging.getLogger("ciel_ai")

if not logger.handlers:
    handler = logging.StreamHandler()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    handler.setFormatter(formatter)
    logger.addHandler(handler)

logger.setLevel(logging.INFO)
logger.propagate = False

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Ciel AI Assistant",
    page_icon=":material/auto_awesome:",
    layout="wide",
    initial_sidebar_state="auto",
)

# ============================================================
# VISUAL SYSTEM
# ============================================================
# Dark workspace, single teal accent, off-black surfaces.
# Styling is scoped through container keys (st-key-*) and stable
# data-testid hooks so it survives Streamlit upgrades as far as possible.

CIEL_CSS = """
<style>
:root {
    --c-bg: #0c1011;
    --c-surface: #12181a;
    --c-raised: #172023;
    --c-line: rgba(220, 240, 238, 0.09);
    --c-line-strong: rgba(220, 240, 238, 0.16);
    --c-text: #e7eeee;
    --c-muted: #93a3a6;
    --c-faint: #6b7b7f;
    --c-accent: #3cc9b6;
    --c-accent-ink: #062521;
    --c-accent-soft: rgba(60, 201, 182, 0.12);
    --c-ok: #4cc38a;
    --c-warn: #e2ae55;
    --c-err: #ee7f74;
    --font-sans: "Geist", "Satoshi", ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
    --font-mono: "Geist Mono", "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
    --ease: cubic-bezier(0.32, 0.72, 0, 1);
}

/* ---------- Base ---------- */
.stApp {
    background:
        radial-gradient(60rem 28rem at 78% -8%, rgba(60, 201, 182, 0.07), transparent 70%),
        var(--c-bg);
    color: var(--c-text);
    font-family: var(--font-sans);
}
.stApp, .stApp p, .stApp li, .stApp label, .stApp button, .stApp textarea, .stApp input {
    font-family: var(--font-sans);
}
header[data-testid="stHeader"] { background: transparent; }
#MainMenu, footer { visibility: hidden; }

[data-testid="stMain"] .block-container,
.stMain .block-container {
    max-width: 52rem;
    padding: 2.25rem 1.5rem 9rem;
}

/* Long content must never push the layout sideways */
.stApp { overflow-x: hidden; }
.stMarkdown, .stMarkdown p, .stMarkdown li { overflow-wrap: anywhere; }
.stMarkdown pre {
    overflow-x: auto;
    max-width: 100%;
    background: var(--c-surface);
    border: 1px solid var(--c-line);
    border-radius: 12px;
}
.stMarkdown code { font-family: var(--font-mono); font-size: 0.86em; }
.stMarkdown table { display: block; max-width: 100%; overflow-x: auto; }
.stMarkdown img, [data-testid="stImage"] img { max-width: 100%; height: auto; border-radius: 12px; }

/* ---------- Focus ---------- */
.stApp :is(button, a, textarea, input, summary, [role="button"]):focus-visible {
    outline: 2px solid var(--c-accent);
    outline-offset: 2px;
}

/* ---------- Top bar ---------- */
.st-key-topbar {
    padding-bottom: 1.1rem;
    margin-bottom: 1.4rem;
    border-bottom: 1px solid var(--c-line);
}
.ciel-topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    flex-wrap: wrap;
}
.ciel-brand { display: flex; align-items: baseline; gap: 0.7rem; min-width: 0; }
.ciel-wordmark {
    font-size: 1.35rem;
    font-weight: 650;
    letter-spacing: -0.03em;
    color: var(--c-text);
}
.ciel-tagline { font-size: 0.84rem; color: var(--c-muted); }

/* ---------- Status ---------- */
.ciel-status {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.28rem 0.7rem 0.28rem 0.6rem;
    border: 1px solid var(--c-line);
    border-radius: 999px;
    background: var(--c-surface);
    font-size: 0.78rem;
    color: var(--c-muted);
    white-space: nowrap;
}
.ciel-status b { font-weight: 560; color: var(--c-text); }
.ciel-dot {
    width: 7px; height: 7px; border-radius: 50%;
    background: var(--c-faint);
    flex: none;
}
.ciel-status[data-state="ok"] .ciel-dot { background: var(--c-ok); }
.ciel-status[data-state="warn"] .ciel-dot { background: var(--c-warn); }
.ciel-status[data-state="error"] .ciel-dot { background: var(--c-err); }

.ciel-statuslist { display: grid; gap: 0.5rem; margin: 0.25rem 0 0.75rem; }
.ciel-statusrow {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    padding: 0.55rem 0.7rem;
    border: 1px solid var(--c-line);
    border-radius: 10px;
    background: var(--c-surface);
    font-size: 0.82rem;
}
.ciel-statusrow span:first-child { color: var(--c-muted); }
.ciel-statusrow .ciel-val { display: inline-flex; align-items: center; gap: 0.45rem; font-weight: 560; }
.ciel-statusrow[data-state="ok"] .ciel-dot { background: var(--c-ok); }
.ciel-statusrow[data-state="warn"] .ciel-dot { background: var(--c-warn); }
.ciel-statusrow[data-state="error"] .ciel-dot { background: var(--c-err); }
.ciel-detail {
    margin: 0 0 0.6rem;
    font-family: var(--font-mono);
    font-size: 0.74rem;
    color: var(--c-muted);
    line-height: 1.6;
    overflow-wrap: anywhere;
}

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] {
    background: var(--c-surface);
    border-right: 1px solid var(--c-line);
}
[data-testid="stSidebar"] .block-container,
[data-testid="stSidebarContent"] { padding-top: 1.4rem; }
.ciel-sidehead { margin-bottom: 1.1rem; }
.ciel-sidehead .ciel-wordmark { display: block; }
.ciel-sidehead .ciel-tagline { display: block; margin-top: 0.2rem; }
.ciel-eyebrow {
    margin: 1.3rem 0 0.55rem;
    font-size: 0.68rem;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--c-faint);
    font-weight: 560;
}
[data-testid="stSidebar"] [data-testid="stExpander"] {
    border: 1px solid var(--c-line);
    border-radius: 12px;
    background: var(--c-bg);
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary { font-size: 0.86rem; }
.ciel-note { font-size: 0.82rem; line-height: 1.65; color: var(--c-muted); }
.ciel-note p { margin: 0 0 0.6rem; }

/* ---------- Buttons ---------- */
.stApp .stButton > button {
    border-radius: 999px;
    border: 1px solid var(--c-line-strong);
    background: var(--c-raised);
    color: var(--c-text);
    font-weight: 540;
    transition: transform 0.45s var(--ease), background 0.45s var(--ease), border-color 0.45s var(--ease);
}
.stApp .stButton > button:hover {
    border-color: rgba(60, 201, 182, 0.55);
    background: #1b272a;
}
.stApp .stButton > button:active { transform: scale(0.98) translateY(1px); }
.stApp .stButton > button[kind="primary"] {
    background: var(--c-accent);
    border-color: var(--c-accent);
    color: var(--c-accent-ink);
}
.st-key-clearchat .stButton > button {
    background: transparent;
    border-color: var(--c-line);
    color: var(--c-muted);
}
.st-key-clearchat .stButton > button:hover {
    color: var(--c-err);
    border-color: rgba(238, 127, 116, 0.5);
    background: rgba(238, 127, 116, 0.06);
}

/* ---------- Empty state ---------- */
.st-key-emptystate { padding: 1.5rem 0 0.5rem; }
.ciel-hero h1 {
    margin: 0 0 0.6rem;
    padding: 0;
    font-size: clamp(1.7rem, 3.2vw, 2.35rem);
    font-weight: 620;
    letter-spacing: -0.035em;
    line-height: 1.12;
    color: var(--c-text);
}
.ciel-hero p {
    margin: 0;
    max-width: 38rem;
    font-size: 1rem;
    line-height: 1.65;
    color: var(--c-muted);
}
.ciel-caps {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0;
    margin: 2rem 0 1.6rem;
    border-top: 1px solid var(--c-line);
}
.ciel-cap {
    padding: 1.05rem 1.1rem 1.05rem 0;
    border-bottom: 1px solid var(--c-line);
}
.ciel-cap:nth-child(even) { padding-left: 1.1rem; border-left: 1px solid var(--c-line); }
.ciel-cap strong { display: block; font-size: 0.95rem; font-weight: 600; letter-spacing: -0.01em; }
.ciel-cap span { display: block; margin-top: 0.25rem; font-size: 0.86rem; line-height: 1.55; color: var(--c-muted); }
.ciel-cap strong::before {
    content: "";
    display: inline-block;
    width: 6px; height: 6px;
    margin-right: 0.55rem;
    border-radius: 2px;
    background: var(--c-accent);
    vertical-align: 0.12em;
}
.st-key-starters .stButton > button {
    width: 100%;
    justify-content: flex-start;
    text-align: left;
    border-radius: 14px;
    padding: 0.7rem 1rem;
    background: var(--c-surface);
    border-color: var(--c-line);
    color: var(--c-text);
}
.st-key-starters .stButton > button:hover { background: var(--c-raised); }
.st-key-starters .stButton > button p { white-space: normal; text-align: left; }

/* ---------- Messages ---------- */
[data-testid="stChatMessage"] {
    background: transparent;
    padding: 0.9rem 0;
    gap: 0.9rem;
    animation: ciel-rise 0.7s var(--ease) both;
}
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] {
    font-size: 0.98rem;
    line-height: 1.75;
    max-width: 46rem;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    background: var(--c-surface);
    border: 1px solid var(--c-line);
    border-radius: 16px;
    padding: 0.85rem 1.05rem;
    margin: 0.6rem 0;
}
[data-testid="stChatMessageAvatarUser"],
[data-testid="stChatMessageAvatarAssistant"] {
    border-radius: 10px;
    width: 2rem; height: 2rem;
}
[data-testid="stChatMessageAvatarUser"] { background: var(--c-raised); color: var(--c-muted); }
[data-testid="stChatMessageAvatarAssistant"] { background: var(--c-accent-soft); color: var(--c-accent); }

/* ---------- Working indicator ---------- */
.ciel-thinking {
    max-width: 26rem;
    padding: 0.2rem 0 0.4rem;
}
.ciel-thinking-head {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    font-size: 0.92rem;
    font-weight: 540;
}
.ciel-dots { display: inline-flex; gap: 4px; }
.ciel-dots i {
    width: 6px; height: 6px;
    border-radius: 50%;
    background: var(--c-accent);
    animation: ciel-pulse 1.2s var(--ease) infinite;
}
.ciel-dots i:nth-child(2) { animation-delay: 0.15s; }
.ciel-dots i:nth-child(3) { animation-delay: 0.3s; }
.ciel-skel { display: grid; gap: 0.5rem; margin: 0.9rem 0 0.7rem; }
.ciel-skel b {
    position: relative;
    display: block;
    height: 0.62rem;
    border-radius: 6px;
    background: var(--c-raised);
    overflow: hidden;
}
.ciel-skel b:nth-child(1) { width: 100%; }
.ciel-skel b:nth-child(2) { width: 86%; }
.ciel-skel b:nth-child(3) { width: 58%; }
.ciel-skel b::after {
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(90deg, transparent, rgba(60, 201, 182, 0.14), transparent);
    transform: translateX(-100%);
    animation: ciel-shimmer 1.7s var(--ease) infinite;
}
.ciel-thinking-note { margin: 0; font-size: 0.78rem; color: var(--c-faint); }

/* ---------- Error card ---------- */
[class*="st-key-errcard"] {
    padding: 0.95rem 1.05rem;
    border: 1px solid rgba(238, 127, 116, 0.32);
    border-left: 3px solid var(--c-err);
    border-radius: 14px;
    background: rgba(238, 127, 116, 0.05);
    max-width: 46rem;
}
.ciel-errhead { display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.35rem; }
.ciel-errhead strong { font-size: 0.98rem; font-weight: 600; }
.ciel-badge {
    padding: 0.12rem 0.5rem;
    border-radius: 999px;
    background: rgba(238, 127, 116, 0.16);
    color: var(--c-err);
    font-size: 0.68rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    font-weight: 620;
}
[class*="st-key-errcard"] [data-testid="stExpander"] {
    border: 1px solid var(--c-line);
    border-radius: 10px;
    background: var(--c-bg);
    margin: 0.5rem 0 0.7rem;
}
[class*="st-key-errcard"] .stButton > button {
    background: var(--c-accent);
    border-color: var(--c-accent);
    color: var(--c-accent-ink);
}

/* ---------- Composer ---------- */
[data-testid="stBottom"] > div,
[data-testid="stBottomBlockContainer"] {
    background: linear-gradient(to top, var(--c-bg) 62%, transparent);
}
[data-testid="stBottomBlockContainer"] { max-width: 52rem; padding-bottom: 1.4rem; }
[data-testid="stChatInput"] {
    padding: 5px;
    border: 1px solid var(--c-line);
    border-radius: 24px;
    background: rgba(220, 240, 238, 0.04);
    transition: border-color 0.45s var(--ease), box-shadow 0.45s var(--ease);
}
[data-testid="stChatInput"] > div {
    border: 1px solid var(--c-line-strong);
    border-radius: 19px;
    background: var(--c-surface);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}
[data-testid="stChatInput"]:focus-within {
    border-color: rgba(60, 201, 182, 0.5);
    box-shadow: 0 0 0 3px var(--c-accent-soft);
}
[data-testid="stChatInput"] textarea { color: var(--c-text); font-size: 0.98rem; }
[data-testid="stChatInput"] textarea::placeholder { color: var(--c-faint); }
[data-testid="stChatInputSubmitButton"] {
    border-radius: 999px;
    background: var(--c-accent);
    color: var(--c-accent-ink);
    transition: transform 0.45s var(--ease);
}
[data-testid="stChatInputSubmitButton"]:active { transform: scale(0.94); }
[data-testid="stChatInputSubmitButton"]:disabled { background: var(--c-raised); color: var(--c-faint); }

/* ---------- Motion ---------- */
@keyframes ciel-rise {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}
@keyframes ciel-pulse {
    0%, 100% { opacity: 0.25; transform: scale(0.8); }
    50% { opacity: 1; transform: scale(1); }
}
@keyframes ciel-shimmer {
    to { transform: translateX(100%); }
}
@media (prefers-reduced-motion: reduce) {
    .stApp *, .stApp *::before, .stApp *::after {
        animation: none !important;
        transition: none !important;
    }
    .ciel-dots i { opacity: 0.7; }
}

/* ---------- Tablet / phone ---------- */
@media (max-width: 900px) {
    [data-testid="stMain"] .block-container,
    .stMain .block-container { padding: 1.5rem 1.1rem 8.5rem; }
}
@media (max-width: 640px) {
    [data-testid="stMain"] .block-container,
    .stMain .block-container { padding: 1rem 0.9rem 8rem; }
    .ciel-caps { grid-template-columns: 1fr; }
    .ciel-cap, .ciel-cap:nth-child(even) { padding: 0.95rem 0; border-left: 0; }
    .ciel-tagline { display: none; }
    [data-testid="stChatMessage"] { gap: 0.65rem; }
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) { padding: 0.75rem 0.85rem; }
    [data-testid="stBottomBlockContainer"] { padding-left: 0.7rem; padding-right: 0.7rem; padding-bottom: 1rem; }
    .st-key-starters .stButton > button { min-height: 2.9rem; }
}
</style>
"""

st.markdown(CIEL_CSS, unsafe_allow_html=True)



# ============================================================
# LOAD ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# CONFIG HELPER
# ============================================================

def get_config(name):
    """
    Ambil konfigurasi dari Streamlit Secrets.
    Jika tidak tersedia, fallback ke environment variable.
    """
    try:
        value = st.secrets.get(name)

        if value:
            return str(value).strip()

    except Exception:
        pass

    value = os.getenv(name)

    if value:
        return str(value).strip()

    return None


# ============================================================
# CONFIGURATION
# ============================================================

NGROK_URL = get_config("NGROK_URL")
NGROK_USER = get_config("NGROK_USER")
NGROK_PASSWORD = get_config("NGROK_PASSWORD")
LANGFLOW_API_KEY = get_config("LANGFLOW_API_KEY")
FLOW_ID = get_config("FLOW_ID")

# Bersihkan URL
if NGROK_URL:
    NGROK_URL = NGROK_URL.rstrip("/")


# ============================================================
# VALIDATE CONFIG
# ============================================================

missing_config = []

if not NGROK_URL:
    missing_config.append("NGROK_URL")

if not NGROK_USER:
    missing_config.append("NGROK_USER")

if not NGROK_PASSWORD:
    missing_config.append("NGROK_PASSWORD")

if not LANGFLOW_API_KEY:
    missing_config.append("LANGFLOW_API_KEY")

if not FLOW_ID:
    missing_config.append("FLOW_ID")


if missing_config:

    st.error(
        "Konfigurasi belum lengkap.\n\n"
        f"Variabel yang belum tersedia: "
        f"{', '.join(missing_config)}"
    )

    st.stop()


# ============================================================
# SESSION STATE
# ============================================================

if "messages" not in st.session_state:
    st.session_state.messages = []

if "pending" not in st.session_state:
    st.session_state.pending = None

if "health" not in st.session_state:
    st.session_state.health = None


# ============================================================
# BACKEND HEALTH CHECK
# ============================================================

def check_backend_health():

    check_id = uuid.uuid4().hex[:8]
    start_time = time.perf_counter()

    url = f"{NGROK_URL}/health_check"

    logger.info(
        "health_check_start id=%s",
        check_id,
    )

    try:

        response = requests.get(
            url,
            auth=(
                NGROK_USER,
                NGROK_PASSWORD
            ),
            timeout=10,
        )

        elapsed = time.perf_counter() - start_time

        logger.info(
            "health_check_response id=%s status=%s elapsed=%.2fs",
            check_id,
            response.status_code,
            elapsed,
        )

        response.raise_for_status()

        data = response.json()

        logger.info(
            "health_check_success id=%s status=%s chat=%s db=%s",
            check_id,
            data.get("status"),
            data.get("chat"),
            data.get("db"),
        )

        return {
            "ok": True,
            "status": data.get("status"),
            "chat": data.get("chat"),
            "db": data.get("db"),
        }

    except requests.exceptions.Timeout:

        logger.error(
            "health_check_timeout id=%s",
            check_id,
        )

        return {
            "ok": False,
            "error": "Timeout saat menghubungi backend."
        }

    except requests.exceptions.ConnectionError:

        logger.error(
            "health_check_connection_error id=%s",
            check_id,
        )

        return {
            "ok": False,
            "error": "Backend tidak dapat dihubungi."
        }

    except requests.exceptions.HTTPError as error:

        logger.error(
            "health_check_http_error id=%s error=%s",
            check_id,
            error,
        )

        return {
            "ok": False,
            "error": f"HTTP Error: {error}"
        }

    except ValueError:

        logger.error(
            "health_check_json_error id=%s",
            check_id,
        )

        return {
            "ok": False,
            "error": "Response backend bukan JSON."
        }

    except Exception as error:

        logger.exception(
            "health_check_unexpected_error id=%s",
            check_id,
        )

        return {
            "ok": False,
            "error": str(error)
        }


# ============================================================
# LANGFLOW API
# ============================================================

def ask_langflow(message):

    request_id = uuid.uuid4().hex[:8]
    start_time = time.perf_counter()

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
        "input_value": message,
        "input_type": "chat",
        "output_type": "chat",
    }

    logger.info(
        "request_start id=%s flow=%s input_length=%d",
        request_id,
        FLOW_ID,
        len(message),
    )

    try:

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
            timeout=120,
        )

        elapsed = time.perf_counter() - start_time

        logger.info(
            "request_response id=%s status=%s elapsed=%.2fs",
            request_id,
            response.status_code,
            elapsed,
        )

        response.raise_for_status()

        data = response.json()

        try:

            answer = (
                data["outputs"][0]
                ["outputs"][0]
                ["results"]["message"]
                ["data"]["text"]
            )

            logger.info(
                "request_success id=%s elapsed=%.2fs output_length=%d",
                request_id,
                elapsed,
                len(answer),
            )

            return answer

        except (KeyError, IndexError, TypeError):

            logger.error(
                "response_parse_error id=%s elapsed=%.2fs",
                request_id,
                elapsed,
            )

            return (
                "⚠️ Response Langflow diterima, "
                "tetapi format output tidak dikenali.\n\n"
                f"```json\n{data}\n```"
            )

    except requests.exceptions.Timeout:

        elapsed = time.perf_counter() - start_time

        logger.error(
            "request_timeout id=%s elapsed=%.2fs",
            request_id,
            elapsed,
        )

        return (
            "⏱️ Request timeout.\n\n"
            "Langflow membutuhkan terlalu lama "
            "untuk memberikan jawaban."
        )

    except requests.exceptions.ConnectionError:

        elapsed = time.perf_counter() - start_time

        logger.error(
            "connection_error id=%s elapsed=%.2fs",
            request_id,
            elapsed,
        )

        return (
            "🔌 Tidak dapat terhubung ke ngrok.\n\n"
            "Pastikan Langflow Desktop dan ngrok "
            "sedang berjalan."
        )

    except requests.exceptions.HTTPError as error:

        elapsed = time.perf_counter() - start_time
        status = response.status_code

        logger.error(
            "http_error id=%s status=%s elapsed=%.2fs",
            request_id,
            status,
            elapsed,
        )

        if status in (401, 403):
            return (
                "🔐 Authentication gagal.\n\n"
                "Periksa konfigurasi API key atau akses backend."
            )

        if status == 429:
            return (
                "⏳ Request terlalu banyak.\n\n"
                "Backend sedang membatasi request. "
                "Silakan coba lagi setelah beberapa saat."
            )

        if status == 500:
            return (
                "⚠️ Backend mengalami internal error.\n\n"
                "Silakan coba lagi setelah backend pulih."
            )

        if status in (502, 503, 504):
            return (
                "🔧 Backend sedang tidak tersedia.\n\n"
                "Langflow/ngrok belum siap atau sedang mengalami "
                "gangguan sementara. Silakan coba lagi nanti."
            )

        return (
            "🚫 Request ke Langflow gagal.\n\n"
            f"HTTP Status: {status}\n"
            f"Request ID: `{request_id}`"
        )

    except requests.exceptions.RequestException as error:

        elapsed = time.perf_counter() - start_time

        logger.error(
            "request_error id=%s elapsed=%.2fs error=%s",
            request_id,
            elapsed,
            error,
        )

        return (
            "❌ Request gagal.\n\n"
            f"{error}"
        )

    except ValueError:

        elapsed = time.perf_counter() - start_time

        logger.error(
            "json_error id=%s elapsed=%.2fs",
            request_id,
            elapsed,
        )

        return (
            "⚠️ Response dari Langflow "
            "bukan JSON yang valid."
        )


# ============================================================
# UI HELPERS
# ============================================================

AVATARS = {
    "user": ":material/person:",
    "assistant": ":material/auto_awesome:",
}

# ask_langflow() reports failures as friendly text that starts with one of
# these markers. The UI recognises them so failures render as an error
# card with a retry action instead of looking like a normal answer.
ERROR_MARKERS = ("⏱", "🔌", "🔐", "⏳", "🔧", "🚫", "❌", "⚠")

STARTER_PROMPTS = (
    "Rangkum perkembangan terbaru model bahasa open-source",
    "Hitung cicilan KPR Rp800 juta, tenor 15 tahun, bunga 7,5% per tahun",
    "Bandingkan dua pendekatan RAG dan kapan masing-masing cocok dipakai",
)

CAPABILITIES = (
    ("Web research", "Mencari dan merangkum sumber terkini dari web."),
    ("Knowledge search", "Menemukan jawaban dari basis pengetahuan yang tersedia."),
    ("Math &amp; analysis", "Menghitung dan menganalisis dengan langkah yang jelas."),
    ("Long-term memory", "Mengingat konteks penting lintas percakapan."),
)

THINKING_HTML = (
    '<div class="ciel-thinking" role="status" aria-live="polite">'
    '<div class="ciel-thinking-head">'
    '<span class="ciel-dots" aria-hidden="true"><i></i><i></i><i></i></span>'
    "<span>Supervisor sedang berpikir</span>"
    "</div>"
    '<div class="ciel-skel" aria-hidden="true"><b></b><b></b><b></b></div>'
    '<p class="ciel-thinking-note">Permintaan riset dapat memakan waktu hingga dua menit.</p>'
    "</div>"
)


def is_error_answer(text):
    return str(text).lstrip().startswith(ERROR_MARKERS)


def split_error(text):
    """Pisahkan pesan error menjadi judul, penjelasan, dan detail teknis."""

    paragraphs = [p.strip() for p in str(text).split("\n\n") if p.strip()]

    if not paragraphs:
        return "Terjadi kesalahan", [], []

    title = re.sub(r"^[^\w`]+", "", paragraphs[0].splitlines()[0]).strip()
    title = title.rstrip(".") or "Terjadi kesalahan"

    extra = paragraphs[0].splitlines()[1:]
    rest = (["\n".join(extra)] if extra else []) + paragraphs[1:]

    technical_markers = ("HTTP Status", "Request ID", "```")
    plain = [p for p in rest if not any(m in p for m in technical_markers)]
    technical = [p for p in rest if any(m in p for m in technical_markers)]

    return title, plain, technical


def health_view(health):
    """Terjemahkan hasil check_backend_health() menjadi status tampilan."""

    if health is None:
        return "idle", "Not checked", []

    if not health["ok"]:
        return "error", "Unreachable", [health.get("error", "")]

    details = [
        f"status: {health.get('status')}",
        f"chat: {health.get('chat')}",
        f"db: {health.get('db')}",
    ]

    if (
        health.get("status") == "ok"
        and health.get("chat") == "ok"
        and health.get("db") == "ok"
    ):
        return "ok", "Healthy", details

    return "warn", "Degraded", details


def queue_prompt(text):
    st.session_state.pending = text


def clear_chat():
    st.session_state.messages = []
    st.session_state.pending = None


def retry_last():
    messages = st.session_state.messages

    if (
        len(messages) >= 2
        and messages[-1]["role"] == "assistant"
        and messages[-1].get("error")
        and messages[-2]["role"] == "user"
    ):
        st.session_state.pending = messages[-2]["content"]
        del messages[-2:]


def render_error(content, index, show_retry):

    title, plain, technical = split_error(content)

    with st.container(key=f"errcard_{index}"):

        st.markdown(
            '<div class="ciel-errhead" role="alert">'
            '<span class="ciel-badge">Error</span>'
            f"<strong>{html.escape(title)}</strong>"
            "</div>",
            unsafe_allow_html=True,
        )

        if plain:
            st.markdown("\n\n".join(plain))

        if technical:
            with st.expander("Technical details"):
                st.markdown("\n\n".join(technical))

        if show_retry:
            st.button(
                "Retry",
                key=f"retry_{index}",
                icon=":material/refresh:",
                on_click=retry_last,
            )


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(
        '<div class="ciel-sidehead">'
        '<span class="ciel-wordmark">Ciel</span>'
        '<span class="ciel-tagline">Research workspace</span>'
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="ciel-eyebrow">System</div>',
        unsafe_allow_html=True,
    )

    status_slot = st.empty()

    # --------------------------------------------------------
    # HEALTH CHECK
    # --------------------------------------------------------

    if st.button(
        "Check backend",
        use_container_width=True,
        icon=":material/monitor_heart:",
    ):

        with st.spinner("Memeriksa backend..."):
            st.session_state.health = check_backend_health()

    health_state, health_label, health_details = health_view(
        st.session_state.health
    )

    details_html = ""

    if health_details:
        details_html = (
            '<p class="ciel-detail">'
            + "<br>".join(html.escape(str(d)) for d in health_details)
            + "</p>"
        )

    status_slot.markdown(
        '<div class="ciel-statuslist">'
        '<div class="ciel-statusrow" data-state="ok">'
        "<span>Configuration</span>"
        '<span class="ciel-val"><span class="ciel-dot" aria-hidden="true"></span>Complete</span>'
        "</div>"
        f'<div class="ciel-statusrow" data-state="{health_state}">'
        "<span>Backend</span>"
        f'<span class="ciel-val"><span class="ciel-dot" aria-hidden="true"></span>{health_label}</span>'
        "</div>"
        "</div>"
        + details_html,
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------
    # MEMORY (INFORMATIF)
    # --------------------------------------------------------

    st.markdown(
        '<div class="ciel-eyebrow">Memory</div>',
        unsafe_allow_html=True,
    )

    with st.expander("About long-term memory"):

        st.markdown(
            '<div class="ciel-note">'
            "<p>Backend Ciel memiliki long-term memory untuk mengingat "
            "konteks penting lintas percakapan.</p>"
            "<p>Ini berbeda dari riwayat chat di layar, yang hanya tersimpan "
            "selama sesi browser ini dan hilang saat chat dibersihkan.</p>"
            "<p>Memory belum dapat dilihat atau diubah dari sini.</p>"
            "</div>",
            unsafe_allow_html=True,
        )

    # --------------------------------------------------------
    # CONNECTION
    # --------------------------------------------------------

    st.markdown(
        '<div class="ciel-eyebrow">Connection</div>',
        unsafe_allow_html=True,
    )

    with st.expander("Connection details"):

        st.caption("Flow ID")

        st.code(FLOW_ID)

        st.caption(
            "AI Backend: Langflow\n\n"
            "Architecture: Multi-Agent System"
        )

    # --------------------------------------------------------
    # CLEAR CHAT (AKSI SEKUNDER)
    # --------------------------------------------------------

    st.markdown(
        '<div class="ciel-eyebrow">Conversation</div>',
        unsafe_allow_html=True,
    )

    with st.container(key="clearchat"):

        st.button(
            "Clear chat",
            use_container_width=True,
            icon=":material/delete:",
            disabled=not st.session_state.messages,
            on_click=clear_chat,
        )


# ============================================================
# HEADER
# ============================================================

with st.container(key="topbar"):

    st.markdown(
        '<div class="ciel-topbar">'
        '<div class="ciel-brand">'
        '<span class="ciel-wordmark">Ciel</span>'
        '<span class="ciel-tagline">Multi-agent AI powered by Langflow</span>'
        "</div>"
        f'<div class="ciel-status" data-state="{health_state}">'
        '<span class="ciel-dot" aria-hidden="true"></span>'
        f"<span>Backend <b>{health_label}</b></span>"
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# CHAT INPUT
# ============================================================
# Dipanggil sebelum riwayat dirender agar empty state langsung hilang
# saat pesan pertama dikirim. Posisi visual composer tetap di bawah.

typed_prompt = st.chat_input(
    "Tanyakan sesuatu kepada Ciel..."
)

if typed_prompt:
    st.session_state.pending = typed_prompt

pending_prompt = st.session_state.pending
st.session_state.pending = None


# ============================================================
# EMPTY STATE
# ============================================================

if not st.session_state.messages and not pending_prompt:

    with st.container(key="emptystate"):

        capabilities_html = "".join(
            f"<div class=\"ciel-cap\"><strong>{name}</strong><span>{desc}</span></div>"
            for name, desc in CAPABILITIES
        )

        st.markdown(
            '<div class="ciel-hero">'
            "<h1>Apa yang ingin kita kerjakan?</h1>"
            "<p>Ciel merutekan pertanyaan Anda ke riset web, pencarian "
            "pengetahuan, matematika dan analisis, serta long-term memory.</p>"
            "</div>"
            f'<div class="ciel-caps">{capabilities_html}</div>',
            unsafe_allow_html=True,
        )

        st.caption("Coba salah satu:")

        with st.container(key="starters"):

            for number, starter in enumerate(STARTER_PROMPTS):

                st.button(
                    starter,
                    key=f"starter_{number}",
                    on_click=queue_prompt,
                    args=(starter,),
                )


# ============================================================
# CHAT HISTORY
# ============================================================

last_index = len(st.session_state.messages) - 1

for index, message in enumerate(st.session_state.messages):

    with st.chat_message(
        message["role"],
        avatar=AVATARS.get(message["role"]),
    ):

        if message.get("error"):

            render_error(
                message["content"],
                index,
                show_retry=(index == last_index),
            )

        else:

            st.markdown(
                message["content"]
            )


# ============================================================
# PROCESS NEW MESSAGE
# ============================================================

if pending_prompt:

    # --------------------------------------------------------
    # USER MESSAGE
    # --------------------------------------------------------

    st.session_state.messages.append(
        {
            "role": "user",
            "content": pending_prompt,
        }
    )

    with st.chat_message("user", avatar=AVATARS["user"]):

        st.markdown(pending_prompt)

    # --------------------------------------------------------
    # ASSISTANT MESSAGE
    # --------------------------------------------------------

    with st.chat_message("assistant", avatar=AVATARS["assistant"]):

        working_slot = st.empty()

        working_slot.markdown(
            THINKING_HTML,
            unsafe_allow_html=True,
        )

        answer = ask_langflow(pending_prompt)

        working_slot.empty()

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer,
            "error": is_error_answer(answer),
        }
    )

    # Render ulang agar jawaban dan tombol retry tampil dari riwayat
    # dengan struktur yang sama seperti pesan lama.
    st.rerun()
