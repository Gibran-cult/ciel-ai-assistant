import gc
import time
import uuid

import chromadb
import requests


OLLAMA_URL = "http://127.0.0.1:11434/api/embed"
EMBEDDING_MODEL = "nomic-embed-text-v2-moe:latest"


MEMORIES = [
    "Saya sedang belajar Data Science dan sekarang fokus pada Python, pandas, statistika, dan machine learning.",
    "Saya masih mahasiswa baru di program studi Data Science.",
    "Saya sedang membangun proyek Ciel AI Master menggunakan Langflow dan Ollama.",
    "Saya ingin memahami coding secara bertahap karena kemampuan Python saya masih dasar.",
    "Saya tertarik dengan pekerjaan freelance yang berkaitan dengan data.",
    "Saya suka bermain game ketika waktu luang.",
    "Saya sering menonton video teknologi.",
    "Saya ingin membuat beberapa project Data Science untuk menambah pengalaman.",
]


QUERIES = [
    {
        "name": "education",
        "query": "Apa yang sedang saya pelajari dalam pendidikan saya?",
        "keywords": ["Data Science", "Python"],
    },
    {
        "name": "python",
        "query": "Apa yang sedang saya pelajari tentang coding?",
        "keywords": ["Python", "coding"],
    },
    {
        "name": "project",
        "query": "Proyek teknologi apa yang sedang saya kerjakan?",
        "keywords": ["Ciel AI Master", "Langflow", "Ollama"],
    },
    {
        "name": "career",
        "query": "Pekerjaan seperti apa yang saya minati?",
        "keywords": ["freelance", "data"],
    },
    {
        "name": "preference",
        "query": "Apa yang saya lakukan ketika waktu luang?",
        "keywords": ["game", "video"],
    },
    {
        "name": "goal",
        "query": "Mengapa saya ingin membuat project Data Science?",
        "keywords": ["project", "pengalaman"],
    },
]


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
        lines.append(f"{i}. {document}")

    return "\n".join(lines)


def approx_tokens(text):
    return max(1, len(text) // 4)


def matches_any_keyword(documents, keywords):
    combined = " ".join(documents).lower()

    return any(
        keyword.lower() in combined
        for keyword in keywords
    )


def matched_keywords(documents, keywords):
    combined = " ".join(documents).lower()

    return [
        keyword
        for keyword in keywords
        if keyword.lower() in combined
    ]


def run_benchmark():

    print()
    print("=" * 100)
    print("CIEL AI MASTER - MULTI-QUERY MEMORY RECALL BENCHMARK")
    print("=" * 100)
    print()

    client = chromadb.Client()
    collection = None

    collection_name = (
        f"ciel_multi_query_{uuid.uuid4().hex[:8]}"
    )

    try:

        collection = client.get_or_create_collection(
            name=collection_name,
            metadata={
                "hnsw:space": "cosine"
            },
        )

        print("Creating memory embeddings...")

        memory_embeddings = [
            create_embedding(memory)
            for memory in MEMORIES
        ]

        collection.add(
            ids=[
                f"memory_{i}_{uuid.uuid4().hex[:8]}"
                for i in range(len(MEMORIES))
            ],
            embeddings=memory_embeddings,
            documents=MEMORIES,
            metadatas=[
                {
                    "source": "multi_query_benchmark",
                    "created_at": "benchmark",
                }
                for _ in MEMORIES
            ],
        )

        print(
            f"Total memory: {collection.count()}"
        )

        print()
        print(
            "Pre-computing query embeddings..."
        )

        query_embeddings = {}

        for case in QUERIES:
            query_embeddings[case["name"]] = (
                create_embedding(case["query"])
            )

        print()
        print("=" * 100)
        print("RESULTS")
        print("=" * 100)

        print()
        print(
            "Query        K   Search(s)   Current Chars   Compact Chars   "
            "Current ~Tok   Compact ~Tok   Recall"
        )
        print("-" * 100)

        summary = {}

        for case in QUERIES:

            name = case["name"]
            query = case["query"]
            keywords = case["keywords"]

            summary[name] = {}

            for k in (1, 3, 5):

                start = time.perf_counter()

                results = collection.query(
                    query_embeddings=[
                        query_embeddings[name]
                    ],
                    n_results=k,
                    include=[
                        "documents",
                        "metadatas",
                        "distances",
                    ],
                )

                elapsed = (
                    time.perf_counter()
                    - start
                )

                documents = (
                    results.get(
                        "documents",
                        [[]],
                    )[0]
                )

                metadatas = (
                    results.get(
                        "metadatas",
                        [[]],
                    )[0]
                )

                distances = (
                    results.get(
                        "distances",
                        [[]],
                    )[0]
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

                recall = matches_any_keyword(
                    documents,
                    keywords,
                )

                matched = matched_keywords(
                    documents,
                    keywords,
                )

                summary[name][k] = {
                    "latency": elapsed,
                    "current_chars": len(
                        current_output
                    ),
                    "compact_chars": len(
                        compact_output
                    ),
                    "current_tokens": approx_tokens(
                        current_output
                    ),
                    "compact_tokens": approx_tokens(
                        compact_output
                    ),
                    "recall": recall,
                    "matched": matched,
                    "documents": documents,
                }

                print(
                    f"{name:<12} "
                    f"{k:<3} "
                    f"{elapsed:>10.4f}   "
                    f"{len(current_output):>14}   "
                    f"{len(compact_output):>13}   "
                    f"{approx_tokens(current_output):>12}   "
                    f"{approx_tokens(compact_output):>11}   "
                    f"{'YES' if recall else 'NO'}"
                )

            print()

        print("=" * 100)
        print("RECALL SUMMARY")
        print("=" * 100)
        print()

        for case in QUERIES:

            name = case["name"]

            results = []

            for k in (1, 3, 5):
                item = summary[name][k]

                results.append(
                    f"K{k}="
                    f"{'YES' if item['recall'] else 'NO'}"
                )

            print(
                f"{name:<12}: "
                + " | ".join(results)
            )

        print()
        print("=" * 100)
        print("COMPACT CONTEXT SAVINGS")
        print("=" * 100)
        print()

        for k in (1, 3, 5):

            current_total = sum(
                summary[name][k]["current_chars"]
                for name in summary
            )

            compact_total = sum(
                summary[name][k]["compact_chars"]
                for name in summary
            )

            savings = (
                100
                * (
                    current_total
                    - compact_total
                )
                / current_total
            )

            print(
                f"K={k}: "
                f"{current_total} -> "
                f"{compact_total} chars "
                f"({savings:.1f}% reduction)"
            )

        print()
        print(
            "Benchmark selesai."
        )

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
