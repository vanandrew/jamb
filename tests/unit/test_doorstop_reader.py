"""Tests for jamb.doorstop.reader module."""

from unittest.mock import MagicMock

from jamb.doorstop.reader import build_traceability_graph, read_tree


class TestReadTree:
    """Tests for read_tree function."""

    def test_extracts_items_from_tree(self, mock_doorstop_tree):
        """Test that read_tree extracts items from doorstop tree."""
        items = read_tree(mock_doorstop_tree)

        assert len(items) == 1
        assert items[0].uid == "SRS001"
        assert items[0].text == "Test requirement text"

    def test_filters_by_document_prefix(self):
        """Test that document_prefixes parameter filters documents."""
        mock_tree = MagicMock()
        mock_doc = MagicMock()
        mock_doc.prefix = "SRS"

        mock_item = MagicMock()
        mock_item.uid = "SRS001"
        mock_item.text = "Test"
        mock_item.active = True
        mock_item.normative = True
        mock_item.header = ""
        mock_item.level = 1.0
        mock_item.links = []
        mock_item.data = {}
        mock_doc.__iter__ = lambda _: iter([mock_item])

        mock_tree.find_document.return_value = mock_doc

        items = read_tree(mock_tree, document_prefixes=["SRS"])

        mock_tree.find_document.assert_called_once_with("SRS")
        assert len(items) == 1

    def test_excludes_inactive_by_default(self):
        """Test that inactive items are excluded by default."""
        mock_tree = MagicMock()
        mock_doc = MagicMock()
        mock_doc.prefix = "SRS"

        mock_active = MagicMock()
        mock_active.uid = "SRS001"
        mock_active.text = "Active"
        mock_active.active = True
        mock_active.normative = True
        mock_active.header = ""
        mock_active.level = 1.0
        mock_active.links = []
        mock_active.data = {}

        mock_inactive = MagicMock()
        mock_inactive.active = False

        mock_doc.__iter__ = lambda _: iter([mock_active, mock_inactive])
        mock_tree.documents = [mock_doc]

        items = read_tree(mock_tree)

        assert len(items) == 1
        assert items[0].uid == "SRS001"

    def test_includes_inactive_when_requested(self):
        """Test that inactive items are included when include_inactive=True."""
        mock_tree = MagicMock()
        mock_doc = MagicMock()
        mock_doc.prefix = "SRS"

        mock_active = MagicMock()
        mock_active.uid = "SRS001"
        mock_active.text = "Active"
        mock_active.active = True
        mock_active.normative = True
        mock_active.header = ""
        mock_active.level = 1.0
        mock_active.links = []
        mock_active.data = {}

        mock_inactive = MagicMock()
        mock_inactive.uid = "SRS002"
        mock_inactive.text = "Inactive"
        mock_inactive.active = False
        mock_inactive.normative = True
        mock_inactive.header = ""
        mock_inactive.level = 1.0
        mock_inactive.links = []
        mock_inactive.data = {}

        mock_doc.__iter__ = lambda _: iter([mock_active, mock_inactive])
        mock_tree.documents = [mock_doc]

        items = read_tree(mock_tree, include_inactive=True)

        assert len(items) == 2

    def test_extracts_links(self):
        """Test that links are extracted correctly."""
        mock_tree = MagicMock()
        mock_doc = MagicMock()
        mock_doc.prefix = "SRS"

        mock_item = MagicMock()
        mock_item.uid = "SRS001"
        mock_item.text = "Test"
        mock_item.active = True
        mock_item.normative = True
        mock_item.header = ""
        mock_item.level = 1.0
        mock_item.links = [MagicMock(__str__=lambda _: "SYS001")]
        mock_item.data = {}
        mock_doc.__iter__ = lambda _: iter([mock_item])
        mock_tree.documents = [mock_doc]

        items = read_tree(mock_tree)

        assert items[0].links == ["SYS001"]

    def test_extracts_custom_attributes(self):
        """Test that custom attributes are extracted."""
        mock_tree = MagicMock()
        mock_doc = MagicMock()
        mock_doc.prefix = "SRS"

        mock_item = MagicMock()
        mock_item.uid = "SRS001"
        mock_item.text = "Test"
        mock_item.active = True
        mock_item.normative = True
        mock_item.header = ""
        mock_item.level = 1.0
        mock_item.links = []
        mock_item.data = {
            "active": True,  # Standard field, should be excluded
            "custom_field": "custom_value",  # Custom field
        }
        mock_doc.__iter__ = lambda _: iter([mock_item])
        mock_tree.documents = [mock_doc]

        items = read_tree(mock_tree)

        assert "custom_field" in items[0].custom_attributes
        assert items[0].custom_attributes["custom_field"] == "custom_value"
        assert "active" not in items[0].custom_attributes


