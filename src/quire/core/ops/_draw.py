"""Low-level content-stream drawing helpers shared by the annotate operations.

pypdf has no text/image drawing API of its own, so these build the PDF
operators by hand: a Helvetica text run for watermarks and page numbers, and a
manually-built Image XObject (via Pillow for decoding) for image stamps. Both
append to whatever content stream a page already has rather than replacing it.
"""

from __future__ import annotations

import math
import zlib

from PIL import Image
from pypdf import PdfWriter
from pypdf._page import PageObject
from pypdf.generic import (
    DecodedStreamObject,
    DictionaryObject,
    FloatObject,
    NameObject,
    NumberObject,
)


def _resources(page: PageObject) -> DictionaryObject:
    resources = page.get("/Resources")
    if resources is None:
        resources = DictionaryObject()
        page[NameObject("/Resources")] = resources
    return resources


def _subdict(resources: DictionaryObject, key: str) -> DictionaryObject:
    sub = resources.get(key)
    if sub is None:
        sub = DictionaryObject()
        resources[NameObject(key)] = sub
    return sub


def _append_content(writer: PdfWriter, page: PageObject, ops: bytes) -> None:
    existing = page.get_contents()
    # ContentStream is dict-like and falsy when it carries no /Filter-style keys
    # of its own, even with real operations in .get_data() -- must check for
    # None explicitly, not truthiness, or a second draw on the same page
    # silently discards everything drawn before it.
    data = (existing.get_data() + b"\n" + ops) if existing is not None else ops
    stream = DecodedStreamObject()
    stream.set_data(data)
    page[NameObject("/Contents")] = writer._add_object(stream)


def draw_text(
    writer: PdfWriter,
    page: PageObject,
    text: str,
    x: float,
    y: float,
    *,
    size: float = 12,
    opacity: float = 1.0,
    rgb: tuple[float, float, float] = (0.0, 0.0, 0.0),
    angle: float = 0.0,
    center: tuple[float, float] | None = None,
) -> None:
    """Draw one line of Helvetica text onto `page`, already added to `writer`."""
    resources = _resources(page)
    fonts = _subdict(resources, "/Font")
    font_name = f"QrF{len(fonts)}"
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    fonts[NameObject(f"/{font_name}")] = writer._add_object(font)

    gstates = _subdict(resources, "/ExtGState")
    gs_name = f"QrGS{len(gstates)}"
    gs = DictionaryObject(
        {NameObject("/Type"): NameObject("/ExtGState"), NameObject("/ca"): FloatObject(opacity)}
    )
    gstates[NameObject(f"/{gs_name}")] = writer._add_object(gs)

    cm = ""
    if center is not None:
        cx, cy = center
        # ponytail: Helvetica average-glyph-width estimate, no real font metrics table
        text_width = size * 0.5 * len(text)
        rad = math.radians(angle)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        cm = f"{cos_a} {sin_a} {-sin_a} {cos_a} {cx} {cy} cm "
        x, y = -text_width / 2, 0

    r, g, b = rgb
    escaped = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    ops = (
        f"q /{gs_name} gs {cm}BT /{font_name} {size} Tf "
        f"{r} {g} {b} rg {x} {y} Td ({escaped}) Tj ET Q"
    ).encode("latin-1")
    _append_content(writer, page, ops)


def draw_image(
    writer: PdfWriter,
    page: PageObject,
    image: Image.Image,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    opacity: float = 1.0,
) -> None:
    """Draw `image` (any Pillow-openable format) onto `page`, scaled to w x h points."""
    rgb = image.convert("RGB")
    data = zlib.compress(rgb.tobytes())
    xobj = DecodedStreamObject()
    xobj.set_data(data)
    xobj[NameObject("/Type")] = NameObject("/XObject")
    xobj[NameObject("/Subtype")] = NameObject("/Image")
    xobj[NameObject("/Width")] = NumberObject(rgb.width)
    xobj[NameObject("/Height")] = NumberObject(rgb.height)
    xobj[NameObject("/ColorSpace")] = NameObject("/DeviceRGB")
    xobj[NameObject("/BitsPerComponent")] = NumberObject(8)
    xobj[NameObject("/Filter")] = NameObject("/FlateDecode")

    resources = _resources(page)
    xobjects = _subdict(resources, "/XObject")
    img_name = f"QrImg{len(xobjects)}"
    xobjects[NameObject(f"/{img_name}")] = writer._add_object(xobj)

    gstates = _subdict(resources, "/ExtGState")
    gs_name = f"QrGS{len(gstates)}"
    gs = DictionaryObject(
        {NameObject("/Type"): NameObject("/ExtGState"), NameObject("/ca"): FloatObject(opacity)}
    )
    gstates[NameObject(f"/{gs_name}")] = writer._add_object(gs)

    ops = f"q /{gs_name} gs {w} 0 0 {h} {x} {y} cm /{img_name} Do Q".encode("latin-1")
    _append_content(writer, page, ops)
