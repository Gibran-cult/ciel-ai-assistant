"""Ciel Exa Search (Langflow custom component).

Same inputs and tools as the official Exa Search toolkit, plus a record of
every URL Exa returns during the run, kept in the graph context. Ciel Source
Guard reads that record to drop sources the Research Agent did not get from
a search.

The record comes from Exa's responses themselves, not from the Agent's
message events, so the guard does not depend on how Langflow logs tool calls.
In 9 probe runs (2026-10-17) both agreed: 2 searches, 10 URLs each time.
"""

from langchain_core.tools import StructuredTool
from langflow.custom import Component
from langflow.field_typing import Tool
from lfx_exa.components.exa.exa_search import ExaSearchToolkit

# Same key in ciel_source_guard.py (components cannot import each other).
RETRIEVED_URLS_KEY = "ciel_retrieved_urls"


def result_urls(response):
    """URLs of an Exa search or get_contents response, in result order."""
    return [str(item.url) for item in getattr(response, "results", None) or [] if getattr(item, "url", None)]


# Component is listed explicitly: Langflow finds a component class by its
# written bases, and ExaSearchToolkit already derives from Component.
class CielExaSearch(ExaSearchToolkit, Component):
    display_name = "Ciel Exa Search"
    description = (
        "Exa search untuk Research Agent. Sama seperti Exa Search, ditambah catatan URL "
        "yang benar-benar dikembalikan Exa untuk dicek Ciel Source Guard."
    )
    name = "CielExaSearch"

    def build_toolkit(self) -> Tool:
        retrieved = self.ctx.setdefault(RETRIEVED_URLS_KEY, [])

        def recorded(original):
            def run(**kwargs):
                response = original.func(**kwargs)
                retrieved.extend(result_urls(response))
                return response

            return StructuredTool.from_function(
                func=run,
                name=original.name,
                description=original.description,
                args_schema=original.args_schema,
            )

        return [recorded(item) for item in super().build_toolkit()]
