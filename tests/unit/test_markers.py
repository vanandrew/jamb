"""Tests for jamb.pytest_plugin.markers module."""

from unittest.mock import MagicMock

from jamb.pytest_plugin.markers import get_requirement_markers


class TestGetRequirementMarkers:
    """Tests for get_requirement_markers function."""

    def test_single_requirement_marker(self):
        """Test extracting a single requirement UID."""
        mock_item = MagicMock()
        mock_marker = MagicMock()
        mock_marker.args = ("SRS001",)
        mock_item.iter_markers.return_value = [mock_marker]

        uids = get_requirement_markers(mock_item)

        assert uids == ["SRS001"]
        mock_item.iter_markers.assert_called_once_with("requirement")

    def test_multiple_uids_in_one_marker(self):
        """Test extracting multiple UIDs from a single marker."""
        mock_item = MagicMock()
        mock_marker = MagicMock()
        mock_marker.args = ("SRS001", "SRS002", "SRS003")
        mock_item.iter_markers.return_value = [mock_marker]

        uids = get_requirement_markers(mock_item)

        assert uids == ["SRS001", "SRS002", "SRS003"]

    def test_multiple_markers(self):
        """Test extracting UIDs from multiple markers."""
        mock_item = MagicMock()
        mock_marker1 = MagicMock()
        mock_marker1.args = ("SRS001",)
        mock_marker2 = MagicMock()
        mock_marker2.args = ("SYS001",)
        mock_item.iter_markers.return_value = [mock_marker1, mock_marker2]

        uids = get_requirement_markers(mock_item)

        assert uids == ["SRS001", "SYS001"]

    def test_no_markers(self):
        """Test that no markers returns empty list."""
        mock_item = MagicMock()
        mock_item.iter_markers.return_value = []

        uids = get_requirement_markers(mock_item)

        assert uids == []

    def test_empty_marker_args(self):
        """Test marker with no args returns empty list."""
        mock_item = MagicMock()
        mock_marker = MagicMock()
        mock_marker.args = ()
        mock_item.iter_markers.return_value = [mock_marker]

        uids = get_requirement_markers(mock_item)

        assert uids == []

    def test_integer_uid_included(self):
        """Integer arg is included (extend doesn't filter by type)."""
        mock_item = MagicMock()
        mock_marker = MagicMock()
        mock_marker.args = (42,)
        mock_item.iter_markers.return_value = [mock_marker]

        uids = get_requirement_markers(mock_item)

        assert uids == [42]

    def test_whitespace_uid_returned_as_is(self):
        """Whitespace in UID is not stripped."""
        mock_item = MagicMock()
        mock_marker = MagicMock()
        mock_marker.args = ("SRS 001",)
        mock_item.iter_markers.return_value = [mock_marker]

        uids = get_requirement_markers(mock_item)

        assert uids == ["SRS 001"]

    def test_none_argument_included(self):
        """None argument is included."""
        mock_item = MagicMock()
        mock_marker = MagicMock()
        mock_marker.args = (None,)
        mock_item.iter_markers.return_value = [mock_marker]

        uids = get_requirement_markers(mock_item)

        assert uids == [None]

    def test_empty_string_argument(self):
        """Empty string argument is included."""
        mock_item = MagicMock()
        mock_marker = MagicMock()
        mock_marker.args = ("",)
        mock_item.iter_markers.return_value = [mock_marker]

        uids = get_requirement_markers(mock_item)

        assert uids == [""]

    def test_duplicate_uids_not_deduplicated(self):
        """Same UID from two markers appears twice."""
        mock_item = MagicMock()
        mock_marker1 = MagicMock()
        mock_marker1.args = ("SRS001",)
        mock_marker2 = MagicMock()
        mock_marker2.args = ("SRS001",)
        mock_item.iter_markers.return_value = [mock_marker1, mock_marker2]

        uids = get_requirement_markers(mock_item)

        assert uids == ["SRS001", "SRS001"]
