"""Sphinx configuration for jamb documentation."""

import importlib.metadata

project = "jamb"
copyright = "2024, Andrew Van"
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

# -- Napoleon settings ---------------------------------------------------------

napoleon_google_docstrings = True
napoleon_numpy_docstrings = False

# -- Intersphinx settings ------------------------------------------------------

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "pytest": ("https://docs.pytest.org/en/stable", None),
}

# -- General settings ----------------------------------------------------------

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
suppress_warnings = ["myst.xref_missing"]

# -- HTML output ---------------------------------------------------------------

html_title = "jamb"
html_theme = "pydata_sphinx_theme"
html_theme_options = {
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
