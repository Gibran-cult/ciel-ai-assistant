import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

V1_BASELINE = (
    ROOT
    / "flow"
    / "v1.0.0"
    / "Ciel_AI_Long-Term_Memory_Master.json"
)

V1_1 = (
    ROOT
    / "flow"
    / "v1.1.0"
    / "Ciel_AI_Long-Term_Memory_Master.json"
)


def load_flow(path):
    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def find_memory_search_nodes(obj):
    found = []

    if isinstance(obj, dict):

        if obj.get("type") == "CielMemorySearch":
            found.append(obj)

        for value in obj.values():
            found.extend(
                find_memory_search_nodes(value)
            )

    elif isinstance(obj, list):

        for value in obj:
            found.extend(
                find_memory_search_nodes(value)
            )

    return found


def extract_component_code(node_data):
    node = node_data.get(
        "node",
        {},
    )

    template = node.get(
        "template",
        {},
    )

    code = template.get(
        "code",
        {},
    )

    if isinstance(code, dict):
        return code.get(
            "value",
            "",
        )

    return ""


class TestMemoryV110Contract(
    unittest.TestCase
):

    def test_baseline_exists(self):
        self.assertTrue(
            V1_BASELINE.exists(),
            "v1.0.0 snapshot tidak ditemukan.",
        )

    def test_v110_exists(self):
        self.assertTrue(
            V1_1.exists(),
            "v1.1.0 snapshot tidak ditemukan.",
        )

    def test_memory_search_exists(self):
        flow = load_flow(V1_1)

        nodes = find_memory_search_nodes(
            flow
        )

        self.assertGreaterEqual(
            len(nodes),
            1,
            "CielMemorySearch tidak ditemukan.",
        )

    def test_top_k_remains_five(self):
        flow = load_flow(V1_1)

        nodes = find_memory_search_nodes(
            flow
        )

        self.assertGreaterEqual(
            len(nodes),
            1,
        )

        found = False

        for node_data in nodes:

            node = node_data.get(
                "node",
                {},
            )

            template = node.get(
                "template",
                {},
            )

            top_k = template.get(
                "top_k",
                {},
            )

            if isinstance(top_k, dict):

                value = top_k.get(
                    "value",
                )

                if value == 5 or value == "5":
                    found = True

        self.assertTrue(
            found,
            "Top K=5 tidak ditemukan pada v1.1.0.",
        )

    def test_compact_output_contract(self):
        flow = load_flow(V1_1)

        nodes = find_memory_search_nodes(
            flow
        )

        self.assertGreaterEqual(
            len(nodes),
            1,
        )

        codes = [
            extract_component_code(node)
            for node in nodes
        ]

        combined = "\n".join(codes)

        self.assertIn(
            "LONG-TERM MEMORY",
            combined,
        )

        self.assertIn(
            "return Message",
            combined,
        )

        self.assertIn(
            "document",
            combined,
        )

    def test_old_verbose_fields_are_not_formatted(self):
        flow = load_flow(V1_1)

        nodes = find_memory_search_nodes(
            flow
        )

        codes = [
            extract_component_code(node)
            for node in nodes
        ]

        combined = "\n".join(codes)

        self.assertNotIn(
            'lines.append(f"Distance:',
            combined,
        )

        self.assertNotIn(
            'lines.append(f"Metadata:',
            combined,
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2,
    )