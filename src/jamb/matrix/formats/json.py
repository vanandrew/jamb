"""JSON traceability matrix output."""

import json
from typing import Any

from jamb.core.models import FullChainMatrix, MatrixMetadata, TestRecord


def render_test_records_json(
    records: list[TestRecord],
    metadata: MatrixMetadata | None = None,
) -> str:
    """Render test records as JSON for machine processing.

    Args:
        records: List of TestRecord objects to render.
        metadata: Optional matrix metadata for IEC 62304 5.7.5 compliance.

    Returns:
        A string containing pretty-printed JSON with a ``metadata`` object
        (if provided), a ``summary`` object (totals and pass rate),
        and a ``tests`` array.
    """
    # Calculate stats
    total = len(records)
    passed = sum(1 for r in records if r.outcome == "passed")
    failed = sum(1 for r in records if r.outcome == "failed")
    skipped = sum(1 for r in records if r.outcome == "skipped")
    error = sum(1 for r in records if r.outcome == "error")
    pass_rate = (100 * passed / total) if total else 0

    data: dict[str, Any] = {
        "summary": {
            "total_tests": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "error": error,
            "pass_rate": pass_rate,
        },
        "tests": [],
    }

    # Add metadata if provided
    if metadata:
        env = metadata.environment
        env_data = None
        if env:
            env_data = {
                "os_name": env.os_name,
                "os_version": env.os_version,
                "python_version": env.python_version,
                "platform": env.platform,
                "processor": env.processor,
                "hostname": env.hostname,
                "cpu_count": env.cpu_count,
            }
        data["metadata"] = {
            "software_version": metadata.software_version,
            "tester_id": metadata.tester_id,
            "execution_timestamp": metadata.execution_timestamp,
            "environment": env_data,
            "test_tools": env.test_tools if env else None,
        }

    for rec in records:
        data["tests"].append(
            {
                "test_id": rec.test_id,
                "test_name": rec.test_name,
                "test_nodeid": rec.test_nodeid,
                "outcome": rec.outcome,
                "requirements": rec.requirements,
                "test_actions": rec.test_actions,
                "expected_results": rec.expected_results,
                "actual_results": rec.actual_results,
                "notes": rec.notes,
                "execution_timestamp": rec.execution_timestamp,
            }
        )

    return json.dumps(data, indent=2)


def render_full_chain_json(
    matrices: list[FullChainMatrix],
    tc_mapping: dict[str, str] | None = None,
) -> str:
    """Render full chain trace matrices as JSON.

    Args:
        matrices: List of FullChainMatrix objects to render.
        tc_mapping: Optional mapping from test nodeid to TC ID for display.

    Returns:
        A string containing pretty-printed JSON with all matrices.
    """
    tc_mapping = tc_mapping or {}

    # Overall summary
    total = sum(m.summary.get("total", 0) for m in matrices)
    passed = sum(m.summary.get("passed", 0) for m in matrices)
    failed = sum(m.summary.get("failed", 0) for m in matrices)
    not_covered = sum(m.summary.get("not_covered", 0) for m in matrices)

    data: dict[str, Any] = {
        "summary": {
            "total_items": total,
            "passed": passed,
            "failed": failed,
            "not_covered": not_covered,
        },
        "matrices": [],
    }

    for matrix in matrices:
        matrix_data: dict[str, Any] = {
            "path_name": matrix.path_name,
            "document_hierarchy": matrix.document_hierarchy,
            "include_ancestors": matrix.include_ancestors,
            "summary": matrix.summary,
            "rows": [],
        }

        for row in matrix.rows:
            row_data: dict[str, Any] = {
                "chain": {},
                "rollup_status": row.rollup_status,
                "ancestor_uids": row.ancestor_uids,
                "tests": [],
            }

            # Document columns
            for prefix in matrix.document_hierarchy:
                item = row.chain.get(prefix)
                if item:
                    row_data["chain"][prefix] = {
                        "uid": item.uid,
                        "text": item.full_display_text,
                        "header": item.header,
                    }
                else:
                    row_data["chain"][prefix] = None

            # Tests
            for test in row.descendant_tests:
                tc_id = tc_mapping.get(test.test_nodeid, "")
                row_data["tests"].append(
                    {
                        "test_id": tc_id,
                        "nodeid": test.test_nodeid,
                        "outcome": test.test_outcome,
                        "item_uid": test.item_uid,
                    }
                )

            matrix_data["rows"].append(row_data)

        data["matrices"].append(matrix_data)

    return json.dumps(data, indent=2)
