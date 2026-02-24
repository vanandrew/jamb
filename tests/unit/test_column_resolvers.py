"""Tests for matrix column resolvers."""

from jamb.core.models import Item, MatrixColumnConfig
from jamb.matrix.column_resolvers import resolve_column, resolve_review_status
from jamb.storage.items import compute_content_hash


class TestResolveReviewStatus:
    """Tests for the review_status built-in resolver."""

    def test_not_reviewed(self):
        """Item with reviewed=None returns 'Not Reviewed'."""
        item = Item(uid="SRS001", text="Requirement", document_prefix="SRS", reviewed=None)
        assert resolve_review_status(item) == "Not Reviewed"

    def test_reviewed_matching_hash(self):
        """Item with reviewed hash matching current content returns 'Reviewed'."""
        item = Item(uid="SRS001", text="Requirement", document_prefix="SRS")
        current_hash = compute_content_hash(
            {"text": item.text, "header": item.header, "links": item.links, "type": item.type}
        )
        item.reviewed = current_hash
        assert resolve_review_status(item) == "Reviewed"

    def test_reviewed_mismatched_hash(self):
        """Item with stale reviewed hash returns 'Suspect'."""
        item = Item(uid="SRS001", text="Updated requirement", document_prefix="SRS")
        item.reviewed = "stale_hash_from_before"
        assert resolve_review_status(item) == "Suspect"


class TestResolveColumn:
    """Tests for the generic resolve_column dispatcher."""

    def test_custom_attribute_present(self):
        """Custom attribute that exists is returned as string."""
        item = Item(
            uid="SRS001",
            text="Req",
            document_prefix="SRS",
            custom_attributes={"safety_class": "B"},
        )
        config = MatrixColumnConfig(key="safety_class", header="Safety Class")
        assert resolve_column(item, config) == "B"

    def test_custom_attribute_missing(self):
        """Missing custom attribute returns the default."""
        item = Item(uid="SRS001", text="Req", document_prefix="SRS")
        config = MatrixColumnConfig(key="safety_class", header="Safety Class", default="-")
        assert resolve_column(item, config) == "-"

    def test_custom_attribute_non_string(self):
        """Non-string custom attribute values are stringified."""
        item = Item(
            uid="SRS001",
            text="Req",
            document_prefix="SRS",
            custom_attributes={"priority": 1},
        )
        config = MatrixColumnConfig(key="priority", header="Priority")
        assert resolve_column(item, config) == "1"

    def test_custom_attribute_bool(self):
        """Boolean custom attribute values are stringified."""
        item = Item(
            uid="SRS001",
            text="Req",
            document_prefix="SRS",
            custom_attributes={"critical": True},
        )
        config = MatrixColumnConfig(key="critical", header="Critical")
        assert resolve_column(item, config) == "True"

    def test_built_in_review_status(self):
        """Built-in review_status dispatches to the reviewer resolver."""
        item = Item(uid="SRS001", text="Req", document_prefix="SRS", reviewed=None)
        config = MatrixColumnConfig(key="review_status", header="Review Status", source="built_in")
        assert resolve_column(item, config) == "Not Reviewed"

    def test_built_in_unknown_key(self):
        """Unknown built-in key returns the default."""
        item = Item(uid="SRS001", text="Req", document_prefix="SRS")
        config = MatrixColumnConfig(key="unknown_thing", header="X", source="built_in", default="N/A")
        assert resolve_column(item, config) == "N/A"

    def test_custom_default_override(self):
        """Custom default value is used when attribute is missing."""
        item = Item(uid="SRS001", text="Req", document_prefix="SRS")
        config = MatrixColumnConfig(key="owner", header="Owner", default="Unassigned")
        assert resolve_column(item, config) == "Unassigned"
