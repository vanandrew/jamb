# Concepts

This page explains the core concepts behind jamb and how they map to IEC 62304 requirements traceability.

## IEC 62304 Context

[IEC 62304](https://en.wikipedia.org/wiki/IEC_62304) is the international standard for medical device software lifecycle processes. It requires that software requirements are:

- **Traceable** to system requirements and risk controls
- **Verified** through testing with documented evidence
- **Reviewed** when changes occur upstream

jamb implements these requirements as a lightweight, git-native tool that integrates directly with pytest.

## Document Hierarchy

jamb organizes requirements into **documents**, each identified by a prefix (e.g., `SRS`, `SYS`, `UN`). Documents form a directed acyclic graph (DAG) where parent-child relationships define the traceability direction.

The default IEC 62304 hierarchy created by `jamb init`:

```
PRJ (Project Requirements) - root
├── UN (User Needs)
│   └── SYS (System Requirements)
│       └── SRS (Software Requirements Specification)
└── HAZ (Hazards)
    └── RC (Risk Controls)
```

Each document lives in its own directory and contains:
- A `.jamb.yml` configuration file (prefix, parent documents, UID formatting)
- Individual YAML files for each item (e.g., `SRS001.yml`, `SRS002.yml`)

### Custom Hierarchies

You can create custom document hierarchies using `jamb doc create`:

```bash
# Create a root document
jamb doc create SYS reqs/sys

# Create a child document
jamb doc create SRS reqs/srs --parent SYS

# A document can have multiple parents
jamb doc create RC reqs/rc --parent HAZ
```

## Items and Types

An **item** is a single requirement, hazard, risk control, or other traceable entity. Each item has:

- **UID** -- unique identifier (e.g., `SRS001`) composed of the document prefix and a sequential number
- **Text** -- the requirement statement
- **Header** -- optional short title
- **Links** -- references to parent items in upstream documents
- **Active** -- whether the item is active (`true`) or deactivated (`false`)
- **Reviewed** -- a content hash indicating the item has been reviewed
- **Derived** -- flag for requirements that don't trace to a parent document (see below)

Items are stored as individual YAML files. See {doc}`yaml-format` for the full field reference.

## Links

Links define traceability relationships between items. A link always points from a **child** item to a **parent** item in an upstream document.

```bash
# SRS001 traces to SYS001
jamb link add SRS001 SYS001
```

Links are stored as a list of parent UIDs in the child item's YAML file. Each link entry also stores a **content hash** of the parent item at the time the link was created or last reviewed. This hash is the basis of suspect link detection.

### Multi-Parent Traceability

An item can link to multiple parents, even across different documents:

```bash
# SRS005 implements both a system requirement and a risk control
jamb link add SRS005 SYS003
jamb link add SRS005 RC001
```

## Suspect Links

When a parent item is modified, the content hash stored in its child's link no longer matches. jamb flags these as **suspect links** -- the child item needs to be reviewed to confirm it is still valid given the parent change.

### Detection

```bash
jamb validate
# WARNING: SRS001 has suspect links: SYS001
```

This means SYS001 was modified after SRS001's link to it was last reviewed.

### Resolution

After reviewing that the downstream item is still valid:

```bash
# Mark the item as reviewed and clear the suspect link
jamb review mark SRS001
jamb review clear SRS001

# Or clear only a specific parent link
jamb review clear SRS001 SYS001
```

## Review Cycles

jamb tracks whether each item has been **reviewed** after its last modification. An item's reviewed status is a hash of its content at the time of review.

### Workflow

1. An item is created or edited → reviewed status is cleared
2. A reviewer inspects the item → `jamb review mark SRS001`
3. The reviewed hash is set to the current content hash
4. If the item is later edited, the hash no longer matches → item needs re-review

### Bulk Operations

```bash
# Review all items in a document
jamb review mark SRS

# Review everything
jamb review mark all

# Reset reviews (e.g., after a major restructuring)
jamb review reset all
```

## Derived Requirements

Some requirements emerge from risk analysis rather than user needs. For example, a security hardening requirement may implement a risk control but not trace to any system requirement.

Mark these as **derived** so jamb doesn't flag them for missing parent links:

```yaml
active: true
derived: true
header: Input Validation
links:
- RC001
text: |
  Software shall validate all input against buffer overflow attacks.
```

**When to use `derived: true`:**
- Requirements from risk/hazard analysis
- Security hardening requirements
- Defensive coding requirements
- Any requirement that implements a risk control without a corresponding system requirement

## Traceability Graph

jamb builds a full traceability graph from all documents and their items. This graph is used for:

- **Validation** -- checking for broken links, cycles, orphan items
- **Coverage analysis** -- determining which requirements have linked tests
- **Matrix generation** -- producing traceability matrices with test status
- **Impact analysis** -- determining which downstream items are affected by a change

The graph includes both the document-level DAG (which documents trace to which) and the item-level links (which items trace to which).

## Test Coverage

jamb integrates with pytest to track which requirements have linked tests and whether those tests pass.

Coverage is determined by the `@pytest.mark.requirement` marker:

```python
@pytest.mark.requirement("SRS001")
def test_something():
    ...
```

### Static vs Runtime Checking

| Method | Command | Runs Tests | Shows Pass/Fail |
|--------|---------|-----------|-----------------|
| Static | `jamb check` | No | No |
| Runtime | `pytest --jamb` | Yes | Yes |

Static checking scans test files for `@pytest.mark.requirement` markers without executing tests. Runtime checking executes tests and records pass/fail status for each linked requirement.

See {doc}`pytest-integration` for full details.
