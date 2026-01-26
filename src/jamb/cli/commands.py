"""CLI commands for jamb."""

import ast
import subprocess
import sys
from pathlib import Path

import click


def _run_doorstop(*args: str) -> int:
    """Run a doorstop command, passing through all arguments.

    Args:
        *args: Command arguments to pass to doorstop.

    Returns:
        The exit code from the doorstop command.
    """
    cmd = ["doorstop", *args]
    result = subprocess.run(cmd)
    return result.returncode


@click.group()
@click.version_option()
def cli() -> None:
    """jamb - IEC 62304 requirements traceability for pytest."""
    pass


@cli.command()
def init() -> None:
    """Initialize a new jamb project with default IEC 62304 documents.

    Creates a 'reqs' folder with PRJ, UN, SYS, SRS, HAZ, and RC documents
    in the standard medical device traceability hierarchy:

    \b
      PRJ (Project Requirements) - root
      ├── UN (User Needs)
      │   └── SYS (System Requirements)
      │       └── SRS (Software Requirements Specification)
      └── HAZ (Hazards)
          └── RC (Risk Controls)

    If pyproject.toml exists, adds [tool.jamb] configuration.
    """
    reqs_dir = Path.cwd() / "reqs"

    # Check if reqs folder already exists with documents
    if reqs_dir.exists():
        existing_docs = []
        for doc_name in ["prj", "un", "sys", "srs", "haz", "rc"]:
            doc_path = reqs_dir / doc_name
            if doc_path.exists() and (doc_path / ".doorstop.yml").exists():
                existing_docs.append(doc_name.upper())
        if existing_docs:
            click.echo(
                f"Error: Documents already exist: {', '.join(existing_docs)}",
                err=True,
            )
            click.echo(
                "Remove existing documents or use a different directory.", err=True
            )
            sys.exit(1)

    # Create reqs directory
    reqs_dir.mkdir(exist_ok=True)
    click.echo(f"Created directory: {reqs_dir}")

    # Create documents using doorstop
    documents = [
        ("PRJ", "reqs/prj", None),
        ("UN", "reqs/un", "PRJ"),
        ("SYS", "reqs/sys", "UN"),
        ("SRS", "reqs/srs", "SYS"),
        ("HAZ", "reqs/haz", "PRJ"),
        ("RC", "reqs/rc", "HAZ"),
    ]

    for prefix, path, parent in documents:
        args = ["create", prefix, path, "--digits", "3"]
        if parent:
            args.extend(["--parent", parent])

        result = _run_doorstop(*args)
        if result != 0:
            click.echo(f"Error: Failed to create {prefix} document", err=True)
            sys.exit(result)
        click.echo(f"Created document: {prefix} at {path}")

    # Update pyproject.toml if it exists
    pyproject_path = Path.cwd() / "pyproject.toml"
    if pyproject_path.exists():
        _add_jamb_config_to_pyproject(pyproject_path)

    click.echo("\nInitialization complete!")
    click.echo("Run 'jamb info' to see your document structure.")


def _add_jamb_config_to_pyproject(pyproject_path: Path) -> None:
    """Add [tool.jamb] section to pyproject.toml if it doesn't exist."""
    from typing import cast

    import tomlkit
    from tomlkit import TOMLDocument
    from tomlkit.items import Table

    try:
        content = pyproject_path.read_text()
        doc = cast(TOMLDocument, tomlkit.parse(content))

        # Check if [tool.jamb] already exists
        if "tool" in doc and "jamb" in cast(Table, doc["tool"]):
            click.echo(
                "pyproject.toml already has [tool.jamb] configuration, skipping."
            )
            return

        # Add [tool] section if it doesn't exist
        if "tool" not in doc:
            doc["tool"] = tomlkit.table()

        # Add [tool.jamb] section
        jamb_config = tomlkit.table()
        jamb_config["test_documents"] = ["SRS", "SYS"]
        jamb_config["trace_to_ignore"] = ["PRJ"]
        cast(Table, doc["tool"])["jamb"] = jamb_config

        # Write back
        pyproject_path.write_text(tomlkit.dumps(doc))
        click.echo("Added [tool.jamb] configuration to pyproject.toml")

    except Exception as e:
        click.echo(f"Warning: Could not update pyproject.toml: {e}", err=True)


