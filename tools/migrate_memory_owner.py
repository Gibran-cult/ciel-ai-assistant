"""
Assign an owner to long-term memories saved before flow v1.3.0.

Flow v1.3.0 only searches memories whose metadata `user_id` matches the
signed-in user, so memories stored by older flows (no `user_id`) become
invisible. Run this once on the Langflow host to give them to one account.

Find your ID in the app: sign in, open the sidebar "About long-term memory"
panel, and copy "ID memory".

    python tools/migrate_memory_owner.py --user-id <ID> --dry-run
    python tools/migrate_memory_owner.py --user-id <ID>
"""

import argparse
import re
import sys
from pathlib import Path

DEFAULT_DB_PATH = Path.home() / ".ciel_ai" / "long_term_memory"
COLLECTION_NAME = "ciel_long_term_memory"


def unowned_ids(ids, metadatas):
    """IDs whose metadata has no non-empty user_id."""
    return [
        memory_id
        for memory_id, metadata in zip(ids, metadatas)
        if not str((metadata or {}).get("user_id") or "").strip()
    ]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--user-id", required=True, help="ID memory from the app sidebar")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--dry-run", action="store_true", help="only report what would change")
    args = parser.parse_args(argv)

    user_id = args.user_id.strip()

    if not re.fullmatch(r"[0-9a-f]{16}", user_id):
        parser.error("--user-id must be the 16-character ID shown in the app")

    import chromadb

    client = chromadb.PersistentClient(path=args.db_path)

    try:
        collection = client.get_collection(name=COLLECTION_NAME)
    except Exception as exc:
        print(f"Collection {COLLECTION_NAME!r} not found in {args.db_path}: {exc}")
        return 1

    data = collection.get(include=["metadatas"])
    ids = data.get("ids") or []
    metadatas = data.get("metadatas") or [{} for _ in ids]
    targets = unowned_ids(ids, metadatas)

    print(f"Total memories: {len(ids)}; without owner: {len(targets)}")

    if not targets or args.dry_run:
        if args.dry_run:
            print("Dry run: nothing changed.")
        return 0

    by_id = dict(zip(ids, metadatas))
    collection.update(
        ids=targets,
        metadatas=[{**(by_id[i] or {}), "user_id": user_id} for i in targets],
    )

    print(f"Assigned {len(targets)} memories to {user_id}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
