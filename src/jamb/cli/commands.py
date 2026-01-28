"""CLI commands for jamb."""

import ast
import os
import sys
from pathlib import Path

import click
import yaml

from jamb.storage.document_dag import DocumentDAG
from jamb.storage.items import dump_yaml


def _find_item_path(
    uid: str, root: Path | None = None
) -> tuple[Path | None, str | None]:
    """Find the filesystem path of an item YAML file.

    Args:
        uid: The item UID to locate (e.g. ``"SRS001"``).
        root: Optional project root directory. Defaults to the
            current working directory.

    Returns:
        ``(item_path, document_prefix)`` if found, or
        ``(None, None)`` if the item does not exist.
    """
    import re

    from jamb.storage import discover_documents

    dag = discover_documents(root)

    for prefix, doc_path in dag.document_paths.items():
        config = dag.documents[prefix]
        pattern = re.compile(
            rf"^{re.escape(prefix)}{re.escape(config.sep)}(\d+)$", re.IGNORECASE
        )
        if pattern.match(uid):
            item_path = doc_path / f"{uid}.yml"
            if item_path.exists():
                return item_path, prefix

    return None, None


@click.group()
@click.version_option()
def cli() -> None:
    """jamb - IEC 62304 requirements traceability for pytest."""
    pass


@cli.command()
def init() -> None:
    r"""Initialize a new jamb project with default IEC 62304 documents.

    Creates a 'reqs' folder with PRJ, UN, SYS, SRS, HAZ, and RC documents
    in the standard medical device traceability hierarchy::

        PRJ (Project Requirements) - root
        +-- UN (User Needs)
        |   +-- SYS (System Requirements)
        |       +-- SRS (Software Requirements Specification)
        +-- HAZ (Hazards)
            +-- RC (Risk Controls)

    Also creates an initial PRJ001 heading item using the project name
    from pyproject.toml (falls back to the current directory name).

    \b
    If pyproject.toml exists, adds [tool.jamb] configuration.
    """
    from jamb.storage.document_config import DocumentConfig, save_document_config

    reqs_dir = Path.cwd() / "reqs"

    # Check if reqs folder already exists with documents
    if reqs_dir.exists():
        existing_docs = []
        for doc_name in ["prj", "un", "sys", "srs", "haz", "rc"]:
            doc_path = reqs_dir / doc_name
            if doc_path.exists() and (doc_path / ".jamb.yml").exists():
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

    # Create documents
    documents = [
        DocumentConfig(prefix="PRJ", parents=[], digits=3),
        DocumentConfig(prefix="UN", parents=["PRJ"], digits=3),
        DocumentConfig(prefix="SYS", parents=["UN"], digits=3),
        DocumentConfig(prefix="SRS", parents=["SYS", "RC"], digits=3),
        DocumentConfig(prefix="HAZ", parents=["PRJ"], digits=3),
        DocumentConfig(prefix="RC", parents=["HAZ"], digits=3),
    ]

    for config in documents:
        doc_path = reqs_dir / config.prefix.lower()
        try:
            save_document_config(config, doc_path)
            click.echo(
                f"Created document: {config.prefix} at reqs/{config.prefix.lower()}"
            )
        except (OSError, ValueError) as e:
            click.echo(
                f"Error: Failed to create {config.prefix} document: {e}", err=True
            )
            sys.exit(1)

    # Create initial PRJ001 item from project name
    _create_initial_prj_item(reqs_dir / "prj")

    # Update pyproject.toml if it exists
    pyproject_path = Path.cwd() / "pyproject.toml"
    if pyproject_path.exists():
        _add_jamb_config_to_pyproject(pyproject_path)

    click.echo("\nInitialization complete!")
    click.echo("Run 'jamb info' to see your document structure.")


def _create_initial_prj_item(prj_path: Path) -> None:
    """Create a PRJ001 requirement item using the project name from pyproject.toml.

    Reads the project name from ``[project].name`` in pyproject.toml.
    If pyproject.toml is missing or has no project name, falls back to
    the current directory name.

    Args:
        prj_path: Path to the PRJ document directory.
    """
    from typing import cast

    import yaml

    project_name = Path.cwd().name  # fallback
    pyproject_path = Path.cwd() / "pyproject.toml"
    if pyproject_path.exists():
        try:
            import tomlkit
            from tomlkit.items import Table

            content = pyproject_path.read_text()
            doc = tomlkit.parse(content)
            if "project" in doc:
                project_table = cast(Table, doc["project"])
                if "name" in project_table:
                    project_name = str(project_table["name"])
        except Exception:
            pass  # fall back to directory name

    item_path = prj_path / "PRJ001.yml"
    if item_path.exists():
        return

    item_data = {
        "active": True,
        "header": project_name,
        "type": "requirement",
        "text": project_name,
    }
    with open(item_path, "w") as f:
        yaml.dump(item_data, f, default_flow_style=False, sort_keys=False)

    click.echo(f"Created item: PRJ001 ({project_name})")


