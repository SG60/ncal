"""Test notion_utils module."""
import hypothesis
import pytest
from hypothesis import strategies as st

from ncal import notion_utils


# @pytest.mark.xfail
@pytest.mark.parametrize(
    "test_list,output",
    [
        (
            [
                {
                    "type": "mention",
                    "mention": {
                        "type": "page",
                        "page": {"id": "asdf-1234567"},
                    },
                    "annotations": {},
                    "plain_text": "Untitled",
                    "href": "https://www.notion.so/dffc0e25",
                },
                {
                    "type": "text",
                    "text": {"content": " deadline", "link": None},
                    "annotations": {},
                    "plain_text": " deadline",
                    "href": None,
                },
            ],
            "Untitled deadline",
        ),
        (
            [
                {"type": "text", "plain_text": "12"},
                {"plain_text": "12"},
                {"plain_text": "12"},
            ],
            "121212",
        ),
    ],
)
def test_collapse_rich_text_property_parametrized(test_list, output):
    """Test a function to convert a Notion rich text property to plain text."""
    assert notion_utils.collapse_rich_text_property(test_list) == output


@hypothesis.given(
    test_list=st.lists(
        st.fixed_dictionaries(
            {"type": st.text(), "plain_text": st.text(), "href": st.none()},
            optional={"text": st.none(), "mention": st.none()},
        )
    )
)
def test_collapse_rich_text_property(test_list):
    """Test notion_utils.collapse_rich_text_property.

    Test a function to convert a Notion rich text property to plain text
    using hypothesis.
    """
    assert notion_utils.collapse_rich_text_property(test_list) == "".join(
        i["plain_text"] for i in test_list
    )
