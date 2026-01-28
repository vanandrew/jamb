"""Logging utilities for jamb test messages."""

import pytest

# Stash key for storing JambLog instances per test
JAMB_LOG_KEY = pytest.StashKey["JambLog"]()


class JambLog:
    """
    Collector for custom test messages to include in traceability matrix.

    Usage in tests::

        @pytest.mark.requirement("SRS001")
        def test_something(jamb_log):
            jamb_log.note("Custom verification note")
            jamb_log.test_action("Entered valid credentials")
            jamb_log.expected_result("Login succeeds")
            result = do_something()
            jamb_log.actual_result(f"Got: {result}")
            assert something
    """

    def __init__(self) -> None:
        self._notes: list[str] = []
        self._test_actions: list[str] = []
        self._expected_results: list[str] = []
        self._actual_results: list[str] = []

    def note(self, msg: str) -> None:
        """
        Log a custom note to be included in the traceability matrix.

        Args:
            msg: The note to log. Will appear in the matrix output
                 for any requirement markers on this test.
        """
        self._notes.append(str(msg))

    def test_action(self, action: str) -> None:
        """
        Log a test action to be included in the traceability matrix.

        Args:
            action: Description of a test action performed.
                    Will appear in the "Test Actions" column.
        """
        self._test_actions.append(str(action))

    def expected_result(self, result: str) -> None:
        """
        Log an expected result to be included in the traceability matrix.

        Args:
            result: Description of an expected result.
                    Will appear in the "Expected Results" column.
        """
        self._expected_results.append(str(result))

    def actual_result(self, result: str) -> None:
        """
        Log an actual result to be included in the traceability matrix.

        Args:
            result: Description of an actual result observed during test execution.
                    Will appear in the "Actual Results" column.
        """
        self._actual_results.append(str(result))

    @property
    def notes(self) -> list[str]:
        """Return all logged notes."""
        return self._notes.copy()

    @property
    def test_actions(self) -> list[str]:
        """Return all logged test actions."""
        return self._test_actions.copy()

    @property
    def expected_results(self) -> list[str]:
        """Return all logged expected results."""
        return self._expected_results.copy()

    @property
    def actual_results(self) -> list[str]:
        """Return all logged actual results."""
        return self._actual_results.copy()