class TestBuildTraceabilityGraph:
    """Tests for build_traceability_graph function."""

    def test_builds_graph_with_items(self, mock_doorstop_tree):
        """Test that build_traceability_graph creates graph with items."""
        graph = build_traceability_graph(mock_doorstop_tree)

        assert "SRS001" in graph.items
        assert graph.items["SRS001"].text == "Test requirement text"

    def test_sets_document_parents(self):
        """Test that document parent relationships are set."""
        mock_tree = MagicMock()
        mock_doc = MagicMock()
        mock_doc.prefix = "SRS"
        mock_doc.parent = "SYS"
        mock_doc.__iter__ = lambda _: iter([])
        mock_tree.documents = [mock_doc]

        graph = build_traceability_graph(mock_tree)

        assert graph.document_parents["SRS"] == "SYS"

    def test_sets_root_document_parent_to_none(self):
        """Test that root documents have None as parent."""
        mock_tree = MagicMock()
        mock_doc = MagicMock()
        mock_doc.prefix = "UN"
        mock_doc.parent = None
        mock_doc.__iter__ = lambda _: iter([])
        mock_tree.documents = [mock_doc]

        graph = build_traceability_graph(mock_tree)

        assert graph.document_parents["UN"] is None

    def test_builds_graph_with_document_prefixes(self):
        """Test build_traceability_graph with specific document_prefixes."""
        mock_tree = MagicMock()

        mock_srs_doc = MagicMock()
        mock_srs_doc.prefix = "SRS"
        mock_srs_doc.parent = "SYS"

        mock_item = MagicMock()
        mock_item.uid = "SRS001"
        mock_item.text = "Test"
        mock_item.active = True
        mock_item.normative = True
        mock_item.header = ""
        mock_item.level = 1.0
        mock_item.links = []
        mock_item.data = {}
        mock_srs_doc.__iter__ = lambda _: iter([mock_item])

        mock_tree.find_document.return_value = mock_srs_doc

        graph = build_traceability_graph(mock_tree, document_prefixes=["SRS"])

        # find_document is called twice: once in build_traceability_graph,
        # once in read_tree
        assert mock_tree.find_document.call_count == 2
        mock_tree.find_document.assert_any_call("SRS")
        assert "SRS001" in graph.items
        assert graph.document_parents["SRS"] == "SYS"

    def test_builds_graph_with_include_inactive(self):
        """Test build_traceability_graph with include_inactive=True."""
        mock_tree = MagicMock()
        mock_doc = MagicMock()
        mock_doc.prefix = "SRS"
        mock_doc.parent = None

        mock_active = MagicMock()
        mock_active.uid = "SRS001"
        mock_active.text = "Active"
        mock_active.active = True
        mock_active.normative = True
        mock_active.header = ""
        mock_active.level = 1.0
        mock_active.links = []
        mock_active.data = {}

        mock_inactive = MagicMock()
        mock_inactive.uid = "SRS002"
        mock_inactive.text = "Inactive"
        mock_inactive.active = False
        mock_inactive.normative = True
        mock_inactive.header = ""
        mock_inactive.level = 1.0
        mock_inactive.links = []
        mock_inactive.data = {}

        mock_doc.__iter__ = lambda _: iter([mock_active, mock_inactive])
        mock_tree.documents = [mock_doc]

        graph = build_traceability_graph(mock_tree, include_inactive=True)

        assert "SRS001" in graph.items
        assert "SRS002" in graph.items
