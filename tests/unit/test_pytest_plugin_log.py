"""Tests for jamb.pytest_plugin.log module."""

import pytest

from jamb.pytest_plugin.log import JAMB_LOG_KEY, JambLog


class TestJambLogKey:
    """Tests for JAMB_LOG_KEY constant."""

    def test_stash_key_is_pytest_stash_key(self):
        """Test JAMB_LOG_KEY is a proper pytest StashKey."""
        assert isinstance(JAMB_LOG_KEY, pytest.StashKey)


class TestJambLog:
    """Tests for JambLog class."""

    def test_init_empty_notes(self):
        """Test JambLog initializes with empty notes list."""
        log = JambLog()
        assert log.notes == []

    def test_note_adds_to_list(self):
        """Test note() adds note to internal list."""
        log = JambLog()
        log.note("Test note")
        assert log.notes == ["Test note"]

    def test_note_multiple(self):
        """Test adding multiple notes."""
        log = JambLog()
        log.note("First")
        log.note("Second")
        log.note("Third")
        assert log.notes == ["First", "Second", "Third"]

    def test_note_converts_to_string(self):
        """Test note() converts non-string to string."""
        log = JambLog()
        log.note(123)  # type: ignore[arg-type]
        log.note(True)  # type: ignore[arg-type]
        log.note(3.14)  # type: ignore[arg-type]
        assert log.notes == ["123", "True", "3.14"]

    def test_notes_returns_copy(self):
        """Test notes property returns a copy, not the internal list."""
        log = JambLog()
        log.note("Original")

        notes = log.notes
        notes.append("Modified")

        # Original should be unchanged
        assert log.notes == ["Original"]
        assert "Modified" not in log.notes

    def test_notes_property_is_list(self):
        """Test notes property returns a list type."""
        log = JambLog()
        assert isinstance(log.notes, list)


class TestJambLogTestActions:
    """Tests for JambLog test_action() method."""

    def test_init_empty_test_actions(self):
        """Test JambLog initializes with empty test_actions list."""
        log = JambLog()
        assert log.test_actions == []

    def test_test_action_adds_to_list(self):
        """Test test_action() adds action to internal list."""
        log = JambLog()
        log.test_action("Clicked submit button")
        assert log.test_actions == ["Clicked submit button"]

    def test_test_action_multiple(self):
        """Test adding multiple test actions."""
        log = JambLog()
        log.test_action("Step 1")
        log.test_action("Step 2")
        assert log.test_actions == ["Step 1", "Step 2"]

    def test_test_action_converts_to_string(self):
        """Test test_action() converts non-string to string."""
        log = JambLog()
        log.test_action(42)  # type: ignore[arg-type]
        assert log.test_actions == ["42"]

    def test_test_actions_returns_copy(self):
        """Test test_actions property returns a copy."""
        log = JambLog()
        log.test_action("Original")

        actions = log.test_actions
        actions.append("Modified")

        assert log.test_actions == ["Original"]


class TestJambLogExpectedResults:
    """Tests for JambLog expected_result() method."""

    def test_init_empty_expected_results(self):
        """Test JambLog initializes with empty expected_results list."""
        log = JambLog()
        assert log.expected_results == []

    def test_expected_result_adds_to_list(self):
        """Test expected_result() adds result to internal list."""
        log = JambLog()
        log.expected_result("Login succeeds")
        assert log.expected_results == ["Login succeeds"]

    def test_expected_result_multiple(self):
        """Test adding multiple expected results."""
        log = JambLog()
        log.expected_result("Result 1")
        log.expected_result("Result 2")
        assert log.expected_results == ["Result 1", "Result 2"]

    def test_expected_result_converts_to_string(self):
        """Test expected_result() converts non-string to string."""
        log = JambLog()
        log.expected_result(True)  # type: ignore[arg-type]
        assert log.expected_results == ["True"]

    def test_expected_results_returns_copy(self):
        """Test expected_results property returns a copy."""
        log = JambLog()
        log.expected_result("Original")

        results = log.expected_results
        results.append("Modified")

        assert log.expected_results == ["Original"]


class TestJambLogActualResults:
    """Tests for JambLog actual_result() method."""

    def test_init_empty_actual_results(self):
        """Test JambLog initializes with empty actual_results list."""
        log = JambLog()
        assert log.actual_results == []

    def test_actual_result_adds_to_list(self):
        """Test actual_result() adds result to internal list."""
        log = JambLog()
        log.actual_result("Login returned: success")
        assert log.actual_results == ["Login returned: success"]

    def test_actual_result_multiple(self):
        """Test adding multiple actual results."""
        log = JambLog()
        log.actual_result("Result 1")
        log.actual_result("Result 2")
        assert log.actual_results == ["Result 1", "Result 2"]

    def test_actual_result_converts_to_string(self):
        """Test actual_result() converts non-string to string."""
        log = JambLog()
        log.actual_result(42)  # type: ignore[arg-type]
        assert log.actual_results == ["42"]

    def test_actual_results_returns_copy(self):
        """Test actual_results property returns a copy."""
        log = JambLog()
        log.actual_result("Original")

        results = log.actual_results
        results.append("Modified")

        assert log.actual_results == ["Original"]
