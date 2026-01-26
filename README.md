# jamb

IEC 62304 requirements traceability for pytest, built on doorstop.

jamb links your pytest tests to doorstop requirements, generating traceability matrices for regulatory compliance. It's designed for medical device software and other regulated industries where you need to prove every requirement has been tested.

## Installation

```bash
pip install jamb
```

This installs jamb along with its dependencies (doorstop, pytest, click).

## Getting Started

**Tutorial:**

- [Tutorial](tutorial/TUTORIAL.md) - Complete walkthrough from getting started to advanced workflows including review cycles, publishing, batch operations, and CI/CD integration.

## CLI Commands

jamb provides commands for managing doorstop documents and items, plus traceability-specific features.

### Validation & Coverage

```bash
# Validate requirements tree (links, suspect items, review status)
jamb validate
jamb validate -v    # Verbose output

# Display document structure and hierarchy
jamb info

# Check test coverage without running tests
jamb check
jamb check --documents SRS    # Check specific documents
```

### Project Initialization

```bash
# Initialize a new jamb project with standard IEC 62304 documents
jamb init
```

Creates a `reqs/` folder with the IEC 62304 medical device hierarchy (PRJ, UN, SYS, SRS, HAZ, RC) and configures `pyproject.toml`.

### Document Management

```bash
# Create a new document (for custom hierarchies)
jamb doc create PREFIX PATH
jamb doc create SRS ./requirements/srs --parent SYS --digits 3

# Delete a document
jamb doc delete PREFIX

# List all documents
jamb doc list

# Reorder items in a document
jamb doc reorder PREFIX
jamb doc reorder SRS --auto     # Automatic reordering
```

### Item Management

```bash
# List items
jamb item list                  # All items across all documents
jamb item list PREFIX           # Items in a specific document

# Add a new item
jamb item add PREFIX
jamb item add SRS --count 3     # Add multiple items
jamb item add SRS --level 1.2   # Specify level

# Remove an item
jamb item remove UID

# Edit an item (opens in $EDITOR)
jamb item edit UID

# Show item details
jamb item show UID

# Import items from CSV/Excel
jamb item import PREFIX PATH
jamb item import SRS ./requirements.csv --map "text=Description"

# Export items to CSV/Excel
jamb item export PREFIX PATH
jamb item export SRS ./export.xlsx --xlsx
jamb item export SRS ./export.csv --csv
```

### Link Management

```bash
# Link a child item to a parent
jamb link add CHILD PARENT
jamb link add SRS001 SYS001

# Remove a link
jamb link remove CHILD PARENT
```

### Review Management

```bash
# Mark item(s) as reviewed
jamb review mark SRS001         # Mark single item
jamb review mark SRS            # Review all items in document
jamb review mark all            # Review all items in all documents

# Clear suspect link status
jamb review clear SRS001        # Clear suspect links on single item
jamb review clear SRS           # Clear in entire document
jamb review clear SRS001 SYS001 # Clear only link to specific parent

# Reset items to unreviewed status
jamb review reset SRS001
```

### Publishing

```bash
# Publish documents using doorstop
jamb publish PREFIX [PATH]
jamb publish SRS                     # Print SRS to terminal
jamb publish SRS srs.html --html     # Export as HTML
jamb publish SRS srs.md --markdown   # Export as Markdown
jamb publish all ./docs --html       # Export all documents

# For traceability matrix with test coverage, use pytest:
pytest --jamb --jamb-matrix matrix.html
```

### Import/Export (Batch Operations)

```bash
# Export current requirements to YAML
jamb export requirements.yml
jamb export requirements.yml --documents SRS,SYS

# Import documents and items from YAML
jamb import requirements.yml
jamb import requirements.yml --dry-run  # Preview changes
jamb import requirements.yml -v         # Verbose output
```

YAML format for import/export:

```yaml
documents:
  - prefix: UN
    path: un
    digits: 3
  - prefix: SRS
    path: srs
    parent: UN
    digits: 3

items:
  - uid: UN001
    text: User shall be able to log in
  - uid: SRS001
    text: Software shall validate credentials
    links: [UN001]
    header: Authentication
```

## pytest Integration

### Marking Tests

Link tests to doorstop items using `@pytest.mark.requirement`:

```python
import pytest

@pytest.mark.requirement("SRS001")
def test_valid_credentials():
    assert authenticate("admin", "secret") is True

# Multiple requirements
@pytest.mark.requirement("SRS001", "SRS002")
def test_shared_functionality():
    ...
```

### pytest Options

```bash
# Enable traceability checking
pytest --jamb

# Generate traceability matrix
pytest --jamb --jamb-matrix matrix.html

# Set matrix format
pytest --jamb --jamb-matrix matrix.md --jamb-matrix-format markdown

# Fail if requirements lack coverage
pytest --jamb --jamb-fail-uncovered

# Check specific documents
pytest --jamb --jamb-documents SRS
```

## Configuration

Configure jamb in `pyproject.toml`:

```toml
[tool.jamb]
# Which doorstop documents represent test specifications
test_documents = ["SRS"]

# Fail pytest if any test spec items lack coverage
fail_uncovered = false

# Output path for traceability matrix
matrix_output = "matrix.html"

# Matrix format: "html", "markdown", or "json"
matrix_format = "html"
```

## CI Setup (GitHub Actions)

```yaml
name: Requirements Traceability

on: [push, pull_request]

jobs:
  traceability:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: pip install jamb

      - name: Validate doorstop configuration
        run: jamb validate

      - name: Run tests with traceability
        run: pytest --jamb --jamb-fail-uncovered --jamb-matrix matrix.html

      - name: Upload traceability matrix
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: traceability-matrix
          path: matrix.html
```

## Understanding the Matrix Output

The HTML matrix shows:

| Column | Description |
|--------|-------------|
| UID | The doorstop item identifier (e.g., SRS001) |
| Description | The requirement text |
| Document | Which document the item belongs to |
| Traces To | Parent requirements this item links to |
| Tests | pytest tests linked via `@pytest.mark.requirement` |
| Status | PASSED (green), FAILED (red), or UNCOVERED (yellow) |

## License

MIT