@cli.command("info")
@click.option(
    "--documents",
    "-d",
    help="Comma-separated test document prefixes to check",
)
@click.option(
    "--root",
    type=click.Path(exists=True, path_type=Path),
    help="Project root directory",
)
def info(documents: str | None, root: Path | None) -> None:
    """Display doorstop document information.

    Shows document structure, hierarchy, and item counts.
    """
    from jamb.doorstop.discovery import discover_tree

    _ = documents  # Reserved for future filtering functionality

    try:
        tree = discover_tree(root)
        click.echo(f"Found doorstop tree with {len(tree.documents)} documents:")
        for doc in tree.documents:
            parent = doc.parent or "(root)"
            count = sum(1 for item in doc if item.active)
            click.echo(f"  - {doc.prefix}: {count} active items (parent: {parent})")

        # Show hierarchy
        click.echo("\nDocument hierarchy:")
        _print_hierarchy(tree)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def _print_hierarchy(tree, prefix: str = "", doc=None) -> None:
    """Print document hierarchy as a tree."""
    if doc is None:
        # Find root documents
        roots = [d for d in tree.documents if d.parent is None]
        for i, root_doc in enumerate(roots):
            is_last = i == len(roots) - 1
            click.echo(f"{prefix}{'`-- ' if is_last else '|-- '}{root_doc.prefix}")
            _print_hierarchy(tree, prefix + ("    " if is_last else "|   "), root_doc)
    else:
        # Find children of this document
        children = [d for d in tree.documents if d.parent == doc.prefix]
        for i, child in enumerate(children):
            is_last = i == len(children) - 1
            click.echo(f"{prefix}{'`-- ' if is_last else '|-- '}{child.prefix}")
            _print_hierarchy(tree, prefix + ("    " if is_last else "|   "), child)


@cli.command()
@click.option(
    "--documents",
    "-d",
    help="Comma-separated test document prefixes to check",
)
@click.option(
    "--root",
    type=click.Path(exists=True, path_type=Path),
    help="Project root directory",
)
def check(documents: str | None, root: Path | None) -> None:
    """Check test coverage without running tests.

    Scans test files for @pytest.mark.requirement markers and
    reports which doorstop items have linked tests.

    Note: This does a static scan and doesn't run tests.
    For full coverage including test outcomes, use pytest --jamb.
    """
    from jamb.config.loader import load_config
    from jamb.doorstop.discovery import discover_tree
    from jamb.doorstop.reader import build_traceability_graph

    try:
        tree = discover_tree(root)
        graph = build_traceability_graph(tree)
        config = load_config()

        # Determine test documents to check
        if documents:
            test_docs = [d.strip() for d in documents.split(",")]
        elif config.test_documents:
            test_docs = config.test_documents
        else:
            test_docs = graph.get_leaf_documents()

        click.echo(f"Checking coverage for documents: {', '.join(test_docs)}")

        # Scan test files for requirement markers
        linked_items = _scan_tests_for_requirements(root or Path.cwd())
        click.echo(f"Found {len(linked_items)} unique item references in test files")

        # Check coverage
        uncovered = []
        for prefix in test_docs:
            for item in graph.get_items_by_document(prefix):
                if item.normative and item.active and item.uid not in linked_items:
                    uncovered.append(item)

        if uncovered:
            click.echo(f"\nFound {len(uncovered)} uncovered items:", err=True)
            for item in uncovered:
                click.echo(f"  - {item.uid}: {item.display_text}", err=True)
            sys.exit(1)
        else:
            total = sum(len(graph.get_items_by_document(p)) for p in test_docs)
            click.echo(f"\nAll {total} items in test documents have linked tests.")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def _scan_tests_for_requirements(root: Path) -> set[str]:
    """Scan test files for requirement markers."""
    import ast

    linked: set[str] = set()

    # Find test files
    for test_file in root.rglob("test_*.py"):
        try:
            source = test_file.read_text()
            tree = ast.parse(source)

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    # Look for pytest.mark.requirement(...)
                    if _is_requirement_marker(node):
                        for arg in node.args:
                            if isinstance(arg, ast.Constant) and isinstance(
                                arg.value, str
                            ):
                                linked.add(arg.value)
        except Exception:
            pass  # Skip files that can't be parsed

    return linked


def _is_requirement_marker(node: ast.Call) -> bool:
    """Check if an AST Call node is a pytest.mark.requirement call."""
    func = node.func

    # @pytest.mark.requirement(...)
    if isinstance(func, ast.Attribute) and func.attr == "requirement":
        if isinstance(func.value, ast.Attribute) and func.value.attr == "mark":
            if (
                isinstance(func.value.value, ast.Name)
                and func.value.value.id == "pytest"
            ):
                return True

    return False


