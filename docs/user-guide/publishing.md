# Publishing Documents

jamb can publish your requirements documents in multiple formats for sharing with stakeholders, regulatory submissions, or archival purposes.

## Overview

The `jamb publish` command renders requirement documents as standalone files with:

- Complete item content (UID, header, text)
- Traceability links (parent and child references)
- Document hierarchy organization
- Format-specific styling and navigation

## Output Formats

### HTML

Standalone HTML document with embedded CSS. Best for:

- Regulatory submissions requiring human-readable documents
- Sharing with stakeholders who need to view in a browser
- Printing (includes print-optimized CSS)

Features:
- Inline CSS (no external dependencies)
- Internal hyperlinks between items
- Color-coded item types (requirement, heading, info)
- Responsive layout for different screen sizes
- Print styles for clean hardcopy output

```bash
jamb publish SRS docs/srs.html --html
# Or auto-detect from extension:
jamb publish SRS docs/srs.html
```

### Markdown

Plain text Markdown suitable for version control and documentation systems. Best for:

- GitHub/GitLab rendering
- Integration with documentation generators (MkDocs, Sphinx)
- Diff-friendly format for code review

Features:
- Standard CommonMark syntax
- Heading hierarchy matches document structure
- Link references as plain text UIDs

```bash
jamb publish SRS docs/srs.md --markdown
# Or auto-detect from extension:
jamb publish SRS docs/srs.md
```

### DOCX (Word)

Microsoft Word document with styled content. Best for:

- Stakeholder review with tracked changes
- Formal document control systems
- Organizations requiring Word format deliverables

Features:
- Configurable styles via templates
- Internal hyperlinks between items
- Page numbers in footer
- Print-ready formatting

```bash
jamb publish SRS docs/srs.docx --docx
# Or auto-detect from extension:
jamb publish SRS docs/srs.docx
```

## Basic Usage

```bash
# Publish single document (format auto-detected from extension)
jamb publish SRS output.html

# Publish all documents to a single file
jamb publish all docs/requirements.html

# Print to stdout (Markdown format, useful for piping)
jamb publish SRS

# Specify format explicitly
jamb publish SRS output.html --html
jamb publish SRS output.md --markdown
jamb publish SRS output.docx --docx
```

## Options

`-H, --html`
: Output HTML format (standalone document with inline CSS)

`-m, --markdown`
: Output Markdown format

`-d, --docx`
: Output DOCX (Word) format

`-L, --no-links`
: Omit link sections from output (parent and child references)

`-t, --template PATH`
: Use a custom DOCX template for styling (only with `--docx`)

## Using Custom Templates

For DOCX output, you can customize fonts, colors, and spacing using a template document.

### Generate a Starter Template

```bash
jamb template my-company-template.docx
```

This creates a template with all styles used by jamb:

- **Heading 1**: Document sections and heading-type items
- **Heading 2**: Requirement item headings
- **Normal**: Body text for requirements

### Customize the Template

1. Open the template in Microsoft Word
2. Modify styles via the Styles pane (don't just format text directly)
3. Save your customized template

### Use the Template

```bash
jamb publish SRS output.docx --template my-company-template.docx
```

## Publishing Multiple Documents

Use `all` to publish all documents in a single file:

```bash
jamb publish all docs/all-requirements.html
```

Items are organized by document in hierarchy order, with section headers separating each document.

## Excluding Links

For cleaner output without traceability information:

```bash
jamb publish SRS output.html --no-links
```

This omits both parent links ("Links:") and child links ("Linked from:") sections.

## Format Comparison

| Feature | HTML | Markdown | DOCX |
|---------|------|----------|------|
| Standalone file | Yes | Yes | Yes |
| Internal hyperlinks | Yes | No | Yes |
| Custom styling | CSS variables | N/A | Templates |
| Print support | Yes (CSS) | Via conversion | Yes |
| Diff-friendly | No | Yes | No |
| File size | Small | Smallest | Larger |

## When to Use Each Format

**HTML** is the default choice for most use cases. It produces self-contained documents that anyone can open in a browser, with good visual styling and navigation.

**Markdown** is ideal when you need:
- Version-controlled documentation
- Integration with documentation pipelines
- Plain text that can be reviewed in pull requests

**DOCX** is best when you need:
- Documents for formal review with tracked changes
- Output matching organizational templates
- Integration with document control systems that require Word format

## Related Commands

- [`jamb template`](commands.md#jamb-template) - Generate a DOCX template
- [`jamb matrix`](commands.md#jamb-matrix) - Generate traceability matrices
- [`jamb export`](commands.md#jamb-export) - Export to machine-readable YAML
