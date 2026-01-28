"""Tests for jamb.pytest_plugin.log module."""

from jamb.pytest_plugin.log import JambLog


class TestJambLog:
    def test_initial_state_empty(self):
        log = JambLog()
        assert log.notes == []
        assert log.test_actions == []
        assert log.expected_results == []

    def test_note_appends(self):
        log = JambLog()
        log.note("first note")
        log.note("second note")
        assert log.notes == ["first note", "second note"]

    def test_test_action_appends(self):
        log = JambLog()
        log.test_action("click button")
        log.test_action("submit form")
        assert log.test_actions == ["click button", "submit form"]

    def test_expected_result_appends(self):
        log = JambLog()
        log.expected_result("page loads")
        log.expected_result("success message")
        assert log.expected_results == ["page loads", "success message"]

    def test_notes_returns_copy(self):
        log = JambLog()
        log.note("a note")
        returned = log.notes
        returned.append("extra")
        assert log.notes == ["a note"]

    def test_test_actions_returns_copy(self):
        log = JambLog()
        log.test_action("an action")
        returned = log.test_actions
        returned.append("extra")
        assert log.test_actions == ["an action"]

    def test_expected_results_returns_copy(self):
        log = JambLog()
        log.expected_result("a result")
        returned = log.expected_results
        returned.append("extra")
        assert log.expected_results == ["a result"]

    def test_note_converts_non_string_to_str(self):
        log = JambLog()
        log.note(42)
        assert log.notes == ["42"]

    def test_test_action_converts_non_string_to_str(self):
        log = JambLog()
        log.test_action(None)
        assert log.test_actions == ["None"]

    def test_expected_result_converts_non_string_to_str(self):
        log = JambLog()
        log.expected_result(3.14)
        assert log.expected_results == ["3.14"]

    def test_empty_string_note(self):
        log = JambLog()
        log.note("")
        assert log.notes == [""]

    def test_unicode_characters(self):
        """Unicode in notes preserved."""
        log = JambLog()
        log.note("Ünïcödé 日本語")
        assert log.notes == ["Ünïcödé 日本語"]

    def test_very_long_note(self):
        """2000-char note stored in full."""
        log = JambLog()
        long_note = "x" * 2000
        log.note(long_note)
        assert log.notes == [long_note]
        assert len(log.notes[0]) == 2000

    def test_special_characters(self):
        """Newlines, tabs, HTML entities preserved."""
        log = JambLog()
        log.note("line1\nline2\ttab &amp; <b>bold</b>")
        assert log.notes == ["line1\nline2\ttab &amp; <b>bold</b>"]

    def test_large_number_of_entries(self):
        """200 notes all stored."""
        log = JambLog()
        for i in range(200):
            log.note(f"note {i}")
        assert len(log.notes) == 200
        assert log.notes[0] == "note 0"
        assert log.notes[199] == "note 199"

    def test_mixed_methods_independent(self):
        """Interleaved note/test_action/expected_result keep separate lists."""
        log = JambLog()
        log.note("n1")
        log.test_action("a1")
        log.expected_result("r1")
        log.note("n2")
        log.test_action("a2")
        log.expected_result("r2")

        assert log.notes == ["n1", "n2"]
        assert log.test_actions == ["a1", "a2"]
        assert log.expected_results == ["r1", "r2"]

    def test_none_note(self):
        """note(None) stores 'None' as string."""
        log = JambLog()
        log.note(None)
        assert log.notes == ["None"]

    def test_actual_result_appends(self):
        """actual_result() appends to list."""
        log = JambLog()
        log.actual_result("result1")
        log.actual_result("result2")
        assert log.actual_results == ["result1", "result2"]

    def test_actual_results_returns_copy(self):
        """actual_results property returns a copy."""
        log = JambLog()
        log.actual_result("a result")
        returned = log.actual_results
        returned.append("extra")
        assert log.actual_results == ["a result"]

    def test_actual_result_converts_non_string_to_str(self):
        """actual_result() converts non-string to str."""
        log = JambLog()
        log.actual_result(123)
        assert log.actual_results == ["123"]

    def test_actual_results_initial_empty(self):
        """actual_results starts empty."""
        log = JambLog()
        assert log.actual_results == []

    def test_all_four_methods_independent(self):
        """All four logging methods maintain separate lists."""
        log = JambLog()
        log.note("n1")
        log.test_action("a1")
        log.expected_result("e1")
        log.actual_result("r1")
        log.note("n2")
        log.test_action("a2")
        log.expected_result("e2")
        log.actual_result("r2")

        assert log.notes == ["n1", "n2"]
        assert log.test_actions == ["a1", "a2"]
        assert log.expected_results == ["e1", "e2"]
        assert log.actual_results == ["r1", "r2"]
