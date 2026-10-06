import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

LANGFLOW_BASE_URL = os.getenv("LANGFLOW_BASE_URL", "http://localhost:7860").rstrip("/")
FLOW_ID = os.getenv("FLOW_ID")
LANGFLOW_API_KEY = os.getenv("LANGFLOW_API_KEY")

if not FLOW_ID:
    raise RuntimeError("FLOW_ID belum tersedia.")

if not LANGFLOW_API_KEY:
    raise RuntimeError("LANGFLOW_API_KEY belum tersedia.")

API_URL = (
    f"{LANGFLOW_BASE_URL}/api/v1/run/"
    f"{FLOW_ID}?stream=false"
)

question = input("Pertanyaan: ")

headers = {
    "Content-Type": "application/json",
    "accept": "application/json",
    "x-api-key": LANGFLOW_API_KEY,
}

payload = {
    "input_value": question,
    "input_type": "chat",
    "output_type": "chat",
}

try:
    response = requests.post(
        API_URL,
        headers=headers,
        json=payload,
        timeout=120,
    )

    response.raise_for_status()

    data = response.json()

    answer = (
        data["outputs"][0]
        ["outputs"][0]
        ["results"]["message"]["data"]["text"]
    )

    print("\nAI:")
    print(answer)

except requests.exceptions.Timeout:
    print("\nAPI Error: request timeout.")

except requests.exceptions.ConnectionError:
    print("\nAPI Error: backend tidak dapat dihubungi.")

except requests.exceptions.HTTPError as error:
    print(f"\nAPI Error: HTTP {response.status_code} - {error}")

except requests.exceptions.RequestException as error:
    print(f"\nAPI Error: {error}")

except (KeyError, IndexError, TypeError) as error:
    print("\nResponse Langflow memiliki struktur yang berbeda.")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"\nDetail: {error}")

except ValueError:
    print("\nResponse Langflow bukan JSON yang valid.")