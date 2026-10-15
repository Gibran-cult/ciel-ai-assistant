import base64
import hashlib
import html
import io
import json
import logging
import os
import re
import threading
import time
import uuid

import requests
import streamlit as st
from dotenv import load_dotenv
from PIL import Image

from pricing import render_pricing

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
    page_icon=":material/cloud:",
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
@import url('https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500&display=swap');

:root {
    --c-bg: #0f1112;
    --c-surface: #151819;
    --c-raised: #1c2021;
    --c-line: rgba(233, 236, 236, 0.09);
    --c-line-strong: rgba(233, 236, 236, 0.18);
    --c-control: #727c7e;
    --c-text: #e9ecec;
    --c-muted: #a3abad;
    --c-faint: #8a9395;
    --c-accent: #5bbfae;
    --c-accent-ink: #06201c;
    --c-ok: #5cb98a;
    --c-warn: #d9a74a;
    --c-err: #ee8479;
    --font-sans: "Geist", ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
    --font-mono: "Geist Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
    --ease: cubic-bezier(0.32, 0.72, 0, 1);
    --r-sm: 6px;
    --r-md: 8px;
    --r-lg: 12px;
}

/* ---------- Base ---------- */
.stApp {
    background: var(--c-bg);
    color: var(--c-text);
    font-family: var(--font-sans);
    font-feature-settings: "ss01", "cv11";
}
.stApp, .stApp p, .stApp li, .stApp label, .stApp button, .stApp textarea, .stApp input {
    font-family: var(--font-sans);
}
header[data-testid="stHeader"] { background: transparent; }
#MainMenu, footer { visibility: hidden; }

[data-testid="stMain"] .block-container,
.stMain .block-container {
    max-width: 50rem;
    padding: 2.25rem 1.5rem 9rem;
}

.stApp { overflow-x: hidden; }
.stMarkdown, .stMarkdown p, .stMarkdown li { overflow-wrap: anywhere; }
.stMarkdown p { text-wrap: pretty; }
.stMarkdown pre {
    overflow-x: auto;
    max-width: 100%;
    background: var(--c-surface);
    border: 1px solid var(--c-line);
    border-radius: var(--r-md);
}
.stMarkdown code { font-family: var(--font-mono); font-size: 0.86em; }
.stMarkdown table { display: block; max-width: 100%; overflow-x: auto; }
.stMarkdown img, [data-testid="stImage"] img { max-width: 100%; height: auto; border-radius: var(--r-md); }
[data-testid="stImageCaption"] { font-family: var(--font-mono); font-size: 0.72rem; color: var(--c-faint); }

/* ---------- Focus ---------- */
.stApp :is(button, a, textarea, input, summary, [role="button"]):focus-visible {
    outline: 2px solid var(--c-accent);
    outline-offset: 2px;
}

/* ---------- Top bar ---------- */
.st-key-topbar {
    padding-bottom: 1rem;
    margin-bottom: 1.6rem;
    border-bottom: 1px solid var(--c-line);
}
.ciel-topbar {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 1rem;
    flex-wrap: wrap;
}
.ciel-brand { display: flex; align-items: baseline; gap: 0.8rem; min-width: 0; }
.ciel-wordmark {
    font-size: 1.3rem;
    font-weight: 600;
    letter-spacing: -0.03em;
    color: var(--c-text);
}
.ciel-tagline { font-size: 0.82rem; color: var(--c-muted); }

