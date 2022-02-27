"""Some utility functions for working with Notion properties etc."""
from typing import Any, Literal

import notion_client


def collapse_rich_text_property(property: list[dict[str, Any]]) -> str:
    """Collapse a Notion Rich Text property into a single string.

    Args:
        property: An array of rich text objects (as returned by a rich text property)
    Returns:
        The plain_text of the rich text objects concatenated.
    """
    return "".join((i["plain_text"] for i in property))


def get_relation_title(
    notion: notion_client.Client, notion_page: dict[str, Any], relation_name: str
) -> str:
    """Get the title of the first page in a relation property."""
    relation_property: list = notion_page["properties"][relation_name]["relation"]
    if relation_property:
        relation_id: str = relation_property[0]["id"]
        relation_title: dict = notion.pages.properties.retrieve(
            relation_id, "title"
        )  # type:ignore
        return relation_title["results"][0]["title"]["plain_text"]
    else:
        return ""


def get_property_text(
    notion: notion_client.Client,
    notion_page: dict[str, Any],
    property_name: str,
    property_type: Literal["relation", "select"],
) -> str:
    """Get the text contained within several different types of property.

    Note: Currently only relation and select are implemented.
    """
    text: str
    if property_type == "select":
        text = notion_page["properties"][property_name]["select"]["name"]
    elif property_type == "relation":
        text = get_relation_title(
            notion=notion, notion_page=notion_page, relation_name=property_name
        )
    else:
        raise ValueError
    return text
