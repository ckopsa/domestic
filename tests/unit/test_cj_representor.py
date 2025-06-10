import pytest
from unittest.mock import MagicMock, patch
from pydantic import BaseModel, Field as PydanticField
from typing import List, Optional, Dict, Any, Union # Added Union for ItemData.value

# Imports from the application
# Adjust as per actual model names - Assuming these are correct based on previous steps
from src.cj_models import CollectionJsonRepresentor, Template, Link, Item, CollectionJson, ItemData, TemplateData, to_collection_json_data
from src.transitions import TransitionManager, Form # FormProperty is not directly used by Form constructor in transitions.py, properties are dicts


# Mock Pydantic Models for testing
class MockModel(BaseModel):
    id: str
    name: str
    value: Optional[int] = None

    # This is a simplified mock. The actual to_cj_data is monkey-patched onto BaseModel.
    # This mock helps create Item-like structures for testing the representor.
    def to_cj_data_mock_impl(self, href: str = "") -> Item: # Renamed to avoid conflict if real one is also present
        item_href = href if href else f"/items/{self.id}"
        data_list = [
            ItemData(name="id", value=self.id, prompt="ID"),
            ItemData(name="name", value=self.name, prompt="Name"),
        ]
        if self.value is not None:
            data_list.append(ItemData(name="value", value=self.value, prompt="Value"))

        return Item(
            href=item_href,
            rel="item", # Default rel for an item
            data=data_list,
            links=[],     # Default to empty, populated by representor
            templates=[]  # Default to empty, populated by representor
        )

# Test Setup Helper
def create_mock_request(endpoint_name: str, openapi_schema: Dict[str, Any] = None):
    request = MagicMock()
    # request.scope = {'endpoint': MagicMock(__name__=endpoint_name)} # Not strictly needed if we mock get_transitions
    request.app = MagicMock()
    # request.app.openapi = MagicMock(return_value=openapi_schema or {"paths": {}}) # Not needed for these tests
    request.url = "http://testserver/current/path"
    return request

def create_form(id: str, href: str, method: str, properties: List[Dict] = None, title: str = None, rel: str = None) -> Form:
    form_properties = []
    if properties:
        for prop_dict in properties:
            # Ensure all required fields for TemplateData are present, even if with default values
            prop_data = {
                "name": prop_dict.get("name", f"prop_{len(form_properties)}"),
                "type": prop_dict.get("type", "string"), # Default type if not specified
                "prompt": prop_dict.get("prompt"),
                "value": prop_dict.get("value"),
                "required": prop_dict.get("required", False),
                # Add other TemplateData fields if necessary, with defaults
            }
            form_properties.append(TemplateData(**prop_data))

    return Form(
        id=id,
        name=id,
        href=href,
        rel=rel or f"custom-{id}",
        tags=["tag1"],
        title=title or f"{method.capitalize()} {id.replace('_', ' ').capitalize()}",
        method=method.upper(),
        properties=form_properties
    )

@pytest.fixture(scope="function", autouse=True)
def ensure_to_cj_data_on_basemodel():
    # This fixture ensures that BaseModel has `to_cj_data` for all tests in this file.
    # It uses the actual `to_collection_json_data` from cj_models.
    # This is crucial because the representor calls `item_model.to_cj_data()`.
    if not hasattr(BaseModel, 'to_cj_data_original_for_test'): # Store original if exists
        BaseModel.to_cj_data_original_for_test = getattr(BaseModel, 'to_cj_data', None)

    BaseModel.to_cj_data = to_collection_json_data
    yield
    # Restore original or remove if it was added by this fixture
    if hasattr(BaseModel, 'to_cj_data_original_for_test'):
        BaseModel.to_cj_data = BaseModel.to_cj_data_original_for_test
        delattr(BaseModel, 'to_cj_data_original_for_test')
    elif hasattr(BaseModel, 'to_cj_data'): # if it was set by this fixture and didn't exist before
        delattr(BaseModel, 'to_cj_data')


@pytest.fixture
def representor() -> CollectionJsonRepresentor:
    tm = TransitionManager()
    return CollectionJsonRepresentor(transition_manager=tm)

