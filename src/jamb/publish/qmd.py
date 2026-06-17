"""Generate Quarto markdown (``.qmd``) source from a publish document.

Everything here is pure: a :class:`~jamb.publish.document.PublishDocument` in,
a ``.qmd`` source string out. No Quarto binary is involved, so this layer is
fully deterministic and unit-testable.
"""

from __future__ import annotations

import re
from functools import lru_cache
from importlib.resources import files

import yaml
from jinja2 import Environment

from jamb.publish.document import PublishDocument
from jamb.publish.formats import OutputFormat

#: Characters given a backslash escape wherever they appear, because each has
#: inline meaning in Pandoc/Quarto markdown.
_ESCAPE_CHARS = frozenset("\\`*_[]{}<>|$~#")

#: Line-leading bullet markers that would start an unordered list.
_BULLET_START = re.compile(r"^(\s*)([-+])(\s)", re.MULTILINE)

#: Line-leading numbered markers that would start an ordered list.
_NUMBER_START = re.compile(r"^(\s*)(\d+)([.)])(\s)", re.MULTILINE)


def _md_escape(text: str) -> str:
    """Escape text so it renders literally in Quarto markdown.

    Args:
        text: Arbitrary requirement text or heading text.

    Returns:
        The text with markdown-significant characters neutralized.
    """
    if not text:
        return text
    escaped = "".join(f"\\{ch}" if ch in _ESCAPE_CHARS else ch for ch in text)
    escaped = _BULLET_START.sub(r"\1\\\2\3", escaped)
    escaped = _NUMBER_START.sub(r"\1\2\\\3\4", escaped)
    return escaped


def _heading_marker(level: int | None) -> str:
    """Return the ``#`` marker for a heading item, clamped to depths 1-6.

    Args:
        level: The requested heading depth, or ``None`` for the default.

    Returns:
        A run of ``#`` characters between one and six long.
    """
    return "#" * max(1, min(6, level or 2))


@lru_cache(maxsize=1)
def _template():
    """Compile and cache the document body template."""
    source = (files("jamb.publish") / "assets" / "document.qmd.j2").read_text(encoding="utf-8")
    env = Environment(
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        # Reassign the comment delimiters so markdown anchors like ``{#UID}``
        # are emitted literally rather than parsed as Jinja comments.
        comment_start_string="{!--",
        comment_end_string="--!}",
    )
    env.filters["mdescape"] = _md_escape
    env.filters["hmarker"] = _heading_marker
    return env.from_string(source)


def _render_body(doc: PublishDocument) -> str:
    """Render the markdown body (sections and items) without front matter."""
    body = _template().render(
        sections=doc.sections,
        include_links=doc.include_links,
        known_uids=doc.known_uids,
    )
    # Collapse the runs of blank lines the template can emit between blocks.
    return re.sub(r"\n{3,}", "\n\n", body).strip() + "\n"


def _front_matter(
    doc: PublishDocument,
    fmt: OutputFormat,
    *,
    theme: str | None,
    reference_doc: str | None,
    typst_header: str | None,
) -> str:
    """Build the YAML front matter block for a renderable format."""
    targets = [OutputFormat.HTML, OutputFormat.DOCX, OutputFormat.PDF] if fmt is OutputFormat.QMD else [fmt]

    blocks: dict[str, object] = {}
    for target in targets:
        if target is OutputFormat.HTML:
            # Render the table of contents inline so HTML reads like a document
            # (a Contents section) rather than a web-app sidebar.
            html: dict[str, object] = {"embed-resources": True, "toc-location": "body"}
            if theme:
                html["theme"] = theme
            blocks["html"] = html
        elif target is OutputFormat.DOCX:
            docx: dict[str, object] = {}
            if reference_doc:
                docx["reference-doc"] = reference_doc
            blocks["docx"] = docx or "default"
        elif target is OutputFormat.PDF:
            typst: dict[str, object] = {
                "papersize": "us-letter",
                "fontsize": "11pt",
                "margin": {"x": "2cm", "y": "2.5cm"},
            }
            if typst_header:
                typst["include-in-header"] = typst_header
            blocks["typst"] = typst

    front_matter: dict[str, object] = {"title": doc.title}
    if doc.subtitle:
        front_matter["subtitle"] = doc.subtitle
    front_matter.update(
        {
            "toc": True,
            "toc-title": "Contents",
            "toc-depth": 4,
            "number-sections": True,
            "format": blocks,
        }
    )
    return yaml.safe_dump(front_matter, sort_keys=False, allow_unicode=True, default_flow_style=False)


def render_qmd(
    doc: PublishDocument,
    fmt: OutputFormat,
    *,
    theme: str | None = None,
    reference_doc: str | None = None,
    typst_header: str | None = None,
) -> str:
    """Render a publish document to ``.qmd`` source.

    Args:
        doc: The document to render.
        fmt: The target format. ``MD`` returns a plain markdown body with no
            front matter; every other format prepends YAML front matter
            carrying the appropriate Quarto ``format`` block.
        theme: HTML theme filename to reference in the front matter.
        reference_doc: DOCX reference-doc filename to reference.
        typst_header: Typst preamble filename to include for PDF output.

    Returns:
        The ``.qmd`` (or plain markdown) source.
    """
    body = _render_body(doc)
    if fmt is OutputFormat.MD:
        return body
    front_matter = _front_matter(
        doc,
        fmt,
        theme=theme,
        reference_doc=reference_doc,
        typst_header=typst_header,
    )
    return f"---\n{front_matter}---\n\n{body}"
