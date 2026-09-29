import os

import requests
import streamlit as st
from dotenv import load_dotenv


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

try:
    API_KEY = st.secrets["LANGFLOW_API_KEY"]
except Exception:
    API_KEY = os.getenv("sk-QcdmsuKch3r1uNzoTYwj-rOR-IYwMlI-rcVdoNasa6Y")
FLOW_ID = "4166c4a3-3926-433e-a48f-d812bc8efb99"

API_URL = (
    f"https://charbroil-datebook-raving.ngrok-free.dev"
    f"/api/v1/run/{FLOW_ID}?stream=false"
)


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Ciel AI Assistant",
    page_icon="🤖",
    layout="centered",
)


# ============================================================
# VALIDATE CONFIG
# ============================================================

if not API_KEY:
    st.error(
        "❌ LANGFLOW_API_KEY tidak ditemukan.\n\n"
        "Pastikan file `.env` berisi:\n\n"
        "`LANGFLOW_API_KEY=API_KEY_KAMU`"
    )
    st.stop()


# ============================================================
# SESSION STATE
# ============================================================

if "messages" not in st.session_state:
    st.session_state.messages = []


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("⚙️ Settings")

    st.success("Langflow API terhubung")

    st.caption("Flow ID")
    st.code(FLOW_ID)

    st.divider()

    if st.button(
        "🗑️ Clear Chat",
        use_container_width=True
    ):
        st.session_state.messages = []
        st.rerun()

    st.divider()

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
# LANGFLOW API
# ============================================================

def ask_langflow(question: str) -> str:

    headers = {
        "Content-Type": "application/json",
        "accept": "application/json",
        "x-api-key": API_KEY,
    }

    payload = {
        "input_value": question,
        "input_type": "chat",
        "output_type": "chat",
    }

    response = requests.post(
        API_URL,
        headers=headers,
        json=payload,
        timeout=120,
    )

    # Raise error for HTTP 4xx / 5xx
    response.raise_for_status()

    data = response.json()

    # Extract Langflow response
    try:
        answer = (
            data["outputs"][0]
            ["outputs"][0]
            ["results"]["message"]
            ["data"]["text"]
        )

    except (
        KeyError,
        IndexError,
        TypeError,
    ) as error:

        raise ValueError(
            "Struktur response Langflow tidak sesuai."
        ) from error

    return answer


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

            try:

                answer = ask_langflow(prompt)

                st.markdown(answer)

                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": answer,
                    }
                )

            except requests.exceptions.Timeout:

                st.error(
                    "⏱️ Request timeout.\n\n"
                    "Langflow membutuhkan terlalu lama "
                    "untuk memberikan jawaban."
                )

            except requests.exceptions.ConnectionError:

                st.error(
                    "🔌 Tidak dapat terhubung ke Langflow.\n\n"
                    "Pastikan Langflow Desktop sedang berjalan "
                    "di `localhost:7860`."
                )

            except requests.exceptions.HTTPError as error:

                st.error(
                    "🚫 Langflow menolak request."
                )

                st.code(
                    str(error)
                )

            except ValueError as error:

                st.error(
                    "⚠️ Response Langflow tidak dikenali."
                )

                st.code(
                    str(error)
                )

            except Exception as error:

                st.error(
                    "❌ Terjadi error yang tidak terduga."
                )

                st.code(
                    str(error)
                )