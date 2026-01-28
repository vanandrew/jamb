"""Sphinx configuration for jamb documentation."""

import importlib.metadata
import logging


class _ClickForwardRefFilter(logging.Filter):
    """Suppress sphinx-autodoc-typehints warnings for Click forward refs.

    Click uses ``from __future__ import annotations`` which turns all its
    annotations into strings.  When sphinx-autodoc-typehints calls
    ``get_type_hints()`` on decorated Click commands, the names ``Context``
    and ``Command`` cannot be resolved outside ``click.core``.  These
    warnings are harmless and cannot be fixed without patching Click.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not (
            "Cannot resolve forward reference" in msg and "jamb.cli.commands" in msg
        )


# sphinx.util.logging.getLogger() prefixes the name with "sphinx.", so the
# underlying Python logger is "sphinx.sphinx_autodoc_typehints".
logging.getLogger("sphinx.sphinx_autodoc_typehints").addFilter(_ClickForwardRefFilter())

project = "jamb"
copyright = "2026, Andrew Van"
author = "Andrew Van"
release = importlib.metadata.version("jamb")
version = release

# -- Extensions ---------------------------------------------------------------

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinx_copybutton",
    "sphinxcontrib.mermaid",
    "sphinx_autodoc_typehints",
]

# -- MyST settings ------------------------------------------------------------

myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "fieldlist",
    "tasklist",
]
myst_heading_anchors = 3

# -- Autodoc settings ----------------------------------------------------------

autodoc_member_order = "bysource"
autodoc_typehints = "description"
autodoc_class_signature = "separated"

# -- sphinx-autodoc-typehints settings ----------------------------------------

always_use_bars_union = True
typehints_use_rtype = False

# -- Napoleon settings ---------------------------------------------------------

napoleon_google_docstrings = True
napoleon_numpy_docstrings = False

# -- Intersphinx settings ------------------------------------------------------

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "pytest": ("https://docs.pytest.org/en/stable", None),
    "click": ("https://click.palletsprojects.com/en/stable/", None),
}

# -- General settings ----------------------------------------------------------

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
suppress_warnings = ["myst.xref_missing"]


def _fixup_click_docstrings(_app, _what, _name, _obj, _options, lines):
    """Fix Click docstrings for Sphinx.

    1. Strip the ``\\x08`` byte that Click's ``\\b`` paragraph marker leaves
       in ``__doc__``.  Without this, the RST parser cannot recognise
       directives that follow.

    2. Convert Napoleon's ``.. rubric:: Examples`` (produced from a Google-
       style ``Examples:`` section) into a proper ``.. code-block:: text``
       so that the example lines render as a preformatted block rather than
       collapsing into a single paragraph.
    """
    # Pass 1 — strip \x08
    for i, line in enumerate(lines):
        if "\x08" in line:
            lines[i] = line.replace("\x08", "")

    # Pass 2 — convert ".. rubric:: Examples" + body into a code block
    i = 0
    while i < len(lines):
        if lines[i].strip() == ".. rubric:: Examples":
            lines[i] = ".. code-block:: text"
            lines.insert(i + 1, "")
            i += 2  # skip the directive + blank line
            # Indent all non-blank body lines that follow
            while i < len(lines) and (
                lines[i].strip() or (i + 1 < len(lines) and lines[i + 1].strip())
            ):
                if lines[i].strip():
                    lines[i] = "   " + lines[i]
                i += 1
        else:
            i += 1


def setup(app):
    app.connect("autodoc-process-docstring", _fixup_click_docstrings)


# -- HTML output ---------------------------------------------------------------

html_title = "jamb"
html_favicon = "_static/icon-light.svg"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_theme = "pydata_sphinx_theme"
html_theme_options = {
    "logo": {
        "image_light": "_static/icon-light.svg",
        "image_dark": "_static/icon-dark.svg",
    },
    "navbar_align": "left",
    "show_nav_level": 2,
    "icon_links": [
        {
            "name": "GitHub",
            "url": "https://github.com/vanandrew/jamb",
            "icon": "fa-brands fa-github",
        },
        {
            "name": "PyPI",
            "url": "https://pypi.org/project/jamb/",
            "icon": "fa-brands fa-python",
        },
    ],
}
