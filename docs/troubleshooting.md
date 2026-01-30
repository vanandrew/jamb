# Troubleshooting

This page lists common errors you may encounter when using jamb, organized by source. Each entry includes the error message, its cause, and how to fix it.

## Validation Errors

These errors and warnings are reported by `jamb validate`.

### Link Issues

**"links to non-existent item: \<UID\>"**
: An item references a UID that does not exist in any document.
: **Fix:** Check for typos in the link UID. Run `jamb item list` to see valid UIDs, then update the link with `jamb link remove` and `jamb link add`.

**"links to inactive item: \<UID\>"**
: An item links to a target that has `active: false`.
: **Fix:** Either reactivate the target item by setting `active: true` in its YAML file, or remove the link with `jamb link remove`.

**"links to non-normative item: \<UID\>"**
: An item links to a target whose type is not `requirement` (e.g., `info` or `heading`).
: **Fix:** Change the target item's type to `requirement`, or remove the link if it was unintentional.

**"links to itself"**
: An item has its own UID in its `links` list.
: **Fix:** Remove the self-referencing link with `jamb link remove <UID> <UID>`.

**"links to \<UID\> in document \<PREFIX\>, which is not a parent document (expected: \<PARENTS\>)"**
: An item links to a target in a document that is not a parent of the item's document in the DAG.
: **Fix:** Ensure the link points to an item in a valid parent document. If you need a cross-hierarchy link, adjust the document DAG with `jamb doc create` to add the target document as a parent.

### Suspect Links

**"suspect link to \<UID\> (content may have changed; run 'jamb review clear' to re-verify)"**
: The content hash stored in the link no longer matches the current content of the target item. The target was modified after the link was last verified.
: **Fix:** Review the change to the target item, then clear the suspect status:
  ```bash
  jamb review clear <CHILD_UID> <PARENT_UID>
  ```

**"link to \<UID\> has no stored hash (run 'jamb review clear' to verify links)"**
: A link exists but has no content hash recorded, so jamb cannot verify whether the target has changed.
: **Fix:** Run `jamb review clear <UID>` to compute and store hashes for all links on the item.

### Review Status

**"has not been reviewed (run 'jamb review mark' to mark as reviewed)"**
: A normative item has never been marked as reviewed.
: **Fix:** Review the item content and mark it:
  ```bash
  jamb review mark <UID>
  ```

**"has been modified since last review (run 'jamb review mark' to re-approve)"**
: An item's content has changed since it was last reviewed (the stored review hash no longer matches).
: **Fix:** Re-review the item and mark it again:
  ```bash
  jamb review mark <UID>
  ```

### Document Structure

**"has no children linking to it from child documents"**
: A normative item in a non-leaf document has no items in child documents linking to it. This may indicate incomplete decomposition.
: **Fix:** Create child items that link to this item, or skip the check with `jamb validate -C`.

**"document contains no items"**
: A document directory exists but contains no item YAML files.
: **Fix:** Add items with `jamb item add <PREFIX>`, or remove the empty document with `jamb doc delete <PREFIX>`.

**"has empty text"**
: An active item has no text content (empty string or whitespace only).
: **Fix:** Edit the item to add text: `jamb item edit <UID>`.

**"normative non-derived item has no links to parent document (add links or set 'derived: true' to suppress)"**
: An active requirement in a child document has no links to any parent document.
: **Fix:** Add a link to a parent item with `jamb link add <UID> <PARENT_UID>`, or set `derived: true` in the item's YAML file if the requirement intentionally has no parent.

**"cycle in item links: \<UID\> -> ... -> \<UID\>"**
: A cycle was detected in the item link graph (items form a circular dependency).
: **Fix:** Remove one of the links in the cycle with `jamb link remove` to break the loop.

**"Cycle detected among documents: \<PREFIXES\>"**
: The document hierarchy contains a cycle (e.g., document A is a parent of B and B is a parent of A).
: **Fix:** Recreate one of the documents with corrected parent relationships using `jamb doc delete` and `jamb doc create`.

**"non-normative item has links"**
: An item with type `info` or `heading` has links to parent items. Only `requirement` items should have traceability links.
: **Fix:** Either change the item type to `requirement` or remove its links.

## CLI Errors

These errors are printed by `jamb` commands.

**"Error: Document '\<PREFIX\>' not found"**
: The specified document prefix does not exist in the project.
: **Fix:** Run `jamb doc list` to see available documents. Check for typos or create the document with `jamb doc create`.

**"Error: Item '\<UID\>' not found"**
: The specified item UID does not exist.
: **Fix:** Run `jamb item list` to see available items. Check for typos in the UID.

**"Error: --after and --before are mutually exclusive"**
: Both `--after` and `--before` were passed to `jamb item add`.
: **Fix:** Use only one of `--after` or `--before`.

