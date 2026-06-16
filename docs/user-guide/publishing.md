# Publishing Documents

jamb can publish your requirements documents in multiple formats for sharing with stakeholders, regulatory submissions, or archival purposes.

## Overview

The `jamb publish` command renders requirement documents through [Quarto](https://quarto.org), producing polished HTML, Word, PDF, and Markdown output from a single source. Every format includes:

- Complete item content (UID, header, text)
- Traceability links (parent and child references) as working cross-references
- Document hierarchy organization with section headings
- A table of contents
- Consistent, professional styling across formats

Quarto ships with jamb, so HTML, DOCX, and PDF work out of the box with no extra tools to install.

### How item types render

Each item type gets its own treatment, consistently across formats:

- **`requirement`** — a level-2 heading (the item UID/header) followed by its text.
- **`heading`** — a section heading whose depth follows the item's `level` field, mapping to `<h1>`–`<h6>` (values are clamped to that range; the default is level 2). Heading items appear in the table of contents and structure the document.
- **`info`** — an anchored heading followed by a [callout](https://quarto.org/docs/authoring/callouts.html) (note) block, giving informational items a distinct, boxed style separate from normative requirements.

## Output Formats

### HTML

A standalone, single-file HTML document (all styles and assets embedded). Best for:

- Regulatory submissions requiring human-readable documents
- Sharing with stakeholders who view in a browser
- A navigable document with a table of contents

```bash
jamb publish SRS docs/srs.html --html
# Or auto-detect from extension:
jamb publish SRS docs/srs.html
```

### PDF

A print-ready PDF rendered with Quarto's built-in [Typst](https://typst.app) engine (no LaTeX required). Best for:

- Fixed-layout deliverables and archival
- Formal submissions where a paginated document is expected

```bash
jamb publish SRS docs/srs.pdf --pdf
# Or auto-detect from extension:
jamb publish SRS docs/srs.pdf
```

### DOCX (Word)

A Microsoft Word document styled from a reference document. Best for:

- Stakeholder review with tracked changes
- Formal document control systems
- Organizations requiring Word deliverables

```bash
jamb publish SRS docs/srs.docx --docx
# Or auto-detect from extension:
jamb publish SRS docs/srs.docx
```

### Markdown and Quarto source

Plain Markdown for version control and documentation systems, or the raw Quarto `.qmd` source if you want to render it yourself. Best for:

- GitHub/GitLab rendering and diff-friendly review
- Feeding into your own Quarto pipeline or documentation generator

```bash
jamb publish SRS docs/srs.md --markdown
# Print Markdown to stdout (useful for piping):
jamb publish SRS
# Emit the Quarto source to render or inspect yourself:
jamb publish SRS docs/srs.qmd
```

Markdown and `.qmd` output are written directly and do not invoke Quarto.

## Basic Usage

```bash
# Publish a single document (format auto-detected from extension)
jamb publish SRS output.html

# Publish all documents to a single file
jamb publish all docs/requirements.pdf

# Print to stdout (Markdown format, useful for piping)
jamb publish SRS

# Specify format explicitly
jamb publish SRS output.html --html
jamb publish SRS output.pdf  --pdf
jamb publish SRS output.docx --docx
jamb publish SRS output.md   --markdown
```

## Options

`-H, --html`
: Output HTML format (standalone, embedded resources)

`-p, --pdf`
: Output PDF format (rendered with Typst)

`-d, --docx`
: Output DOCX (Word) format

`-m, --markdown`
: Output Markdown format

`-L, --no-links`
: Omit link sections from output (parent and child references)

`-t, --template PATH`
: Apply a styling override appropriate to the target format — an SCSS file for HTML, a reference `.docx` for DOCX, or a Typst template for PDF

## Using Custom Styling

Each format has its own styling input — they are independent mechanisms, so an
HTML SCSS theme does **not** affect Word, and vice versa:

| Format | Styling input | Override flag |
|--------|---------------|---------------|
| HTML   | An SCSS theme file | `--template theme.scss` |
| DOCX   | A Word reference document | `--template reference.docx` |
| PDF    | A Typst template | `--template template.typ` |

### Scaffold the styling assets

```bash
jamb template
```

By default this writes `./jamb-assets/theme.scss` — the HTML theme (colors,
fonts, headings). Because SCSS only styles HTML, the Word reference document is
opt-in:

```bash
jamb template --docx
```

That adds `./jamb-assets/reference.docx` (Word paragraph/heading styles, page
numbers). Pass a directory to choose a different location: `jamb template ./my-styles`.

### Apply your styling

Edit `theme.scss` (SCSS variables and rules), or open `reference.docx` in Word
and modify its named styles. Then apply it either **per command**:

```bash
jamb publish SRS output.html --template jamb-assets/theme.scss
jamb publish SRS output.docx --template jamb-assets/reference.docx
```

…or **once for every publish** via `pyproject.toml` (no `--template` needed):

```toml
[tool.jamb]
publish_html_theme = "jamb-assets/theme.scss"
publish_docx_reference = "jamb-assets/reference.docx"
publish_pdf_template = "jamb-assets/template.typ"
```

A `--template` passed on the command line always overrides the configured value.

## Publishing Multiple Documents

Use `all` to publish every document in a single file:

```bash
jamb publish all docs/all-requirements.pdf
```

Items are organized by document in hierarchy order, with a section heading per document.

## Excluding Links

For cleaner output without traceability information:

```bash
jamb publish SRS output.html --no-links
```

This omits both parent links ("Links:") and child links ("Linked from:") sections.

## When to Use Each Format

**PDF** is ideal for fixed-layout, paginated deliverables and archival.

**HTML** produces a self-contained, navigable document anyone can open in a browser.

**DOCX** is best for formal review with tracked changes and document control systems that require Word.

**Markdown / `.qmd`** suit version-controlled documentation and custom rendering pipelines.

## Related Commands

- [`jamb template`](commands.md#jamb-template) - Scaffold styling assets for publishing
- [`jamb matrix`](commands.md#jamb-matrix) - Generate traceability matrices
- [`jamb export`](commands.md#jamb-export) - Export to machine-readable YAML