# =============================================================================
# Document Management Commands
# =============================================================================


@cli.group()
def doc() -> None:
    """Manage doorstop documents."""
    pass


@doc.command("create")
@click.argument("prefix")
@click.argument("path")
@click.option("--parent", "-p", help="Parent document prefix")
@click.option(
    "--digits", "-d", default=3, type=int, help="Number of digits for item IDs"
)
@click.option("--sep", "-s", default="", help="Separator between prefix and number")
def doc_create(
    prefix: str, path: str, parent: str | None, digits: int, sep: str
) -> None:
    """Create a new document.

    PREFIX is the document identifier (e.g., SRS, UT).
    PATH is the directory where the document will be created.
    """
    args = ["create", prefix, path, "--digits", str(digits)]
    if parent:
        args.extend(["--parent", parent])
    if sep:
        args.extend(["--sep", sep])
    sys.exit(_run_doorstop(*args))


@doc.command("delete")
@click.argument("prefix")
def doc_delete(prefix: str) -> None:
    """Delete a document.

    PREFIX is the document identifier to delete (e.g., SRS, UT).
    """
    sys.exit(_run_doorstop("delete", prefix))


@doc.command("list")
@click.option(
    "--root",
    type=click.Path(exists=True, path_type=Path),
    help="Project root directory",
)
def doc_list(root: Path | None) -> None:
    """List all documents in the tree."""
    from jamb.doorstop.discovery import discover_tree

    try:
        tree = discover_tree(root)
        click.echo(f"Found {len(tree.documents)} documents:")
        for doc in tree.documents:
            parent = doc.parent or "(root)"
            count = sum(1 for item in doc if item.active)
            click.echo(f"  {doc.prefix}: {count} active items (parent: {parent})")

        click.echo("\nHierarchy:")
        _print_hierarchy(tree)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@doc.command("reorder")
@click.argument("prefix")
@click.option("--auto", "-a", is_flag=True, help="Automatically reorder items")
@click.option("--manual", "-m", is_flag=True, help="Manually reorder items")
def doc_reorder(prefix: str, auto: bool, manual: bool) -> None:
    """Reorder items in a document.

    PREFIX is the document identifier (e.g., SRS, UT).
    """
    args = ["reorder", prefix]
    if auto:
        args.append("--auto")
    if manual:
        args.append("--manual")
    sys.exit(_run_doorstop(*args))


# =============================================================================
# Item Management Commands
# =============================================================================


@cli.group()
def item() -> None:
    """Manage doorstop items."""
    pass


@item.command("add")
@click.argument("prefix")
@click.option("--level", "-l", help="Item level (e.g., 1.2)")
@click.option("--count", "-c", default=1, type=int, help="Number of items to add")
def item_add(prefix: str, level: str | None, count: int) -> None:
    """Add a new item to a document.

    PREFIX is the document to add the item to (e.g., SRS, UT).
    """
    args = ["add", prefix]
    if level:
        args.extend(["--level", level])
    if count > 1:
        args.extend(["--count", str(count)])
    sys.exit(_run_doorstop(*args))


