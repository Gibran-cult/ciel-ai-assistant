import gc
import time
import uuid
from pathlib import Path

import chromadb
import requests


OLLAMA_URL = "http://127.0.0.1:11434/api/embed"
EMBEDDING_MODEL = "nomic-embed-text-v2-moe:latest"


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
            f"Response embedding tidak sesuai:\n{data}"
        ) from exc


def format_current(
    query,
    documents,
    metadatas,
    distances,
):
    lines = [
        "HASIL LONG-TERM MEMORY",
        f"Query: {query}",
        f"Jumlah hasil: {len(documents)}",
        "",
    ]

    for i, document in enumerate(documents, start=1):

        metadata = (
            metadatas[i - 1]
            if i - 1 < len(metadatas)
            else {}
        )

        distance = (
            distances[i - 1]
            if i - 1 < len(distances)
            else None
        )

        lines.append(f"[Memory {i}]")
        lines.append(f"Isi: {document}")

        if distance is not None:
            lines.append(
                f"Distance: {distance:.6f}"
            )

        if metadata:
            lines.append(
                f"Metadata: {metadata}"
            )

        lines.append("")

    return "\n".join(lines)


def format_compact(documents):
    lines = [
        "LONG-TERM MEMORY",
        "",
    ]

    for i, document in enumerate(documents, start=1):
        lines.append(
            f"{i}. {document}"
        )

    return "\n".join(lines)


def approx_tokens(text):
    # Estimasi kasar saja untuk membandingkan ukuran relatif.
    return max(1, len(text) // 4)


def run_benchmark():

    print()
    print("=" * 72)
    print("CIEL AI MASTER — MEMORY CONTEXT OPTIMIZATION")
    print("=" * 72)
    print()

    memories = [
        (
            "Saya sedang belajar Data Science dan "
            "sekarang fokus pada Python, pandas, "
            "statistika, dan machine learning."
        ),
        (
            "Saya masih mahasiswa baru di program "
            "studi Data Science."
        ),
        (
            "Saya sedang membangun proyek Ciel AI Master "
            "menggunakan Langflow dan Ollama."
        ),
        (
            "Saya ingin memahami coding secara bertahap "
            "karena kemampuan Python saya masih dasar."
        ),
        (
            "Saya tertarik dengan pekerjaan freelance "
            "yang berkaitan dengan data."
        ),
        (
            "Saya suka bermain game ketika waktu luang."
        ),
        (
            "Saya sering menonton video teknologi."
        ),
        (
            "Saya ingin membuat beberapa project Data Science "
            "untuk menambah pengalaman."
        ),
    ]

    query = (
        "Apa yang sedang saya pelajari "
        "dalam bidang pendidikan dan teknologi?"
    )

    client = chromadb.Client()
    collection = None
    collection_name = (
        f"ciel_context_opt_{uuid.uuid4().hex[:8]}"
    )

    try:

        collection = client.get_or_create_collection(
            name=collection_name,
            metadata={
                "hnsw:space": "cosine"
            },
        )

        print("Membuat embedding memory...")

        embeddings = [
            create_embedding(memory)
            for memory in memories
        ]

        query_embedding = create_embedding(query)

        ids = [
            f"memory_{i}_{uuid.uuid4().hex[:8]}"
            for i in range(len(memories))
        ]

        timestamp = "benchmark"

        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=memories,
            metadatas=[
                {
                    "created_at": timestamp,
                    "source": "context_optimization",
                }
                for _ in memories
            ],
        )

        print()
        print(
            f"Total memory: {collection.count()}"
        )
        print(
            f"Query: {query}"
        )
        print()

        print(
            "K | Search(s) | Current chars | Compact chars | "
            "Current ~tok | Compact ~tok | Relevant"
        )
        print("-" * 72)

        for k in (1, 3, 5):

            start = time.perf_counter()

            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=k,
                include=[
                    "documents",
                    "metadatas",
                    "distances",
                ],
            )

            elapsed = time.perf_counter() - start

            documents = (
                results.get("documents", [[]])[0]
            )

            metadatas = (
                results.get("metadatas", [[]])[0]
            )

            distances = (
                results.get("distances", [[]])[0]
            )

            current_output = format_current(
                query,
                documents,
                metadatas,
                distances,
            )

            compact_output = format_compact(
                documents
            )

            relevant = any(
                "Data Science" in document
                or "Python" in document
                or "Langflow" in document
                for document in documents
            )

            print(
                f"{k:<1} | "
                f"{elapsed:>9.4f} | "
                f"{len(current_output):>13} | "
                f"{len(compact_output):>13} | "
                f"{approx_tokens(current_output):>12} | "
                f"{approx_tokens(compact_output):>11} | "
                f"{'YES' if relevant else 'NO'}"
            )

            print()
            print(f"Top {k} current output:")
            print(current_output)
            print()

            print(f"Top {k} compact output:")
            print(compact_output)
            print()

            print("-" * 72)

        print()
        print("Benchmark selesai.")

    finally:

        if collection is not None:

            try:
                client.delete_collection(
                    name=collection_name
                )
            except Exception:
                pass

        collection = None
        client = None
        gc.collect()


if __name__ == "__main__":
    run_benchmark()
