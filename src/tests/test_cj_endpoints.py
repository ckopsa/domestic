import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any, Type # Added typing
from datetime import datetime # Added datetime
import uuid # Added uuid

from main import app # Assuming your FastAPI app instance is named 'app' in main.py
from models import WorkflowDefinition as PDWorkflowDefinition, TaskDefinitionBase
# from db_models import WorkflowDefinition as DBWorkflowDefinition # Import your DB model - Not used with mock
from services import WorkflowService
from dependencies import get_db, get_workflow_service # get_db not used with mock
from cj_models import CollectionJson # To validate response structure

# Need to import BaseModel from Pydantic for the mock service
from pydantic import BaseModel

# Sample data for testing
sample_wf_def_1_dict = {
    "id": "cj-wf-def-1",
    "name": "Test Workflow Definition 1 (CJ)",
    "description": "A test workflow definition for CJ endpoints",
    "task_definitions": [
        {"name": "Task 1 for CJ def 1", "order": 1, "due_datetime_offset_minutes": 60},
        {"name": "Task 2 for CJ def 1", "order": 2},
    ],
    "due_datetime": None,
}

sample_wf_def_2_dict = {
    "id": "cj-wf-def-2",
    "name": "Another Test Workflow (CJ)",
    "description": "More testing for CJ",
    "task_definitions": [
        {"name": "Task A for CJ def 2", "order": 1},
    ],
    "due_datetime": None,
}


@pytest.fixture(scope="function")
def db_session(tmp_path):
    # Placeholder for no actual DB session in this mocked example
    yield None


@pytest.fixture(scope="function")
def mock_workflow_service(db_session): # db_session is kept for future DB integration
    wf_def_1 = PDWorkflowDefinition(**sample_wf_def_1_dict)
    wf_def_2 = PDWorkflowDefinition(**sample_wf_def_2_dict)

    class MockWorkflowService:
        async def list_workflow_definitions(self, limit: int = 100, offset: int = 0, name_filter: str = None):
            defs = [wf_def_1, wf_def_2]
            if name_filter:
                return [d for d in defs if name_filter.lower() in d.name.lower()]
            return defs[offset:offset+limit]

        async def get_workflow_definition_by_id(self, definition_id: str):
            if definition_id == wf_def_1.id:
                return wf_def_1
            if definition_id == wf_def_2.id:
                return wf_def_2
            return None

        async def create_new_definition(self, name: str, description: Optional[str], task_definitions: List[TaskDefinitionBase], due_datetime: Optional[datetime] = None):
            new_id = "cj-wf-def-" + str(uuid.uuid4())[:4]
            # Ensure task_definitions are dicts if they are passed as Pydantic models
            task_defs_as_dicts = [td.model_dump() if isinstance(td, BaseModel) else td for td in task_definitions]
            new_def_data = {
                "id": new_id,
                "name": name,
                "description": description,
                "task_definitions": task_defs_as_dicts,
                "due_datetime": due_datetime # Store as datetime object, Pydantic will handle serialization
            }
            return PDWorkflowDefinition(**new_def_data)

        # Mock other methods needed for PUT/POST if we test those later
        async def update_definition(self, definition_id: str, name: str, description: Optional[str], task_definitions: List[TaskDefinitionBase], due_datetime: Optional[datetime] = None):
            if definition_id == wf_def_1.id or definition_id == wf_def_2.id:
                task_defs_as_dicts = [td.model_dump() if isinstance(td, BaseModel) else td for td in task_definitions]
                updated_def_data = {
                    "id": definition_id,
                    "name": name,
                    "description": description,
                    "task_definitions": task_defs_as_dicts,
                    "due_datetime": due_datetime
                }
                return PDWorkflowDefinition(**updated_def_data)
            return None


    return MockWorkflowService()