**"Error: --html requires an output PATH" / "--markdown requires an output PATH" / "--docx requires an output PATH"**
: A format flag was used with `jamb publish` but no output path was provided.
: **Fix:** Provide an output path, e.g. `jamb publish SRS output.html --html`.

**"Error: 'all' requires an output PATH"**
: `jamb publish all` was called without a format flag or output path.
: **Fix:** Provide both a path and format, e.g. `jamb publish all docs/all.html --html`.

**"Error: --neighbors requires --items to be specified"**
: The `--neighbors` flag was used with `jamb export` without specifying `--items`.
: **Fix:** Add `--items` to specify which items to include neighbors for.

## Test Reference Issues

These issues relate to `@pytest.mark.requirement()` decorators in test files.

**"Unknown items referenced in tests: SRS001, SRS002"**
: Test files reference requirement UIDs that don't exist in your documents. This can happen when:
  - Requirements were deleted but tests weren't updated
  - Typos in requirement UIDs
  - Requirements were reordered without updating tests
: **Fix:** Update your test files to use valid UIDs. Run `jamb check` to see which UIDs are referenced.

**"WARNING: SRS001 is referenced by N test(s)"**
: When removing an item with `jamb item remove`, jamb warns you that tests reference this item.
: **Fix:** Proceed with removal if intended, then update your test files to remove the orphaned references. Use `--force` to skip the confirmation prompt.

**Orphaned test references after reorder**
: If you used `jamb reorder --no-update-tests`, test files may reference old UIDs that no longer exist.
: **Fix:** Either:
  - Re-run reorder without `--no-update-tests` to let jamb update test files automatically
  - Manually update the `@pytest.mark.requirement()` decorators in your test files

## pytest Integration Errors

These errors occur when running `pytest --jamb`.

**"Cannot run with --jamb: requirement graph failed to load. Check earlier warnings for details."**
: The requirement documents could not be loaded. This typically happens when:
  - No `reqs/` directory exists (run `jamb init` first)
  - Document `.jamb.yml` files are malformed or missing
  - YAML syntax errors in item files
: **Fix:** Check the warning messages above this error for the specific cause. Common fixes:
  ```bash
  # Initialize a new project if not already done
  jamb init

  # Validate your documents to find issues
  jamb validate

  # Check document structure
  jamb info
  ```

## Configuration Errors

These errors come from loading `.jamb.yml` document config files.

**"Invalid config file: \<path\>"**
: The `.jamb.yml` file is missing or does not contain a `settings` key.
: **Fix:** Ensure the file exists and contains a valid `settings` section. Recreate the document with `jamb doc create` if needed.

**"Config file missing 'prefix': \<path\>"**
: The `.jamb.yml` file has a `settings` section but no `prefix` field.
: **Fix:** Add a `prefix` field to the `settings` section in `.jamb.yml`, or recreate the document with `jamb doc create`.

## Import Errors

These errors come from `jamb import`.

**"YAML file must contain a mapping"**
: The import file is not a YAML mapping (dictionary). It may be a list, a scalar, or invalid YAML.
: **Fix:** Ensure the file starts with `documents:` and/or `items:` top-level keys. Run `jamb import --template` for a valid example.

**"Document missing 'prefix': ..." / "Document missing 'path': ..."**
: A document entry in the import file is missing a required field.
: **Fix:** Add the missing `prefix` or `path` field to the document entry.

**"Item missing 'uid': ..." / "Item missing 'text': ..."**
: An item entry in the import file is missing a required field.
: **Fix:** Add the missing `uid` or `text` field to the item entry.

**"Duplicate UIDs in import file: \<UIDs\>"**
: The import file contains multiple items with the same UID.
: **Fix:** Remove or rename duplicate entries so each UID is unique.

## Matrix Generation Warnings

These warnings are reported when generating traceability or test records matrices.

**"Orphaned items in coverage not found in graph: ['SRS001', 'SRS002'] and N more"**
: The `.jamb` coverage file contains items that no longer exist in your requirement documents. This can happen when:
  - Requirements were deleted after running tests
  - Item UIDs were renamed
  - The wrong `.jamb` file is being used
: **Fix:** Regenerate the coverage file by running `pytest --jamb` again.

**"trace_from 'XXX' not found in documents"**
: The `trace_from` configuration option references a document prefix that doesn't exist in your project.
: **Fix:** Check your `pyproject.toml` and ensure `trace_from` matches one of your document prefixes (e.g., UN, SYS, SRS). Run `jamb doc list` to see available documents.

**"Large dataset warning: N rows. Consider using CSV format for better performance."**
: The matrix being generated contains more than 5,000 rows. HTML and XLSX formats may be slow to generate and consume significant memory for large datasets.
: **Fix:** Use a `.csv` extension for large matrices (e.g., `--jamb-trace-matrix matrix.csv`), or use `jamb matrix output.csv` to generate CSV format.
