"""The vision path: read what the text layer cannot.

Tables drawn as vector strokes, charts, and scanned pages have no useful text
layer — `page.get_text()` returns the cell contents in stroke order, or nothing
at all. Rendering the page to an image and asking a model to read it recovers
the content.

The cost of that is provenance. A vision fact has no character offset into the
source, so its `source_span` is page-level (`p3:vision`) and its confidence is
below 1.0. `facts.py` keeps the distinction rather than flattening it: a text
fact is verifiable, a vision fact is asserted.

Rendering goes through pymupdf's rasterizer rather than Pillow. pymupdf can
render at a chosen DPI directly, so the resize-after-the-fact step the reference
implementation needs does not arise, and Pillow stays out of the dependency
list.
"""

from __future__ import annotations

import base64
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)

MAX_IMAGE_BYTES = 5 * 1024 * 1024
"""Provider ceiling on a single image."""

MAX_IMAGE_DIMENSION = 1568
"""Long-edge target for rendered PDF pages.

Deliberately below the 2576 px high-resolution ceiling. Full resolution costs
roughly 3x the image tokens (~4784 vs ~1600), and input tokens are essentially
the whole cost model for this pipeline. A page rendered at 1568 px is legible
enough for table structure; if a fixture ever proves otherwise, raise it for
that call rather than globally.
"""

RENDER_DPI = 150
"""Rasterization density before the long-edge cap applies.

150 DPI puts a US Letter page at ~1650 px on the long edge, just above the
target, so `render_page_png` scales down slightly rather than up — upscaling a
72 DPI render would add pixels without adding legibility.
"""


def _open(pdf_source: str | Path | bytes):
    """Open a PDF from a path or from an in-memory byte stream.

    The API layer holds uploads as bytes and never writes them to disk, so
    every rendering entry point has to accept both. `pymupdf.open` treats its
    first positional argument as a filename, which turns a bytes payload into
    an unreadable path rather than an error worth reading.
    """
    import pymupdf

    if isinstance(pdf_source, bytes):
        return pymupdf.open(stream=pdf_source, filetype="pdf")
    return pymupdf.open(pdf_source)


def render_page_png(pdf_source: str | Path | bytes, page_number: int) -> bytes:
    """Render one 1-indexed PDF page to PNG bytes, capped at the long edge.

    Raises:
        IndexError: If `page_number` is outside the document.
        ValueError: If the rendered image exceeds the provider's size limit.
    """
    with _open(pdf_source) as doc:
        if not 1 <= page_number <= doc.page_count:
            raise IndexError(
                f"page {page_number} out of range for a {doc.page_count}-page document"
            )
        data = _render(doc, page_number)

    _check_image_size(data, f"rendered page {page_number}")
    return data


def render_pages(pdf_source: str | Path | bytes, page_numbers: list[int]) -> dict[int, bytes]:
    """Render several pages with one document open, skipping pages that fail.

    The single open matters: opening a PDF re-parses its cross-reference table,
    and the vision path renders every text-sparse page of a document in one
    ingest run. A page that is out of range or renders oversized is logged and
    dropped rather than failing the batch — the text path has already produced
    what it can, and losing one page beats losing the document.
    """
    images: dict[int, bytes] = {}

    with _open(pdf_source) as doc:
        for page_number in page_numbers:
            if not 1 <= page_number <= doc.page_count:
                log.warning("vision_page_out_of_range", page=page_number, pages=doc.page_count)
                continue
            data = _render(doc, page_number)
            try:
                _check_image_size(data, f"rendered page {page_number}")
            except ValueError as exc:
                log.warning("vision_page_oversized", page=page_number, error=str(exc))
                continue
            images[page_number] = data

    return images


def _render(doc, page_number: int) -> bytes:
    import pymupdf

    page = doc[page_number - 1]
    zoom = _zoom_for(page.rect.width, page.rect.height)
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
    data: bytes = pixmap.tobytes("png")
    return data


def _check_image_size(data: bytes, label: str) -> None:
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError(
            f"{label} is {len(data) / 1024 / 1024:.1f} MB — "
            f"exceeds the {MAX_IMAGE_BYTES / 1024 / 1024:.0f} MB limit"
        )


def encode_image_base64(data: bytes) -> str:
    """Base64-encode image bytes. No line breaks, no data-URI prefix.

    Raises:
        ValueError: If the image exceeds the provider's size limit.
    """
    _check_image_size(data, "image")
    return base64.standard_b64encode(data).decode("utf-8")


def _zoom_for(width_pt: float, height_pt: float) -> float:
    """Scale factor that renders at RENDER_DPI without exceeding the long edge.

    PDF user space is 72 points per inch, so DPI/72 is the base zoom. If that
    overshoots the pixel ceiling, the cap wins.
    """
    zoom = RENDER_DPI / 72.0
    longest_pt = max(width_pt, height_pt)
    if longest_pt <= 0:
        return zoom

    if longest_pt * zoom > MAX_IMAGE_DIMENSION:
        zoom = MAX_IMAGE_DIMENSION / longest_pt

    return zoom