@pytest.fixture(scope="function")
def client(mock_workflow_service):
    app.dependency_overrides[get_workflow_service] = lambda: mock_workflow_service
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_list_workflow_definitions_cj_json(client):
    response = client.get("/cj/workflow-definitions/") # Added trailing slash
    assert response.status_code == 200

    content = response.json()
    cj_data = CollectionJson(**content)
    assert cj_data.collection is not None
    assert cj_data.collection.version == "1.0"
    # The href from the app might include the host, so endswith is safer
    assert cj_data.collection.href.endswith("/cj/workflow-definitions/") # Added trailing slash
    assert len(cj_data.collection.items) == 2
    assert cj_data.template is not None # Changed from cj_data.collection.template and fixed indent

    item1 = cj_data.collection.items[0]
    assert item1.href.endswith(f"/cj/workflow-definitions/{sample_wf_def_1_dict['id']}/") # Added trailing slash to base
    item1_data_names = [d.name for d in item1.data]
    assert "name" in item1_data_names
    assert "description" in item1_data_names

    rels = [link.rel for link in cj_data.collection.links]
    assert "self" in rels
    assert "create" in rels


def test_list_workflow_definitions_cj_html(client):
    response = client.get("/cj/workflow-definitions/", headers={"Accept": "text/html"}) # Added trailing slash
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    html_content = response.text
    assert "<title>Simple Checklist MVP</title>" in html_content
    # Check for parts of the hrefs, as full URL might vary with TestClient
    assert "<h1>/cj/workflow-definitions/</h1>" in html_content # Actual href rendered, added trailing slash
    assert f"Item: /cj/workflow-definitions/{sample_wf_def_1_dict['id']}/" in html_content # Added trailing slash to base
    assert "Template for New Item" in html_content


def test_get_workflow_definition_by_id_cj_json(client):
    def_id = sample_wf_def_1_dict["id"]
    response = client.get(f"/cj/workflow-definitions/{def_id}/") # Added trailing slash
    assert response.status_code == 200

    content = response.json()
    cj_data = CollectionJson(**content)
    assert cj_data.collection is not None
    assert len(cj_data.collection.items) == 1
    item = cj_data.collection.items[0]
    assert item.href.endswith(f"/cj/workflow-definitions/{def_id}/") # Added trailing slash

    name_data = next((d for d in item.data if d.name == "name"), None)
    assert name_data is not None
    assert name_data.value == sample_wf_def_1_dict["name"]

    item_link_rels = [link.rel for link in item.links]
    assert "self" in item_link_rels


def test_get_workflow_definition_by_id_cj_html(client):
    def_id = sample_wf_def_1_dict["id"]
    response = client.get(f"/cj/workflow-definitions/{def_id}/", headers={"Accept": "text/html"}) # Added trailing slash
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    html_content = response.text
    assert f"<h1>Item Details: /cj/workflow-definitions/{def_id}/</h1>" in html_content # Actual href rendered, added trailing slash
    assert sample_wf_def_1_dict["name"] in html_content


def test_get_workflow_definition_not_found_cj(client):
    response = client.get("/cj/workflow-definitions/non-existent-id/") # Added trailing slash
    assert response.status_code == 404
    content = response.json()
    cj_data = CollectionJson(**content)
    assert cj_data.collection.error is not None
    assert cj_data.collection.error.code == 404


def test_get_workflow_definition_form_cj_json(client):
    response = client.get("/cj/workflow-definitions/form/") # Added trailing slash
    assert response.status_code == 200
    content = response.json()
    cj_data = CollectionJson(**content)
    assert cj_data.collection.template is not None
    assert len(cj_data.collection.items) == 0

def test_get_workflow_definition_form_cj_html(client):
    response = client.get("/cj/workflow-definitions/form/", headers={"Accept": "text/html"}) # Added trailing slash
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "<form" in response.text
    assert "<h1>Collection+JSON Form" in response.text
    assert 'action="/cj/workflow-definitions/form/"' in response.text # Check form action, added trailing slash
