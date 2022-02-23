from unittest import mock

import pytest

from ncal import core


@pytest.mark.parametrize("property_type", ("relation", "other"))
@mock.patch("notion_client.Client")
def test_get_property_text(MockNotionClient, property_type):
    property_name = "rel_name"
    property_text = "Property Title Text"
    example_page = {"properties": {property_name: {"relation": [{"id": "12345"}]}}}

    # mocking of notion response
    client = MockNotionClient.return_value
    client.pages.properties.retrieve.return_value = {
        "name": "asdf",
        "results": [{"a": "asdf", "title": {"plain_text": property_text}}],
    }

    if property_type == "relation":
        assert (
            core.get_property_text(client, example_page, property_name, property_type)
            == property_text
        )
    else:
        with pytest.raises(ValueError):
            core.get_property_text(client, example_page, property_name, property_type)
