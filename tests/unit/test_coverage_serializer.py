"""Unit tests for coverage serializer."""

import json
from pathlib import Path

import pytest

from jamb.core.models import (
    Item,
    ItemCoverage,
    LinkedTest,
    MatrixMetadata,
    TestEnvironment,
    TraceabilityGraph,
)
from jamb.coverage.serializer import (
    COVERAGE_FILE,
    load_coverage,
    save_coverage,
)


class TestCoverageFile:
    """Tests for the default coverage file constant."""

    def test_coverage_file_name(self):
        """Test that the default coverage file name is .jamb."""
        assert COVERAGE_FILE == ".jamb"


class TestSaveCoverage:
    """Tests for the save_coverage function."""

    def test_save_creates_file(self, tmp_path: Path):
        """Test that save_coverage creates the output file."""
        output_path = tmp_path / ".jamb"
        graph = TraceabilityGraph()
        coverage: dict[str, ItemCoverage] = {}

        save_coverage(coverage, graph, str(output_path))

        assert output_path.exists()

    def test_save_writes_valid_json(self, tmp_path: Path):
        """Test that saved file is valid JSON."""
        output_path = tmp_path / ".jamb"
        graph = TraceabilityGraph()
        coverage: dict[str, ItemCoverage] = {}

        save_coverage(coverage, graph, str(output_path))

        content = output_path.read_text()
        data = json.loads(content)
        assert "version" in data
        assert data["version"] == 1

    def test_save_includes_coverage_data(self, tmp_path: Path):
        """Test that coverage data is serialized correctly."""
        output_path = tmp_path / ".jamb"
        graph = TraceabilityGraph()

        item = Item(uid="SRS001", text="Test item", document_prefix="SRS")
        graph.add_item(item)

        linked_test = LinkedTest(
            test_nodeid="test_foo.py::test_bar",
            item_uid="SRS001",
            test_outcome="passed",
        )

        coverage = {
            "SRS001": ItemCoverage(item=item, linked_tests=[linked_test]),
        }

        save_coverage(coverage, graph, str(output_path))

        data = json.loads(output_path.read_text())
        assert "SRS001" in data["coverage"]
        assert data["coverage"]["SRS001"]["item"]["uid"] == "SRS001"
        assert len(data["coverage"]["SRS001"]["linked_tests"]) == 1

    def test_save_includes_metadata(self, tmp_path: Path):
        """Test that metadata is serialized when provided."""
        output_path = tmp_path / ".jamb"
        graph = TraceabilityGraph()
        coverage: dict[str, ItemCoverage] = {}

        metadata = MatrixMetadata(
            software_version="1.0.0",
            tester_id="CI",
            execution_timestamp="2024-01-01T00:00:00Z",
        )

        save_coverage(coverage, graph, str(output_path), metadata=metadata)

        data = json.loads(output_path.read_text())
        assert "metadata" in data
        assert data["metadata"]["software_version"] == "1.0.0"
        assert data["metadata"]["tester_id"] == "CI"

    def test_save_includes_graph_relationships(self, tmp_path: Path):
        """Test that graph relationships are preserved."""
        output_path = tmp_path / ".jamb"
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", ["SYS"])

        item = Item(uid="SRS001", text="Test item", document_prefix="SRS")
        graph.add_item(item)

        coverage: dict[str, ItemCoverage] = {}

        save_coverage(coverage, graph, str(output_path))

        data = json.loads(output_path.read_text())
        assert "SRS" in data["graph"]["document_parents"]
        assert "SYS" in data["graph"]["document_parents"]["SRS"]


class TestLoadCoverage:
    """Tests for the load_coverage function."""

    def test_load_raises_on_missing_file(self, tmp_path: Path):
        """Test that FileNotFoundError is raised for missing file."""
        with pytest.raises(FileNotFoundError):
            load_coverage(str(tmp_path / "nonexistent.jamb"))

    def test_load_raises_on_invalid_json(self, tmp_path: Path):
        """Test that ValueError is raised for invalid JSON."""
        bad_file = tmp_path / ".jamb"
        bad_file.write_text("not valid json")

        with pytest.raises(ValueError):
            load_coverage(str(bad_file))

    def test_load_roundtrip(self, tmp_path: Path):
        """Test that save/load roundtrip preserves data."""
        output_path = tmp_path / ".jamb"
        graph = TraceabilityGraph()
        graph.set_document_parents("SRS", ["SYS"])

        item = Item(
            uid="SRS001",
            text="Test item",
            document_prefix="SRS",
            header="Test Header",
        )
        graph.add_item(item)

        linked_test = LinkedTest(
            test_nodeid="test_foo.py::test_bar",
            item_uid="SRS001",
            test_outcome="passed",
            notes=["Note 1"],
        )

        original_coverage = {
            "SRS001": ItemCoverage(item=item, linked_tests=[linked_test]),
        }

        metadata = MatrixMetadata(
            software_version="1.0.0",
            tester_id="CI",
            execution_timestamp="2024-01-01T00:00:00Z",
        )

        save_coverage(original_coverage, graph, str(output_path), metadata=metadata)

        # Load and verify
        loaded_coverage, loaded_graph, loaded_metadata = load_coverage(str(output_path))

        assert "SRS001" in loaded_coverage
        assert loaded_coverage["SRS001"].item.uid == "SRS001"
        assert loaded_coverage["SRS001"].item.header == "Test Header"
        assert len(loaded_coverage["SRS001"].linked_tests) == 1
        assert loaded_coverage["SRS001"].linked_tests[0].test_outcome == "passed"

        assert loaded_graph.document_parents.get("SRS") == ["SYS"]
        assert "SRS001" in loaded_graph.items

        assert loaded_metadata is not None
        assert loaded_metadata.software_version == "1.0.0"
        assert loaded_metadata.tester_id == "CI"

    def test_load_with_environment(self, tmp_path: Path):
        """Test that environment data is deserialized correctly."""
        output_path = tmp_path / ".jamb"
        graph = TraceabilityGraph()
        coverage: dict[str, ItemCoverage] = {}

        env = TestEnvironment(
            os_name="Linux",
            os_version="5.4.0",
            python_version="3.10.0",
            platform="x86_64",
            processor="Intel",
            hostname="testhost",
            cpu_count=4,
            test_tools={"pytest": "7.0.0"},
        )

        metadata = MatrixMetadata(
            software_version="1.0.0",
            tester_id="CI",
            execution_timestamp="2024-01-01T00:00:00Z",
            environment=env,
        )

        save_coverage(coverage, graph, str(output_path), metadata=metadata)

        _, _, loaded_metadata = load_coverage(str(output_path))

        assert loaded_metadata is not None
        assert loaded_metadata.environment is not None
        assert loaded_metadata.environment.os_name == "Linux"
        assert loaded_metadata.environment.cpu_count == 4
        assert loaded_metadata.environment.test_tools == {"pytest": "7.0.0"}