# Tests
def test_page_level_multiple_templates_and_links(representor: CollectionJsonRepresentor):
    mock_models = [MockModel(id="1", name="Test Model 1")]
    request = create_mock_request("get_items_route")

    page_transitions = [
        create_form(id="create_item", href="/items", method="POST", properties=[{"name": "name", "type": "string", "prompt": "Name", "required": True}]),
        create_form(id="update_all_items", href="/items", method="PUT", properties=[{"name": "status", "type": "string", "prompt": "Status"}]),
        create_form(id="delete_all_items", href="/items", method="DELETE", properties=[{"name": "confirm", "type": "boolean", "prompt": "Confirm"}]),
        create_form(id="search_items", href="/items/search", method="GET", properties=[]), # Explicitly no properties for a link
        create_form(id="other_action_no_props", href="/items/other", method="POST", properties=[]), # POST without properties = link
    ]

    with patch.object(representor.transition_manager, 'get_transitions', return_value=page_transitions):
        with patch.object(representor.transition_manager, 'get_item_transitions', return_value=[]):
            cj_response = representor.to_collection_json(request, mock_models)

    assert cj_response.collection.links is not None
    assert len(cj_response.collection.links) == 2
    assert cj_response.collection.links[0].rel == "custom-search_items"
    assert cj_response.collection.links[0].method == "GET"
    assert cj_response.collection.links[1].rel == "custom-other_action_no_props"
    assert cj_response.collection.links[1].method == "POST"

    assert cj_response.template is not None, "Page templates should be present"
    assert len(cj_response.template) == 3, "Should have 3 page-level templates with properties"

    assert cj_response.template[0].method == "POST"
    assert cj_response.template[0].prompt == "Post Create item"
    assert len(cj_response.template[0].data) == 1
    assert cj_response.template[0].data[0].name == "name"
    assert cj_response.template[0].data[0].required is True

    assert cj_response.template[1].method == "PUT"
    assert len(cj_response.template[1].data) == 1
    assert cj_response.template[1].data[0].name == "status"

    assert cj_response.template[2].method == "DELETE"
    assert len(cj_response.template[2].data) == 1
    assert cj_response.template[2].data[0].name == "confirm"

def test_item_level_multiple_templates_and_links(representor: CollectionJsonRepresentor):
    mock_items_data = [MockModel(id="1", name="Item 1"), MockModel(id="2", name="Item 2")]
    request = create_mock_request("get_specific_item_route")

    item_trans = [
        create_form(id="update_item", href="/items/{item_id}", method="PUT", properties=[{"name": "name", "type": "string", "prompt": "Name"}]),
        create_form(id="delete_item", href="/items/{item_id}", method="DELETE", properties=[{"name": "confirm", "type": "boolean", "prompt": "Confirm"}]),
        create_form(id="view_item_details", href="/items/{item_id}/details", method="GET", properties=[]),
        create_form(id="perform_action_no_props", href="/items/{item_id}/action", method="PUT", properties=[]),
    ]

    def item_context_mapper(item_model: MockModel) -> Dict[str, str]:
        return {"item_id": item_model.id}

    with patch.object(representor.transition_manager, 'get_transitions', return_value=[]):
        with patch.object(representor.transition_manager, 'get_item_transitions', return_value=item_trans):
            cj_response = representor.to_collection_json(request, mock_items_data, item_context_mapper=item_context_mapper)

    assert len(cj_response.collection.items) == 2

    for i, item_cj in enumerate(cj_response.collection.items):
        item_id = mock_items_data[i].id
        assert item_cj.links is not None
        assert len(item_cj.links) == 2

        link_rels = {link.rel for link in item_cj.links}
        assert f"custom-view_item_details" in link_rels
        assert f"custom-perform_action_no_props" in link_rels

        view_link = next(l for l in item_cj.links if l.rel == "custom-view_item_details")
        action_link = next(l for l in item_cj.links if l.rel == "custom-perform_action_no_props")

        assert view_link.href == f"/items/{item_id}/details"
        assert view_link.method == "GET"
        assert action_link.href == f"/items/{item_id}/action"
        assert action_link.method == "PUT"

        assert item_cj.templates is not None, f"Item {item_id} templates should be present"
        assert len(item_cj.templates) == 2, f"Item {item_id} should have 2 templates with properties"

        assert item_cj.templates[0].method == "PUT"
        assert item_cj.templates[0].href == f"/items/{item_id}"
        assert len(item_cj.templates[0].data) == 1
        assert item_cj.templates[0].data[0].name == "name"

        assert item_cj.templates[1].method == "DELETE"
        assert item_cj.templates[1].href == f"/items/{item_id}"
        assert len(item_cj.templates[1].data) == 1
        assert item_cj.templates[1].data[0].name == "confirm"

