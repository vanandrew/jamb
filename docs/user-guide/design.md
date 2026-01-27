# Design & Architecture

This page describes jamb's internal architecture and the reasoning behind key design choices.

## Package Overview

jamb is organized into focused packages, each with a single responsibility:

| Package | Role |
|---------|------|
| `core` | Domain models (`Item`, `LinkedTest`, `ItemCoverage`, `TraceabilityGraph`) |
| `storage` | Filesystem I/O: discovery, YAML reading/writing, graph building, validation |
| `pytest_plugin` | pytest hooks, marker extraction, test-outcome recording |
| `matrix` | Traceability-matrix generation in multiple formats |
| `publish` | Human-readable document rendering (HTML, DOCX) |
| `cli` | Click-based command-line interface |

Shared modules at the package root include `config` (configuration loading from `pyproject.toml`) and `yaml_io` (YAML utilities).

```{mermaid}
graph TD
    CLI[cli] --> Storage[storage]
    CLI --> Matrix[matrix]
    CLI --> Publish[publish]
    Plugin[pytest_plugin] --> Storage
    Plugin --> Matrix
    Plugin --> Core[core]
    Matrix --> Core
    Publish --> Core
    Storage --> Core
    Storage --> Config[config]
    Storage --> YamlIO[yaml_io]

    style Core fill:#e8f5e9,stroke:#388e3c
```

**Design rationale.** Domain models in `core/` have zero I/O dependencies, making them easy to test in isolation. All filesystem interaction is confined to `storage/`, so the rest of the codebase works with pure in-memory data structures.

## Domain Models

The core domain lives in `core/models.py`:

- **`Item`** -- A single requirement, informational note, or heading. Key fields: `uid`, `text`, `document_prefix`, `type`, `links`, `header`, `reviewed`, `derived`.
- **`LinkedTest`** -- A test-to-requirement link. Records `test_nodeid`, `item_uid`, `test_outcome`, plus optional `notes`, `test_actions`, and `expected_results` captured via the `jamb_log` fixture.
- **`ItemCoverage`** -- Pairs an `Item` with its `LinkedTest` list and exposes `is_covered` / `all_tests_passed` properties.
- **`TraceabilityGraph`** -- The complete bidirectional graph. Stores items by UID and maintains two adjacency lists (`item_parents`, `item_children`) plus a document-level DAG (`document_parents`). Provides BFS-based `get_ancestors()` and `get_descendants()` traversals.

`TraceabilityGraph` uses adjacency lists rather than a matrix because the graph is sparse -- most items link to only one or two parents.

## The Document DAG

Documents form a **directed acyclic graph** (DAG), not a simple tree, because a child document can trace to multiple parents. For example, a Risk Controls document may trace to both a Hazard Analysis and a Software Requirements Specification.

The `DocumentDAG` class (`storage/document_dag.py`) manages document relationships and provides two critical operations:

