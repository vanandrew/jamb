"""Build a Word reference document whose styles match the default HTML theme.

Word output is styled by a *reference document* (named paragraph/character
styles that Pandoc copies), not by SCSS. To keep DOCX visually consistent with
the HTML theme, this module takes Pandoc's built-in reference document and
restyles it to the same palette and typeface: near-black body text, a single
blue accent for hyperlinks, near-black headings, and a clean sans-serif.

Editing happens in memory on the OOXML parts; nothing is written to disk and no
binary asset is committed, so the styling stays in sync with the values here.
"""

from __future__ import annotations

import io
import re
import subprocess
import zipfile

from jamb.publish.quarto import QuartoNotFoundError, find_quarto

# Shared with the HTML theme (see assets/theme.scss): a formal look with a
# serif body, sans-serif headings, and a conservative blue accent.
_BODY_COLOR = "1D1D1F"
_ACCENT_COLOR = "0A52A3"
_BODY_FONT = "Georgia"  # serif body, widely available on Word platforms
_HEADING_FONT = "Helvetica Neue"  # sans-serif headings

# Defaults baked into Pandoc's reference document that we recolor.
_PANDOC_HEADING_COLOR = "0F4761"
_PANDOC_HYPERLINK_COLOR = "4F81BD"


def _pandoc_reference_bytes() -> bytes | None:
    """Return Pandoc's built-in reference.docx bytes, or None if unavailable."""
    try:
        executable = find_quarto()
    except QuartoNotFoundError:
        return None
    try:
        result = subprocess.run(
            [executable, "pandoc", "--print-default-data-file", "reference.docx"],
            capture_output=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0 or not result.stdout:
        return None
    return result.stdout


def _restyle_theme(theme_xml: str) -> str:
    """Point the major (heading) and minor (body) theme fonts at our typefaces."""
    theme_xml = re.sub(
        r'(<a:majorFont>\s*<a:latin typeface=")[^"]*(")',
        rf"\g<1>{_HEADING_FONT}\g<2>",
        theme_xml,
        count=1,
    )
    theme_xml = re.sub(
        r'(<a:minorFont>\s*<a:latin typeface=")[^"]*(")',
        rf"\g<1>{_BODY_FONT}\g<2>",
        theme_xml,
        count=1,
    )
    return theme_xml


def _restyle_styles(styles_xml: str) -> str:
    """Recolor headings, hyperlinks, and the default text color."""
    styles_xml = styles_xml.replace(f'w:val="{_PANDOC_HEADING_COLOR}"', f'w:val="{_BODY_COLOR}"')
    styles_xml = styles_xml.replace(f'w:val="{_PANDOC_HYPERLINK_COLOR}"', f'w:val="{_ACCENT_COLOR}"')
    # Add a near-black default text color in the document defaults.
    styles_xml = re.sub(
        r"(<w:rPrDefault>\s*<w:rPr>\s*<w:rFonts[^>]*/>)",
        rf'\g<1><w:color w:val="{_BODY_COLOR}"/>',
        styles_xml,
        count=1,
    )
    return styles_xml


def build_reference_docx() -> bytes | None:
    """Return reference.docx bytes matching the HTML theme, or None on failure.

    Returns ``None`` when Pandoc's reference document cannot be obtained, in
    which case the caller falls back to Quarto's default Word styling.
    """
    raw = _pandoc_reference_bytes()
    if raw is None:
        return None

    source = io.BytesIO(raw)
    result = io.BytesIO()
    with (
        zipfile.ZipFile(source) as archive_in,
        zipfile.ZipFile(result, "w", zipfile.ZIP_DEFLATED) as archive_out,
    ):
        for item in archive_in.infolist():
            data = archive_in.read(item.filename)
            if item.filename == "word/theme/theme1.xml":
                data = _restyle_theme(data.decode("utf-8")).encode("utf-8")
            elif item.filename == "word/styles.xml":
                data = _restyle_styles(data.decode("utf-8")).encode("utf-8")
            archive_out.writestr(item, data)
    return result.getvalue()
