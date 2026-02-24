"""Resolvers for extra columns in the full chain traceability matrix."""

from __future__ import annotations

from jamb.core.models import Item, MatrixColumnConfig
from jamb.storage.items import compute_content_hash


#: Built-in column keys recognised by :func:`resolve_column`.
BUILT_IN_COLUMNS: frozenset[str] = frozenset({"review_status"})


def resolve_review_status(item: Item) -> str:
    """Derive review status from :attr:`Item.reviewed`.

    Returns:
        ``"Reviewed"`` if the stored hash matches current content,
        ``"Suspect"`` if the hash exists but no longer matches, or
        ``"Not Reviewed"`` if :attr:`Item.reviewed` is ``None``.
    """
    if item.reviewed is None:
        return "Not Reviewed"

    current_hash = compute_content_hash(
        {
            "text": item.text,
            "header": item.header,
            "links": item.links,
            "type": item.type,
        }
    )

    if item.reviewed == current_hash:
        return "Reviewed"
    return "Suspect"


def resolve_column(item: Item, config: MatrixColumnConfig) -> str:
    """Resolve an extra column value for *item*.

    Args:
        item: The item to extract the value from.
        config: The column configuration.

    Returns:
        The display string for this column, or :attr:`config.default`
        when the value cannot be determined.
    """
    if config.source == "built_in":
        if config.key == "review_status":
            return resolve_review_status(item)
        return config.default

    # custom_attribute
    value = item.custom_attributes.get(config.key)
    if value is None:
        return config.default
    return str(value)
