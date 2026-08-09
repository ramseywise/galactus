"""Hybrid PDF ingest: a text path and a vision path, converging on `Fact`.

Neither path alone is sufficient. Text extraction gives exact character offsets
— which is what makes a citation checkable — but returns nothing for a chart, a
diagram, or a table rendered as vector strokes. Vision reads those, but its
output is model-generated prose with no offset into the source.

So both run, and both produce `Fact` objects carrying an `origin` that says
which path found them. The grounding check downstream treats them differently:
a text fact can be verified against the page bytes, a vision fact cannot.
"""

from galactus.ml6.src.galactus.ingest.facts import ingest_pdf, ingest_pdf_bytes
from galactus.ml6.src.galactus.ingest.text import extract_text_facts
from galactus.ml6.src.galactus.ingest.vision import (
    encode_image_base64,
    image_to_message,
    page_images,
    render_page_png,
)

__all__ = [
    "encode_image_base64",
    "extract_text_facts",
    "image_to_message",
    "ingest_pdf",
    "ingest_pdf_bytes",
    "page_images",
    "render_page_png",
]
