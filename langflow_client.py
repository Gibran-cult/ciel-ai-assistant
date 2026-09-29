import requests
import json

API_URL = "http://localhost:7860/api/v1/run/4166c4a3-3926-433e-a48f-d812bc8efb99?stream=false"
API_KEY = "sk-QcdmsuKch3r1uNzoTYwj-rOR-IYwMlI-rcVdoNasa6Y"

question = input("Pertanyaan: ")

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

except requests.exceptions.RequestException as e:
    print(f"\nAPI Error: {e}")

except (KeyError, IndexError, TypeError) as e:
    print("\nResponse Langflow memiliki struktur yang berbeda.")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"\nDetail: {e}")