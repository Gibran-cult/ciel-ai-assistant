"""
Copy Langflow flows, and the sub-flows they call, from one server to another.

The main flow reaches Math Tutor Agent and Knowledge Retriever through Run
Flow nodes that point at flow IDs, and those IDs differ on every Langflow
server. This tool exports the given flows plus, recursively, their Run Flow
targets, imports the targets first, and rewrites each Run Flow node to the
new ID before importing the flow that calls it:

    python tools/migrate_flows.py --source-url http://127.0.0.1:7860 \\
        --target-url https://langflow.example.com --flow-id <main flow id> \\
        --map-out id_map.json --snapshot-dir flow/subflows

Keys come from SOURCE_LANGFLOW_API_KEY and TARGET_LANGFLOW_API_KEY in the
environment or a .env file. The ID map written by --map-out holds flow IDs
only, no secrets. --snapshot-dir saves each Run Flow target as pretty JSON
(`<name with spaces as _>.json`) so the sub-flows can be kept in Git.

The tool is not idempotent: run it once per target. A re-run imports every
flow again and Langflow keeps the copies as "(1)" duplicates. If an import
fails halfway, the exit code is 1 and the flows already created are listed
(and written to --map-out); delete them on the target before retrying.
"""

import argparse
import copy
import json
import os
import re
import sys
from pathlib import Path

import requests

TIMEOUT = 60
IMPORT_DROP_KEYS = ("id", "user_id", "folder_id", "updated_at", "webhook", "endpoint_name")


class MigrationError(Exception):
    """An import failed; `partial` maps the source IDs already created on the target."""

    def __init__(self, message, partial):
        super().__init__(message)
        self.partial = partial


def _run_flow_values(flow):
    """Yield (selector, value) for every Run Flow node's flow_id_selected."""
    for node in (flow.get("data") or {}).get("nodes") or []:
        data = node.get("data") or {}
        if data.get("type") != "RunFlow":
            continue
        selector = ((data.get("node") or {}).get("template") or {}).get("flow_id_selected")
        if isinstance(selector, dict) and selector.get("value"):
            yield selector, selector["value"]


def run_flow_targets(flow):
    """IDs of the flows called by the Run Flow nodes of `flow`."""
    return {value for _, value in _run_flow_values(flow)}


def remap_run_flows(flow, id_map):
    """Deep copy of `flow` with every Run Flow target replaced through `id_map`."""
    out = copy.deepcopy(flow)
    for selector, value in _run_flow_values(out):
        if value not in id_map:
            raise KeyError(f"Run Flow target {value} is not in the ID map")
        selector["value"] = id_map[value]
    return out


def importable(flow):
    """Copy of `flow` without the fields that belong to the source server."""
    return {key: value for key, value in flow.items() if key not in IMPORT_DROP_KEYS}


def snapshot_name(flow):
    return re.sub(r"\s+", "_", flow["name"].strip()) + ".json"


def write_snapshot(directory, flow):
    path = Path(directory) / snapshot_name(flow)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(importable(flow), indent=2, ensure_ascii=False) + "\n"
    path.write_bytes(text.encode("utf-8"))
    return path


def export_flow(base_url, headers, flow_id):
    response = requests.get(f"{base_url}/api/v1/flows/{flow_id}", headers=headers, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def import_flow(base_url, headers, flow):
    response = requests.post(f"{base_url}/api/v1/flows/", headers=headers, json=flow, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()["id"]


def collect_in_import_order(base_url, headers, flow_ids):
    """Export `flow_ids` and their Run Flow targets, callees before callers."""
    ordered = {}   # flow id -> flow, in dependency order
    visiting = []

    def visit(flow_id):
        if flow_id in ordered:
            return
        if flow_id in visiting:
            raise ValueError("Circular Run Flow reference: " + " -> ".join(visiting + [flow_id]))
        visiting.append(flow_id)
        flow = export_flow(base_url, headers, flow_id)
        for target in sorted(run_flow_targets(flow)):
            visit(target)
        visiting.pop()
        ordered[flow_id] = flow

    for flow_id in flow_ids:
        visit(flow_id)
    return ordered


def migrate(source_url, source_key, target_url, target_key, flow_ids, snapshot_dir=None):
    """Copy `flow_ids` and their sub-flows to the target; return {old_id: new_id}."""
    source_url, target_url = source_url.rstrip("/"), target_url.rstrip("/")
    source_headers = {"x-api-key": source_key, "Accept": "application/json"}
    target_headers = {"x-api-key": target_key, "Accept": "application/json"}

    flows = collect_in_import_order(source_url, source_headers, flow_ids)

    if snapshot_dir:
        called = set().union(*(run_flow_targets(flow) for flow in flows.values()))
        for flow_id in flows:
            if flow_id in called:
                write_snapshot(snapshot_dir, flows[flow_id])

    id_map = {}
    for flow_id, flow in flows.items():
        body = remap_run_flows(importable(flow), id_map)
        try:
            id_map[flow_id] = import_flow(target_url, target_headers, body)
        except Exception as error:
            raise MigrationError(
                f"Importing {flow.get('name', flow_id)} ({flow_id}) failed: {error}", dict(id_map)
            ) from error
    return id_map


def load_env_file():
    """Load a local .env if python-dotenv is installed."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Copy Langflow flows and their sub-flows between servers.")
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--target-url", required=True)
    parser.add_argument("--flow-id", action="append", required=True, help="flow to copy (repeatable)")
    parser.add_argument("--map-out", help="write the {old_id: new_id} map as JSON to this path")
    parser.add_argument("--snapshot-dir", help="save each exported Run Flow target here as pretty JSON")
    args = parser.parse_args(argv)

    load_env_file()

    source_key = os.getenv("SOURCE_LANGFLOW_API_KEY")
    target_key = os.getenv("TARGET_LANGFLOW_API_KEY")
    if not source_key or not target_key:
        parser.error("SOURCE_LANGFLOW_API_KEY and TARGET_LANGFLOW_API_KEY must be set (environment or .env)")

    failure = None
    try:
        id_map = migrate(args.source_url, source_key, args.target_url, target_key, args.flow_id, args.snapshot_dir)
    except MigrationError as error:
        failure, id_map = error, error.partial

    for old_id, new_id in id_map.items():
        print(f"Imported {old_id} -> {new_id}")
    if args.map_out:
        Path(args.map_out).write_text(json.dumps(id_map, indent=2) + "\n", encoding="utf-8")
        print(f"ID map written to {args.map_out}")
    if failure:
        print(f"ERROR: {failure}", file=sys.stderr)
        print(
            f"The target is partially migrated: {len(id_map)} flows were created. "
            "Delete these new flow IDs on the target before retrying: "
            + (", ".join(id_map.values()) or "(none)"),
            file=sys.stderr,
        )
        return 1
    print(f"Done: {len(id_map)} flows imported.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