def _add_jamb_config_to_pyproject(pyproject_path: Path) -> None:
    """Add [tool.jamb] section to pyproject.toml if it doesn't exist.

    Args:
        pyproject_path: Path to the pyproject.toml file.
    """
    from typing import cast

    import tomlkit
    from tomlkit.items import Table

    try:
        content = pyproject_path.read_text()
        doc = tomlkit.parse(content)

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
        jamb_config["test_documents"] = ["SRS"]
        jamb_config["trace_to_ignore"] = ["PRJ"]
        cast(Table, doc["tool"])["jamb"] = jamb_config

        # Write back
        pyproject_path.write_text(tomlkit.dumps(doc))
        click.echo("Added [tool.jamb] configuration to pyproject.toml")

    except (OSError, tomlkit.exceptions.TOMLKitError) as e:
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
    """Display document information.

    Shows document structure, hierarchy, and item counts.
    Lists each discovered document with its active item count and parent
    relationships, then prints a tree view of the full document hierarchy.
    """
    from jamb.storage import discover_documents
    from jamb.storage.items import read_document_items

    _ = documents  # Reserved for future filtering functionality

    try:
        dag = discover_documents(root)
        click.echo(f"Found {len(dag.documents)} documents:")
        for prefix in dag.topological_sort():
            config = dag.documents[prefix]
            doc_path = dag.document_paths.get(prefix)
            count = 0
            if doc_path:
                items = read_document_items(doc_path, prefix, sep=config.sep)
                count = len(items)
            parents_str = ", ".join(config.parents) if config.parents else "(root)"
            click.echo(f"  - {prefix}: {count} active items (parents: {parents_str})")

        # Show hierarchy
        click.echo("\nDocument hierarchy:")
        _print_dag_hierarchy(dag)

    except (ValueError, FileNotFoundError, KeyError, OSError, yaml.YAMLError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def _print_dag_hierarchy(
    dag: DocumentDAG, prefix: str = "", nodes: list[str] | None = None
) -> None:
    """Print document hierarchy as a tree (DAG-aware).

    Args:
        dag: The document DAG containing documents and their relationships.
        prefix: Indentation prefix string used for tree drawing. Each
            recursive call appends connector characters to build the
            visual tree structure.
        nodes: List of document prefixes to display at this level. If
            ``None``, the root documents of the DAG are used.
    """
    if nodes is None:
        nodes = dag.get_root_documents() or []

    for i, node in enumerate(nodes):
        is_last = i == len(nodes) - 1
        config = dag.documents[node]
        parents_info = ""
        if config.parents:
            parents_info = f" (parents: {', '.join(config.parents)})"
        click.echo(f"{prefix}{'`-- ' if is_last else '|-- '}{node}{parents_info}")
        children = dag.get_children(node)
        if children:
            _print_dag_hierarchy(
                dag,
                prefix + ("    " if is_last else "|   "),
                children,
            )


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
    reports which items have linked tests.

    Note: This does a static scan and doesn't run tests.
    For full coverage including test outcomes, use pytest --jamb.
    """
    from jamb.config.loader import load_config
    from jamb.storage import build_traceability_graph, discover_documents

    try:
        dag = discover_documents(root)
        graph = build_traceability_graph(dag)
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
                if (
                    item.type == "requirement"
                    and item.active
                    and item.uid not in linked_items
                ):
                    uncovered.append(item)

        if uncovered:
            click.echo(f"\nFound {len(uncovered)} uncovered items:", err=True)
            for item in uncovered:
                click.echo(f"  - {item.uid}: {item.display_text}", err=True)
            sys.exit(1)
        else:
            total = sum(len(graph.get_items_by_document(p)) for p in test_docs)
            click.echo(f"\nAll {total} items in test documents have linked tests.")

    except (ValueError, FileNotFoundError, KeyError, OSError, yaml.YAMLError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def _scan_tests_for_requirements(root: Path) -> set[str]:
    """Scan test files for requirement markers.

    Walks all ``test_*.py`` files under *root*, parses them into ASTs,
    and collects string arguments from ``@pytest.mark.requirement`` calls.

    Args:
        root: Project root directory to search for test files.

    Returns:
        Set of requirement UID strings found in test markers.
    """
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
        except (SyntaxError, OSError):
            continue  # Skip unreadable/unparseable test files

    return linked


def _is_requirement_marker(node: ast.Call) -> bool:
    """Check if an AST Call node is a pytest.mark.requirement call.

    Args:
        node: An ``ast.Call`` node to inspect.

    Returns:
        ``True`` if the node represents a ``pytest.mark.requirement(...)``
        call, ``False`` otherwise.
    """
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
# Reorder Command
# =============================================================================


@cli.command("reorder")
@click.argument("prefix")
def reorder(prefix: str) -> None:
    """Renumber item UIDs sequentially to fill gaps.

    PREFIX is the document identifier (e.g., SRS, UT).

    Items are sorted by current UID and renumbered to form a contiguous
    sequence (e.g., SRS001, SRS002, ...).  All cross-document links that
    reference renamed UIDs are updated automatically.
    """
    from jamb.storage import discover_documents
    from jamb.storage.reorder import reorder_document

    try:
        dag = discover_documents()
        if prefix not in dag.document_paths:
            click.echo(f"Error: Document '{prefix}' not found", err=True)
            sys.exit(1)

        doc_path = dag.document_paths[prefix]
        config = dag.documents[prefix]
        all_doc_paths = dict(dag.document_paths)

        stats = reorder_document(
            doc_path, prefix, config.digits, config.sep, all_doc_paths
        )
        click.echo(
            f"Reordered {prefix}: {stats['renamed']} renamed, "
            f"{stats['unchanged']} unchanged"
        )

    except (ValueError, FileNotFoundError, KeyError, OSError, yaml.YAMLError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# =============================================================================
# Document Management Commands
# =============================================================================


@cli.group()
def doc() -> None:
    """Manage documents.

    Subcommands: create, delete, list.
    """
    pass


@doc.command("create")
@click.argument("prefix")
@click.argument("path")
@click.option(
    "--parent", "-p", multiple=True, help="Parent document prefix (repeatable for DAG)"
)
@click.option(
    "--digits", "-d", default=3, type=int, help="Number of digits for item IDs"
)
@click.option("--sep", "-s", default="", help="Separator between prefix and number")
def doc_create(
    prefix: str, path: str, parent: tuple[str, ...], digits: int, sep: str
) -> None:
    """Create a new document.

    PREFIX is the document identifier (e.g., SRS, UT).
    PATH is the directory where the document will be created.

    Supports multiple parents for DAG hierarchy:
        jamb doc create SRS reqs/srs --parent SYS --parent RC
    """
    from jamb.storage.document_config import DocumentConfig, save_document_config

    config = DocumentConfig(
        prefix=prefix,
        parents=list(parent),
        digits=digits,
        sep=sep,
    )

    doc_path = Path(path)
    try:
        save_document_config(config, doc_path)
        parents_str = f" (parents: {', '.join(parent)})" if parent else ""
        click.echo(f"Created document: {prefix} at {path}{parents_str}")
    except (ValueError, FileNotFoundError, KeyError, OSError, yaml.YAMLError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@doc.command("delete")
@click.argument("prefix")
@click.option(
    "--root",
    type=click.Path(exists=True, path_type=Path),
    help="Project root directory",
)
def doc_delete(prefix: str, root: Path | None) -> None:
    """Delete a document.

    PREFIX is the document identifier to delete (e.g., SRS, UT).
    """
    from jamb.storage import discover_documents

    try:
        dag = discover_documents(root)
        if prefix not in dag.document_paths:
            click.echo(f"Error: Document '{prefix}' not found", err=True)
            sys.exit(1)

        doc_path = dag.document_paths[prefix]
        import shutil

        shutil.rmtree(doc_path)
        click.echo(f"Deleted document: {prefix}")

    except (ValueError, FileNotFoundError, KeyError, OSError, yaml.YAMLError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@doc.command("list")
@click.option(
    "--root",
    type=click.Path(exists=True, path_type=Path),
    help="Project root directory",
)
def doc_list(root: Path | None) -> None:
    """List all documents in the tree."""
    from jamb.storage import discover_documents
    from jamb.storage.items import read_document_items

    try:
        dag = discover_documents(root)
        click.echo(f"Found {len(dag.documents)} documents:")
        for prefix in dag.topological_sort():
            config = dag.documents[prefix]
            doc_path = dag.document_paths.get(prefix)
            count = 0
            if doc_path:
                items = read_document_items(doc_path, prefix, sep=config.sep)
                count = len(items)
            parents_str = ", ".join(config.parents) if config.parents else "(root)"
            click.echo(f"  {prefix}: {count} active items (parents: {parents_str})")

        click.echo("\nHierarchy:")
        _print_dag_hierarchy(dag)

    except (ValueError, FileNotFoundError, KeyError, OSError, yaml.YAMLError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# =============================================================================
# Item Management Commands
# =============================================================================


@cli.group()
def item() -> None:
    """Manage items.

    Subcommands: add, list, remove, edit, show.
    """
    pass


@item.command("add")
@click.argument("prefix")
@click.option("--count", "-c", default=1, type=int, help="Number of items to add")
@click.option("--after", "after_uid", default=None, help="Insert after this UID")
@click.option("--before", "before_uid", default=None, help="Insert before this UID")
@click.option("--header", default=None, help="Set the item header")
@click.option("--text", default=None, help="Set the item body text")
@click.option("--links", multiple=True, help="Add parent link(s) (multiple allowed)")
def item_add(
    prefix: str,
    count: int,
    after_uid: str | None,
    before_uid: str | None,
    header: str | None,
    text: str | None,
    links: tuple[str, ...],
) -> None:
    """Add a new item to a document.

    PREFIX is the document to add the item to (e.g., SRS, UT).
    """
    import re

    from jamb.storage import discover_documents
    from jamb.storage.items import next_uid, read_document_items, write_item

    try:
        if after_uid and before_uid:
            click.echo("Error: --after and --before are mutually exclusive", err=True)
            sys.exit(1)

        dag = discover_documents()
        if prefix not in dag.document_paths:
            click.echo(f"Error: Document '{prefix}' not found", err=True)
            sys.exit(1)

        config = dag.documents[prefix]
        doc_path = dag.document_paths[prefix]

        anchor_uid = after_uid or before_uid
        if anchor_uid:
            # Validate anchor UID exists
            anchor_path = doc_path / f"{anchor_uid}.yml"
            if not anchor_path.exists():
                click.echo(f"Error: Item '{anchor_uid}' not found", err=True)
                sys.exit(1)

            # Parse numeric part
            pattern = re.compile(
                rf"^{re.escape(prefix)}{re.escape(config.sep)}(\d+)$", re.IGNORECASE
            )
            m = pattern.match(anchor_uid)
            if not m:
                click.echo(f"Error: Cannot parse UID '{anchor_uid}'", err=True)
                sys.exit(1)

            anchor_num = int(m.group(1))
            position = anchor_num + 1 if after_uid else anchor_num

            from jamb.storage.reorder import insert_items

            new_uids = insert_items(
                doc_path,
                prefix,
                config.digits,
                config.sep,
                position,
                count,
                dag.document_paths,
            )

            for uid in new_uids:
                item_data = {
                    "header": header or "",
                    "active": True,
                    "type": "requirement",
                    "links": list(links) if links else [],
                    "text": text or "",
                    "reviewed": None,
                }
                item_path = doc_path / f"{uid}.yml"
                write_item(item_data, item_path)
                click.echo(f"Added item: {uid}")
        else:
            existing = read_document_items(
                doc_path, prefix, include_inactive=True, sep=config.sep
            )
            existing_uids = [i["uid"] for i in existing]

            for _ in range(count):
                uid = next_uid(prefix, config.digits, existing_uids, config.sep)
                item_data = {
                    "header": header or "",
                    "active": True,
                    "type": "requirement",
                    "links": list(links) if links else [],
                    "text": text or "",
                    "reviewed": None,
                }
                item_path = doc_path / f"{uid}.yml"
                write_item(item_data, item_path)
                existing_uids.append(uid)
                click.echo(f"Added item: {uid}")

    except (ValueError, FileNotFoundError, KeyError, OSError, yaml.YAMLError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


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
    from jamb.storage import discover_documents
    from jamb.storage.items import read_document_items

    try:
        dag = discover_documents(root)

        if prefix:
            if prefix not in dag.document_paths:
                click.echo(f"Error: Document '{prefix}' not found", err=True)
                sys.exit(1)
            prefixes = [prefix]
        else:
            prefixes = dag.topological_sort()

        for p in prefixes:
            doc_path = dag.document_paths.get(p)
            if not doc_path:
                continue
            config = dag.documents[p]
            items = read_document_items(doc_path, p, sep=config.sep)
            if items:
                click.echo(f"\n{p} ({len(items)} items):")
                for item_data in items:
                    text = (
                        item_data["text"][:60] + "..."
                        if len(item_data["text"]) > 60
                        else item_data["text"]
                    )
                    text = text.replace("\n", " ").strip()
                    click.echo(f"  {item_data['uid']}: {text}")

    except (ValueError, FileNotFoundError, KeyError, OSError, yaml.YAMLError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@item.command("remove")
@click.argument("uid")
def item_remove(uid: str) -> None:
    """Remove an item by UID.

    UID is the item identifier (e.g., SRS001, UT002).
    """
    item_path, _ = _find_item_path(uid)
    if item_path is None:
        click.echo(f"Error: Item '{uid}' not found", err=True)
        sys.exit(1)

    item_path.unlink()
    click.echo(f"Removed item: {uid}")


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
    import subprocess

    item_path, _ = _find_item_path(uid)
    if item_path is None:
        click.echo(f"Error: Item '{uid}' not found", err=True)
        sys.exit(1)

    editor: str = tool if tool else os.environ.get("EDITOR", "vim")
    result = subprocess.run([editor, str(item_path)])
    sys.exit(result.returncode)


@item.command("show")
@click.argument("uid")
def item_show(uid: str) -> None:
    """Display item details.

    UID is the item identifier (e.g., SRS001, UT002).
    """
    from jamb.storage.items import read_item

    try:
        item_path, prefix = _find_item_path(uid)
        if item_path is None or prefix is None:
            click.echo(f"Error: Item '{uid}' not found", err=True)
            sys.exit(1)

        data = read_item(item_path, prefix)

        click.echo(f"UID: {data['uid']}")
        click.echo(f"Document: {data['document_prefix']}")
        click.echo(f"Active: {data['active']}")
        click.echo(f"Type: {data['type']}")
        if data.get("header"):
            click.echo(f"Header: {data['header']}")
        if data.get("links"):
            click.echo(f"Links: {', '.join(data['links'])}")
        if data.get("reviewed"):
            click.echo(f"Reviewed: {data['reviewed']}")
        click.echo(f"\nText:\n{data['text']}")

    except (ValueError, FileNotFoundError, KeyError, OSError, yaml.YAMLError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# =============================================================================
# Link Management Commands
# =============================================================================


@cli.group()
def link() -> None:
    """Manage item links.

    Subcommands: add, remove.
    """
    pass


@link.command("add")
@click.argument("child")
@click.argument("parent")
def link_add(child: str, parent: str) -> None:
    """Link a child item to a parent item.

    CHILD is the child item UID (e.g., SRS001).
    PARENT is the parent item UID (e.g., SYS001).
    """
    item_path, prefix = _find_item_path(child)
    if item_path is None:
        click.echo(f"Error: Item '{child}' not found", err=True)
        sys.exit(1)

    with open(item_path) as f:
        data = yaml.safe_load(f) or {}

    links = data.get("links", [])
    # Check if link already exists
    for entry in links:
        link_uid = entry if isinstance(entry, str) else next(iter(entry))
        if str(link_uid) == parent:
            click.echo(f"Link already exists: {child} -> {parent}")
            return

    links.append(parent)
    data["links"] = links

    with open(item_path, "w") as f:
        dump_yaml(data, f)

    click.echo(f"Linked: {child} -> {parent}")


@link.command("remove")
@click.argument("child")
@click.argument("parent")
def link_remove(child: str, parent: str) -> None:
    """Remove a link between items.

    CHILD is the child item UID (e.g., SRS001).
    PARENT is the parent item UID (e.g., SYS001).
    """
    item_path, prefix = _find_item_path(child)
    if item_path is None:
        click.echo(f"Error: Item '{child}' not found", err=True)
        sys.exit(1)

    with open(item_path) as f:
        data = yaml.safe_load(f) or {}

    links = data.get("links", [])
    new_links = []
    removed = False
    for entry in links:
        link_uid = entry if isinstance(entry, str) else next(iter(entry))
        if str(link_uid) == parent:
            removed = True
        else:
            new_links.append(entry)

    if not removed:
        click.echo(f"Link not found: {child} -> {parent}", err=True)
        sys.exit(1)

    data["links"] = new_links
    with open(item_path, "w") as f:
        dump_yaml(data, f)

    click.echo(f"Unlinked: {child} -> {parent}")


# =============================================================================
# Review Management Commands
# =============================================================================


@cli.group()
def review() -> None:
    """Manage item reviews.

    Subcommands: mark, clear, reset.
    """
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
    from jamb.storage import discover_documents
    from jamb.storage.items import compute_content_hash, read_item

    try:
        dag = discover_documents()
        items_to_mark = _resolve_label_to_item_paths(label, dag)

        count = 0
        for item_path, prefix in items_to_mark:
            data = read_item(item_path, prefix)
            content_hash = compute_content_hash(data)

            # Read raw YAML and set reviewed field
            with open(item_path) as f:
                raw = yaml.safe_load(f) or {}
            raw["reviewed"] = content_hash
            with open(item_path, "w") as f:
                dump_yaml(raw, f)
            count += 1
            click.echo(f"marked item {data['uid']} as reviewed")

        if count == 0:
            click.echo("no items to mark")
        else:
            click.echo(f"marked {count} items as reviewed")

    except (ValueError, FileNotFoundError, KeyError, OSError, yaml.YAMLError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


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
    from jamb.storage import discover_documents
    from jamb.storage.items import compute_content_hash, read_item

    try:
        dag = discover_documents()
        items_to_clear = _resolve_label_to_item_paths(label, dag)
        parent_set = set(parents) if parents else None

        count = 0
        for item_path, _prefix in items_to_clear:
            # Read raw YAML
            with open(item_path) as f:
                raw = yaml.safe_load(f) or {}

            links = raw.get("links", [])
            updated = False

            # Update link hashes for specified parents (or all)
            new_links = []
            for entry in links:
                if isinstance(entry, dict):
                    link_uid = next(iter(entry))
                elif isinstance(entry, str):
                    link_uid = entry
                else:
                    link_uid = str(entry)

                if parent_set is None or str(link_uid) in parent_set:
                    # Compute current hash for the linked item
                    linked_path, linked_prefix = _find_item_path(str(link_uid))
                    if linked_path and linked_prefix:
                        linked_data = read_item(linked_path, linked_prefix)
                        new_hash = compute_content_hash(linked_data)
                        new_links.append({str(link_uid): new_hash})
                        updated = True
                    else:
                        new_links.append(entry)
                else:
                    new_links.append(entry)

            if updated:
                raw["links"] = new_links
                with open(item_path, "w") as f:
                    dump_yaml(raw, f)
                count += 1

        click.echo(f"Cleared suspect links on {count} items")

    except (ValueError, FileNotFoundError, KeyError, OSError, yaml.YAMLError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


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
    from jamb.storage import discover_documents

    try:
        dag = discover_documents(root)
        items_to_reset = _resolve_label_to_item_paths(label, dag)

        count = 0
        for item_path, _prefix in items_to_reset:
            with open(item_path) as f:
                data = yaml.safe_load(f) or {}

            changed = False
            if "reviewed" in data:
                del data["reviewed"]
                changed = True

            # Strip link hashes, keeping just the UIDs
            links = data.get("links", [])
            if links:
                new_links: list[str] = []
                for entry in links:
                    if isinstance(entry, dict):
                        new_links.extend(entry.keys())
                    else:
                        new_links.append(entry)
                data["links"] = new_links
                if new_links != links:
                    changed = True

            if changed:
                with open(item_path, "w") as f:
                    dump_yaml(data, f)
                click.echo(f"reset item {item_path.stem} to unreviewed")
                count += 1

        if count == 0:
            click.echo("no items needed resetting")
        else:
            click.echo(f"reset {count} items to unreviewed")

    except (ValueError, FileNotFoundError, KeyError, OSError, yaml.YAMLError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def _resolve_label_to_item_paths(
    label: str, dag: DocumentDAG
) -> list[tuple[Path, str]]:
    """Resolve a label (UID, prefix, or 'all') to list of (item_path, prefix) tuples.

    The label is matched in the following order: the literal string
    ``"all"`` returns every item across all documents; a known document
    prefix returns all items in that document; otherwise the label is
    treated as an individual item UID.

    Args:
        label: An item UID (e.g. ``"SRS001"``), a document prefix
            (e.g. ``"SRS"``), or the string ``"all"``.
        dag: The document DAG used to locate documents and items.

    Returns:
        A list of ``(item_path, prefix)`` tuples for the resolved items.

    Raises:
        SystemExit: If the label does not match any item or document.
    """
    from jamb.storage.items import read_document_items

    result: list[tuple[Path, str]] = []

    if label.lower() == "all":
        for prefix, doc_path in dag.document_paths.items():
            config = dag.documents.get(prefix)
            sep = config.sep if config else ""
            items = read_document_items(
                doc_path, prefix, include_inactive=True, sep=sep
            )
            for item_data in items:
                result.append((doc_path / f"{item_data['uid']}.yml", prefix))
        return result

    # Try as document prefix first
    if label in dag.document_paths:
        doc_path = dag.document_paths[label]
        config = dag.documents.get(label)
        sep = config.sep if config else ""
        items = read_document_items(doc_path, label, include_inactive=True, sep=sep)
        for item_data in items:
            result.append((doc_path / f"{item_data['uid']}.yml", label))
        return result

    # Try as item UID
    for prefix, doc_path in dag.document_paths.items():
        item_path = doc_path / f"{label}.yml"
        if item_path.exists():
            return [(item_path, prefix)]

    click.echo(f"Error: '{label}' is not a valid item or document", err=True)
    sys.exit(1)


# =============================================================================
# Publish Command
# =============================================================================


@cli.command()
@click.argument("prefix")
@click.argument("path", required=False)
@click.option("--html", "-H", is_flag=True, help="Output HTML")
@click.option("--markdown", "-m", is_flag=True, help="Output Markdown")
@click.option("--docx", "-d", is_flag=True, help="Output DOCX (Word document)")
@click.option(
    "--no-child-links", "-C", is_flag=True, help="Do not include child links on items"
)
@click.option(
    "--template",
    "-t",
    type=click.Path(exists=True, path_type=Path),
    help="DOCX template file to use for styling (use with --docx)",
)
def publish(
    prefix: str,
    path: str | None,
    html: bool,
    markdown: bool,
    docx: bool,
    no_child_links: bool,
    template: Path | None,
) -> None:
    """Publish a document.

    PREFIX is the document prefix (e.g., SRS) or 'all' for all documents.
    PATH is the output file or directory (optional).

    Use --template with a .docx file to apply custom styles.
    Generate a starter template with: jamb publish-template

    For a traceability matrix with test coverage, use: pytest --jamb --jamb-matrix PATH
    """
    include_links = not no_child_links

    # Validate template option
    if template:
        if not str(template).lower().endswith(".docx"):
            click.echo("Error: --template must be a .docx file", err=True)
            sys.exit(1)

    # Handle DOCX export
    if docx:
        if not path:
            click.echo(
                "Error: --docx requires an output PATH",
                err=True,
            )
            click.echo("Example: jamb publish SRS output.docx --docx", err=True)
            sys.exit(1)

        _publish_docx(prefix, path, include_links, template)
        return

    # Handle HTML export
    if html:
        if template:
            click.echo("Warning: --template is only used with DOCX output", err=True)
        if not path:
            click.echo("Error: --html requires an output PATH", err=True)
            sys.exit(1)
        _publish_html(prefix, path, include_links)
        return

    # Handle Markdown export natively
    if markdown:
        if not path:
            click.echo("Error: --markdown requires an output PATH", err=True)
            sys.exit(1)
        _publish_markdown(prefix, path)
        return

    # Validate: "all" requires an output path
    if prefix.lower() == "all" and not path:
        click.echo(
            "Error: 'all' requires an output PATH",
            err=True,
        )
        click.echo("Example: jamb publish all ./docs --docx", err=True)
        sys.exit(1)

    # Auto-detect format from file extension
    if path:
        if path.endswith(".html") or path.endswith(".htm"):
            if template:
                click.echo(
                    "Warning: --template is only used with DOCX output", err=True
                )
            _publish_html(prefix, path, include_links)
        elif path.endswith(".docx"):
            _publish_docx(prefix, path, include_links, template)
        else:
            if template:
                click.echo(
                    "Warning: --template is only used with DOCX output", err=True
                )
            _publish_markdown(prefix, path)
    else:
        if template:
            click.echo("Warning: --template is only used with DOCX output", err=True)
        _publish_markdown_stdout(prefix)


def _publish_html(prefix: str, path: str, include_links: bool) -> None:
    """Publish documents as a standalone HTML file.

    Args:
        prefix: Document prefix (e.g. ``"SRS"``) or ``"all"`` for every
            document.
        path: Filesystem path for the output HTML file.
        include_links: Whether to render child-link references in the
            output.
    """
    from jamb.core.models import Item
    from jamb.publish.formats.html import render_html
    from jamb.storage import build_traceability_graph, discover_documents

    try:
        dag = discover_documents()
        graph = build_traceability_graph(dag)
        output_path = Path(path)

        doc_order = dag.topological_sort()

        if prefix.lower() == "all":
            items: list[Item] = list(graph.items.values())
            title = "Requirements Document"
        else:
            items = graph.get_items_by_document(prefix)
            title = f"{prefix} Requirements Document"

        if not items:
            click.echo(f"Error: No items found for '{prefix}'", err=True)
            sys.exit(1)

        html_content = render_html(items, title, include_links, doc_order, graph)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html_content)
        click.echo(f"Published to {output_path}")

    except (ValueError, FileNotFoundError, KeyError, OSError, yaml.YAMLError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def _publish_markdown_stdout(prefix: str) -> None:
    """Publish a document as markdown to stdout.

    Args:
        prefix: Document prefix identifying the document to publish
            (e.g. ``"SRS"``).
    """
    from jamb.storage import build_traceability_graph, discover_documents

    try:
        dag = discover_documents()
        graph = build_traceability_graph(dag)

        items = graph.get_items_by_document(prefix)
        if not items:
            click.echo(f"Error: No items found for '{prefix}'", err=True)
            sys.exit(1)

        items.sort(key=lambda i: i.uid)
        click.echo(f"# {prefix}\n")
        for item_obj in items:
            item_type = getattr(item_obj, "type", "requirement")
            if item_type == "heading":
                heading_display = item_obj.header if item_obj.header else item_obj.uid
                click.echo(f"## {item_obj.uid}: {heading_display}\n")
            else:
                if item_obj.header:
                    click.echo(f"## {item_obj.uid}: {item_obj.header}\n")
                else:
                    click.echo(f"## {item_obj.uid}\n")
                if item_obj.text:
                    if item_type == "info":
                        click.echo(f"*{item_obj.text}*\n")
                    else:
                        click.echo(f"{item_obj.text}\n")
            if item_obj.links:
                click.echo(f"*Links: {', '.join(item_obj.links)}*\n")
            children = graph.item_children.get(item_obj.uid, [])
            if children:
                click.echo(f"*Linked from: {', '.join(children)}*\n")

    except (ValueError, FileNotFoundError, KeyError, OSError, yaml.YAMLError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def _publish_markdown(prefix: str, path: str) -> None:
    """Publish a document as markdown to a file.

    Args:
        prefix: Document prefix (e.g. ``"SRS"``) or ``"all"`` for every
            document.
        path: Filesystem path for the output Markdown file.
    """
    from jamb.storage import build_traceability_graph, discover_documents

    try:
        dag = discover_documents()
        graph = build_traceability_graph(dag)
        output_path = Path(path)

        if prefix.lower() == "all":
            prefixes = dag.topological_sort()
        else:
            prefixes = [prefix]

        lines: list[str] = []
        for p in prefixes:
            items = graph.get_items_by_document(p)
            if not items:
                continue

            items.sort(key=lambda i: i.uid)
            lines.append(f"# {p}\n")
            for item_obj in items:
                item_type = getattr(item_obj, "type", "requirement")
                if item_type == "heading":
                    heading_display = (
                        item_obj.header if item_obj.header else item_obj.uid
                    )
                    lines.append(f"## {item_obj.uid}: {heading_display}\n")
                else:
                    if item_obj.header:
                        lines.append(f"## {item_obj.uid}: {item_obj.header}\n")
                    else:
                        lines.append(f"## {item_obj.uid}\n")
                    if item_obj.text:
                        if item_type == "info":
                            lines.append(f"*{item_obj.text}*\n")
                        else:
                            lines.append(f"{item_obj.text}\n")
                if item_obj.links:
                    link_parts = [f"[{uid}](#{uid})" for uid in item_obj.links]
                    lines.append(f"*Links: {', '.join(link_parts)}*\n")
                children = graph.item_children.get(item_obj.uid, [])
                if children:
                    child_parts = [f"[{uid}](#{uid})" for uid in children]
                    lines.append(f"*Linked from: {', '.join(child_parts)}*\n")
                lines.append("")

        if not lines:
            click.echo(f"Error: No items found for '{prefix}'", err=True)
            sys.exit(1)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(lines))
        click.echo(f"Published to {output_path}")

    except (ValueError, FileNotFoundError, KeyError, OSError, yaml.YAMLError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def _publish_docx(
    prefix: str, path: str, include_child_links: bool, template: Path | None = None
) -> None:
    """Publish documents as a single DOCX file.

    Args:
        prefix: Document prefix (e.g. ``"SRS"``) or ``"all"`` for every
            document.
        path: Filesystem path for the output DOCX file.
        include_child_links: Whether to include child (reverse) link
            references in the generated document.
        template: Optional path to a DOCX template file to use for styling.
    """
    from jamb.core.models import Item
    from jamb.publish.formats.docx import render_docx
    from jamb.storage import build_traceability_graph, discover_documents

    try:
        dag = discover_documents()
        graph = build_traceability_graph(dag)
        output_path = Path(path)

        doc_order = dag.topological_sort()

        if prefix.lower() == "all":
            items: list[Item] = list(graph.items.values())
            title = "Requirements Document"
        else:
            items = graph.get_items_by_document(prefix)
            title = f"{prefix} Requirements Document"

        if not items:
            click.echo(f"Error: No items found for '{prefix}'", err=True)
            sys.exit(1)

        template_path = str(template) if template else None
        docx_bytes = render_docx(
            items, title, include_child_links, doc_order, graph, template_path
        )
        output_path.write_bytes(docx_bytes)
        click.echo(f"Published to {output_path}")

    except (ValueError, FileNotFoundError, KeyError, OSError, yaml.YAMLError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command("publish-template")
@click.argument("path", required=False, default="jamb-template.docx")
def publish_template(path: str) -> None:
    """Generate a DOCX template file with jamb styles.

    PATH is the output file path (default: jamb-template.docx).

    The generated template contains all styles used by jamb when publishing
    DOCX documents. Open it in Microsoft Word, customize the styles (fonts,
    colors, spacing), then use it with:

        jamb publish SRS output.docx --template jamb-template.docx

    \b
    Examples:
        jamb publish-template
        jamb publish-template my-company-template.docx
    """
    from jamb.publish.formats.docx import generate_template

    output_path = Path(path)

    if output_path.exists():
        if not click.confirm(f"File '{path}' exists. Overwrite?"):
            click.echo("Aborted.")
            return

    try:
        generate_template(str(output_path))
        click.echo(f"Generated template: {output_path}")
        click.echo("\nNext steps:")
        click.echo("  1. Open the template in Microsoft Word")
        click.echo("  2. Customize styles (Heading 1, Heading 2, Normal, etc.)")
        click.echo("  3. Save the template")
        click.echo(f"  4. Use with: jamb publish SRS output.docx --template {path}")
    except (OSError, ValueError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# =============================================================================
# Validate Command
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
    "--no-child-check",
    "-C",
    is_flag=True,
    help="Do not validate child (reverse) links",
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
    no_child_check: bool,
    no_suspect_check: bool,
    no_review_check: bool,
    skip_prefix: tuple[str, ...],
    warn_all: bool,
    error_all: bool,
) -> None:
    r"""Validate the requirements tree.

    Checks for issues like:

    - Cycles in document hierarchy
    - Invalid or missing links
    - Suspect links (items needing re-review)
    - Items without required links

    \b
    Examples::

        jamb validate              # Run validation
        jamb validate -v           # Verbose output
        jamb validate --skip UT    # Skip unit test document
        jamb validate -S           # Skip suspect checks
    """
    from jamb.storage import build_traceability_graph, discover_documents
    from jamb.storage.validation import validate as run_validate

    try:
        dag = discover_documents()
        graph = build_traceability_graph(dag, include_inactive=True)

        issues = run_validate(
            dag,
            graph,
            check_links=True,
            check_suspect=not no_suspect_check,
            check_review=not no_review_check,
            check_children=not no_child_check,
            skip_prefixes=list(skip_prefix),
        )

        # Promote/demote issue levels based on flags
        for issue in issues:
            if warn_all and issue.level == "info":
                issue.level = "warning"
            if error_all and issue.level == "warning":
                issue.level = "error"

        # Display issues
        has_errors = False
        for issue in issues:
            if quiet and issue.level not in ("error",):
                continue
            if not verbose and issue.level == "info":
                continue
            click.echo(str(issue))
            if issue.level == "error":
                has_errors = True

        if not issues:
            click.echo("Validation passed - no issues found")
        elif not has_errors:
            warnings_count = sum(1 for i in issues if i.level == "warning")
            click.echo(f"\nValidation passed with {warnings_count} warnings")
        else:
            errors_count = sum(1 for i in issues if i.level == "error")
            click.echo(f"\nValidation failed with {errors_count} errors")
            sys.exit(1)

    except (ValueError, FileNotFoundError, KeyError, OSError, yaml.YAMLError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


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
    from jamb.yaml_io import export_items_to_yaml, export_to_yaml

    # Validate: --neighbors requires --items
    if neighbors and not items:
        click.echo("Error: --neighbors requires --items to be specified", err=True)
        sys.exit(1)

    try:
        prefixes = None
        if documents:
            prefixes = [d.strip() for d in documents.split(",")]

        if items:
            # Export specific items (with optional neighbors)
            item_uids = [uid.strip() for uid in items.split(",")]
            export_items_to_yaml(output, item_uids, neighbors, prefixes, root)
        else:
            # Export all items (original behavior)
            export_to_yaml(output, prefixes, root)

        click.echo(f"Exported to {output}")

    except (ValueError, FileNotFoundError, KeyError, OSError, yaml.YAMLError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


_IMPORT_TEMPLATE = """\
# Example jamb import file
# Usage: jamb import requirements.yml
documents:               # optional - create new documents
  - prefix: SRS
    path: reqs/srs
    parents: [SYS]       # optional
    digits: 3            # optional, default: 3

items:                   # optional - create new items
  - uid: SRS001
    text: "Requirement text here"
    header: "Section Title"  # optional
    links: [SYS001]         # optional - parent item UIDs
"""


@cli.command("import")
@click.argument(
    "file",
    type=click.Path(exists=True, path_type=Path),
    required=False,
    default=None,
)
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
@click.option(
    "--template",
    is_flag=True,
    help="Output a starter YAML template to stdout",
)
def import_yaml_cmd(
    file: Path | None,
    dry_run: bool,
    update: bool,
    verbose: bool,
    template: bool,
) -> None:
    """Import documents and items from a YAML file.

    FILE is the path to a YAML file containing documents and items to create.

    \b
    Expected YAML schema::

        documents:                # optional
          - prefix: SRS           # required - document prefix
            path: reqs/srs        # required - directory path
            parents: [SYS]        # optional - parent document prefixes
            digits: 3             # optional - UID digit count (default: 3)
        items:                    # optional
          - uid: SRS001           # required - unique item identifier
            text: "requirement"   # required - item text
            header: "Title"       # optional - section header
            links: [SYS001]       # optional - linked parent item UIDs

    \b
    Examples::

        jamb import requirements.yml
        jamb import requirements.yml --dry-run
        jamb import requirements.yml --update
        jamb import --template > requirements.yml
    """
    if template:
        click.echo(_IMPORT_TEMPLATE, nl=False)
        return

    if file is None:
        click.echo("Error: Missing argument 'FILE'.", err=True)
        sys.exit(1)

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

    except (ValueError, FileNotFoundError, KeyError, OSError, yaml.YAMLError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# =============================================================================
# Migration Command
# =============================================================================


if __name__ == "__main__":
    cli()
