"""JSON traceability matrix output."""

import json
from typing import Any

from jamb.core.models import ItemCoverage, TraceabilityGraph


def render_json(
    coverage: dict[str, ItemCoverage],
    graph: TraceabilityGraph | None,
    trace_to_ignore: frozenset[str] | set[str] = frozenset(),
) -> str:
    """Render coverage as JSON for machine processing.

    Args:
        coverage: Dict mapping UIDs to ItemCoverage objects representing
            each traceable item and its test linkage.
        graph: Optional TraceabilityGraph used to resolve ancestor chains
            for each item. When None, ancestor lists are left empty.
        trace_to_ignore: Set of document prefixes to exclude from the
            ancestor display.

    Returns:
        A string containing pretty-printed JSON with a ``summary``
        object (totals and coverage percentage) and an ``items`` object
        keyed by UID.
    """
    # Calculate stats
    total = len(coverage)
    covered = sum(1 for c in coverage.values() if c.is_covered)
    passed = sum(1 for c in coverage.values() if c.all_tests_passed)

    data: dict[str, Any] = {
        "summary": {
            "total_items": total,
            "covered": covered,
            "coverage_percentage": (100 * covered / total) if total else 0,
            "all_tests_passing": passed,
        },
        "items": {},
    }

    for uid, cov in coverage.items():
        # Get ancestors
        ancestors = []
        if graph:
            for ancestor in graph.get_ancestors(uid):
                if ancestor.document_prefix in trace_to_ignore:
                    continue
                ancestors.append(
                    {
                        "uid": ancestor.uid,
                        "text": ancestor.display_text,
                        "document": ancestor.document_prefix,
                    }
                )

        data["items"][uid] = {
            "uid": uid,
            "text": cov.item.text,
            "header": cov.item.header,
            "document": cov.item.document_prefix,
            "normative": cov.item.type == "requirement",
            "active": cov.item.active,
            "traces_to": ancestors,
            "is_covered": cov.is_covered,
            "all_tests_passed": cov.all_tests_passed,
            "linked_tests": [
                {
                    "nodeid": t.test_nodeid,
                    "outcome": t.test_outcome,
                    "test_actions": t.test_actions,
                    "expected_results": t.expected_results,
                    "notes": t.notes,
                }
                for t in cov.linked_tests
            ],
        }

    return json.dumps(data, indent=2)