@item.command("list")
@click.argument("prefix", required=False)
@click.option(
    "--root",
    type=click.Path(exists=True, path_type=Path),
    help="Project root directory",
)
def item_list(prefix: str | None, root: Path | None) -> None:
    """List items in a document or all documents.

    PREFIX is optional - if provided, only list items in that document.
    """
    from jamb.doorstop.discovery import discover_tree

    try:
        tree = discover_tree(root)

        if prefix:
            # List items in specific document
            doc = tree.find_document(prefix)
            docs = [doc]
        else:
            # List all documents
            docs = tree.documents

        for doc in docs:
            items = [item for item in doc if item.active]
            if items:
                click.echo(f"\n{doc.prefix} ({len(items)} items):")
                for item in items:
                    text = item.text[:60] + "..." if len(item.text) > 60 else item.text
                    text = text.replace("\n", " ").strip()
                    click.echo(f"  {item.uid}: {text}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@item.command("remove")
@click.argument("uid")
def item_remove(uid: str) -> None:
    """Remove an item by UID.

    UID is the item identifier (e.g., SRS001, UT002).
    """
    sys.exit(_run_doorstop("remove", uid))


@item.command("edit")
@click.argument("uid")
@click.option(
    "--tool",
    "-T",
    help="Text editor to use (default: $EDITOR or vim)",
)
def item_edit(uid: str, tool: str | None) -> None:
    """Edit an item in the default editor.

    UID is the item identifier (e.g., SRS001, UT002).
    """
    args = ["edit", uid]
    if tool:
        args.extend(["--tool", tool])
    sys.exit(_run_doorstop(*args))


@item.command("show")
@click.argument("uid")
def item_show(uid: str) -> None:
    """Display item details.

    UID is the item identifier (e.g., SRS001, UT002).
    """
    from jamb.doorstop.discovery import discover_tree

    try:
        tree = discover_tree()
        found_item = tree.find_item(uid)

        click.echo(f"UID: {found_item.uid}")
        click.echo(f"Document: {found_item.document.prefix}")
        click.echo(f"Active: {found_item.active}")
        click.echo(f"Normative: {found_item.normative}")
        click.echo(f"Level: {found_item.level}")
        if found_item.header:
            click.echo(f"Header: {found_item.header}")
        if found_item.links:
            click.echo(f"Links: {', '.join(str(link) for link in found_item.links)}")
        click.echo(f"\nText:\n{found_item.text}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@item.command("import")
@click.argument("prefix")
@click.argument("path")
@click.option("--file", "-f", "file_path", help="Path to import file")
@click.option(
    "--map", "-m", "mapping", help="Column mapping (e.g., 'text=Description')"
)
def item_import(
    prefix: str, path: str, file_path: str | None, mapping: str | None
) -> None:
    """Import items from a file.

    PREFIX is the document to import into.
    PATH is the path to the import file (CSV, TSV, XLSX).
    """
    args = ["import", prefix, path]
    if file_path:
        args.extend(["--file", file_path])
    if mapping:
        args.extend(["--map", mapping])
    sys.exit(_run_doorstop(*args))


@item.command("export")
@click.argument("prefix")
@click.argument("path")
@click.option("--xlsx", is_flag=True, help="Export as Excel file")
@click.option("--csv", is_flag=True, help="Export as CSV file")
def item_export(prefix: str, path: str, xlsx: bool, csv: bool) -> None:
    """Export items to a file.

    PREFIX is the document to export.
    PATH is the output file path.
    """
    args = ["export", prefix, path]
    if xlsx:
        args.append("--xlsx")
    if csv:
        args.append("--csv")
    sys.exit(_run_doorstop(*args))


# =============================================================================
# Link Management Commands
# =============================================================================


@cli.group()
def link() -> None:
    """Manage item links."""
    pass


@link.command("add")
@click.argument("child")
@click.argument("parent")
def link_add(child: str, parent: str) -> None:
    """Link a child item to a parent item.

    CHILD is the child item UID (e.g., SRS001).
    PARENT is the parent item UID (e.g., SYS001).
    """
    sys.exit(_run_doorstop("link", child, parent))


@link.command("remove")
@click.argument("child")
@click.argument("parent")
def link_remove(child: str, parent: str) -> None:
    """Remove a link between items.

    CHILD is the child item UID (e.g., SRS001).
    PARENT is the parent item UID (e.g., SYS001).
    """
    sys.exit(_run_doorstop("unlink", child, parent))


# =============================================================================
# Review Management Commands
# =============================================================================


@cli.group()
def review() -> None:
    """Manage item reviews."""
    pass


@review.command("mark")
@click.argument("label")
def review_mark(label: str) -> None:
    """Mark an item as reviewed.

    LABEL is an item UID, document prefix, or 'all'.

    \b
    Examples:
        jamb review mark SRS001   # Mark single item
        jamb review mark SRS      # Mark all items in SRS document
        jamb review mark all      # Mark all items in all documents
    """
    sys.exit(_run_doorstop("review", label))


@review.command("clear")
@click.argument("label")
@click.argument("parents", nargs=-1)
def review_clear(label: str, parents: tuple[str, ...]) -> None:
    """Absolve items of their suspect link status.

    LABEL is an item UID, document prefix, or 'all'.
    PARENTS optionally limits clearing to links with specific parent UIDs.

    \b
    Examples:
        jamb review clear SRS001        # Clear suspect links on single item
        jamb review clear SRS           # Clear suspect links in SRS document
        jamb review clear all           # Clear all suspect links
        jamb review clear SRS001 CUS001 # Clear only link to CUS001
    """
    args = ["clear", label]
    args.extend(parents)
    sys.exit(_run_doorstop(*args))


@review.command("reset")
@click.argument("label")
@click.option(
    "--root",
    type=click.Path(exists=True, path_type=Path),
    help="Project root directory",
)
def review_reset(label: str, root: Path | None) -> None:
    """Reset items to unreviewed status.

    LABEL is an item UID, document prefix, or 'all'.

    \b
    Examples:
        jamb review reset SRS001   # Reset single item
        jamb review reset SRS      # Reset all items in SRS document
        jamb review reset all      # Reset all items in all documents
    """
    from jamb.doorstop.discovery import discover_tree

    try:
        tree = discover_tree(root)

        # Determine which items to reset
        items_to_reset = []
        if label.lower() == "all":
            for doc in tree.documents:
                items_to_reset.extend(doc)
        else:
            # Try as document prefix first
            try:
                doc = tree.find_document(label)
                items_to_reset.extend(doc)
            except Exception:
                # Try as item UID
                try:
                    item = tree.find_item(label)
                    items_to_reset.append(item)
                except Exception:
                    click.echo(
                        f"Error: '{label}' is not a valid item or document", err=True
                    )
                    sys.exit(1)

        # Reset each item
        count = 0
        for item in items_to_reset:
            if item.reviewed:
                item.reviewed = None
                item.save()
                click.echo(f"reset item {item.uid} to unreviewed")
                count += 1

        if count == 0:
            click.echo("no items needed resetting")
        else:
            click.echo(f"reset {count} items to unreviewed")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# =============================================================================
# Publish Command (doorstop passthrough)
# =============================================================================


@cli.command()
@click.argument("prefix")
@click.argument("path", required=False)
@click.option("--html", "-H", is_flag=True, help="Output HTML")
@click.option("--markdown", "-m", is_flag=True, help="Output Markdown")
@click.option("--latex", "-l", is_flag=True, help="Output LaTeX")
@click.option("--text", "-t", is_flag=True, help="Output text (default when no path)")
@click.option("--docx", "-d", is_flag=True, help="Output DOCX (Word document)")
@click.option("--template", help="Template file for custom formatting")
@click.option(
    "--no-child-links", "-C", is_flag=True, help="Do not include child links on items"
)
def publish(
    prefix: str,
    path: str | None,
    html: bool,
    markdown: bool,
    latex: bool,
    text: bool,
    docx: bool,
    template: str | None,
    no_child_links: bool,
) -> None:
    """Publish a document.

    PREFIX is the document prefix (e.g., SRS) or 'all' for all documents.
    PATH is the output file or directory (optional).

    For a traceability matrix with test coverage, use: pytest --jamb --jamb-matrix PATH
    """
    # Handle DOCX export (custom jamb functionality)
    if docx:
        if not path:
            click.echo(
                "Error: --docx requires an output PATH",
                err=True,
            )
            click.echo("Example: jamb publish SRS output.docx --docx", err=True)
            sys.exit(1)

        _publish_docx(prefix, path, not no_child_links)
        return

    # Validate: "all" requires an output path (doorstop limitation)
    if prefix.lower() == "all" and not path:
        click.echo(
            "Error: 'all' requires an output PATH "
            "(doorstop cannot display multiple documents to terminal)",
            err=True,
        )
        click.echo("Example: jamb publish all ./docs --html", err=True)
        sys.exit(1)

    args = ["publish", prefix]
    if path:
        args.append(path)
    if html:
        args.append("--html")
    if markdown:
        args.append("--markdown")
    if latex:
        args.append("--latex")
    if text:
        args.append("--text")
    if template:
        args.extend(["--template", template])
    if no_child_links:
        args.append("--no-child-links")
    sys.exit(_run_doorstop(*args))


def _get_document_hierarchy_order(tree) -> list[str]:
    """Get document prefixes in hierarchy order.

    Returns prefixes in depth-first order, with parents before children.
    """
    order = []
    docs_by_parent: dict[str | None, list] = {}

    # Group documents by parent
    for doc in tree.documents:
        parent = doc.parent if doc.parent else None
        if parent not in docs_by_parent:
            docs_by_parent[parent] = []
        docs_by_parent[parent].append(doc)

    # DFS traversal - keeps each branch together
    def visit(prefix: str | None) -> None:
        children = docs_by_parent.get(prefix, [])
        for doc in children:
            order.append(doc.prefix)
            visit(doc.prefix)

    visit(None)  # Start from roots
    return order


def _publish_docx(prefix: str, path: str, include_child_links: bool) -> None:
    """Publish documents as a single DOCX file.

    Args:
        prefix: Document prefix or 'all' for all documents.
        path: Output file path.
        include_child_links: Whether to include child links.
    """
    from jamb.doorstop.discovery import discover_tree
    from jamb.doorstop.reader import read_tree
    from jamb.publish.formats.docx import render_docx

    try:
        tree = discover_tree()
        output_path = Path(path)

        # Get document hierarchy order
        doc_order = _get_document_hierarchy_order(tree)

        if prefix.lower() == "all":
            # Export all documents to a single file
            items = read_tree(tree)
            title = "Requirements Document"
        else:
            # Export single document
            items = read_tree(tree, [prefix])
            title = f"{prefix} Requirements Document"

        if not items:
            click.echo(f"Error: No items found for '{prefix}'", err=True)
            sys.exit(1)

        docx_bytes = render_docx(items, title, include_child_links, doc_order)
        output_path.write_bytes(docx_bytes)
        click.echo(f"Published to {output_path}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# =============================================================================
# Doorstop Passthrough Command
# =============================================================================


@cli.command("validate")
@click.option(
    "--verbose",
    "-v",
    count=True,
    help="Enable verbose logging (can be repeated)",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    help="Only display errors and prompts",
)
@click.option(
    "--no-reformat",
    "-F",
    is_flag=True,
    help="Do not reformat item files during validation",
)
@click.option(
    "--reorder",
    "-r",
    is_flag=True,
    help="Reorder document levels during validation",
)
@click.option(
    "--no-level-check",
    "-L",
    is_flag=True,
    help="Do not validate document levels",
)
@click.option(
    "--no-ref-check",
    "-R",
    is_flag=True,
    help="Do not validate external file references",
)
@click.option(
    "--no-child-check",
    "-C",
    is_flag=True,
    help="Do not validate child (reverse) links",
)
@click.option(
    "--strict-child-check",
    "-Z",
    is_flag=True,
    help="Require child (reverse) links from every document",
)
@click.option(
    "--no-suspect-check",
    "-S",
    is_flag=True,
    help="Do not check for suspect links",
)
@click.option(
    "--no-review-check",
    "-W",
    is_flag=True,
    help="Do not check item review status",
)
@click.option(
    "--skip",
    "-s",
    "skip_prefix",
    multiple=True,
    help="Skip a document during validation (can be repeated)",
)
@click.option(
    "--warn-all",
    "-w",
    is_flag=True,
    help="Display all info-level issues as warnings",
)
@click.option(
    "--error-all",
    "-e",
    is_flag=True,
    help="Display all warning-level issues as errors",
)
def validate(
    verbose: int,
    quiet: bool,
    no_reformat: bool,
    reorder: bool,
    no_level_check: bool,
    no_ref_check: bool,
    no_child_check: bool,
    strict_child_check: bool,
    no_suspect_check: bool,
    no_review_check: bool,
    skip_prefix: tuple[str, ...],
    warn_all: bool,
    error_all: bool,
) -> None:
    """Validate the requirements tree.

    \b
    Runs doorstop validation to check for issues like:
      - Missing parent documents
      - Suspect links (items needing re-review)
      - Items without required links

    \b
    Examples:
        jamb validate              # Run validation
        jamb validate -v           # Verbose output
        jamb validate --skip UT    # Skip unit test document
        jamb validate -F -S        # Skip reformatting and suspect checks
    """
    args: list[str] = []
    for _ in range(verbose):
        args.append("--verbose")
    if quiet:
        args.append("--quiet")
    if no_reformat:
        args.append("--no-reformat")
    if reorder:
        args.append("--reorder")
    if no_level_check:
        args.append("--no-level-check")
    if no_ref_check:
        args.append("--no-ref-check")
    if no_child_check:
        args.append("--no-child-check")
    if strict_child_check:
        args.append("--strict-child-check")
    if no_suspect_check:
        args.append("--no-suspect-check")
    if no_review_check:
        args.append("--no-review-check")
    for prefix in skip_prefix:
        args.extend(["--skip", prefix])
    if warn_all:
        args.append("--warn-all")
    if error_all:
        args.append("--error-all")

    sys.exit(_run_doorstop(*args))


# =============================================================================
# Import/Export Commands
# =============================================================================


@cli.command("export")
@click.argument("output", type=click.Path(path_type=Path))
@click.option(
    "--documents",
    "-d",
    help="Comma-separated document prefixes to export (default: all)",
)
@click.option(
    "--items",
    "-i",
    help="Comma-separated item UIDs to export (e.g., SRS001,SRS002)",
)
@click.option(
    "--neighbors",
    "-n",
    is_flag=True,
    help="Include ancestors and descendants of specified items (requires --items)",
)
@click.option(
    "--root",
    type=click.Path(exists=True, path_type=Path),
    help="Project root directory",
)
def export_yaml(
    output: Path,
    documents: str | None,
    items: str | None,
    neighbors: bool,
    root: Path | None,
) -> None:
    """Export documents and items to a YAML file.

    OUTPUT is the path to write the YAML file.

    \b
    Examples:
        jamb export requirements.yml
        jamb export reqs.yml --documents SRS,SYS
        jamb export output.yml --items SRS001,SRS002
        jamb export output.yml --items SRS001 --neighbors
        jamb export output.yml --items SRS001 --neighbors --documents SRS,SYS
    """
    from jamb.doorstop.discovery import discover_tree
    from jamb.yaml_io import export_items_to_yaml, export_to_yaml

    # Validate: --neighbors requires --items
    if neighbors and not items:
        click.echo("Error: --neighbors requires --items to be specified", err=True)
        sys.exit(1)

    try:
        tree = discover_tree(root)

        prefixes = None
        if documents:
            prefixes = [d.strip() for d in documents.split(",")]

        if items:
            # Export specific items (with optional neighbors)
            item_uids = [uid.strip() for uid in items.split(",")]
            export_items_to_yaml(tree, output, item_uids, neighbors, prefixes)
        else:
            # Export all items (original behavior)
            export_to_yaml(tree, output, prefixes)

        click.echo(f"Exported to {output}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command("import")
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be created without making changes",
)
@click.option(
    "--update",
    is_flag=True,
    help="Update existing items instead of skipping them",
)
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def import_yaml_cmd(file: Path, dry_run: bool, update: bool, verbose: bool) -> None:
    """Import documents and items from a YAML file.

    FILE is the path to a YAML file containing documents and items to create.

    \b
    Examples:
        jamb import requirements.yml
        jamb import requirements.yml --dry-run
        jamb import requirements.yml --update
    """
    from jamb.yaml_io import import_from_yaml

    try:
        if dry_run:
            click.echo("Dry run - no changes will be made:")

        stats = import_from_yaml(
            file,
            dry_run=dry_run,
            update=update,
            verbose=verbose,
            echo=click.echo,
        )

        click.echo("")
        parts = []
        if dry_run:
            if stats["documents_created"] > 0:
                parts.append(f"Would create {stats['documents_created']} documents")
            if stats["items_created"] > 0:
                parts.append(f"would create {stats['items_created']} items")
            if stats["items_updated"] > 0:
                parts.append(f"would update {stats['items_updated']} items")
            if parts:
                click.echo(", ".join(parts).capitalize())
            else:
                click.echo("No changes")
        else:
            if stats["documents_created"] > 0:
                parts.append(f"Created {stats['documents_created']} documents")
            if stats["items_created"] > 0:
                parts.append(f"created {stats['items_created']} items")
            if stats["items_updated"] > 0:
                parts.append(f"updated {stats['items_updated']} items")
            if parts:
                click.echo(", ".join(parts).capitalize())
            else:
                click.echo("No changes made")
        if stats["skipped"] > 0:
            click.echo(
                f"Skipped {stats['skipped']} existing items (use --update to modify)"
            )

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# =============================================================================
# Trace Commands
# =============================================================================


def _get_active_normative_items(graph, prefix: str) -> list:
    """Get active normative items from a document prefix."""
    return [
        item
        for item in graph.get_items_by_document(prefix)
        if item.active and item.normative
    ]


def _print_trace_results(
    failures: list[tuple], rule_name: str, args_label: str, error: bool
) -> None:
    """Print trace check results and exit appropriately."""
    for item, message in failures:
        click.echo(f"WARNING: {item.uid} ({item.display_text}) {message}")

    if failures:
        click.echo(f"\n{len(failures)} items failed check: {rule_name} {args_label}")
        if error:
            sys.exit(1)
    else:
        click.echo(f"All items passed check: {rule_name} {args_label}")


@cli.group()
def trace() -> None:
    """Check cross-document traceability rules."""
    pass


@trace.command("has-children")
@click.argument("document")
@click.option("-e", "--error", is_flag=True, help="Exit with code 1 on failure")
@click.option(
    "--root",
    type=click.Path(exists=True, path_type=Path),
    help="Project root directory",
)
def trace_has_children(document: str, error: bool, root: Path | None) -> None:
    """Check that every active normative item in DOCUMENT has at least one child.

    A child is any item from any document that links to the item.
    """
    from jamb.doorstop.discovery import discover_tree
    from jamb.doorstop.reader import build_traceability_graph

    try:
        tree = discover_tree(root)
        graph = build_traceability_graph(tree)
        items = _get_active_normative_items(graph, document)

        failures = []
        for item in items:
            children = graph.item_children.get(item.uid, [])
            if not children:
                failures.append((item, "has no children linking to it"))

        _print_trace_results(failures, "has-children", document, error)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@trace.command("has-parents")
@click.argument("document")
@click.option("-e", "--error", is_flag=True, help="Exit with code 1 on failure")
@click.option(
    "--root",
    type=click.Path(exists=True, path_type=Path),
    help="Project root directory",
)
def trace_has_parents(document: str, error: bool, root: Path | None) -> None:
    """Check every active normative item in DOCUMENT has a parent."""
    from jamb.doorstop.discovery import discover_tree
    from jamb.doorstop.reader import build_traceability_graph

    try:
        tree = discover_tree(root)
        graph = build_traceability_graph(tree)
        items = _get_active_normative_items(graph, document)

        failures = []
        for item in items:
            parents = graph.item_parents.get(item.uid, [])
            if not parents:
                failures.append((item, "has no parent links"))

        _print_trace_results(failures, "has-parents", document, error)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@trace.command("links-to")
@click.argument("source")
@click.argument("target")
@click.option("-e", "--error", is_flag=True, help="Exit with code 1 on failure")
@click.option(
    "--root",
    type=click.Path(exists=True, path_type=Path),
    help="Project root directory",
)
def trace_links_to(source: str, target: str, error: bool, root: Path | None) -> None:
    """Check every active normative item in SOURCE links to TARGET."""
    from jamb.doorstop.discovery import discover_tree
    from jamb.doorstop.reader import build_traceability_graph

    try:
        tree = discover_tree(root)
        graph = build_traceability_graph(tree)
        items = _get_active_normative_items(graph, source)

        failures = []
        for item in items:
            parents_in_target = graph.get_parents_from_document(item.uid, target)
            if not parents_in_target:
                failures.append((item, f"does not link to any item in {target}"))

        _print_trace_results(failures, "links-to", f"{source} {target}", error)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@trace.command("one-to-one")
@click.argument("doc_a")
@click.argument("doc_b")
@click.option("-e", "--error", is_flag=True, help="Exit with code 1 on failure")
@click.option(
    "--root",
    type=click.Path(exists=True, path_type=Path),
    help="Project root directory",
)
def trace_one_to_one(doc_a: str, doc_b: str, error: bool, root: Path | None) -> None:
    """Check 1:1 mapping between DOC_A and DOC_B.

    Every active normative item in DOC_A must have exactly one child in DOC_B,
    and every active normative item in DOC_B must link to exactly one item in DOC_A.
    """
    from jamb.doorstop.discovery import discover_tree
    from jamb.doorstop.reader import build_traceability_graph

    try:
        tree = discover_tree(root)
        graph = build_traceability_graph(tree)

        failures = []

        # Check DOC_A items each have exactly one child in DOC_B
        for item in _get_active_normative_items(graph, doc_a):
            children_in_b = graph.get_children_from_document(item.uid, doc_b)
            if len(children_in_b) == 0:
                failures.append((item, f"has no children in {doc_b}"))
            elif len(children_in_b) > 1:
                child_uids = ", ".join(c.uid for c in children_in_b)
                failures.append(
                    (
                        item,
                        f"has {len(children_in_b)} children in "
                        f"{doc_b} ({child_uids}), expected 1",
                    )
                )

        # Check DOC_B items each link to exactly one item in DOC_A
        for item in _get_active_normative_items(graph, doc_b):
            parents_in_a = graph.get_parents_from_document(item.uid, doc_a)
            if len(parents_in_a) == 0:
                failures.append((item, f"does not link to any item in {doc_a}"))
            elif len(parents_in_a) > 1:
                parent_uids = ", ".join(p.uid for p in parents_in_a)
                failures.append(
                    (
                        item,
                        f"links to {len(parents_in_a)} items in "
                        f"{doc_a} ({parent_uids}), expected 1",
                    )
                )

        _print_trace_results(failures, "one-to-one", f"{doc_a} {doc_b}", error)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
