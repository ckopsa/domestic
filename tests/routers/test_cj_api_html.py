import pytest
from unittest.mock import patch, AsyncMock, MagicMock # Added MagicMock

from fastapi.testclient import TestClient
# Assuming your FastAPI app is 'app' in 'main.py'
# For a multi-file project, ensure 'main.py' and 'src' are discoverable.
# This might require adjusting PYTHONPATH or how pytest discovers the app.
# For now, direct import if main.py is at root or configured in PYTHONPATH.
from main import app
from src.models import CJWorkflowDefinition, WorkflowDefinition, TaskDefinitionBase # Ensure these are correctly imported
from src.cj_models import CollectionJson, Collection, Link, Item, ItemData as Data, CollectionJSONRepresentable # Added CollectionJSONRepresentable
from src.dependencies import get_workflow_service, get_db # For potential overrides

# Mock database session provider for dependency overrides
async def mock_db_session_provider():
    # FastAPI expects a generator for `yield` based dependencies
    mock_session = AsyncMock() # The session object itself

    # session.query is a synchronous method, so it should be a MagicMock
    mock_session.query = MagicMock()

    # What session.query(...) returns needs to be a synchronous mock object
    mock_query_sync_obj = MagicMock()
    mock_session.query.return_value = mock_query_sync_obj # query(...) returns mock_query_sync_obj

    mock_query_sync_obj.filter.return_value = mock_query_sync_obj # filter(...) is chainable
    mock_query_sync_obj.order_by.return_value = mock_query_sync_obj # order_by(...) is chainable
    mock_query_sync_obj.all.return_value = []  # .all() is a sync method call
    mock_query_sync_obj.first.return_value = None # .first() is a sync method call
    mock_query_sync_obj.count.return_value = 0   # .count() is a sync method call

    # For methods like session.add, session.commit, session.refresh, session.delete
    # They are called synchronously in the repository.
    mock_session.add = MagicMock()
    mock_session.commit = MagicMock()
    mock_session.refresh = MagicMock()
    mock_session.delete = MagicMock()

    yield mock_session

# Mock data for workflow definitions
# Simplified mock data structure for Pydantic model creation
# In a real scenario, ensure datetime strings are valid if models expect datetime objects.
# For this test, CJWorkflowDefinition.to_cj_representation is mocked, so internal details of
# mocked_cj_definitions are less critical as long as it's a list of objects with an 'id'.
mocked_workflow_definitions_data = [
    {
        "id": "def-1",
        "name": "Test Definition 1",
        "description": "Description for Test Definition 1",
        "task_definitions": [
            {"name": "Task 1", "description": "First task", "order": 1},
            {"name": "Task 2", "description": "Second task", "order": 2},
        ],
        # Not including datetime strings here as WorkflowDefinition model doesn't have created_at/updated_at
        # And CJWorkflowDefinition inherits from WorkflowDefinition.
    }
]
# Convert to Pydantic models
# Note: CJWorkflowDefinition inherits from WorkflowDefinition.
# WorkflowDefinition in src/models.py does not have created_at/updated_at.
# The mock data provided in the prompt had these, but the model doesn't.
mocked_cj_definitions = [CJWorkflowDefinition(**data) for data in mocked_workflow_definitions_data]


# This is the CollectionJson object that the patched to_cj_representation will return
mock_collection_json_for_definitions = CollectionJson(
    collection=Collection(
        version="1.0",
        href="http://testserver/api/cj/workflow-definitions/",
        title="Workflow Definitions", # Expected title for this route
        links=[Link(rel="self", href="http://testserver/api/cj/workflow-definitions/")],
        items=[
            Item(
                href=f"http://testserver/api/cj/workflow-definitions/{wd.id}",
                rel=CJWorkflowDefinition.cj_item_rel, # Added rel field
                # Simplified data for mock. Real to_cj_item would produce more detailed ItemData.
                data=[Data(name="name", value=wd.name), Data(name="description", value=str(wd.description))],
                links=[Link(rel="self", href=f"http://testserver/api/cj/workflow-definitions/{wd.id}")]
            ) for wd in mocked_cj_definitions # Use the Pydantic models here
        ]
    )
)

# Test for get_cj_api_root
def test_get_cj_api_root_html_response(client_fixture: TestClient): # Use fixture name
    response = client_fixture.get("/api/cj/", headers={"Accept": "text/html"})
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    # Check for a known piece of text from the template/API root
    assert "<title>CollectionJSON Viewer</title>" in response.text # Actual title from cj_template.html
    assert "<h1>Collection+JSON API Root</h1>" in response.text # Title set in get_cj_api_root
    assert 'href="http://testserver/api/cj/workflow-definitions/"' in response.text

# Pytest fixture for TestClient
@pytest.fixture
def client_fixture() -> TestClient: # Renamed to client_fixture to avoid conflict with client module
    # Setup dependency overrides that might be general for all tests if needed
    # For now, keeping it simple as per subtask instructions for specific test.
    # Overrides will be managed within the test function itself if specific.
    return TestClient(app)

@patch('src.routers.cj_api.CJWorkflowDefinition.to_cj_representation') # Patching at the call site in the router module
def test_list_workflow_definitions_cj_html_response(mock_router_cj_def_to_cj_rep, client_fixture: TestClient):
    mock_router_cj_def_to_cj_rep.return_value = mock_collection_json_for_definitions

    original_overrides = app.dependency_overrides.copy()
    # Set get_db override for this test - uses the enhanced global mock_db_session_provider
    app.dependency_overrides[get_db] = mock_db_session_provider

    # Ensure get_workflow_service override is removed if it was set by a previous test/globally
    if get_workflow_service in app.dependency_overrides:
        del app.dependency_overrides[get_workflow_service]

    try:
        response = client_fixture.get("/api/cj/workflow-definitions/", headers={"Accept": "text/html"})

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        mock_router_cj_def_to_cj_rep.assert_called_once()

        assert "<h1>Workflow Definitions</h1>" in response.text
        assert "Test Definition 1" in response.text # This comes from mock_collection_json_for_definitions
        assert 'href="http://testserver/api/cj/workflow-definitions/def-1"' in response.text
    finally:
        app.dependency_overrides = original_overrides
