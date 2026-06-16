"""Render a publish document to a file, driving Quarto where needed."""

from __future__ import annotations

import os
import shutil
import tempfile
from importlib.resources import files
from pathlib import Path

from jamb.publish.document import PublishDocument
from jamb.publish.docx_reference import build_reference_docx
from jamb.publish.formats import QUARTO_TARGET, RENDERED_EXTENSION, OutputFormat
from jamb.publish.qmd import render_qmd
from jamb.publish.quarto import QuartoRenderError, run_quarto

#: Filenames used for styling inputs inside the temporary render directory.
_THEME_NAME = "theme.scss"
_REFERENCE_NAME = "reference.docx"
_TYPST_THEME_NAME = "typst-theme.typ"


def default_theme() -> str:
    """Return the bundled default HTML theme (SCSS) source."""
    return (files("jamb.publish") / "assets" / _THEME_NAME).read_text(encoding="utf-8")


def default_typst_theme() -> str:
    """Return the bundled default Typst preamble for PDF output."""
    return (files("jamb.publish") / "assets" / _TYPST_THEME_NAME).read_text(encoding="utf-8")


def render_document(
    doc: PublishDocument,
    fmt: OutputFormat,
    output_path: str | Path,
    *,
    template: str | Path | None = None,
) -> None:
    """Render a document to ``output_path`` in the requested format.

    Markdown and ``.qmd`` output are written directly. HTML, DOCX, and PDF are
    produced by invoking Quarto against a generated ``.qmd`` in an isolated
    temporary directory.

    Args:
        doc: The document to render.
        fmt: The target output format.
        output_path: Destination file path.
        template: Optional styling override appropriate to the format — an
            SCSS file for HTML, a reference ``.docx`` for DOCX, or a Typst
            preamble for PDF. When omitted, the bundled defaults are applied so
            all three formats share the same look.

    Raises:
        QuartoNotFoundError: When a rendered format is requested but Quarto
            is unavailable.
        QuartoRenderError: When Quarto fails to produce the output.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if fmt in (OutputFormat.MD, OutputFormat.QMD):
        output_path.write_text(render_qmd(doc, fmt), encoding="utf-8")
        return

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        theme = reference_doc = typst_header = None

        if fmt is OutputFormat.HTML:
            scss = Path(template).read_text(encoding="utf-8") if template else default_theme()
            (tmpdir / _THEME_NAME).write_text(scss, encoding="utf-8")
            theme = _THEME_NAME
        elif fmt is OutputFormat.PDF:
            typst = Path(template).read_text(encoding="utf-8") if template else default_typst_theme()
            (tmpdir / _TYPST_THEME_NAME).write_text(typst, encoding="utf-8")
            typst_header = _TYPST_THEME_NAME
        elif fmt is OutputFormat.DOCX:
            if template:
                shutil.copyfile(template, tmpdir / _REFERENCE_NAME)
                reference_doc = _REFERENCE_NAME
            else:
                reference_bytes = build_reference_docx()
                if reference_bytes is not None:
                    (tmpdir / _REFERENCE_NAME).write_bytes(reference_bytes)
                    reference_doc = _REFERENCE_NAME

        source = render_qmd(
            doc,
            fmt,
            theme=theme,
            reference_doc=reference_doc,
            typst_header=typst_header,
        )
        qmd_path = tmpdir / "document.qmd"
        qmd_path.write_text(source, encoding="utf-8")

        result = run_quarto(["render", qmd_path.name, "--to", QUARTO_TARGET[fmt]], cwd=tmpdir)
        produced = tmpdir / f"document{RENDERED_EXTENSION[fmt]}"

        if result.returncode != 0 or not produced.exists():
            if os.environ.get("JAMB_DEBUG"):
                debug_copy = output_path.with_suffix(".debug.qmd")
                shutil.copyfile(qmd_path, debug_copy)
            raise QuartoRenderError(
                f"Quarto failed to render {fmt.value} output.",
                returncode=result.returncode,
                stderr=result.stderr or result.stdout,
                qmd_path=str(qmd_path),
            )

        shutil.move(str(produced), str(output_path))
