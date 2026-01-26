# Jamb Command Reference

Complete reference for all `jamb` CLI commands.

## Table of Contents

- [Top-Level Commands](#top-level-commands)
  - [jamb](#jamb)
  - [jamb init](#jamb-init)
  - [jamb info](#jamb-info)
  - [jamb check](#jamb-check)
  - [jamb validate](#jamb-validate)
  - [jamb publish](#jamb-publish)
  - [jamb export](#jamb-export)
  - [jamb import](#jamb-import)
- [Document Commands](#document-commands)
  - [jamb doc](#jamb-doc)
  - [jamb doc create](#jamb-doc-create)
  - [jamb doc delete](#jamb-doc-delete)
  - [jamb doc list](#jamb-doc-list)
  - [jamb doc reorder](#jamb-doc-reorder)
- [Item Commands](#item-commands)
  - [jamb item](#jamb-item)
  - [jamb item add](#jamb-item-add)
  - [jamb item remove](#jamb-item-remove)
  - [jamb item edit](#jamb-item-edit)
  - [jamb item show](#jamb-item-show)
  - [jamb item list](#jamb-item-list)
  - [jamb item import](#jamb-item-import)
  - [jamb item export](#jamb-item-export)
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
  check     Check test coverage without running tests.
  doc       Manage doorstop documents.
  export    Export documents and items to a YAML file.
  import    Import documents and items from a YAML file.
  info      Display doorstop document information.
  init      Initialize a new jamb project with default IEC 62304 documents.
  item      Manage doorstop items.
  link      Manage item links.
  publish   Publish a document.
  review    Manage item reviews.
  validate  Validate the requirements tree.
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

  Display doorstop document information.

  Shows document structure, hierarchy, and item counts.

Options:
  -d, --documents TEXT  Comma-separated test document prefixes to check
  --root PATH           Project root directory
  --help                Show this message and exit.
```

**Example:**
```bash
# Show all documents in the current project
jamb info

# Show specific documents
jamb info --documents SRS,SYS

# Specify a different project root
jamb info --root /path/to/project
```

---

### jamb check

```
Usage: jamb check [OPTIONS]

  Check test coverage without running tests.

  Scans test files for @pytest.mark.requirement markers and reports which
  doorstop items have linked tests.

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

  Runs doorstop validation to check for issues like:
    - Missing parent documents
    - Suspect links (items needing re-review)
    - Items without required links

  Examples:
      jamb validate              # Run validation
      jamb validate -v           # Verbose output
      jamb validate --skip UT    # Skip unit test document
      jamb validate -F -S        # Skip reformatting and suspect checks

Options:
  -v, --verbose             Enable verbose logging (can be repeated)
  -q, --quiet               Only display errors and prompts
  -F, --no-reformat         Do not reformat item files during validation
  -r, --reorder             Reorder document levels during validation
  -L, --no-level-check      Do not validate document levels
  -R, --no-ref-check        Do not validate external file references
  -C, --no-child-check      Do not validate child (reverse) links
  -Z, --strict-child-check  Require child (reverse) links from every document
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

# Skip reformatting and suspect link checks
jamb validate -F -S

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

  For a traceability matrix with test coverage, use:
  pytest --jamb --jamb-matrix PATH

Options:
  -H, --html            Output HTML
  -m, --markdown        Output Markdown
  -l, --latex           Output LaTeX
  -t, --text            Output text (default when no path)
  -d, --docx            Output DOCX (Word document)
  --template TEXT       Template file for custom formatting
  -C, --no-child-links  Do not include child links on items
  --help                Show this message and exit.
```

**Example:**
```bash
# Publish SRS document to HTML
jamb publish SRS --html docs/srs.html

# Publish all documents to markdown
jamb publish all --markdown docs/

# Publish to text (stdout)
jamb publish SRS --text

# Publish to Word document
jamb publish SRS --docx docs/srs.docx

# Publish with custom template
jamb publish SRS --html --template my_template.html docs/srs.html
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
Usage: jamb import [OPTIONS] FILE

  Import documents and items from a YAML file.

  FILE is the path to a YAML file containing documents and items to create.

  Examples:
      jamb import requirements.yml
      jamb import requirements.yml --dry-run
      jamb import requirements.yml --update

Options:
  --dry-run      Show what would be created without making changes
  --update       Update existing items instead of skipping them
  -v, --verbose  Verbose output
  --help         Show this message and exit.
```

**Example:**
```bash
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

## Document Commands

### jamb doc

```
Usage: jamb doc [OPTIONS] COMMAND [ARGS]...

  Manage doorstop documents.

Options:
  --help  Show this message and exit.

Commands:
  create   Create a new document.
  delete   Delete a document.
  list     List all documents in the tree.
  reorder  Reorder items in a document.
```

---

### jamb doc create

```
Usage: jamb doc create [OPTIONS] PREFIX PATH

  Create a new document.

  PREFIX is the document identifier (e.g., SRS, UT).
  PATH is the directory where the document will be created.

Options:
  -p, --parent TEXT     Parent document prefix
  -d, --digits INTEGER  Number of digits for item IDs
  -s, --sep TEXT        Separator between prefix and number
  --help                Show this message and exit.
```

**Example:**
```bash
# Create a root document
jamb doc create SYS reqs/sys

# Create a child document with parent
jamb doc create SRS reqs/srs --parent SYS

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
  --help  Show this message and exit.
```

**Example:**
```bash
# Delete a document
jamb doc delete UT
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

### jamb doc reorder

```
Usage: jamb doc reorder [OPTIONS] PREFIX

  Reorder items in a document.

  PREFIX is the document identifier (e.g., SRS, UT).

Options:
  -a, --auto    Automatically reorder items
  -m, --manual  Manually reorder items
  --help        Show this message and exit.
```

**Example:**
```bash
# Automatically reorder items (fixes duplicate level warnings)
jamb doc reorder SRS --auto

# Manually reorder items (opens editor)
jamb doc reorder SRS --manual
```

---

## Item Commands

### jamb item

```
Usage: jamb item [OPTIONS] COMMAND [ARGS]...

  Manage doorstop items.

Options:
  --help  Show this message and exit.

Commands:
  add     Add a new item to a document.
  edit    Edit an item in the default editor.
  export  Export items to a file.
  import  Import items from a file.
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
  -l, --level TEXT     Item level (e.g., 1.2)
  -c, --count INTEGER  Number of items to add
  --help               Show this message and exit.
```

**Example:**
```bash
# Add a single item
jamb item add SRS

# Add an item at a specific level
jamb item add SRS --level 1.2

# Add multiple items at once
jamb item add SRS --count 5
```

---

### jamb item remove

```
Usage: jamb item remove [OPTIONS] UID

  Remove an item by UID.

  UID is the item identifier (e.g., SRS001, UT002).

Options:
  --help  Show this message and exit.
```

**Example:**
```bash
# Remove an item
jamb item remove SRS005
```

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

### jamb item import

```
Usage: jamb item import [OPTIONS] PREFIX PATH

  Import items from a file.

  PREFIX is the document to import into.
  PATH is the path to the import file (CSV, TSV, XLSX).

Options:
  -f, --file TEXT  Path to import file
  -m, --map TEXT   Column mapping (e.g., 'text=Description')
  --help           Show this message and exit.
```

**Example:**
```bash
# Import items from CSV
jamb item import SRS requirements.csv

# Import with column mapping
jamb item import SRS reqs.xlsx --map "text=Description" --map "header=Title"
```

---

### jamb item export

```
Usage: jamb item export [OPTIONS] PREFIX PATH

  Export items to a file.

  PREFIX is the document to export.
  PATH is the output file path.

Options:
  --xlsx  Export as Excel file
  --csv   Export as CSV file
  --help  Show this message and exit.
```

**Example:**
```bash
# Export to Excel
jamb item export SRS requirements.xlsx --xlsx

# Export to CSV
jamb item export SRS requirements.csv --csv
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

This tells doorstop the requirement is intentionally not linked to the parent document (SYS) because it emerges from risk analysis rather than user needs.

**When to use `derived: true`:**
- Requirements that emerge from risk/hazard analysis
- Security hardening requirements
- Defensive coding requirements
- Any requirement that doesn't trace to a user need but implements a risk control