1. **Topological sort** (Kahn's algorithm) -- Orders documents so that parents are always loaded before children. This ensures that when an item's links are resolved, the target items already exist in memory.
2. **Cycle detection** -- After running Kahn's algorithm, any nodes not visited form cycles. The validator reports the specific prefixes involved.

```{mermaid}
graph TD
    PRJ[PRJ<br/>Project Plan] --> UN[UN<br/>User Needs]
    PRJ --> HAZ[HAZ<br/>Hazard Analysis]
    UN --> SYS[SYS<br/>System Requirements]
    SYS --> SRS[SRS<br/>Software Requirements]
    HAZ --> RC[RC<br/>Risk Controls]
    SRS -.-> RC

    style PRJ fill:#e3f2fd,stroke:#1565c0
    style UN fill:#e3f2fd,stroke:#1565c0
    style SYS fill:#e3f2fd,stroke:#1565c0
    style SRS fill:#e3f2fd,stroke:#1565c0
    style HAZ fill:#fff3e0,stroke:#e65100
    style RC fill:#fff3e0,stroke:#e65100
```

The dashed line from SRS to RC shows that a document can have multiple parents -- RC traces to both HAZ and SRS.

## Data Flow

The discovery-to-graph pipeline runs in three phases:

1. **Discovery** (`storage/discovery.py`) -- Walks the filesystem from the project root, finding all `.jamb.yml` config files via `Path.rglob()`. Each config defines a document prefix and its parent documents. The result is a `DocumentDAG`.
2. **Graph building** (`storage/graph_builder.py`) -- Iterates documents in topological order, reading YAML item files via `storage/items.py`. Each file becomes an `Item` added to the `TraceabilityGraph`.
3. **Item reading** (`storage/items.py`) -- Parses individual YAML files, normalizing two link formats (plain `- UID` and hashed `- UID: hash_value`) into a consistent structure.

```{mermaid}
flowchart LR
    FS["Filesystem<br/>.jamb.yml files"] --> Disc["discovery.py<br/>discover_documents()"]
    Disc --> DAG["DocumentDAG"]
    DAG --> GB["graph_builder.py<br/>build_traceability_graph()"]
    GB --> Items["items.py<br/>read_document_items()"]
    Items --> TG["TraceabilityGraph"]

    style FS fill:#f5f5f5,stroke:#616161
    style TG fill:#e8f5e9,stroke:#388e3c
```

## pytest Integration Lifecycle

The pytest plugin (`pytest_plugin/plugin.py` and `pytest_plugin/collector.py`) integrates with pytest through a chain of hooks:

```{mermaid}
sequenceDiagram
    participant U as User
    participant P as pytest
    participant Pl as plugin.py
    participant C as RequirementCollector
    participant M as markers.py
    participant G as TraceabilityGraph
    participant Mx as matrix/generator.py

    U->>P: pytest --jamb
    P->>Pl: pytest_addoption()
    P->>Pl: pytest_configure()
    Pl->>C: create collector
    C->>G: discover & build graph
    P->>C: pytest_collection_modifyitems()
    C->>M: get_requirement_markers()
    M-->>C: list of UIDs
    C->>C: create LinkedTest entries
    loop each test
        P->>C: pytest_runtest_makereport()
        C->>C: record outcome, notes, actions
    end
    P->>Pl: pytest_sessionfinish()
    Pl->>Mx: generate_matrix() (if --jamb-matrix)
    P->>Pl: pytest_terminal_summary()
    Pl->>U: coverage report
```

Key hooks in order:

1. **`pytest_addoption`** -- Registers `--jamb`, `--jamb-matrix`, `--jamb-matrix-format`, `--jamb-fail-uncovered`, `--jamb-documents`.
2. **`pytest_configure`** -- Creates a `RequirementCollector` that discovers documents and builds the graph.
3. **`pytest_collection_modifyitems`** -- Scans collected tests for `@pytest.mark.requirement` markers and creates `LinkedTest` entries.
4. **`pytest_runtest_makereport`** -- After each test's call phase, records the outcome and any data from `jamb_log`.
5. **`pytest_sessionfinish`** -- Generates the traceability matrix if requested; sets exit code if uncovered items exist and `--jamb-fail-uncovered` is set.
6. **`pytest_terminal_summary`** -- Prints coverage statistics, uncovered items, and unknown UIDs.

## Suspect Link Detection

When an item's content changes, any items that link *to* it may become outdated. jamb detects this through content hashing.

**Hash computation** (`storage/items.py: compute_content_hash()`):
- Concatenates `text`, `header`, sorted `links`, and `type` with `|` as delimiter.
- Computes a SHA-256 digest.
- Encodes as URL-safe base64 (padding stripped).

**Why hashing over timestamps?** Hashes are deterministic across git clones -- every developer and CI runner computes the same hash for the same content. Timestamps would break on fresh clones or rebases.

**Detection flow** (`storage/validation.py: _check_suspect_links()`):

```{mermaid}
flowchart TD
    Start["validate()"] --> Load["Load all active items"]
    Load --> Loop{"For each item<br/>with stored link hashes"}
    Loop --> Read["Read raw YAML to<br/>get link_hashes dict"]
    Read --> Hash["Compute current hash<br/>of linked item"]
    Hash --> Compare{"Stored hash ==<br/>current hash?"}
    Compare -- Yes --> Next["Link is clean"]
    Compare -- No --> Flag["Flag as suspect link<br/>(warning)"]
    Next --> Loop
    Flag --> Loop
    Loop -- "No stored hash" --> Warn["Warn: link not verified"]

    style Flag fill:#fff3e0,stroke:#e65100
    style Warn fill:#fff3e0,stroke:#e65100
```

## Matrix & Publishing

The matrix generator (`matrix/generator.py`) dispatches to format-specific renderers based on a simple if/elif chain. Five formats are supported: **HTML**, **Markdown**, **JSON**, **CSV**, and **XLSX**.

Format modules are imported lazily inside the dispatch function. This avoids requiring optional dependencies (like `openpyxl` for XLSX) when they aren't used.

The publish package (`publish/formats/`) renders human-readable requirement documents in **HTML** and **DOCX** formats, with internal hyperlinks between items and document-order grouping.

## Validation Architecture

The `validate()` function (`storage/validation.py`) is the single entry point for all validation. It runs ten independent checks that can each be toggled via keyword flags (all default to `True`):

**Structural checks:**
- **DAG acyclicity** -- Detects cycles in the document hierarchy.
- **Item link cycles** -- DFS with three-color marking (white/gray/black) to find cycles in item-to-item links.
- **Link conformance** -- Verifies links point to items in valid parent documents per the DAG.

**Content checks:**
- **Link validity** -- Catches self-links, links to non-existent items, links to inactive items, and non-normative items with links.
- **Suspect links** -- Content-hash comparison (see above).
- **Review status** -- Checks that normative items have a `reviewed` hash matching current content.
- **Empty text** -- Flags items with blank or whitespace-only text.

**Completeness checks:**
- **Child links** -- Non-leaf-document items should have children linking to them.
- **Unlinked items** -- Child-document items (non-derived) should link to a parent document.
- **Empty documents** -- Flags documents containing no items.

Each check returns a list of `ValidationIssue` objects with a `level` (error, warning, or info), the relevant `uid` or `prefix`, and a descriptive message.

## Design Decisions Summary

| Decision | Alternative | Rationale |
|----------|------------|-----------|
| DAG over tree | Tree hierarchy | Multi-parent tracing (e.g., risk controls linked to both hazards and software requirements) |
| Content hashing (SHA-256) | Timestamps | Deterministic across git clones; no breakage on fresh checkout or rebase |
| YAML per item | Single file per document | Better git diffs, fewer merge conflicts when multiple authors edit the same document |
| In-memory graph | Database | Data fits in memory; no need for a query language or external process |
| pytest hooks | Custom test runner | Leverages the existing pytest ecosystem, markers, and reporting |
| Lazy format imports | Plugin registry | Simple and sufficient for a small, stable set of output formats |
