# Concepts

This page explains the core concepts behind jamb and how they map to IEC 62304 requirements traceability.

## IEC 62304 Context

[IEC 62304](https://en.wikipedia.org/wiki/IEC_62304) is the international standard governing the software lifecycle processes for medical device software. It defines the activities, tasks, and documentation required at each stage of development — from planning and requirements analysis through architecture, implementation, testing, release, and maintenance. The standard assigns one of three safety classifications to software systems: **Class A** (no injury possible), **Class B** (non-serious injury possible), and **Class C** (serious injury or death possible). The required rigour of lifecycle activities scales with the classification, with Class C demanding the most comprehensive documentation and verification.

A central theme of IEC 62304 is **bidirectional traceability**: every software requirement must trace upward to a system requirement or risk control, and every requirement must trace downward to verification evidence (tests). The standard also requires **change impact analysis** — when an upstream requirement changes, all affected downstream artefacts must be reviewed — and **risk management integration**, ensuring that software items linked to hazard mitigations are identified and verified. These traceability and change-control obligations make tooling support essential for any non-trivial project.

jamb implements these requirements as a lightweight, git-native tool that integrates directly with pytest. For a comprehensive overview of IEC 62304 and how jamb supports its traceability requirements, see the {doc}`/iec-62304/index` guide.

## Document Hierarchy

jamb organizes requirements into **documents**, each identified by a prefix (e.g., `SRS`, `SYS`, `UN`). Documents form a directed acyclic graph (DAG) where parent-child relationships define the traceability direction.

The default IEC 62304 hierarchy created by `jamb init`:

```
`-- PRJ
    |-- HAZ (parents: PRJ)
    |   `-- RC (parents: HAZ)
    |       `-- SRS (parents: SYS, RC)
    `-- UN (parents: PRJ)
        `-- SYS (parents: UN)
            `-- SRS (parents: SYS, RC)
```

Each document lives in its own directory and contains a `.jamb.yml` configuration file (defining the prefix, parent documents, and UID formatting) alongside individual YAML files for each item (e.g., `SRS001.yml`, `SRS002.yml`).

### Custom Hierarchies

You can create custom document hierarchies using `jamb doc create`:

```bash
# Create documents
jamb doc create SYS reqs/sys
jamb doc create RC reqs/rc --parent HAZ

# A document can have multiple parents (--parent is repeatable)
jamb doc create SRS reqs/srs --parent SYS --parent RC
```

## Items and Types

An **item** is a single requirement, hazard, risk control, or other traceable entity. Every item is identified by a **UID** (e.g., `SRS001`), composed of the document prefix and a sequential number. The item's **text** holds the requirement statement, and an optional **header** provides a short title for listings and the traceability matrix. **Links** are references to parent items in upstream documents. The **active** flag controls whether the item participates in validation and coverage checks, **reviewed** stores a content hash indicating when the item was last reviewed, and **derived** marks requirements that intentionally don't trace to a parent document (see below).

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

Use `derived: true` for requirements that originate from risk or hazard analysis, security hardening requirements, defensive coding requirements, or any requirement that implements a risk control without a corresponding system requirement.

## Traceability Graph

jamb builds a full traceability graph from all documents and their items. The graph drives validation (checking for broken links, cycles, and orphan items), coverage analysis (determining which requirements have linked tests), matrix generation (producing traceability matrices with test status), and impact analysis (determining which downstream items are affected by a change).

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
