"""Tests for jamb.pytest_plugin.markers module."""

from unittest.mock import MagicMock

import pytest

from jamb.pytest_plugin.markers import get_requirement_markers, get_tc_id_marker


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

    def test_integer_uid_raises_type_error(self):
        """Integer arg raises TypeError."""
        mock_item = MagicMock()
        mock_marker = MagicMock()
        mock_marker.args = (42,)
        mock_item.iter_markers.return_value = [mock_marker]

        with pytest.raises(TypeError, match="must be strings"):
            get_requirement_markers(mock_item)

    def test_whitespace_uid_returned_as_is(self):
        """Whitespace in UID is not stripped."""
        mock_item = MagicMock()
        mock_marker = MagicMock()
        mock_marker.args = ("SRS 001",)
        mock_item.iter_markers.return_value = [mock_marker]

        uids = get_requirement_markers(mock_item)

        assert uids == ["SRS 001"]

    def test_none_argument_raises_type_error(self):
        """None argument raises TypeError."""
        mock_item = MagicMock()
        mock_marker = MagicMock()
        mock_marker.args = (None,)
        mock_item.iter_markers.return_value = [mock_marker]

        with pytest.raises(TypeError, match="must be strings"):
            get_requirement_markers(mock_item)

    def test_empty_string_argument(self):
        """Empty string argument raises ValueError."""
        import pytest

        mock_item = MagicMock()
        mock_marker = MagicMock()
        mock_marker.args = ("",)
        mock_item.iter_markers.return_value = [mock_marker]

        with pytest.raises(ValueError, match="Empty requirement UID"):
            get_requirement_markers(mock_item)

    def test_duplicate_uids_deduplicated(self):
        """Same UID from two markers is deduplicated to appear once."""
        mock_item = MagicMock()
        mock_marker1 = MagicMock()
        mock_marker1.args = ("SRS001",)
        mock_marker2 = MagicMock()
        mock_marker2.args = ("SRS001",)
        mock_item.iter_markers.return_value = [mock_marker1, mock_marker2]

        uids = get_requirement_markers(mock_item)

        assert uids == ["SRS001"]


class TestGetTcIdMarker:
    """Tests for get_tc_id_marker function."""

    def test_single_tc_id_marker(self):
        """Test extracting a valid TC ID."""
        mock_item = MagicMock()
        mock_item.nodeid = "test_foo.py::test_bar"
        mock_marker = MagicMock()
        mock_marker.args = ("TC001",)
        mock_item.iter_markers.return_value = [mock_marker]

        tc_id = get_tc_id_marker(mock_item)

        assert tc_id == "TC001"
        mock_item.iter_markers.assert_called_once_with("tc_id")

    def test_tc_id_with_whitespace_stripped(self):
        """Test that leading/trailing whitespace is stripped."""
        mock_item = MagicMock()
        mock_item.nodeid = "test_foo.py::test_bar"
        mock_marker = MagicMock()
        mock_marker.args = ("  TC001  ",)
        mock_item.iter_markers.return_value = [mock_marker]

        tc_id = get_tc_id_marker(mock_item)

        assert tc_id == "TC001"

    def test_no_marker_returns_none(self):
        """Test that no tc_id marker returns None."""
        mock_item = MagicMock()
        mock_item.iter_markers.return_value = []

        tc_id = get_tc_id_marker(mock_item)

        assert tc_id is None

    def test_raises_type_error_for_int_argument(self):
        """Integer argument raises TypeError."""
        mock_item = MagicMock()
        mock_item.nodeid = "test_foo.py::test_bar"
        mock_marker = MagicMock()
        mock_marker.args = (42,)
        mock_item.iter_markers.return_value = [mock_marker]

        with pytest.raises(TypeError, match="must be a string"):
            get_tc_id_marker(mock_item)

    def test_raises_type_error_for_none_argument(self):
        """None argument raises TypeError."""
        mock_item = MagicMock()
        mock_item.nodeid = "test_foo.py::test_bar"
        mock_marker = MagicMock()
        mock_marker.args = (None,)
        mock_item.iter_markers.return_value = [mock_marker]

        with pytest.raises(TypeError, match="must be a string"):
            get_tc_id_marker(mock_item)

    def test_raises_value_error_for_no_arguments(self):
        """Marker with no args raises ValueError."""
        mock_item = MagicMock()
        mock_item.nodeid = "test_foo.py::test_bar"
        mock_marker = MagicMock()
        mock_marker.args = ()
        mock_item.iter_markers.return_value = [mock_marker]

        with pytest.raises(ValueError, match="exactly one argument"):
            get_tc_id_marker(mock_item)

    def test_raises_value_error_for_multiple_arguments(self):
        """Marker with multiple args raises ValueError."""
        mock_item = MagicMock()
        mock_item.nodeid = "test_foo.py::test_bar"
        mock_marker = MagicMock()
        mock_marker.args = ("TC001", "TC002")
        mock_item.iter_markers.return_value = [mock_marker]

        with pytest.raises(ValueError, match="exactly one argument"):
            get_tc_id_marker(mock_item)

    def test_raises_value_error_for_empty_string(self):
        """Empty string raises ValueError."""
        mock_item = MagicMock()
        mock_item.nodeid = "test_foo.py::test_bar"
        mock_marker = MagicMock()
        mock_marker.args = ("",)
        mock_item.iter_markers.return_value = [mock_marker]

        with pytest.raises(ValueError, match="Empty tc_id"):
            get_tc_id_marker(mock_item)

    def test_raises_value_error_for_whitespace_only(self):
        """Whitespace-only string raises ValueError."""
        mock_item = MagicMock()
        mock_item.nodeid = "test_foo.py::test_bar"
        mock_marker = MagicMock()
        mock_marker.args = ("   ",)
        mock_item.iter_markers.return_value = [mock_marker]

        with pytest.raises(ValueError, match="Empty tc_id"):
            get_tc_id_marker(mock_item)

    def test_raises_value_error_for_multiple_markers(self):
        """Multiple tc_id markers raises ValueError."""
        mock_item = MagicMock()
        mock_item.nodeid = "test_foo.py::test_bar"
        mock_marker1 = MagicMock()
        mock_marker1.args = ("TC001",)
        mock_marker2 = MagicMock()
        mock_marker2.args = ("TC002",)
        mock_item.iter_markers.return_value = [mock_marker1, mock_marker2]

        with pytest.raises(ValueError, match="Multiple tc_id markers"):
            get_tc_id_marker(mock_item)

    def test_special_characters_in_tc_id(self):
        """TC ID with hyphens and underscores works."""
        mock_item = MagicMock()
        mock_item.nodeid = "test_foo.py::test_bar"
        mock_marker = MagicMock()
        mock_marker.args = ("TC-AUTH_001",)
        mock_item.iter_markers.return_value = [mock_marker]

        tc_id = get_tc_id_marker(mock_item)

        assert tc_id == "TC-AUTH_001"
