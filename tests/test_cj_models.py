import pytest
from unittest.mock import MagicMock, PropertyMock

import fastapi

from src.cj_models import CollectionJsonRepresentor, Link, Query, TemplateData, ItemData
from transitions import TransitionManager, Form


# Helper to create a mock FastAPI request
def mock_request(url: str = "http://testserver/items", endpoint_name: str = "test_endpoint"):
    req = MagicMock(spec=fastapi.Request)
    req.url = url
    # Mock the scope to simulate a real request environment if needed by the code under test
    req.scope = {"endpoint": type('Endpoint', (), {'__name__': endpoint_name})}
    return req


# Test case for CollectionJsonRepresentor.to_collection_json
def test_to_collection_json_with_transitions():
    # 1. Setup Mocks
    mock_tm = MagicMock(spec=TransitionManager)

    # 2. Define Test Transitions (Forms)
    # GET transition without properties (becomes a Link)
    get_link_form = Form(
        id="link_form_id", # Added id
        rel="link_rel",
        href="/link_href",
        method="GET",
        properties=[],
        name="LinkName", # Used for internal reference, not directly in Link JSON
        title="Link Prompt from Title", # Used for Link.prompt
        tags="tag1" # Added tags
    )

    # GET transition with properties (becomes a Query)
    # Form.properties should be List[dict]
    get_query_form_properties_dicts = [
        {"name": "param1", "type": "string", "prompt": "Param 1 Query"},
        {"name": "param2", "type": "integer", "prompt": "Param 2 Query", "value": 10}
    ]
    get_query_form = Form(
        id="query_form_id", # Added id
        rel="query_rel",
        href="/query_href",
        method="GET",
        properties=get_query_form_properties_dicts,
        name="QueryName", # Used for internal reference
        title="Query Prompt from Title", # Used for Query.prompt
        tags="tag2" # Added tags
    )

    # POST transition with properties (becomes a Template)
    # Form.properties should be List[dict]
    post_template_form_properties_dicts = [
        {"name": "field1", "type": "string", "prompt": "Field 1 Template", "required": True},
        {"name": "field2", "type": "boolean", "prompt": "Field 2 Template"}
    ]
    post_template_form = Form(
        id="template_form_id", # Added id
        rel="template_rel",
        href="/template_href",
        method="POST",
        properties=post_template_form_properties_dicts,
        name="TemplateName", # This becomes Template.name
        title="Template Prompt from Title", # This becomes Template.prompt
        tags="tag3" # Added tags
    )

    all_transitions = [get_link_form, get_query_form, post_template_form]
    mock_tm.get_transitions.return_value = all_transitions
    mock_tm.get_item_transitions.return_value = []  # No item-specific links for this test

    # 3. Instantiate CollectionJsonRepresentor
    representor = CollectionJsonRepresentor(transition_manager=mock_tm)

    # 4. Call to_collection_json
    request_mock = mock_request()
    result = representor.to_collection_json(request=request_mock, models=[], context={})

    # 5. Assert Correctness
    # Verify Links
    assert len(result.collection.links) == 1
    link_result = result.collection.links[0]
    assert link_result.rel == get_link_form.rel
    assert link_result.href == get_link_form.href
    assert link_result.prompt == get_link_form.title # Corrected: Form.title maps to Link.prompt
    assert link_result.method == "GET"

    # Verify Queries
    assert len(result.collection.queries) == 1
    query_result = result.collection.queries[0]
    assert query_result.rel == get_query_form.rel
    assert query_result.href == get_query_form.href
    assert query_result.prompt == get_query_form.title # Corrected: Form.title maps to Query.prompt
    assert len(query_result.data) == len(get_query_form.properties)
    # Form.to_query creates TemplateData from dicts in Form.properties
    for i, expected_prop_dict in enumerate(get_query_form_properties_dicts):
        actual_query_data = query_result.data[i]
        assert actual_query_data.name == expected_prop_dict["name"]
        assert actual_query_data.prompt == expected_prop_dict["prompt"]
        assert actual_query_data.type == expected_prop_dict["type"]
        assert actual_query_data.value == expected_prop_dict.get("value") # Use .get for optional value
        # TemplateData has a 'required' field, default False. QueryData does not.
        # cj_models.TemplateData(**prop) will set required if present in prop dict.
        assert actual_query_data.required == expected_prop_dict.get("required", False)


    # Verify Template
    assert result.template is not None
    assert len(result.template) == 1
    template_result = result.template[0]
    assert template_result.name == post_template_form.name # Correct: Form.name maps to Template.name
    assert template_result.href == post_template_form.href
    assert template_result.method == post_template_form.method
    assert template_result.prompt == post_template_form.title # Corrected: Form.title maps to Template.prompt
    assert len(template_result.data) == len(post_template_form.properties)
    # Form.to_template creates TemplateData from dicts in Form.properties
    for i, expected_prop_dict in enumerate(post_template_form_properties_dicts):
        actual_template_data = template_result.data[i]
        assert actual_template_data.name == expected_prop_dict["name"]
        assert actual_template_data.prompt == expected_prop_dict["prompt"]
        assert actual_template_data.type == expected_prop_dict["type"]
        assert actual_template_data.required == expected_prop_dict.get("required", False)


    # Check that get_transitions was called
    mock_tm.get_transitions.assert_called_once_with(request_mock)
    mock_tm.get_item_transitions.assert_called_once_with(request_mock)

    # Verify that context formatting is applied if context was provided (even if empty here)
    # This is implicitly tested if hrefs are correct, but could be more explicit
    # if complex formatting was involved.
    # For this test, hrefs don't have placeholders.

    # Check title and version (basic sanity checks)
    assert result.collection.href == str(request_mock.url)
    assert result.collection.version == "1.0"
    assert result.collection.title == "Title" # Default title
    assert result.error is None
    assert result.collection.items == []

if __name__ == "__main__":
    pytest.main()
