"""Ciel Scholar Search (Langflow custom component, flow Ciel Riset Skripsi).

Same inputs as the official Exa Search toolkit, with two differences from
Ciel Exa Search (main flow):

- Only the `search` tool is given to the Agent. `get_contents` is left out,
  so the Agent cannot fetch full pages (the prompt forbade it; now the flow
  does too).
- Besides the URL list that Ciel Source Guard reads, every result's metadata
  (title, author, published date) is kept in the graph context. Ciel Reference
  Builder writes the APA reference list from that record, so authors and
  years come from Exa, never from the model.
- The Exa highlights (the passages the Agent read) are kept too. The builder
  hands them to the app, which compares a student's draft against them
  (Cek kutipan & kemiripan).

The year range comes from the app as a tweak on `start_published_date`
(YYYY-01-01), which Exa applies on its side.
"""

from langchain_core.tools import StructuredTool
from langflow.custom import Component
from langflow.field_typing import Tool
from lfx_exa.components.exa.exa_search import ExaSearchToolkit

# Same keys in ciel_source_guard.py and ciel_reference_builder.py
# (components cannot import each other).
RETRIEVED_URLS_KEY = "ciel_retrieved_urls"
RETRIEVED_SOURCES_KEY = "ciel_retrieved_sources"

MAX_HIGHLIGHTS = 3
MAX_HIGHLIGHT_CHARS = 1500


def result_metadata(response):
    """[{url, title, author, published_date[, highlights]}] of an Exa search response, in result order."""
    sources = []
    for item in getattr(response, "results", None) or []:
        url = getattr(item, "url", None)
        if not url:
            continue
        source = {
            "url": str(url),
            "title": str(getattr(item, "title", None) or "").strip(),
            "author": str(getattr(item, "author", None) or "").strip(),
            "published_date": str(getattr(item, "published_date", None) or "").strip(),
        }
        highlights = [
            str(text).strip()[:MAX_HIGHLIGHT_CHARS]
            for text in getattr(item, "highlights", None) or []
            if str(text or "").strip()
        ][:MAX_HIGHLIGHTS]
        if highlights:
            source["highlights"] = highlights
        sources.append(source)
    return sources


# Component is listed explicitly: Langflow finds a component class by its
# written bases, and ExaSearchToolkit already derives from Component.
class CielScholarSearch(ExaSearchToolkit, Component):
    display_name = "Ciel Scholar Search"
    description = (
        "Pencarian Exa untuk Riset Skripsi. Hanya tool search; mencatat URL dan "
        "metadata sumber (judul, penulis, tanggal) untuk Ciel Source Guard dan "
        "Ciel Reference Builder."
    )
    name = "CielScholarSearch"

    def build_toolkit(self) -> Tool:
        urls = self.ctx.setdefault(RETRIEVED_URLS_KEY, [])
        sources = self.ctx.setdefault(RETRIEVED_SOURCES_KEY, [])
        search = next(item for item in super().build_toolkit() if item.name == "search")

        def run(**kwargs):
            response = search.func(**kwargs)
            found = result_metadata(response)
            urls.extend(source["url"] for source in found)
            sources.extend(found)
            return response

        return [
            StructuredTool.from_function(
                func=run,
                name=search.name,
                description=search.description,
                args_schema=search.args_schema,
            )
        ]
