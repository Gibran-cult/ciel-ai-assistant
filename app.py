import os
import time
import uuid
import logging

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
    page_icon="🤖",
    layout="centered",
)


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
        "❌ Konfigurasi belum lengkap.\n\n"
        f"Variabel yang belum tersedia: "
        f"{', '.join(missing_config)}"
    )

    st.stop()


# ============================================================
# SESSION STATE
# ============================================================

if "messages" not in st.session_state:
    st.session_state.messages = []


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

        logger.error(
            "http_error id=%s status=%s elapsed=%.2fs error=%s",
            request_id,
            response.status_code,
            elapsed,
            error,
        )

        return (
            "🚫 Langflow/ngrok menolak request.\n\n"
            f"HTTP Error: {error}\n\n"
            f"Response:\n{response.text}"
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
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("⚙️ Settings")

    st.success("Langflow API terhubung")

    # --------------------------------------------------------
    # HEALTH CHECK
    # --------------------------------------------------------

    if st.button(
        "🔎 Check Backend",
        use_container_width=True
    ):

        health = check_backend_health()

        if health["ok"]:

            if (
                health["status"] == "ok"
                and health["chat"] == "ok"
                and health["db"] == "ok"
            ):

                st.success(
                    "✅ Backend sehat"
                )

                st.caption(
                    f"Status: {health['status']}\n\n"
                    f"Chat: {health['chat']}\n\n"
                    f"DB: {health['db']}"
                )

            else:

                st.warning(
                    "⚠️ Backend merespons, "
                    "tetapi ada komponen yang bermasalah."
                )

                st.json(health)

        else:

            st.error(
                f"❌ Backend tidak sehat\n\n"
                f"{health['error']}"
            )

    # --------------------------------------------------------
    # FLOW ID
    # --------------------------------------------------------

    st.caption("Flow ID")

    st.code(FLOW_ID)

    st.divider()

    # --------------------------------------------------------
    # CLEAR CHAT
    # --------------------------------------------------------

    if st.button(
        "🗑️ Clear Chat",
        use_container_width=True
    ):

        st.session_state.messages = []

        st.rerun()

    st.divider()

    # --------------------------------------------------------
    # ABOUT
    # --------------------------------------------------------

    st.caption(
        "AI Backend: Langflow\n\n"
        "Architecture: Multi-Agent System"
    )


# ============================================================
# HEADER
# ============================================================

st.title("🤖 Ciel AI Assistant")

st.caption(
    "Multi-Agent AI powered by Langflow"
)


# ============================================================
# CHAT HISTORY
# ============================================================

for message in st.session_state.messages:

    with st.chat_message(
        message["role"]
    ):

        st.markdown(
            message["content"]
        )


# ============================================================
# CHAT INPUT
# ============================================================

prompt = st.chat_input(
    "Tanyakan sesuatu kepada AI..."
)


if prompt:

    # --------------------------------------------------------
    # USER MESSAGE
    # --------------------------------------------------------

    st.session_state.messages.append(
        {
            "role": "user",
            "content": prompt,
        }
    )

    with st.chat_message("user"):

        st.markdown(prompt)

    # --------------------------------------------------------
    # ASSISTANT MESSAGE
    # --------------------------------------------------------

    with st.chat_message("assistant"):

        with st.spinner(
            "🧠 Supervisor sedang berpikir..."
        ):

            answer = ask_langflow(prompt)

            st.markdown(answer)

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": answer,
                }
            )
