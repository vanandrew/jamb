# Installation

## Requirements

- Python 3.10 or later
- Git (for version-controlled requirements)

## Install from PyPI

```bash
pip install jamb
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv add jamb
```

This installs jamb along with its dependencies (pytest, click, pyyaml, jinja2, openpyxl, python-docx, tomlkit).

## Verify Installation

```bash
jamb --version
```

## Development Installation

To install from source for development:

```bash
git clone https://github.com/vanandrew/jamb.git
cd jamb
uv sync --group dev
```

To also install the documentation dependencies:

```bash
uv sync --group docs
```
