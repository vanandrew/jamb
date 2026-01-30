# Configuration

jamb uses a two-level configuration model. Project-wide settings live in `pyproject.toml` under the `[tool.jamb]` section, controlling behavior like which documents require test coverage, matrix output format, and CI enforcement options. Per-document settings live in a `.jamb.yml` file inside each document directory, defining the document's prefix, parent relationships, and UID formatting. The sections below describe both levels in detail.

## Project Configuration (`pyproject.toml`)

jamb is configured in `pyproject.toml` under the `[tool.jamb]` section:

```toml
[tool.jamb]
test_documents = ["SRS"]
fail_uncovered = false
require_all_pass = true
software_version = "1.0.0"
exclude_patterns = []
trace_to_ignore = []

# Matrix output options (format inferred from extension)
test_matrix_output = "test-records.html"
trace_matrix_output = "traceability.html"
trace_from = "UN"
include_ancestors = true
```

### Options Reference

`test_documents`
: List of document prefixes that represent test specifications. These are the documents checked for test coverage.
: **Type:** `list[str]`
: **Default:** `[]`

`fail_uncovered`
: Fail the pytest session if any items in `test_documents` lack test coverage.
: **Type:** `bool`
: **Default:** `false`

`require_all_pass`
: Require all linked tests to pass (not just exist) for an item to be considered covered.
: **Type:** `bool`
: **Default:** `true`

`test_matrix_output`
: Output path for the test records matrix (test-centric view). Can be overridden with `--jamb-test-matrix`. Format is inferred from the file extension.
: **Type:** `str | null`
: **Default:** `null`

`trace_matrix_output`
: Output path for the traceability matrix (requirement-centric view). Can be overridden with `--jamb-trace-matrix`. Format is inferred from the file extension.
: **Type:** `str | null`
: **Default:** `null`

`exclude_patterns`
: Glob patterns for documents or items to exclude from processing.
: **Type:** `list[str]`
: **Default:** `[]`

`trace_to_ignore`
: Document prefixes to exclude from the "Traces To" column in the traceability matrix.
: **Type:** `list[str]`
: **Default:** `[]`

`software_version`
: Software version to display in the traceability matrix metadata. If not set, jamb auto-detects the version from `[project].version` in pyproject.toml, or from dynamic version files (hatch-vcs, setuptools_scm). Can be overridden at runtime with `--jamb-software-version`.
: **Type:** `str | null`
: **Default:** `null` (auto-detected)

`trace_from`
: Starting document prefix for full chain trace matrix. When set, the trace matrix starts from this document and traces down through the hierarchy.
: **Type:** `str | null`
: **Default:** `null` (auto-detect root document)

`include_ancestors`
: Include a "Traces To" column showing ancestor UIDs in the trace matrix.
: **Type:** `bool`
: **Default:** `false`

### Example Configurations

**Minimal (most projects):**

```toml
[tool.jamb]
test_documents = ["SRS"]
```

**Strict CI enforcement:**

```toml
[tool.jamb]
test_documents = ["SRS", "SYS"]
fail_uncovered = true
require_all_pass = true
trace_matrix_output = "matrix.html"
trace_to_ignore = ["PRJ"]
```

**Dual-matrix output (trace + test records):**

```toml
[tool.jamb]
test_documents = ["SRS"]
trace_matrix_output = "docs/traceability.html"
test_matrix_output = "docs/test-records.html"
trace_from = "UN"
include_ancestors = true
trace_to_ignore = ["PRJ", "HAZ"]
```

## Document Configuration (`.jamb.yml`)

Each document directory contains a `.jamb.yml` file that configures the document:

```yaml
settings:
  prefix: SRS
  parents:
    - SYS
  digits: 3
  sep: ""
```

All fields are nested under a `settings` key.

### Fields

`prefix`
: The document identifier used in item UIDs (e.g., `SRS` → `SRS001`).
: **Required**

`parents`
: List of parent document prefixes. Defines where items in this document should link to.
: **Default:** `[]` (root document)

`digits`
: Number of digits in the sequential part of item UIDs.
: **Default:** `3`
: **Range:** `1` to `10`
: **Example:** `digits: 3` → `SRS001`, `digits: 4` → `SRS0001`

`sep`
: Separator between prefix and number in UIDs.
: **Default:** `""` (no separator)
: **Constraint:** Cannot start with an alphanumeric character (would create ambiguous UIDs like `SRSX001`)
: **Example:** `sep: "-"` → `SRS-001`

### Creating Documents

Documents are created with `jamb doc create`, which generates the `.jamb.yml` file:

```bash
jamb doc create SRS reqs/srs --parent SYS --digits 3
```

See {doc}`commands` for all document management commands.
