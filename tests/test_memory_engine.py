import gc
import uuid
from datetime import datetime, timezone

import chromadb
import requests


# ============================================================
# CONFIGURATION
# ============================================================

OLLAMA_URL = "http://127.0.0.1:11434/api/embed"
EMBEDDING_MODEL = "nomic-embed-text-v2-moe:latest"


# ============================================================
# EMBEDDING
# ============================================================

def create_embedding(text):

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": EMBEDDING_MODEL,
            "input": text,
        },
        timeout=120,
    )

    response.raise_for_status()

    data = response.json()

    try:
        return data["embeddings"][0]

    except (KeyError, IndexError, TypeError) as exc:

        raise RuntimeError(
            f"Response embedding Ollama tidak sesuai:\n{data}"
        ) from exc


# ============================================================
# MEMORY REGRESSION TEST
# ============================================================

def run_memory_regression_test():

    print()
    print("=" * 55)
    print("CIEL AI MASTER — MEMORY REGRESSION TEST")
    print("=" * 55)
    print()

    target_memory = (
        "Saya sedang belajar Data Science dan "
        "sekarang fokus pada Python, pandas, "
        "statistika, dan machine learning."
    )

    distractor_memory = (
        "Saya suka menonton film dan bermain game "
        "saat waktu luang."
    )

    search_query = (
        "Apa yang sedang saya pelajari?"
    )

    # ========================================================
    # CHROMA DATABASE
    # ========================================================

    client = chromadb.Client()
    collection = None
    collection_name = (
        f"ciel_regression_{uuid.uuid4().hex[:8]}"
    )

    try:

        print(
            "📦 Membuat temporary Chroma database..."
        )

        collection = client.get_or_create_collection(
            name=collection_name,
            metadata={
                "hnsw:space": "cosine"
            },
        )

        # ====================================================
        # CREATE EMBEDDINGS
        # ====================================================

        print(
            "🧠 Membuat embedding memory..."
        )

        target_embedding = create_embedding(
            target_memory
        )

        distractor_embedding = create_embedding(
            distractor_memory
        )

        query_embedding = create_embedding(
            search_query
        )

        # ====================================================
        # STORE
        # ====================================================

        print(
            "💾 Menyimpan test memory..."
        )

        target_id = (
            f"memory_{uuid.uuid4().hex}"
        )

        distractor_id = (
            f"memory_{uuid.uuid4().hex}"
        )

        timestamp = (
            datetime.now(timezone.utc).isoformat()
        )

        collection.add(
            ids=[
                target_id,
                distractor_id,
            ],
            embeddings=[
                target_embedding,
                distractor_embedding,
            ],
            documents=[
                target_memory,
                distractor_memory,
            ],
            metadatas=[
                {
                    "created_at": timestamp,
                    "source": "ciel_memory_regression",
                },
                {
                    "created_at": timestamp,
                    "source": "ciel_memory_regression",
                },
            ],
        )

        count = collection.count()

        store_pass = (
            count == 2
        )

        print(
            f"{'✅' if store_pass else '❌'} "
            f"Memory Store              "
            f"{'PASS' if store_pass else 'FAIL'}"
        )

        if not store_pass:
            return False

        # ====================================================
        # SEARCH
        # ====================================================

        print(
            "🔎 Melakukan semantic search..."
        )

        results = collection.query(
            query_embeddings=[
                query_embedding
            ],
            n_results=1,
            include=[
                "documents",
                "metadatas",
                "distances",
            ],
        )

        documents = (
            results.get(
                "documents",
                [[]]
            )[0]
        )

        metadatas = (
            results.get(
                "metadatas",
                [[]]
            )[0]
        )

        distances = (
            results.get(
                "distances",
                [[]]
            )[0]
        )

        # ====================================================
        # VALIDATE SEARCH
        # ====================================================

        search_pass = (
            len(documents) == 1
            and "Data Science" in documents[0]
            and "Python" in documents[0]
        )

        print(
            f"{'✅' if search_pass else '❌'} "
            f"Memory Search              "
            f"{'PASS' if search_pass else 'FAIL'}"
        )

        if documents:

            print(
                f"   Result: {documents[0]}"
            )

        if distances:

            print(
                f"   Distance: {distances[0]:.6f}"
            )

        # ====================================================
        # VALIDATE METADATA
        # ====================================================

        metadata_pass = (
            len(metadatas) == 1
            and metadatas[0].get(
                "source"
            ) == "ciel_memory_regression"
            and "created_at" in metadatas[0]
        )

        print(
            f"{'✅' if metadata_pass else '❌'} "
            f"Memory Metadata            "
            f"{'PASS' if metadata_pass else 'FAIL'}"
        )

        # ====================================================
        # FINAL RESULT
        # ====================================================

        final_pass = (
            store_pass
            and search_pass
            and metadata_pass
        )

        print()
        print("=" * 55)

        if final_pass:

            print(
                "✅ MEMORY REGRESSION TEST PASSED"
            )

        else:

            print(
                "❌ MEMORY REGRESSION TEST FAILED"
            )

        print("=" * 55)

        return final_pass

    finally:

        print()
        print(
            "🧹 Membersihkan temporary memory..."
        )

        try:

            if collection is not None:

                client.delete_collection(
                    name=collection_name
                )

        except Exception:

            pass

        collection = None
        client = None

        gc.collect()

        print(
            "✅ Temporary memory dibersihkan."
        )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    success = run_memory_regression_test()

    if not success:

        raise SystemExit(1)