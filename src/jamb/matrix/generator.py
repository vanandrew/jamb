"""Generate traceability matrix in various formats."""

from pathlib import Path

from jamb.core.models import ItemCoverage, MatrixMetadata, TraceabilityGraph


def generate_matrix(
    coverage: dict[str, ItemCoverage],
    graph: TraceabilityGraph | None,
    output_path: str,
    output_format: str = "html",
    trace_to_ignore: set[str] | None = None,
    metadata: MatrixMetadata | None = None,
) -> None:
    """
    Generate traceability matrix in specified format.

    Args:
        coverage: Coverage data for test spec items.
        graph: The full traceability graph for ancestor lookups.
        output_path: Path to write the output file.
        output_format: Output format: "html", "markdown", "json", "csv", or "xlsx".
        trace_to_ignore: Document prefixes to exclude from "Traces To".
        metadata: Optional matrix metadata for IEC 62304 5.7.5 compliance.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ignore: set[str] | frozenset[str] = trace_to_ignore or frozenset()

    if output_format == "html":
        from jamb.matrix.formats.html import render_html

        content = render_html(
            coverage, graph, trace_to_ignore=ignore, metadata=metadata
        )
        path.write_text(content)
    elif output_format == "markdown":
        from jamb.matrix.formats.markdown import render_markdown

        content = render_markdown(
            coverage, graph, trace_to_ignore=ignore, metadata=metadata
        )
        path.write_text(content)
    elif output_format == "json":
        from jamb.matrix.formats.json import render_json

        content = render_json(
            coverage, graph, trace_to_ignore=ignore, metadata=metadata
        )
        path.write_text(content)
    elif output_format == "csv":
        from jamb.matrix.formats.csv import render_csv

        content = render_csv(coverage, graph, trace_to_ignore=ignore, metadata=metadata)
        path.write_text(content)
    elif output_format == "xlsx":
        from jamb.matrix.formats.xlsx import render_xlsx

        content_bytes = render_xlsx(
            coverage, graph, trace_to_ignore=ignore, metadata=metadata
        )
        path.write_bytes(content_bytes)
    else:
        raise ValueError(f"Unknown format: {output_format}")