def test_no_page_or_item_templates_or_links(representor: CollectionJsonRepresentor):
    mock_models = [MockModel(id="1", name="Test Model 1")]
    request = create_mock_request("get_items_route")

    with patch.object(representor.transition_manager, 'get_transitions', return_value=[]):
        with patch.object(representor.transition_manager, 'get_item_transitions', return_value=[]):
            cj_response = representor.to_collection_json(request, mock_models)

    assert cj_response.collection.links is not None
    assert len(cj_response.collection.links) == 0
    assert cj_response.template is None

    assert len(cj_response.collection.items) == 1
    item_result = cj_response.collection.items[0]
    # The `to_cj_data` method in `cj_models.py` will be used.
    # It initializes `links` and `templates` if they are part of the Item model.
    # Item model has: links: List[Link] = PydanticField(default_factory=list)
    # templates: Optional[List[Template]] = PydanticField(default_factory=list)
    assert item_result.links is not None
    assert len(item_result.links) == 0
    assert item_result.templates is not None
    assert len(item_result.templates) == 0


def test_page_template_href_with_context(representor: CollectionJsonRepresentor):
    mock_models = []
    request = create_mock_request("some_route_with_context")
    context = {"parent_id": "parent123"}

    page_transitions = [
        create_form(id="create_child", href="/parents/{parent_id}/children", method="POST", properties=[{"name": "child_name", "type": "string", "prompt": "Child Name"}])
    ]

    with patch.object(representor.transition_manager, 'get_transitions', return_value=page_transitions):
        with patch.object(representor.transition_manager, 'get_item_transitions', return_value=[]):
            cj_response = representor.to_collection_json(request, mock_models, context=context)

    assert cj_response.template is not None
    assert len(cj_response.template) == 1
    assert cj_response.template[0].href == "/parents/parent123/children"
    assert cj_response.template[0].method == "POST"
    assert len(cj_response.template[0].data) == 1
    assert cj_response.template[0].data[0].name == "child_name"

def test_item_template_and_link_href_with_full_context_and_mapper(representor: CollectionJsonRepresentor):
    mock_items_data = [MockModel(id="itemA", name="Item A")]
    request = create_mock_request("complex_route")
    page_context = {"org_id": "orgXYZ", "user_id": "user789"}

    item_specific_transitions = [
        create_form(id="modify_item_attr", href="/orgs/{org_id}/users/{user_id}/items/{item_id}/modify", method="PUT", properties=[{"name": "attr", "type": "string"}]),
        create_form(id="get_item_log", href="/orgs/{org_id}/items/{item_id}/log", method="GET", properties=[]),
    ]

    def item_mapper(item: MockModel) -> Dict[str, str]:
        return {"item_id": item.id}

    with patch.object(representor.transition_manager, 'get_transitions', return_value=[]):
        with patch.object(representor.transition_manager, 'get_item_transitions', return_value=item_specific_transitions):
            cj_response = representor.to_collection_json(
                request,
                mock_items_data,
                context=page_context,
                item_context_mapper=item_mapper
            )

    assert len(cj_response.collection.items) == 1
    item_cj = cj_response.collection.items[0]

    assert item_cj.templates is not None and len(item_cj.templates) == 1
    assert item_cj.templates[0].href == "/orgs/orgXYZ/users/user789/items/itemA/modify"
    assert item_cj.templates[0].method == "PUT"

    assert item_cj.links is not None and len(item_cj.links) == 1
    assert item_cj.links[0].href == "/orgs/orgXYZ/items/itemA/log"
    assert item_cj.links[0].method == "GET"
```
