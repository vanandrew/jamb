"""Output formats supported by the publishing system."""

from __future__ import annotations

from enum import Enum
from pathlib import Path


class OutputFormat(Enum):
    """A document output format produced by ``jamb publish``."""

    HTML = "html"
    DOCX = "docx"
    PDF = "pdf"
    MD = "md"
    QMD = "qmd"


#: File extensions mapped to the format they select during auto-detection.
_EXTENSIONS: dict[str, OutputFormat] = {
    ".html": OutputFormat.HTML,
    ".htm": OutputFormat.HTML,
    ".docx": OutputFormat.DOCX,
    ".pdf": OutputFormat.PDF,
    ".md": OutputFormat.MD,
    ".markdown": OutputFormat.MD,
    ".qmd": OutputFormat.QMD,
}

#: Formats that are produced by invoking Quarto, mapped to the Quarto
#: ``--to`` target. Formats absent from this mapping are written directly.
QUARTO_TARGET: dict[OutputFormat, str] = {
    OutputFormat.HTML: "html",
    OutputFormat.DOCX: "docx",
    OutputFormat.PDF: "typst",
}

#: The file extension Quarto produces for each rendered format.
RENDERED_EXTENSION: dict[OutputFormat, str] = {
    OutputFormat.HTML: ".html",
    OutputFormat.DOCX: ".docx",
    OutputFormat.PDF: ".pdf",
}


def format_from_path(path: str | Path) -> OutputFormat | None:
    """Return the output format implied by a file extension.

    Args:
        path: The output path whose suffix selects the format.

    Returns:
        The matching :class:`OutputFormat`, or ``None`` when the
        extension is not recognized.
    """
    return _EXTENSIONS.get(Path(path).suffix.lower())
