# Command Reference

Complete reference for all `jamb` CLI commands.

## Quick Reference

| Group | Commands | Description |
|-------|----------|-------------|
| Top-level | `init`, `info`, `check`, `validate`, `publish`, `publish-template`, `export`, `import`, `reorder`, `matrix` | Project setup, validation, publishing, and data exchange |
| Document | `doc create`, `doc delete`, `doc list` | Create, remove, and list requirement documents |
| Item | `item add`, `item remove`, `item edit`, `item show`, `item list` | Add, remove, edit, inspect, and list requirement items |
| Link | `link add`, `link remove` | Create and remove traceability links between items |
| Review | `review mark`, `review clear`, `review reset` | Mark items as reviewed, clear suspect links, and reset review status |

## Table of Contents

- [Top-Level Commands](#top-level-commands)
  - [jamb](#jamb)
  - [jamb init](#jamb-init)
  - [jamb info](#jamb-info)
  - [jamb check](#jamb-check)
  - [jamb validate](#jamb-validate)
  - [jamb publish](#jamb-publish)
  - [jamb publish-template](#jamb-publish-template)
  - [jamb export](#jamb-export)
  - [jamb import](#jamb-import)
  - [jamb reorder](#jamb-reorder)
  - [jamb matrix](#jamb-matrix)
- [Document Commands](#document-commands)
  - [jamb doc](#jamb-doc)
  - [jamb doc create](#jamb-doc-create)
  - [jamb doc delete](#jamb-doc-delete)
  - [jamb doc list](#jamb-doc-list)
- [Item Commands](#item-commands)
  - [jamb item](#jamb-item)
  - [jamb item add](#jamb-item-add)
  - [jamb item remove](#jamb-item-remove)
  - [jamb item edit](#jamb-item-edit)
  - [jamb item show](#jamb-item-show)
  - [jamb item list](#jamb-item-list)
- [Link Commands](#link-commands)
  - [jamb link](#jamb-link)
  - [jamb link add](#jamb-link-add)
  - [jamb link remove](#jamb-link-remove)
- [Review Commands](#review-commands)
  - [jamb review](#jamb-review)
  - [jamb review mark](#jamb-review-mark)
  - [jamb review clear](#jamb-review-clear)
  - [jamb review reset](#jamb-review-reset)

---

## Top-Level Commands

### jamb

```
Usage: jamb [OPTIONS] COMMAND [ARGS]...

  jamb - IEC 62304 requirements traceability for pytest.

Options:
  --version  Show the version and exit.
  --help     Show this message and exit.

Commands:
  check             Check test coverage without running tests.
  doc               Manage documents.
  export            Export documents and items to a YAML file.
  import            Import documents and items from a YAML file.
  info              Display document information.
  init              Initialize a new jamb project with default IEC 62304 documents.
  item              Manage items.
  link              Manage item links.
  matrix            Generate traceability or test records matrix.
  publish           Publish a document.
  publish-template  Generate a DOCX template file with jamb styles.
  reorder           Renumber item UIDs sequentially to fill gaps.
  review            Manage item reviews.
  validate          Validate the requirements tree.
```

**Example:**
```bash
# Show version
jamb --version

# Show help
jamb --help
```

---

### jamb init

```
Usage: jamb init [OPTIONS]

  Initialize a new jamb project with default IEC 62304 documents.

  Creates a 'reqs' folder with PRJ, UN, SYS, SRS, HAZ, and RC documents
  in the standard medical device traceability hierarchy:

    PRJ (Project Requirements) - root
    ├── UN (User Needs)
    │   └── SYS (System Requirements)
    │       └── SRS (Software Requirements Specification)
    └── HAZ (Hazards)
        └── RC (Risk Controls)

  Also creates an initial PRJ001 heading item using the project name
  from pyproject.toml (or the current directory name if pyproject.toml is not found).

  If pyproject.toml exists, adds [tool.jamb] configuration.

Options:
  --help  Show this message and exit.
```

**Example:**
```bash
# Initialize a new jamb project in the current directory
jamb init

# Typical workflow: create project, init git, then init jamb
mkdir my-project && cd my-project
git init
jamb init
```

---

### jamb info

```
Usage: jamb info [OPTIONS]

  Display document information.

  Shows document structure, hierarchy, and item counts.

Options:
  --root PATH           Project root directory
  --help                Show this message and exit.
```

**Example:**
```bash
# Show all documents in the current project
jamb info

# Specify a different project root
jamb info --root /path/to/project
```

---

### jamb check

```
Usage: jamb check [OPTIONS]

  Check test coverage without running tests.

  Scans test files for @pytest.mark.requirement markers and reports which
  items have linked tests.

  Note: This does a static scan and doesn't run tests. For full coverage
  including test outcomes, use pytest --jamb.

Options:
  -d, --documents TEXT  Comma-separated test document prefixes to check
  --root PATH           Project root directory
  --help                Show this message and exit.
```

**Example:**
```bash
# Check coverage for all documents
jamb check

# Check only specific documents
jamb check --documents SRS

# Check in a specific project directory
jamb check --root ./examples/advanced
```

---

### jamb validate

```
Usage: jamb validate [OPTIONS]

  Validate the requirements tree.

  Checks for issues like:
    - Cycles in document hierarchy
    - Invalid or missing links
    - Suspect links (items needing re-review)
    - Items without required links

  Examples:
      jamb validate              # Run validation
      jamb validate -v           # Verbose output
      jamb validate --skip UT    # Skip unit test document
      jamb validate -S           # Skip suspect checks
Options:
  -v, --verbose             Enable verbose logging (can be repeated)
  -q, --quiet               Only display errors and prompts
  -C, --no-child-check      Do not validate child (reverse) links
  -S, --no-suspect-check    Do not check for suspect links
  -W, --no-review-check     Do not check item review status
  -s, --skip TEXT           Skip a document during validation (can be repeated)
  -w, --warn-all            Display all info-level issues as warnings
  -e, --error-all           Display all warning-level issues as errors
  --help                    Show this message and exit.
```

**Example:**
```bash
# Run validation
jamb validate

# Run with verbose output
jamb validate -v

# Skip a document during validation
jamb validate --skip UT

# Treat all warnings as errors (strict mode)
jamb validate --error-all
```

---

### jamb publish

```
Usage: jamb publish [OPTIONS] PREFIX [PATH]

  Publish a document.

  PREFIX is the document prefix (e.g., SRS) or 'all' for all documents.
  PATH is the output file or directory (optional).

  Use --template with a .docx file to apply custom styles.
  Generate a starter template with: jamb publish-template

  For a traceability matrix with test coverage, use:
  pytest --jamb --jamb-trace-matrix PATH

Options:
  -H, --html            Output HTML (standalone document with inline CSS and hyperlinks)
  -m, --markdown        Output Markdown
  -d, --docx            Output DOCX (Word document)
  -L, --no-links        Do not include link sections in output
  -t, --template PATH   DOCX template file to use for styling (use with --docx)
  --help                Show this message and exit.
```

**Example:**
```bash
# Publish SRS document to HTML
jamb publish SRS docs/srs.html --html

# Publish all documents to HTML
jamb publish all docs/all.html --html

# Publish to markdown file
jamb publish SRS docs/srs.md --markdown

# Print markdown to stdout (default when no format flag and no path)
jamb publish SRS

# Publish to Word document
jamb publish SRS docs/srs.docx --docx

# Publish to Word document with custom template
jamb publish SRS docs/srs.docx --template my-company-template.docx

# Auto-detect format from file extension
jamb publish SRS docs/srs.html
```

---

### jamb publish-template

```
Usage: jamb publish-template [OPTIONS] [PATH]

  Generate a DOCX template file with jamb styles.

  PATH is the output file path (default: jamb-template.docx).

  The generated template contains all styles used by jamb when publishing
  DOCX documents. Open it in Microsoft Word, customize the styles (fonts,
  colors, spacing), then use it with:

      jamb publish SRS output.docx --template jamb-template.docx

Options:
  --help  Show this message and exit.
```

**Example:**
```bash
# Generate default template
jamb publish-template

# Generate template with custom name
jamb publish-template my-company-template.docx

# Workflow: generate, customize, then use
jamb publish-template
# Open jamb-template.docx in Word, customize styles, save
jamb publish SRS output.docx --template jamb-template.docx
```

---

### jamb export

```
Usage: jamb export [OPTIONS] OUTPUT

  Export documents and items to a YAML file.

  OUTPUT is the path to write the YAML file.

  Examples:
      jamb export requirements.yml
      jamb export reqs.yml --documents SRS,SYS
      jamb export output.yml --items SRS001,SRS002
      jamb export output.yml --items SRS001 --neighbors
      jamb export output.yml --items SRS001 --neighbors --documents SRS,SYS

Options:
  -d, --documents TEXT  Comma-separated document prefixes to export (default: all)
  -i, --items TEXT      Comma-separated item UIDs to export (e.g., SRS001,SRS002)
  -n, --neighbors       Include ancestors and descendants of specified items
                        (requires --items)
  --root PATH           Project root directory
  --help                Show this message and exit.
```

**Example:**
```bash
# Export all documents
jamb export requirements.yml

# Export specific documents
jamb export reqs.yml --documents SRS,SYS

# Export specific items only
jamb export subset.yml --items SRS001,SRS002,SYS001

# Export items with their ancestors and descendants
jamb export with-context.yml --items SRS001 --neighbors

# Export from a specific project
jamb export backup.yml --root ./examples/advanced
```

---

### jamb import

```
Usage: jamb import [OPTIONS] [FILE]

  Import documents and items from a YAML file.

  FILE is the path to a YAML file containing documents and items to create.

  Examples:
      jamb import requirements.yml
      jamb import requirements.yml --dry-run
      jamb import requirements.yml --update
      jamb import --template > requirements.yml

Options:
  --template     Print a starter YAML template to stdout and exit
  --dry-run      Show what would be created without making changes
  --update       Update existing items instead of skipping them
  -v, --verbose  Verbose output
  --help         Show this message and exit.
```

**Example:**
```bash
# Generate a starter YAML template
jamb import --template > requirements.yml

# Preview what would be imported
jamb import requirements.yml --dry-run

# Import new items (skip existing)
jamb import requirements.yml

# Import and update existing items
jamb import requirements.yml --update

# Import with verbose output
jamb import requirements.yml --verbose
```

---

### jamb reorder

```
Usage: jamb reorder [OPTIONS] PREFIX

  Renumber item UIDs sequentially to fill gaps.

  PREFIX is the document identifier (e.g., SRS, UT).

  Items are sorted by current UID and renumbered to form a contiguous sequence
  (e.g., SRS001, SRS002, ...).  All cross-document links that reference
  renamed UIDs are updated automatically.

  By default, test files with @pytest.mark.requirement() decorators are also
  updated to reflect the new UIDs. Use --no-update-tests to skip this.

Options:
  --no-update-tests   Skip updating test file references
  --root PATH         Project root directory
  --help              Show this message and exit.
```

**Example:**
```bash
# Renumber SRS items to fill gaps (updates requirement YAML and test files)
jamb reorder SRS

# Renumber UT items
jamb reorder UT

# Reorder without updating test files
jamb reorder SRS --no-update-tests

# Reorder in a specific project directory
jamb reorder SRS --root /path/to/project
```

**Output:**
```
Reordered SRS: 3 renamed, 1 unchanged
Updated test references in 2 files:
  tests/test_feature.py: SRS003->SRS002, SRS005->SRS004
  tests/test_integration.py: SRS003->SRS002
```

**Test File Updates:**

When reordering, jamb automatically updates `@pytest.mark.requirement()` decorators in test files to match the new UIDs. This maintains traceability between tests and requirements.

Supported decorator styles:
- `@pytest.mark.requirement("SRS001")` — fully qualified
- `@mark.requirement("SRS001")` — with `from pytest import mark`
- `@requirement("SRS001")` — with `from pytest.mark import requirement`

---

### jamb matrix

```
Usage: jamb matrix [OPTIONS] OUTPUT

  Generate traceability or test records matrix from saved coverage data.

  OUTPUT is the output file path. Format is inferred from the file extension
  (.html, .json, .csv, .md, .xlsx).

Options:
  -i, --input PATH              Coverage file path (default: .jamb)
  --trace-from PREFIX           Starting document prefix for trace matrix
  --test-records                Generate test records matrix instead of trace matrix
  --include-ancestors           Include "Traces To" column showing ancestors
  --trace-to-ignore PREFIX      Exclude document prefix from matrix (repeatable)
  --help                        Show this message and exit.
```

**Example:**
```bash
# Generate trace matrix from root document
jamb matrix trace.html

# Generate trace matrix starting from SYS document
jamb matrix trace.html --trace-from=SYS

# Generate test records matrix
jamb matrix test-records.html --test-records

# Exclude PRJ document from trace matrix
jamb matrix trace.html --trace-to-ignore=PRJ

# Generate trace matrix with ancestor column
jamb matrix trace.html --include-ancestors

# Use a specific coverage file
jamb matrix trace.html --input=.jamb-coverage
```

---

## Document Commands

### jamb doc

```
Usage: jamb doc [OPTIONS] COMMAND [ARGS]...

  Manage documents.

Options:
  --help  Show this message and exit.

Commands:
  create  Create a new document.
  delete  Delete a document.
  list    List all documents in the tree.
```

---

### jamb doc create

```
Usage: jamb doc create [OPTIONS] PREFIX PATH

  Create a new document.

  PREFIX is the document identifier (e.g., SRS, UT).
  PATH is the directory where the document will be created.

Options:
  -p, --parent TEXT     Parent document prefix (repeatable for multi-parent DAG)
  -d, --digits INTEGER  Number of digits for item IDs
  -s, --sep TEXT        Separator between prefix and number
  --help                Show this message and exit.
```

**Validation Rules:**

- `PREFIX` must be at least 2 characters long
- `PREFIX` must start with an uppercase letter and contain only uppercase letters, digits, and underscores
- `--digits` must be between 1 and 10 (inclusive)
- `--sep` cannot start with an alphanumeric character (would create ambiguous UIDs)

**Example:**
```bash
# Create a root document
jamb doc create SYS reqs/sys

# Create a child document with parent
jamb doc create SRS reqs/srs --parent SYS

# Create a document with multiple parents
jamb doc create SRS reqs/srs --parent SYS --parent RC

# Create with 4-digit item IDs
jamb doc create UT tests/unit --parent SRS --digits 4

# Create with custom separator
jamb doc create UN reqs --sep "-"  # Creates UN-001, UN-002, etc.
```

---

### jamb doc delete

```
Usage: jamb doc delete [OPTIONS] PREFIX

  Delete a document.

  PREFIX is the document identifier to delete (e.g., SRS, UT).

Options:
  --root PATH  Project root directory
  --force      Force deletion even if other documents link to items in this document
  --help       Show this message and exit.
```

**Example:**
```bash
# Delete a document
jamb doc delete UT

# Delete a document in a specific project
jamb doc delete UT --root /path/to/project

# Force deletion even if other documents reference this one
jamb doc delete SYS --force
```

---

### jamb doc list

```
Usage: jamb doc list [OPTIONS]

  List all documents in the tree.

Options:
  --root PATH  Project root directory
  --help       Show this message and exit.
```

**Example:**
```bash
# List all documents
jamb doc list

# List documents in a specific project
jamb doc list --root ./examples/advanced
```

---

## Item Commands

### jamb item

```
Usage: jamb item [OPTIONS] COMMAND [ARGS]...

  Manage items.

Options:
  --help  Show this message and exit.

Commands:
  add     Add a new item to a document.
  edit    Edit an item in the default editor.
  list    List items in a document or all documents.
  remove  Remove an item by UID.
  show    Display item details.
```

---

### jamb item add

```
Usage: jamb item add [OPTIONS] PREFIX

  Add a new item to a document.

  PREFIX is the document to add the item to (e.g., SRS, UT).

Options:
  -c, --count INTEGER  Number of items to add
  --after TEXT         Insert after this UID
  --before TEXT        Insert before this UID
  --header TEXT        Set the item header
  --text TEXT          Set the item body text
  --links TEXT         Add parent link(s) (multiple allowed)
  --help               Show this message and exit.
```

**Example:**
```bash
# Add a single item
jamb item add SRS

# Add multiple items at once
jamb item add SRS --count 5

# Insert after a specific item
jamb item add SRS --after SRS003

# Insert before a specific item
jamb item add SRS --before SRS005

# Add an item with a header and body text
jamb item add SRS --header "Login Page" --text "The system shall display a login page."

# Add an item with parent links
jamb item add UT --links SRS001 --links SRS002
```

---

### jamb item remove

```
Usage: jamb item remove [OPTIONS] UID

  Remove an item by UID.

  UID is the item identifier (e.g., SRS001, UT002).

  If the item is referenced by tests (via @pytest.mark.requirement), jamb
  displays a warning and prompts for confirmation. Use --force to skip the
  confirmation prompt.

Options:
  --force       Skip confirmation prompts for test references
  --root PATH   Project root directory
  --help        Show this message and exit.
```

**Example:**
```bash
# Remove an item (prompts if tests reference it)
jamb item remove SRS005

# Force removal without confirmation
jamb item remove SRS005 --force

# Remove from a specific project directory
jamb item remove SRS005 --root /path/to/project
```

**Test Reference Warning:**

When removing an item that is referenced by tests, jamb warns you before deletion:

```
WARNING: SRS004 is referenced by 3 test(s):
  - tests/test_validation.py::test_range_validation (line 45)
  - tests/test_validation.py::test_boundary_check (line 72)
  - tests/test_integration.py::test_full_workflow (line 23)

These test references will become orphaned.
Proceed with removal? [y/N]: y
Removed item: SRS004
Note: Update test files to remove orphaned references.
```

Use `--force` to skip the confirmation prompt (useful in scripts), but remember to update your test files afterward to remove orphaned references.

---

### jamb item edit

```
Usage: jamb item edit [OPTIONS] UID

  Edit an item in the default editor.

  UID is the item identifier (e.g., SRS001, UT002).

Options:
  -T, --tool TEXT  Text editor to use (default: $EDITOR or vim)
  --help           Show this message and exit.
```

**Example:**
```bash
# Edit an item in your default editor
jamb item edit SRS001

# Edit with a specific editor
jamb item edit SRS001 --tool nano
jamb item edit SRS001 --tool "code --wait"
```

---

### jamb item show

```
Usage: jamb item show [OPTIONS] UID

  Display item details.

  UID is the item identifier (e.g., SRS001, UT002).

Options:
  --help  Show this message and exit.
```

**Example:**
```bash
# Show details for a specific item
jamb item show SRS001
```

---

### jamb item list

```
Usage: jamb item list [OPTIONS] [PREFIX]

  List items in a document or all documents.

  PREFIX is optional - if provided, only list items in that document.

Options:
  --root PATH  Project root directory
  --help       Show this message and exit.
```

**Example:**
```bash
# List all items in all documents
jamb item list

# List items in a specific document
jamb item list SRS

# List items from a specific project
jamb item list --root ./examples/advanced
```

---

## Link Commands

### jamb link

```
Usage: jamb link [OPTIONS] COMMAND [ARGS]...

  Manage item links.

Options:
  --help  Show this message and exit.

Commands:
  add     Link a child item to a parent item.
  remove  Remove a link between items.
```

---

### jamb link add

```
Usage: jamb link add [OPTIONS] CHILD PARENT

  Link a child item to a parent item.

  CHILD is the child item UID (e.g., SRS001).
  PARENT is the parent item UID (e.g., SYS001).

Options:
  --help  Show this message and exit.
```

**Example:**
```bash
# Link SRS001 to its parent SYS001
jamb link add SRS001 SYS001

# Link a test to a requirement
jamb link add UT001 SRS001
```

---

### jamb link remove

```
Usage: jamb link remove [OPTIONS] CHILD PARENT

  Remove a link between items.

  CHILD is the child item UID (e.g., SRS001).
  PARENT is the parent item UID (e.g., SYS001).

Options:
  --help  Show this message and exit.
```

**Example:**
```bash
# Remove link between SRS001 and SYS001
jamb link remove SRS001 SYS001
```

---

## Review Commands

### jamb review

```
Usage: jamb review [OPTIONS] COMMAND [ARGS]...

  Manage item reviews.

Options:
  --help  Show this message and exit.

Commands:
  clear  Absolve items of their suspect link status.
  mark   Mark an item as reviewed.
  reset  Reset items to unreviewed status.
```

---

### jamb review mark

```
Usage: jamb review mark [OPTIONS] LABEL

  Mark an item as reviewed.

  LABEL is an item UID, document prefix, or 'all'.

  Examples:
      jamb review mark SRS001   # Mark single item
      jamb review mark SRS      # Mark all items in SRS document
      jamb review mark all      # Mark all items in all documents

Options:
  --help  Show this message and exit.
```

**Example:**
```bash
# Mark a single item as reviewed
jamb review mark SRS001

# Mark all items in a document as reviewed
jamb review mark SRS

# Mark all items in all documents as reviewed
jamb review mark all
```

---

### jamb review clear

```
Usage: jamb review clear [OPTIONS] LABEL [PARENTS]...

  Absolve items of their suspect link status.

  LABEL is an item UID, document prefix, or 'all'.
  PARENTS optionally limits clearing to links with specific parent UIDs.

  Examples:
      jamb review clear SRS001        # Clear suspect links on single item
      jamb review clear SRS           # Clear suspect links in SRS document
      jamb review clear all           # Clear all suspect links
      jamb review clear SRS001 UN001 # Clear only link to UN001

Options:
  --help  Show this message and exit.
```

**Example:**
```bash
# Clear suspect links on a single item
jamb review clear SRS001

# Clear suspect links on all items in a document
jamb review clear SRS

# Clear all suspect links in all documents
jamb review clear all

# Clear only the suspect link to a specific parent
jamb review clear SRS001 SYS001
```

---

### jamb review reset

```
Usage: jamb review reset [OPTIONS] LABEL

  Reset items to unreviewed status.

  LABEL is an item UID, document prefix, or 'all'.

  Examples:
      jamb review reset SRS001   # Reset single item
      jamb review reset SRS      # Reset all items in SRS document
      jamb review reset all      # Reset all items in all documents

Options:
  --root PATH  Project root directory
  --help       Show this message and exit.
```

**Example:**
```bash
# Reset a single item to unreviewed
jamb review reset SRS001

# Reset all items in a document
jamb review reset SRS

# Reset all items in all documents
jamb review reset all
```

---

## Derived Requirements for Risk Controls

Risk-driven SRS items that only implement risk controls (RC) and don't trace to a system requirement (SYS) should be marked as `derived: true`:

```yaml
# SRS item that only implements a risk control
active: true
derived: true  # No SYS parent needed
header: Input Validation
links:
- RC001  # Links to risk control only
text: |
  Software shall validate all input against buffer overflow attacks.
```

This tells jamb the requirement is intentionally not linked to the parent document (SYS) because it emerges from risk analysis rather than user needs.

**When to use `derived: true`:**
- Requirements that emerge from risk/hazard analysis
- Security hardening requirements
- Defensive coding requirements
- Any requirement that doesn't trace to a user need but implements a risk control
