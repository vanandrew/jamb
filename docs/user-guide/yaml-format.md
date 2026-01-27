# YAML Format Reference

jamb stores all data as YAML files in your git repository. This page documents the format of each file type.

## Item Files (`<UID>.yml`)

Each requirement item is stored as a single YAML file named after its UID (e.g., `SRS001.yml`).

### Fields

```yaml
active: true
derived: false
header: Authentication
reviewed: "a1b2c3d4"
links:
  - uid: SYS001
    hash: "e5f6a7b8"
text: |
  Software shall authenticate users with username and password.
```

`active`
: Whether the item is active. Inactive items are excluded from validation and coverage checks.
: **Type:** `bool`
: **Default:** `true`

`text`
: The requirement statement. Use YAML block scalar (`|`) for multiline text.
: **Type:** `str`
: **Required**

`header`
: Optional short title for the item. Displayed in listings and the traceability matrix.
: **Type:** `str`
: **Default:** (none)

`links`
: List of parent item references. Each link stores the parent UID and a content hash of the parent at the time the link was reviewed.
: **Type:** `list`
: **Default:** `[]`

`reviewed`
: Content hash of the item at the time it was last reviewed. When the item content changes, this hash no longer matches, indicating the item needs re-review.
: **Type:** `str | null`
: **Default:** `null`

`derived`
: Flag indicating this item intentionally does not trace to its document's parent document. Used for requirements that emerge from risk analysis rather than user needs.
: **Type:** `bool`
: **Default:** `false`

`type`
: Item type. Standard items use `requirement`. Headings and informational items use `heading` or `information`.
: **Type:** `str`
: **Default:** `"requirement"`

### Link Format

Links can appear in two forms:

**Simple** (UID string only, no hash tracking):
```yaml
links:
  - SYS001
  - SYS002
```

**Full** (with content hash for suspect link detection):
```yaml
links:
  - uid: SYS001
    hash: "e5f6a7b8"
  - uid: SYS002
    hash: "c3d4e5f6"
```

The hash is a truncated SHA-256 of the parent item's content. When you run `jamb review clear`, the hash is updated to the parent's current content hash. If the parent is later modified, the stored hash no longer matches, making the link **suspect**.

## Document Configuration (`.jamb.yml`)

Each document directory contains a `.jamb.yml` configuration file:

```yaml
prefix: SRS
parents:
  - SYS
digits: 3
sep: ""
```

`prefix`
: The document identifier used as the UID prefix.
: **Required**

`parents`
: List of parent document prefixes. Defines the traceability direction.
: **Default:** `[]` (root document)

`digits`
: Number of digits in the sequential part of item UIDs.
: **Default:** `3`

`sep`
: Separator between prefix and number.
: **Default:** `""` (no separator)

## Import/Export Format

The `jamb export` and `jamb import` commands use a YAML format that includes both documents and items:

```yaml
documents:
  - prefix: UN
    path: un
    digits: 3
  - prefix: SRS
    path: srs
    parents:
      - UN
    digits: 3

items:
  - uid: UN001
    text: User shall be able to log in
    header: Login
  - uid: SRS001
    text: Software shall validate credentials
    header: Authentication
    links:
      - UN001
```

### Document Fields (Import/Export)

`prefix`
: Document identifier. **Required.**

`path`
: Directory path for the document (relative to the requirements root). **Required for new documents.**

`parents`
: List of parent document prefixes. **Default:** `[]`

`digits`
: Number of digits for item UIDs. **Default:** `3`

### Item Fields (Import/Export)

`uid`
: Item identifier. **Required.**

`text`
: Requirement text. **Required.**

`header`
: Optional short title.

`links`
: List of parent item UIDs (simple string form).

`active`
: Whether the item is active. **Default:** `true`

`derived`
: Whether the item is derived. **Default:** `false`

### Import Behavior

- **New items** are created with the specified fields
- **Existing items** are skipped by default; use `--update` to overwrite
- When updating, `text`, `header`, and `links` are replaced; `active` and other fields are preserved
- The `reviewed` hash is cleared on updated items, marking them for re-review
- Use `--dry-run` to preview changes before applying