.ciel-status {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.2rem 0.6rem;
    border: 1px solid var(--c-line-strong);
    border-radius: var(--r-sm);
    font-family: var(--font-mono);
    font-size: 0.74rem;
    color: var(--c-muted);
    white-space: nowrap;
}
.ciel-status b { font-weight: 500; color: var(--c-text); }
.ciel-dot { width: 6px; height: 6px; border-radius: 1px; background: var(--c-accent); flex: none; }

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] {
    background: var(--c-surface);
    border-right: 1px solid var(--c-line);
}
[data-testid="stSidebarContent"] { padding-top: 1.4rem; }
.ciel-sidehead { margin-bottom: 1.1rem; }
.ciel-sidehead .ciel-wordmark { display: block; }
.ciel-sidehead .ciel-tagline { display: block; margin-top: 0.15rem; }
.ciel-eyebrow {
    margin: 1.4rem 0 0.4rem;
    font-size: 0.78rem;
    color: var(--c-faint);
    font-weight: 500;
    letter-spacing: 0.01em;
}
[data-testid="stSidebar"] [data-testid="stExpander"] {
    border: 1px solid var(--c-line);
    border-radius: var(--r-md);
    background: var(--c-bg);
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary { font-size: 0.86rem; }
.ciel-note { font-size: 0.82rem; line-height: 1.65; color: var(--c-muted); }
.ciel-note p { margin: 0 0 0.6rem; }

/* ---------- Buttons ---------- */
.stApp .stButton > button,
[data-testid="stSidebar"] [data-testid="stPopover"] > button {
    border-radius: var(--r-md);
    border: 1px solid var(--c-line-strong);
    background: transparent;
    color: var(--c-text);
    font-weight: 500;
    transition: transform 0.4s var(--ease), background-color 0.4s var(--ease), border-color 0.4s var(--ease);
}
.stApp .stButton > button:hover,
[data-testid="stSidebar"] [data-testid="stPopover"] > button:hover {
    background: var(--c-raised);
    border-color: var(--c-faint);
}
.stApp .stButton > button:active { transform: translateY(1px); }
.stApp .stButton > button[kind="primary"] {
    background: var(--c-accent);
    border-color: var(--c-accent);
    color: var(--c-accent-ink);
    font-weight: 600;
}
.stApp .stButton > button[kind="primary"]:hover { background: #73cdbd; border-color: #73cdbd; }
.st-key-nav { margin-top: 0.35rem; }
.st-key-clearchat .stButton > button {
    border-color: transparent;
    color: var(--c-muted);
}
.st-key-clearchat .stButton > button:hover {
    color: var(--c-err);
    border-color: rgba(238, 132, 121, 0.45);
    background: transparent;
}

/* ---------- Empty state ---------- */
.st-key-emptystate { padding: 1.2rem 0 0.5rem; }
.ciel-hero h1 {
    margin: 0 0 0.9rem;
    padding: 0;
    font-size: clamp(1.9rem, 3.8vw, 2.7rem);
    font-weight: 560;
    letter-spacing: -0.045em;
    line-height: 1.05;
    text-wrap: balance;
    color: var(--c-text);
}
.ciel-hero p {
    margin: 0;
    max-width: 34rem;
    font-size: 1rem;
    line-height: 1.65;
    color: var(--c-muted);
    text-wrap: pretty;
}
.ciel-caps { margin: 2.2rem 0 1.8rem; border-top: 1px solid var(--c-line); }
.ciel-cap {
    display: grid;
    grid-template-columns: 11rem 1fr;
    gap: 1rem;
    padding: 0.95rem 0;
    border-bottom: 1px solid var(--c-line);
}
.ciel-cap strong { font-size: 0.92rem; font-weight: 560; letter-spacing: -0.01em; }
.ciel-cap span { font-size: 0.88rem; line-height: 1.55; color: var(--c-muted); }
.st-key-starters .stButton > button {
    width: 100%;
    justify-content: flex-start;
    text-align: left;
    border: 0;
    border-bottom: 1px solid var(--c-line);
    border-radius: 0;
    padding: 0.8rem 0;
    background: transparent;
    color: var(--c-text);
    font-weight: 400;
}
.st-key-starters .stButton > button::before {
    content: "\\2192";
    font-family: var(--font-mono);
    color: var(--c-accent);
    margin-right: 0.85rem;
    transition: transform 0.4s var(--ease);
}
.st-key-starters .stButton > button:hover { background: transparent; }
.st-key-starters .stButton > button:hover::before { transform: translateX(3px); }
.st-key-starters .stButton > button p { white-space: normal; text-align: left; }

/* ---------- Messages ---------- */
[data-testid="stChatMessage"] {
    background: transparent;
    padding: 0.9rem 0;
    gap: 0.9rem;
    animation: ciel-rise 0.6s var(--ease) both;
}
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] {
    font-size: 0.98rem;
    line-height: 1.75;
    max-width: 44rem;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    background: var(--c-surface);
    border: 1px solid var(--c-line);
    border-radius: var(--r-lg);
    padding: 0.85rem 1.05rem;
    margin: 0.6rem 0;
}
[data-testid="stChatMessageAvatarUser"],
[data-testid="stChatMessageAvatarAssistant"] {
    border-radius: var(--r-sm);
    width: 1.9rem; height: 1.9rem;
    font-family: var(--font-mono);
    font-weight: 500;
}
[data-testid="stChatMessageAvatarUser"] { background: var(--c-raised); color: var(--c-muted); }
[data-testid="stChatMessageAvatarAssistant"] { background: var(--c-accent); color: var(--c-accent-ink); }

/* ---------- Working indicator ---------- */
.ciel-thinking { max-width: 26rem; padding: 0.2rem 0 0.4rem; }
.ciel-thinking-head { font-size: 0.92rem; font-weight: 500; }
.ciel-thinking-head::after {
    content: "";
    display: inline-block;
    width: 0.5ch;
    height: 1em;
    margin-left: 0.4ch;
    vertical-align: -0.15em;
    background: var(--c-accent);
    animation: ciel-caret 1.1s steps(1) infinite;
}
.ciel-skel { display: grid; gap: 0.5rem; margin: 0.9rem 0 0.7rem; }
.ciel-skel b {
    position: relative;
    display: block;
    height: 0.6rem;
    border-radius: 3px;
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
    background: linear-gradient(90deg, transparent, rgba(233, 236, 236, 0.07), transparent);
    transform: translateX(-100%);
    animation: ciel-shimmer 1.7s var(--ease) infinite;
}
.ciel-thinking-note { margin: 0; font-size: 0.8rem; color: var(--c-faint); }

/* ---------- Error card ---------- */
[class*="st-key-errcard"] {
    padding: 0.95rem 1.05rem;
    border: 1px solid rgba(238, 132, 121, 0.3);
    border-left: 3px solid var(--c-err);
    border-radius: var(--r-md);
    background: rgba(238, 132, 121, 0.05);
    max-width: 44rem;
}
.ciel-errhead { display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.35rem; }
.ciel-errhead strong { font-size: 0.98rem; font-weight: 560; }
.ciel-badge {
    padding: 0.1rem 0.45rem;
    border-radius: 3px;
    background: rgba(238, 132, 121, 0.16);
    color: var(--c-err);
    font-family: var(--font-mono);
    font-size: 0.7rem;
    font-weight: 500;
}
[class*="st-key-errcard"] [data-testid="stExpander"] {
    border: 1px solid var(--c-line);
    border-radius: var(--r-md);
    background: var(--c-bg);
    margin: 0.5rem 0 0.7rem;
}

/* ---------- Composer ---------- */
[data-testid="stBottom"] > div,
[data-testid="stBottomBlockContainer"] {
    background: linear-gradient(to top, var(--c-bg) 70%, transparent);
}
[data-testid="stBottomBlockContainer"] { max-width: 50rem; padding-bottom: 1.4rem; }
[data-testid="stChatInput"] {
    border: 1px solid var(--c-control);
    border-radius: var(--r-lg);
    background: var(--c-surface);
    transition: border-color 0.4s var(--ease);
}
[data-testid="stChatInput"] > div { background: transparent; border: 0; }
[data-testid="stChatInput"]:focus-within { border-color: var(--c-accent); }
[data-testid="stChatInput"] textarea { color: var(--c-text); font-size: 0.98rem; }
[data-testid="stChatInput"] textarea::placeholder { color: var(--c-faint); }
[data-testid="stChatInputSubmitButton"] {
    border-radius: var(--r-md);
    background: var(--c-accent);
    color: var(--c-accent-ink);
    transition: transform 0.4s var(--ease);
}
[data-testid="stChatInputSubmitButton"]:active { transform: translateY(1px); }
[data-testid="stChatInputSubmitButton"]:disabled { background: var(--c-raised); color: var(--c-faint); }

/* ---------- Projects, history, files ---------- */
[data-testid="stSidebar"] .stButton > button,
[data-testid="stSidebar"] [data-testid="stPopover"] > button { width: 100%; }
.st-key-nav .stButton > button,
.st-key-projects .stButton > button,
.st-key-history .stButton > button {
    justify-content: flex-start;
    text-align: left;
    border-color: transparent;
    color: var(--c-muted);
    min-height: 2.2rem;
}
.st-key-nav .stButton > button:hover,
.st-key-projects .stButton > button:hover,
.st-key-history .stButton > button:hover {
    background: var(--c-raised);
    color: var(--c-text);
    border-color: transparent;
}
[class*="st-key-navactive_"] .stButton > button,
.stButton[class*="st-key-navactive_"] > button,
[class*="st-key-projactive_"] .stButton > button,
[class*="st-key-chatactive_"] .stButton > button,
.stButton[class*="st-key-projactive_"] > button,
.stButton[class*="st-key-chatactive_"] > button {
    background: var(--c-raised);
    border-color: var(--c-line-strong);
    color: var(--c-text);
    box-shadow: inset 2px 0 0 var(--c-accent);
}
.st-key-history .stButton > button p,
.st-key-projects .stButton > button p {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
[data-testid="stSidebar"] [data-testid="stFileUploader"] section {
    background: var(--c-bg);
    border: 1px dashed var(--c-control);
    border-radius: var(--r-md);
}
.ciel-projfile {
    display: flex;
    justify-content: space-between;
    gap: 0.6rem;
    margin: 0.5rem 0 0.15rem;
    font-size: 0.8rem;
    color: var(--c-text);
    overflow-wrap: anywhere;
}
.ciel-projfile em { font-style: normal; color: var(--c-faint); font-family: var(--font-mono); font-size: 0.72rem; white-space: nowrap; }
.ciel-files { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.55rem; }
.ciel-filechip {
    padding: 0.18rem 0.55rem;
    border: 1px solid var(--c-line-strong);
    border-radius: var(--r-sm);
    font-family: var(--font-mono);
    font-size: 0.74rem;
    color: var(--c-muted);
    overflow-wrap: anywhere;
}

/* ---------- Motion ---------- */
@keyframes ciel-rise {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
}
@keyframes ciel-caret {
    0%, 100% { opacity: 1; }
    50% { opacity: 0; }
}
@keyframes ciel-shimmer {
    to { transform: translateX(100%); }
}
@media (prefers-reduced-motion: reduce) {
    .stApp *, .stApp *::before, .stApp *::after {
        animation: none !important;
        transition: none !important;
    }
}

/* ---------- Tablet / phone ---------- */
@media (max-width: 900px) {
    [data-testid="stMain"] .block-container,
    .stMain .block-container { padding: 1.5rem 1.1rem 8.5rem; }
}
@media (max-width: 640px) {
    [data-testid="stMain"] .block-container,
    .stMain .block-container { padding: 1rem 0.9rem 8rem; }
    .ciel-cap { grid-template-columns: 1fr; gap: 0.2rem; }
    .ciel-tagline { display: none; }
    [data-testid="stChatMessage"] { gap: 0.65rem; }
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) { padding: 0.75rem 0.85rem; }
    [data-testid="stBottomBlockContainer"] { padding-left: 0.7rem; padding-right: 0.7rem; padding-bottom: 1rem; }
    .stApp .stButton > button,
    [data-testid="stSidebar"] [data-testid="stPopover"] > button { min-height: 2.75rem; }
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


def get_int_config(name, default):
    value = get_config(name)

    try:
        return max(1, int(value)) if value else default
    except ValueError:
        logger.warning("config_invalid_int name=%s", name)
        return default


def auth_configured():
    """Login Google aktif hanya jika blok [auth] ada di secrets."""
    try:
        return "auth" in st.secrets
    except Exception:
        return False


# ============================================================
# CONFIGURATION
# ============================================================

NGROK_URL = get_config("NGROK_URL")
NGROK_USER = get_config("NGROK_USER")
NGROK_PASSWORD = get_config("NGROK_PASSWORD")
LANGFLOW_API_KEY = get_config("LANGFLOW_API_KEY")
FLOW_ID = get_config("FLOW_ID")

# ID komponen Chat Input di flow Langflow; dipakai untuk mengirim gambar.
CHAT_INPUT_ID = get_config("CHAT_INPUT_ID") or "ChatInput-X8W7I"

# ID komponen memory di flow (v1.3.0); app mengirim pemilik memory lewat tweaks.
MEMORY_SEARCH_ID = get_config("MEMORY_SEARCH_ID") or "CielMemorySearch-BC6pl"
MEMORY_STORE_ID = get_config("MEMORY_STORE_ID") or "CielMemoryStore-uBmzx"

# ID komponen Ciel Table Analyst di flow (v1.5.0); app mengirim file CSV/TSV
# pengguna lewat tweaks agar angkanya dihitung langsung dari file.
TABLE_ANALYST_ID = get_config("TABLE_ANALYST_ID") or "CielTableAnalyst-t4bL3"

# Batas pesan per jam untuk menjaga biaya model dan beban backend.
# Batas total anonim mencegah orang melewati batas dengan memuat ulang tab.
RATE_LIMIT_PER_HOUR = get_int_config("RATE_LIMIT_PER_HOUR", 20)
RATE_LIMIT_PER_HOUR_LOGIN = get_int_config("RATE_LIMIT_PER_HOUR_LOGIN", 60)
RATE_LIMIT_ANON_TOTAL_PER_HOUR = get_int_config("RATE_LIMIT_ANON_TOTAL_PER_HOUR", 150)

AUTH_ENABLED = auth_configured()

# Opsional: tujuan tombol paket berbayar di halaman harga (https:// atau mailto:).
CONTACT_URL = get_config("CONTACT_URL")

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

# Riwayat chat dan proyek hanya hidup selama sesi browser ini.
if "chats" not in st.session_state:
    st.session_state.chats = {}

if "projects" not in st.session_state:
    st.session_state.projects = {}

if "active_chat" not in st.session_state:
    st.session_state.active_chat = None

if "active_project" not in st.session_state:
    st.session_state.active_project = None

if "pending" not in st.session_state:
    st.session_state.pending = None

if "upload_nonce" not in st.session_state:
    st.session_state.upload_nonce = 0

# Identitas anonim per sesi browser, dipakai untuk session_id dan rate limit.
if "visitor_id" not in st.session_state:
    st.session_state.visitor_id = uuid.uuid4().hex[:16]


# ============================================================
# USER IDENTITY
# ============================================================

def logged_in():
    return AUTH_ENABLED and bool(st.user.get("is_logged_in"))


def memory_owner_id():
    """
    ID pemilik long-term memory: hash stabil dari akun login.
    Kosong untuk pengguna anonim, sehingga komponen memory di flow
    menolak membaca/menyimpan dan memory tidak bocor antar pengunjung.
    """
    if not logged_in():
        return ""

    subject = st.user.get("sub") or st.user.get("email")

    if not subject:
        return ""

    return hashlib.sha256(f"ciel-memory:{subject}".encode()).hexdigest()[:16]


def user_key():
    return memory_owner_id() or st.session_state.visitor_id


# ============================================================
# RATE LIMIT
# ============================================================

def rate_limit_ok(store, limits, now, window=3600):
    """
    Catat satu request jika semua key di `limits` ({key: batas}) masih di
    bawah batasnya dalam `window` detik terakhir. Tidak mencatat apa pun
    jika salah satu batas sudah tercapai.
    """
    recent = {
        key: [t for t in store.get(key, ()) if now - t < window]
        for key in limits
    }

    allowed = all(len(recent[key]) < limit for key, limit in limits.items())

    for key, times in recent.items():

        if allowed:
            times.append(now)

        if times:
            store[key] = times
        else:
            store.pop(key, None)

    return allowed


@st.cache_resource
def rate_limit_state():
    # Dibagi semua sesi di proses server ini; reset saat app restart.
    return {"lock": threading.Lock(), "hits": {}}


def check_rate_limit():
    """Kembalikan None jika boleh lanjut, atau pesan error ber-marker ⏳."""

    if logged_in():
        limit = RATE_LIMIT_PER_HOUR_LOGIN
        limits = {f"user:{user_key()}": limit}
    else:
        limit = RATE_LIMIT_PER_HOUR
        limits = {
            f"visitor:{user_key()}": limit,
            "anon:total": RATE_LIMIT_ANON_TOTAL_PER_HOUR,
        }

    state = rate_limit_state()

    with state["lock"]:
        allowed = rate_limit_ok(state["hits"], limits, time.time())

    if allowed:
        return None

    logger.warning("rate_limited logged_in=%s", logged_in())

    hint = (
        " Masuk dengan akun Google untuk batas yang lebih tinggi."
        if AUTH_ENABLED and not logged_in()
        else ""
    )

    return (
        "⏳ Batas pemakaian tercapai.\n\n"
        f"Ciel menerima hingga {limit} pesan per jam per pengguna, dan "
        "pemakaian anonim juga dibatasi bersama. Silakan coba lagi nanti."
        f"{hint}"
    )


# ============================================================
# LANGFLOW API
# ============================================================

def final_answer_text(message):
    """
    Langflow 1.12 menyusun Message.text dari semua blok teks di semua
    putaran Agent (teks sebelum memanggil tool, jawaban yang ditulis ulang),
    sehingga jawaban bisa muncul dua kali atau tersambung tanpa spasi.
    Jawaban akhir adalah blok teks terakhir yang ditulis model; blok berjudul
    "Output" adalah gabungan buatan Langflow. Tanpa content_blocks, pakai
    data.text seperti sebelumnya (KeyError jika struktur tidak dikenal).
    """
    if not isinstance(message, dict):
        raise TypeError("results.message bukan objek")

    texts = [
        content.get("text")
        for block in message.get("content_blocks") or []
        for content in block.get("contents") or []
        if content.get("type") == "text"
        and not (content.get("header") or {}).get("title")
        and str(content.get("text") or "").strip()
    ]

    if texts:
        return texts[-1]

    return message["data"]["text"]


def ask_langflow(message, tweaks=None, session_id=None):

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

    if tweaks:
        payload["tweaks"] = tweaks

    # Tanpa session_id Langflow memakai satu session default, sehingga
    # riwayat Agent tercampur antar pengunjung dan antar chat.
    if session_id:
        payload["session_id"] = session_id

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
            # Pesan bergambar + beberapa tool bisa > 2 menit di backend CPU.
            timeout=240,
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

            answer = final_answer_text(
                data["outputs"][0]
                ["outputs"][0]
                ["results"]["message"]
            )

            logger.info(
                "request_success id=%s elapsed=%.2fs output_length=%d",
                request_id,
                elapsed,
                len(answer),
            )

            return answer

        except (KeyError, IndexError, TypeError):

            # Isi response hanya masuk log server; pengguna publik tidak
            # boleh melihat JSON mentah Langflow (struktur flow, isi tool).
            logger.error(
                "response_parse_error id=%s elapsed=%.2fs detail=%s",
                request_id,
                elapsed,
                str(data)[:500],
            )

            return (
                "⚠️ Response Langflow diterima, "
                "tetapi format output tidak dikenali.\n\n"
                "Silakan coba lagi. Jika terus terjadi, sampaikan kode "
                "di bagian detail teknis kepada admin.\n\n"
                f"Request ID: `{request_id}`"
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

        # Detail error Langflow hanya masuk log server, tidak ditampilkan
        # ke pengguna. Tanpa ini penyebab HTTP 500 tidak bisa dilacak.
        logger.error(
            "http_error id=%s status=%s elapsed=%.2fs detail=%s",
            request_id,
            status,
            elapsed,
            (getattr(response, "text", "") or "")[:500],
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

        # Pesan exception bisa memuat URL/host backend (ngrok); cukup di log.
        logger.error(
            "request_error id=%s elapsed=%.2fs type=%s error=%s",
            request_id,
            elapsed,
            type(error).__name__,
            error,
        )

        return (
            "❌ Request gagal.\n\n"
            "Terjadi gangguan saat menghubungi Ciel. Silakan coba lagi.\n\n"
            f"Request ID: `{request_id}`"
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
# IMAGE UPLOAD (LANGFLOW FILES API)
# ============================================================

def upload_images(images):
    """
    Unggah gambar ke Langflow agar bisa dipakai komponen Chat Input.

    Mengembalikan (daftar_path, None) jika berhasil, atau
    ([], pesan_error) dengan format pesan yang sama seperti
    ask_langflow() agar UI menampilkannya sebagai error.
    """

    request_id = uuid.uuid4().hex[:8]
    start_time = time.perf_counter()

    url = (
        f"{NGROK_URL}"
        f"/api/v1/files/upload/{FLOW_ID}"
    )

    headers = {
        "Accept": "application/json",
        "x-api-key": LANGFLOW_API_KEY,
    }

    logger.info(
        "image_upload_start id=%s count=%d",
        request_id,
        len(images),
    )

    paths = []

    try:

        for image in images:

            response = requests.post(
                url,
                headers=headers,
                auth=(
                    NGROK_USER,
                    NGROK_PASSWORD
                ),
                files={
                    "file": (
                        image["name"],
                        image["data"],
                        image["mime"],
                    )
                },
                timeout=60,
            )

            response.raise_for_status()

            data = response.json()

            path = data.get("file_path") or data.get("path")

            if not path:
                raise ValueError("file_path tidak ada di response")

            paths.append(path)

        logger.info(
            "image_upload_success id=%s count=%d elapsed=%.2fs",
            request_id,
            len(paths),
            time.perf_counter() - start_time,
        )

        return paths, None

    except requests.exceptions.Timeout:

        logger.error("image_upload_timeout id=%s", request_id)

        return [], (
            "⏱️ Upload gambar timeout.\n\n"
            "Gambar terlalu besar atau koneksi lambat. "
            "Coba gambar yang lebih kecil."
        )

    except requests.exceptions.ConnectionError:

        logger.error("image_upload_connection_error id=%s", request_id)

        return [], (
            "🔌 Tidak dapat terhubung ke ngrok saat mengunggah gambar.\n\n"
            "Pastikan Langflow Desktop dan ngrok sedang berjalan."
        )

    except requests.exceptions.HTTPError:

        status = response.status_code

        logger.error(
            "image_upload_http_error id=%s status=%s",
            request_id,
            status,
        )

        if status in (401, 403):
            return [], (
                "🔐 Authentication gagal saat mengunggah gambar.\n\n"
                "Periksa konfigurasi API key atau akses backend."
            )

        if status in (404, 405):
            return [], (
                "🚫 Endpoint upload gambar tidak ditemukan.\n\n"
                "Versi Langflow mungkin berbeda atau flow ID salah.\n\n"
                f"HTTP Status: {status}\n"
                f"Request ID: `{request_id}`"
            )

        return [], (
            "🚫 Upload gambar ke Langflow gagal.\n\n"
            f"HTTP Status: {status}\n"
            f"Request ID: `{request_id}`"
        )

    except (ValueError, requests.exceptions.JSONDecodeError):

        logger.error("image_upload_parse_error id=%s", request_id)

        return [], (
            "⚠️ Upload gambar berhasil dikirim, tetapi response "
            "Langflow tidak dikenali.\n\n"
            f"Request ID: `{request_id}`"
        )

    except requests.exceptions.RequestException as error:

        # Pesan exception bisa memuat URL/host backend (ngrok); cukup di log.
        logger.error(
            "image_upload_error id=%s type=%s error=%s",
            request_id,
            type(error).__name__,
            error,
        )

        return [], (
            "❌ Upload gambar gagal.\n\n"
            "Terjadi gangguan saat mengunggah gambar. Silakan coba lagi.\n\n"
            f"Request ID: `{request_id}`"
        )


# ============================================================
# UI HELPERS
# ============================================================

AVATARS = {
    "user": ":material/person:",
    "assistant": ":material/cloud:",
}

# ask_langflow() reports failures as friendly text that starts with one of
# these markers. The UI recognises them so failures render as an error
# card with a retry action instead of looking like a normal answer.
ERROR_MARKERS = ("⏱", "🔌", "🔐", "⏳", "🔧", "🚫", "❌", "⚠")

STARTER_PROMPTS = (
    "Ajari aku limit fungsi dari dasar, lalu kasih 2 soal latihan",
    "Analisis: apakah model bahasa open-source sudah layak dipakai untuk riset skripsi?",
    "Rangkum perkembangan terbaru model bahasa open-source beserta sumbernya",
)

CAPABILITIES = (
    ("Riset anti-ngarang", "Jawaban riset disertai sumber. Kalau buktinya tidak ada, Ciel bilang belum tahu."),
    ("Teman belajar", "Menjelaskan bertahap, memberi latihan, dan mengingat progresmu (perlu login)."),
    ("Mode analisis", "Awali dengan &ldquo;analisis&rdquo; untuk jawaban terstruktur lengkap dengan tingkat keyakinan."),
    ("Hitung &amp; data", "Angka dari CSV/TSV-mu dihitung langsung dari file, bukan ditebak."),
)

THINKING_HTML = (
    '<div class="ciel-thinking" role="status" aria-live="polite">'
    '<div class="ciel-thinking-head">'
    '<span class="ciel-dots" aria-hidden="true"><i></i><i></i><i></i></span>'
    "<span>Ciel sedang mencari dan memeriksa</span>"
    "</div>"
    '<div class="ciel-skel" aria-hidden="true"><b></b><b></b><b></b></div>'
    '<p class="ciel-thinking-note">Permintaan riset dapat memakan waktu hingga dua menit.</p>'
    "</div>"
)

# File yang dilampirkan dibaca sebagai teks lalu disisipkan ke prompt.
# Backend Langflow hanya menerima teks, jadi hanya format teks yang didukung.
ALLOWED_FILE_TYPES = [
    "txt", "md", "markdown", "csv", "tsv", "json", "jsonl",
    "yaml", "yml", "xml", "html", "css", "js", "ts", "py",
    "sql", "log", "ini", "toml",
]
ALLOWED_IMAGE_TYPES = ["png", "jpg", "jpeg", "bmp"]
IMAGE_MIME = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "bmp": "image/bmp",
}
MAX_IMAGES_PER_MESSAGE = 4
MAX_IMAGE_BYTES = 5 * 1024 * 1024
THUMBNAIL_PX = 360
MAX_FILES_PER_MESSAGE = 5
MAX_FILE_CHARS = 40_000
# Satu salinan konteks file per permintaan; Agent juga memuat salinan
# terakhir dari riwayat, jadi totalnya bisa dua kali lipat angka ini.
MAX_CONTEXT_CHARS = 80_000
# Kirim ulang isi file proyek setiap N giliran, sebelum salinan lama keluar
# dari riwayat Agent (n_messages=10, yaitu 5 giliran tanya-jawab).
PROJECT_CONTEXT_REFRESH_TURNS = 4

# CSV/TSV dihitung utuh oleh Ciel Table Analyst; prompt hanya berisi cuplikan.
TABLE_FILE_TYPES = ("csv", "tsv")
MAX_TABLE_CHARS = 1_000_000
TABLE_PREVIEW_ROWS = 20
MAX_CHAT_TABLES = 5
HISTORY_LIMIT = 12
DEFAULT_FILE_QUESTION = "Tolong baca dan rangkum file yang saya lampirkan."
DEFAULT_IMAGE_QUESTION = "Tolong jelaskan gambar yang saya lampirkan."


def short(text, limit):
    text = " ".join(str(text).split())

    if len(text) <= limit:
        return text

    return text[: limit - 1].rstrip() + "…"


def format_size(size):
    if size < 1024:
        return f"{size} B"

    return f"{size / 1024:.1f} KB"


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


# ------------------------------------------------------------
# FILES
# ------------------------------------------------------------

def read_text_file(uploaded):
    """Baca file unggahan sebagai teks. Kembalikan (data, error)."""

    raw = uploaded.getvalue()

    if b"\x00" in raw[:4096]:
        return None, f"{uploaded.name}: bukan file teks."

    text = raw.decode("utf-8", errors="replace")

    if file_extension(uploaded.name) in TABLE_FILE_TYPES:
        return read_table_text(uploaded.name, text, len(raw)), None

    truncated = len(text) > MAX_FILE_CHARS

    if truncated:
        text = text[:MAX_FILE_CHARS]

    return {
        "name": uploaded.name,
        "text": text,
        "size": len(raw),
        "truncated": truncated,
    }, None


def read_table_text(name, text, size):
    """
    CSV/TSV: simpan isi utuh untuk Ciel Table Analyst, dan hanya cuplikan
    beberapa baris untuk prompt. Model tidak perlu (dan tidak boleh)
    menghitung dari cuplikan, sehingga token tetap kecil.
    """
    lines = text.splitlines()
    rows = max(len(lines) - 1, 0)

    return {
        "name": name,
        "text": "\n".join(lines[: TABLE_PREVIEW_ROWS + 1]),
        "size": size,
        "truncated": False,
        "rows": rows,
        "table": {
            "text": text[:MAX_TABLE_CHARS],
            "truncated": len(text) > MAX_TABLE_CHARS,
        },
    }


def project_signature(project_files):
    """Berubah jika file proyek ditambah, dihapus, atau isinya berbeda."""

    digest = hashlib.sha256()

    for item in project_files:
        digest.update(item["name"].encode("utf-8"))
        digest.update(b"\0")
        digest.update(item["text"].encode("utf-8"))
        digest.update(b"\0")

    return digest.hexdigest()[:16]


def project_context_due(chat, project_files, user_turn):
    """
    Kirim isi file proyek hanya jika chat baru, file berubah, atau salinan
    terakhir hampir keluar dari riwayat Agent. Langflow menyimpan setiap
    pesan beserta isi file, dan Agent memuat 10 pesan terakhir (5 giliran),
    jadi mengirim ulang di setiap pesan membuat file yang sama terbaca
    berkali-kali dalam satu permintaan.
    """
    if not project_files:
        return False

    sent = (chat or {}).get("project_context")

    if not sent or sent["signature"] != project_signature(project_files):
        return True

    return user_turn - sent["turn"] >= PROJECT_CONTEXT_REFRESH_TURNS


def build_payload(text, files, project_files, project_note=()):
    """
    Gabungkan isi file dan pertanyaan menjadi satu teks untuk Langflow.
    `project_note` berisi nama file proyek yang isinya sudah dikirim
    sebelumnya di chat ini (masih ada di riwayat Agent).
    """

    blocks = []
    budget = MAX_CONTEXT_CHARS

    def add(label, item):
        nonlocal budget

        if budget <= 0:
            return

        body = item["text"][:budget]
        budget -= len(body)

        cut = item.get("truncated") or len(body) < len(item["text"])
        note = " (dipotong)" if cut else ""

        if "table" in item:
            shown = min(item["rows"], TABLE_PREVIEW_ROWS)
            note = (
                f" (cuplikan {shown} dari {item['rows']} baris; "
                "hitung angka dengan Ciel Table Analyst)"
            )

        blocks.append(f"### {label}: {item['name']}{note}\n{body}")

    for item in project_files:
        add("File proyek", item)

    if project_note:
        blocks.append(
            "### File proyek (isinya sudah dikirim di pesan sebelumnya "
            "dalam percakapan ini): " + ", ".join(project_note)
        )

    for item in files:
        add("File terlampir", item)

    if not blocks:
        return text

    return (
        "Gunakan isi file berikut sebagai konteks.\n\n"
        + "\n\n".join(blocks)
        + "\n\n### Pertanyaan\n"
        + text
    )


# ------------------------------------------------------------
# STATE: CHATS & PROJECTS
# ------------------------------------------------------------

def active_chat():
    return st.session_state.chats.get(st.session_state.active_chat)


def current_messages():
    chat = active_chat()
    return chat["messages"] if chat else []


def context_project_id():
    chat = active_chat()

    if chat:
        return chat["project_id"]

    return st.session_state.active_project


def project_files_for(project_id):
    project = st.session_state.projects.get(project_id)
    return project["files"] if project else []


def file_extension(name):
    return str(name).rsplit(".", 1)[-1].lower() if "." in str(name) else ""


def read_image(uploaded):
    """Baca gambar unggahan. Kembalikan (data, error)."""

    raw = uploaded.getvalue()

    if len(raw) > MAX_IMAGE_BYTES:
        return None, (
            f"{uploaded.name}: ukuran melebihi "
            f"{MAX_IMAGE_BYTES // (1024 * 1024)} MB."
        )

    return {
        "name": uploaded.name,
        "data": raw,
        "mime": IMAGE_MIME.get(file_extension(uploaded.name), "image/png"),
    }, None


def make_thumbnail(image):
    """
    Perkecil gambar yang sudah terkirim agar riwayat chat tidak menyimpan
    file asli (hingga 5 MB per foto) di memori server selama sesi berjalan.
    """
    try:
        with Image.open(io.BytesIO(image["data"])) as img:
            img.thumbnail((THUMBNAIL_PX, THUMBNAIL_PX))
            out = io.BytesIO()
            img.convert("RGB").save(out, format="JPEG", quality=82)
    except Exception:
        return image

    return {**image, "data": out.getvalue(), "mime": "image/jpeg"}


def chat_tables(chat):
    """File CSV/TSV yang bisa dihitung di chat ini: file proyek + lampiran chat."""

    tables = {
        item["name"]: item["table"]
        for item in project_files_for(chat["project_id"])
        if "table" in item
    }
    tables.update(chat.get("tables", {}))

    return tables


def encode_tables(tables):
    """
    Base64 dari JSON tabel. Langflow mengubah setiap backslash-n di input
    teks menjadi baris baru, yang merusak JSON biasa; base64 tidak memuat
    backslash sehingga isi file sampai utuh ke Ciel Table Analyst.
    """
    if not tables:
        return ""

    raw = json.dumps(tables, ensure_ascii=False).encode("utf-8")

    return base64.b64encode(raw).decode("ascii")


def build_tweaks(image_paths=None, tables=None):
    owner = memory_owner_id()

    tweaks = {
        MEMORY_SEARCH_ID: {"memory_owner": owner},
        MEMORY_STORE_ID: {"memory_owner": owner},
        TABLE_ANALYST_ID: {
            "attached_tables": encode_tables(tables),
        },
    }

    if image_paths:
        tweaks[CHAT_INPUT_ID] = {
            "files": (
                image_paths[0]
                if len(image_paths) == 1
                else image_paths
            )
        }

    return tweaks


def make_pending(text, uploaded_files):
    """Bangun permintaan yang menunggu diproses dari teks dan lampiran."""

    uploaded_files = list(uploaded_files)

    image_uploads = [
        u for u in uploaded_files
        if file_extension(u.name) in ALLOWED_IMAGE_TYPES
    ]
    text_uploads = [u for u in uploaded_files if u not in image_uploads]

    files = []

    for uploaded in text_uploads[:MAX_FILES_PER_MESSAGE]:

        data, error = read_text_file(uploaded)

        if error:
            st.toast(error, icon=":material/error:")
            continue

        files.append(data)

    if len(text_uploads) > MAX_FILES_PER_MESSAGE:
        st.toast(
            f"Maksimal {MAX_FILES_PER_MESSAGE} file per pesan.",
            icon=":material/info:",
        )

    images = []

    for uploaded in image_uploads[:MAX_IMAGES_PER_MESSAGE]:

        data, error = read_image(uploaded)

        if error:
            st.toast(error, icon=":material/error:")
            continue

        images.append(data)

    if len(image_uploads) > MAX_IMAGES_PER_MESSAGE:
        st.toast(
            f"Maksimal {MAX_IMAGES_PER_MESSAGE} foto per pesan.",
            icon=":material/info:",
        )

    text = (text or "").strip()

    if not text:
        text = DEFAULT_IMAGE_QUESTION if images else DEFAULT_FILE_QUESTION

    chat = active_chat()
    project_files = project_files_for(context_project_id())
    user_turn = sum(1 for m in (chat or {}).get("messages", []) if m["role"] == "user")
    send_project = project_context_due(chat, project_files, user_turn)

    return {
        "text": text,
        "files": [f["name"] for f in files],
        "images": images,
        "tables": {f["name"]: f["table"] for f in files if "table" in f},
        "project_context": (
            {"signature": project_signature(project_files), "turn": user_turn}
            if send_project
            else None
        ),
        "payload": build_payload(
            text,
            files,
            project_files if send_project else [],
            project_note=() if send_project else [f["name"] for f in project_files],
        ),
    }


def unpack_chat_input(value):
    if isinstance(value, str):
        return value, []

    return value["text"], list(value["files"] or [])


def current_view():
    # Disimpan di URL (?page=pricing) agar halaman harga bisa dibagikan.
    return "pricing" if st.query_params.get("page") == "pricing" else "chat"


def show_chat():
    st.query_params.pop("page", None)


def show_pricing():
    st.query_params["page"] = "pricing"


def new_chat():
    show_chat()
    st.session_state.active_chat = None
    st.session_state.pending = None


def select_chat(chat_id):
    show_chat()
    st.session_state.active_chat = chat_id
    st.session_state.pending = None


def select_project(project_id):
    show_chat()
    st.session_state.active_project = project_id
    st.session_state.active_chat = None
    st.session_state.pending = None


def create_project():
    name = (st.session_state.get("newproj_name") or "").strip()

    if not name:
        return

    project_id = uuid.uuid4().hex[:8]

    st.session_state.projects[project_id] = {
        "id": project_id,
        "name": name,
        "files": [],
    }

    st.session_state.newproj_name = ""
    select_project(project_id)


def delete_project(project_id):
    st.session_state.projects.pop(project_id, None)

    for chat in st.session_state.chats.values():
        if chat["project_id"] == project_id:
            chat["project_id"] = None

    select_project(None)


def add_project_files(project_id, upload_key):
    uploaded_files = st.session_state.get(upload_key) or []
    project = st.session_state.projects.get(project_id)

    if project is None:
        return

    known = {item["name"] for item in project["files"]}

    for uploaded in uploaded_files:

        if uploaded.name in known:
            continue

        data, error = read_text_file(uploaded)

        if error:
            st.toast(error, icon=":material/error:")
            continue

        project["files"].append(data)
        known.add(uploaded.name)

    # Ganti key uploader agar daftar yang sudah diproses dikosongkan.
    st.session_state.upload_nonce += 1


def remove_project_file(project_id, name):
    project = st.session_state.projects.get(project_id)

    if project:
        project["files"] = [
            item for item in project["files"] if item["name"] != name
        ]


def clear_chat():
    chat_id = st.session_state.active_chat

    if chat_id:
        st.session_state.chats.pop(chat_id, None)

    new_chat()


def queue_prompt(text):
    st.session_state.pending = make_pending(text, [])


def retry_last():
    messages = current_messages()

    if (
        len(messages) >= 2
        and messages[-1]["role"] == "assistant"
        and messages[-1].get("error")
        and messages[-2]["role"] == "user"
    ):
        user = messages[-2]

        st.session_state.pending = {
            "text": user["content"],
            "files": user.get("files", []),
            "images": user.get("images", []),
            "payload": user.get("payload", user["content"]),
        }

        del messages[-2:]


# ------------------------------------------------------------
# RENDER
# ------------------------------------------------------------

def render_files(names):
    if not names:
        return

    chips = "".join(
        f'<span class="ciel-filechip">{html.escape(name)}</span>'
        for name in names
    )

    st.markdown(
        f'<div class="ciel-files" aria-label="Lampiran">{chips}</div>',
        unsafe_allow_html=True,
    )


def render_user(message):
    st.markdown(message["content"])
    render_files(message.get("files"))

    images = message.get("images") or []

    if images:
        st.image(
            [image["data"] for image in images],
            caption=[image["name"] for image in images],
            width=180,
        )


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
        '<span class="ciel-tagline">Riset &amp; teman belajar</span>'
        "</div>",
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------
    # NEW CHAT
    # --------------------------------------------------------

    st.button(
        "New chat",
        key="newchat",
        type="primary",
        icon=":material/add:",
        on_click=new_chat,
    )

    with st.container(key="nav"):

        st.button(
            "Harga & paket",
            key=(
                "navactive_pricing"
                if current_view() == "pricing"
                else "nav_pricing"
            ),
            icon=":material/sell:",
            on_click=show_pricing,
        )

    # --------------------------------------------------------
    # PROJECTS
    # --------------------------------------------------------

    st.markdown(
        '<div class="ciel-eyebrow">Projects</div>',
        unsafe_allow_html=True,
    )

    active_project_id = st.session_state.active_project

    with st.container(key="projects"):

        st.button(
            "All chats",
            key=(
                "projactive_all"
                if active_project_id is None
                else "proj_all"
            ),
            icon=":material/forum:",
            on_click=select_project,
            args=(None,),
        )

        for project_id, project in st.session_state.projects.items():

            is_active = project_id == active_project_id

            st.button(
                short(project["name"], 30),
                key=(
                    f"projactive_{project_id}"
                    if is_active
                    else f"proj_{project_id}"
                ),
                icon=":material/folder:",
                on_click=select_project,
                args=(project_id,),
            )

    with st.popover("New project", icon=":material/create_new_folder:"):

        st.text_input(
            "Project name",
            key="newproj_name",
            max_chars=40,
            placeholder="Contoh: Riset kompetitor",
        )

        st.button(
            "Create project",
            key="createproj",
            type="primary",
            on_click=create_project,
        )

    if active_project_id in st.session_state.projects:

        project = st.session_state.projects[active_project_id]
        upload_key = f"pfup_{active_project_id}_{st.session_state.upload_nonce}"

        with st.expander(
            f"Project files ({len(project['files'])})",
            expanded=not project["files"],
        ):

            st.file_uploader(
                "Add files to this project",
                type=ALLOWED_FILE_TYPES,
                accept_multiple_files=True,
                key=upload_key,
                on_change=add_project_files,
                args=(active_project_id, upload_key),
                help=(
                    "File teks akan dipakai sebagai konteks di semua "
                    "chat dalam proyek ini."
                ),
            )

            if not project["files"]:
                st.caption("Belum ada file di proyek ini.")

            for item in project["files"]:

                st.markdown(
                    '<div class="ciel-projfile">'
                    f"<span>{html.escape(short(item['name'], 28))}</span>"
                    f"<em>{format_size(item['size'])}</em>"
                    "</div>",
                    unsafe_allow_html=True,
                )

                st.button(
                    f"Remove {short(item['name'], 20)}",
                    key=f"rmfile_{active_project_id}_{item['name']}",
                    icon=":material/close:",
                    on_click=remove_project_file,
                    args=(active_project_id, item["name"]),
                )

            st.button(
                "Delete project",
                key=f"delproj_{active_project_id}",
                icon=":material/delete:",
                on_click=delete_project,
                args=(active_project_id,),
            )

    # --------------------------------------------------------
    # HISTORY
    # --------------------------------------------------------

    st.markdown(
        '<div class="ciel-eyebrow">History</div>',
        unsafe_allow_html=True,
    )

    history = sorted(
        (
            chat
            for chat in st.session_state.chats.values()
            if active_project_id is None
            or chat["project_id"] == active_project_id
        ),
        key=lambda chat: chat["updated"],
        reverse=True,
    )[:HISTORY_LIMIT]

    if not history:
        st.caption("Belum ada percakapan.")

    with st.container(key="history"):

        for chat in history:

            is_active = chat["id"] == st.session_state.active_chat

            st.button(
                short(chat["title"], 34),
                key=(
                    f"chatactive_{chat['id']}"
                    if is_active
                    else f"chat_{chat['id']}"
                ),
                on_click=select_chat,
                args=(chat["id"],),
            )

    # --------------------------------------------------------
    # MEMORY (INFORMATIF)
    # --------------------------------------------------------

    st.markdown(
        '<div class="ciel-eyebrow">Memory</div>',
        unsafe_allow_html=True,
    )

    if AUTH_ENABLED:

        if logged_in():

            st.caption(
                f"Masuk sebagai {st.user.get('name') or st.user.get('email') or 'pengguna'}"
            )

            st.button(
                "Keluar",
                key="logout",
                icon=":material/logout:",
                on_click=st.logout,
            )

        else:

            st.button(
                "Masuk dengan Google",
                key="login",
                icon=":material/login:",
                on_click=st.login,
            )

    if logged_in():
        memory_status = (
            "<p>Long-term memory aktif dan hanya milik akunmu. Ciel bisa "
            "mengingat konteks penting lintas percakapan.</p>"
            f"<p>ID memory: <code>{memory_owner_id()}</code></p>"
        )
    elif AUTH_ENABLED:
        memory_status = (
            "<p>Kamu belum masuk, jadi Ciel tidak menyimpan atau membaca "
            "long-term memory untukmu. Masuk untuk mengaktifkannya.</p>"
        )
    else:
        memory_status = (
            "<p>Long-term memory nonaktif di deployment ini karena login "
            "belum dikonfigurasi.</p>"
        )

    with st.expander("About long-term memory"):

        st.markdown(
            '<div class="ciel-note">'
            f"{memory_status}"
            "<p>Ini berbeda dari riwayat chat di sidebar, yang hanya "
            "tersimpan selama sesi browser ini.</p>"
            "<p>Memory belum dapat dilihat atau diubah dari sini.</p>"
            "</div>",
            unsafe_allow_html=True,
        )

    # --------------------------------------------------------
    # CLEAR CHAT (AKSI SEKUNDER)
    # --------------------------------------------------------

    with st.container(key="clearchat"):

        st.button(
            "Clear chat",
            key="clearchat_btn",
            icon=":material/delete:",
            disabled=active_chat() is None,
            on_click=clear_chat,
        )


# ============================================================
# HEADER
# ============================================================

topbar_project = st.session_state.projects.get(
    st.session_state.active_project
)

with st.container(key="topbar"):

    project_chip = ""

    if topbar_project:
        project_chip = (
            '<div class="ciel-status" data-state="ok">'
            '<span class="ciel-dot" aria-hidden="true"></span>'
            f"<span>Project <b>{html.escape(short(topbar_project['name'], 28))}</b></span>"
            "</div>"
        )

    st.markdown(
        '<div class="ciel-topbar">'
        '<div class="ciel-brand">'
        '<span class="ciel-wordmark">Ciel</span>'
        '<span class="ciel-tagline">Riset tanpa ngarang, teman belajar yang ingat progresmu</span>'
        "</div>"
        f"{project_chip}"
        "</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# PRICING PAGE
# ============================================================
# Dirender sebelum chat input supaya composer tidak muncul di halaman harga.

if current_view() == "pricing":
    render_pricing(
        contact_url=CONTACT_URL,
        on_start_chat=show_chat,
        rate_limits=(RATE_LIMIT_PER_HOUR, RATE_LIMIT_PER_HOUR_LOGIN),
        memory_enabled=AUTH_ENABLED,
    )
    st.stop()


# ============================================================
# CHAT INPUT
# ============================================================
# Dipanggil sebelum riwayat dirender agar empty state langsung hilang
# saat pesan pertama dikirim. Posisi visual composer tetap di bawah.

chat_value = st.chat_input(
    "Tanyakan sesuatu kepada Ciel...",
    accept_file="multiple",
    file_type=ALLOWED_FILE_TYPES + ALLOWED_IMAGE_TYPES,
)

if chat_value:

    typed_text, typed_files = unpack_chat_input(chat_value)

    if typed_text.strip() or typed_files:
        st.session_state.pending = make_pending(typed_text, typed_files)

pending_request = st.session_state.pending
st.session_state.pending = None


# ============================================================
# EMPTY STATE
# ============================================================

messages = current_messages()

if not messages and not pending_request:

    with st.container(key="emptystate"):

        capabilities_html = "".join(
            f"<div class=\"ciel-cap\"><strong>{name}</strong><span>{desc}</span></div>"
            for name, desc in CAPABILITIES
        )

        st.markdown(
            '<div class="ciel-hero">'
            "<h1>Riset yang jujur, belajar yang ditemani.</h1>"
            "<p>Ciel menjawab dari sumber dan data yang bisa dicek, bilang "
            "terus terang kalau belum tahu, dan menemanimu belajar langkah "
            "demi langkah. Lampirkan file teks atau foto dari tombol di "
            "kotak pesan.</p>"
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

last_index = len(messages) - 1

for index, message in enumerate(messages):

    with st.chat_message(
        message["role"],
        avatar=AVATARS.get(message["role"]),
    ):

        if message["role"] == "user":

            render_user(message)

        elif message.get("error"):

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

if pending_request:

    # --------------------------------------------------------
    # CHAT (BUAT BARU JIKA BELUM ADA)
    # --------------------------------------------------------

    chat = active_chat()

    if chat is None:

        chat_id = uuid.uuid4().hex[:8]

        chat = {
            "id": chat_id,
            "title": short(pending_request["text"], 48),
            "messages": [],
            "project_id": st.session_state.active_project,
            "updated": time.time(),
        }

        st.session_state.chats[chat_id] = chat
        st.session_state.active_chat = chat_id

    # --------------------------------------------------------
    # USER MESSAGE
    # --------------------------------------------------------

    user_message = {
        "role": "user",
        "content": pending_request["text"],
        "files": pending_request["files"],
        "images": pending_request["images"],
        "payload": pending_request["payload"],
    }

    chat["messages"].append(user_message)
    chat["updated"] = time.time()

    with st.chat_message("user", avatar=AVATARS["user"]):

        render_user(user_message)

    # --------------------------------------------------------
    # ASSISTANT MESSAGE
    # --------------------------------------------------------

    with st.chat_message("assistant", avatar=AVATARS["assistant"]):

        working_slot = st.empty()

        working_slot.markdown(
            THINKING_HTML,
            unsafe_allow_html=True,
        )

        # Satu session Langflow per chat: "New chat" benar-benar mulai
        # dari konteks kosong dan riwayat Agent tidak tercampur antar pengguna.
        session_id = f"{user_key()}-{chat['id']}"

        # Lampiran CSV/TSV tetap tersedia untuk pertanyaan lanjutan di chat ini.
        stored_tables = chat.setdefault("tables", {})
        stored_tables.update(pending_request.get("tables", {}))

        while len(stored_tables) > MAX_CHAT_TABLES:
            stored_tables.pop(next(iter(stored_tables)))

        tables = chat_tables(chat)

        answer = check_rate_limit()

        if answer is None and pending_request["images"]:

            image_paths, upload_error = upload_images(
                pending_request["images"]
            )

            if upload_error:
                answer = upload_error
            else:
                answer = ask_langflow(
                    pending_request["payload"],
                    tweaks=build_tweaks(image_paths, tables),
                    session_id=session_id,
                )

        elif answer is None:

            answer = ask_langflow(
                pending_request["payload"],
                tweaks=build_tweaks(tables=tables),
                session_id=session_id,
            )

        working_slot.empty()

    failed = is_error_answer(answer)

    # Lampiran asli hanya perlu disimpan untuk tombol Retry.
    if not failed:
        # Catat kapan isi file proyek terakhir dikirim; pesan berikutnya
        # cukup menyebut nama filenya selama salinan ini masih di riwayat.
        if pending_request.get("project_context"):
            chat["project_context"] = pending_request["project_context"]

        user_message.pop("payload", None)
        user_message["images"] = [
            make_thumbnail(image) for image in user_message["images"]
        ]

    chat["messages"].append(
        {
            "role": "assistant",
            "content": answer,
            "error": failed,
        }
    )
    chat["updated"] = time.time()

    # Render ulang agar jawaban, riwayat sidebar, dan tombol retry tampil
    # dari state dengan struktur yang sama seperti pesan lama.
    st.rerun()
