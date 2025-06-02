import pytest
import sys
import os
import json
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, ANY
from datetime import date
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from app.db_models import Base
from app.main import app
from app.database import get_db, engine # get_db might not be directly used by these new tests
from app.dependencies import get_workflow_service, get_html_renderer # For overriding
from app.services import WorkflowService # For spec
from app.core.html_renderer import HtmlRendererInterface # For spec
from app.core.security import AuthenticatedUser, get_current_active_user
from app.db_models.enums import WorkflowStatus # For test cases

# Test client - can be initialized per test or per module if state is managed
# client = TestClient(app) # Will re-initialize client in fixture for overrides

# Mock user for authentication
mock_user = AuthenticatedUser(user_id="test_user", username="testuser", email="test@example.com")

# Fixture to setup and teardown the database
@pytest.fixture(scope="function")
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = get_db().__next__()
    yield session
    session.close()
    transaction.rollback()
    connection.close()

# Mock the get_current_active_user dependency
def override_get_current_active_user():
    return mock_user

# Override the dependency in the app for testing
app.dependency_overrides[get_current_active_user] = override_get_current_active_user

@pytest.mark.asyncio
async def test_list_workflow_definitions(db_session):
    # Act
    response = client.get("/api/workflow-definitions")

    # Assert
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_list_workflow_definitions_with_name_filter(db_session):
    # Arrange: Create a few workflow definitions
    def_alpha_data = {"name": "Test Workflow Alpha", "description": "Alpha test", "task_names": ["Task A"]}
    def_beta_data = {"name": "Another Workflow Beta", "description": "Beta test", "task_names": ["Task B"]}
    def_gamma_data = {"name": "Test Workflow Gamma", "description": "Gamma test", "task_names": ["Task C"]}

    response_alpha = client.post("/api/workflow-definitions", json=def_alpha_data)
    assert response_alpha.status_code == 201
    id_alpha = response_alpha.json()["id"]

    response_beta = client.post("/api/workflow-definitions", json=def_beta_data)
    assert response_beta.status_code == 201
    # id_beta = response_beta.json()["id"] # Not strictly needed for this test's assertions

    response_gamma = client.post("/api/workflow-definitions", json=def_gamma_data)
    assert response_gamma.status_code == 201
    id_gamma = response_gamma.json()["id"]

    # Act: Filter by name "Test Workflow"
    response_filter = client.get("/api/workflow-definitions?name=Test%20Workflow")

    # Assert: Check filtered results
    assert response_filter.status_code == 200
    filtered_defs = response_filter.json()
    assert isinstance(filtered_defs, list)
    assert len(filtered_defs) == 2

    # Check that the correct definitions are present (case-insensitive)
    returned_ids = {d["id"] for d in filtered_defs}
    assert id_alpha in returned_ids
    assert id_gamma in returned_ids

    # Ensure names match, allowing for case variation in the filter term (though API is case-insensitive)
    for d in filtered_defs:
        assert "test workflow" in d["name"].lower()
        assert "another workflow beta" not in d["name"].lower()


    # Act: Filter by a name that should not match anything
    response_no_match = client.get("/api/workflow-definitions?name=NonExistentName")

    # Assert: Check for no matches
    assert response_no_match.status_code == 200
    assert response_no_match.json() == []

    # Act: Get all definitions (no filter)
    response_all = client.get("/api/workflow-definitions")

    # Assert: Check for all definitions
    assert response_all.status_code == 200
    all_defs = response_all.json()
    assert isinstance(all_defs, list)
    # Depending on whether other tests run in parallel and create definitions,
    # we should ensure at least our 3 are present.
    # For a cleaner test, ideally, we'd clear the DB or ensure unique names not used elsewhere.
    # For now, we'll check that the count is at least 3 and our specific ones are present.
    assert len(all_defs) >= 3
    all_returned_ids = {d["id"] for d in all_defs}
    assert id_alpha in all_returned_ids
    assert response_beta.json()["id"] in all_returned_ids # Get id_beta here
    assert id_gamma in all_returned_ids


@pytest.mark.asyncio
async def test_create_workflow_definition(db_session):
    # Arrange
    data = {
        "name": "Test Workflow",
        "description": "A test workflow",
        "task_names": ["Task 1", "Task 2", "Task 3"]
    }

    # Act
    response = client.post("/api/workflow-definitions", json=data)

    # Assert
    assert response.status_code == 201  # Created
    assert response.json()["name"] == "Test Workflow"

@pytest.mark.asyncio
async def test_create_workflow_definition_invalid_data(db_session):
    # Arrange
    data = {
        "name": "",  # Empty name should fail validation
        "description": "A test workflow",
        "task_names": ["Task 1", "Task 2"]
    }

    # Act
    response = client.post("/api/workflow-definitions", json=data)

    # Assert
    assert response.status_code == 400  # Bad request due to validation error

@pytest.mark.asyncio
async def test_edit_workflow_definition(db_session):
    # Arrange: First create a definition
    definition_data = {
        "name": "Original Workflow",
        "description": "Original description",
        "task_names": ["Original Task 1", "Original Task 2"]
    }
    create_response = client.post("/api/workflow-definitions", json=definition_data)
    assert create_response.status_code == 201
    definition_id = create_response.json()["id"]

    # Update data
    update_data = {
        "name": "Updated Workflow",
        "description": "Updated description",
        "task_names": ["Updated Task 1", "Updated Task 2"]
    }

    # Act
    response = client.put(f"/api/workflow-definitions/{definition_id}", json=update_data)

    # Assert
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Workflow"

@pytest.mark.asyncio
async def test_edit_workflow_definition_not_found(db_session):
    # Arrange
    data = {
        "name": "Updated Workflow",
        "description": "Updated description",
        "task_names": ["Updated Task 1"]
    }

    # Act
    response = client.put("/api/workflow-definitions/nonexistent_id", json=data)

    # Assert
    assert response.status_code == 404  # Not found

@pytest.mark.asyncio
async def test_delete_workflow_definition(db_session):
    # Arrange: First create a definition
    definition_data = {
        "name": "Workflow to Delete",
        "description": "This will be deleted",
        "task_names": ["Task 1", "Task 2"]
    }
    create_response = client.post("/api/workflow-definitions", json=definition_data)
    assert create_response.status_code == 201
    definition_id = create_response.json()["id"]

    # Act
    response = client.delete(f"/api/workflow-definitions/{definition_id}")

    # Assert
    assert response.status_code == 204  # No content after successful deletion

@pytest.mark.asyncio
async def test_delete_workflow_definition_not_found(db_session):
    # Act
    response = client.delete("/api/workflow-definitions/nonexistent_id")

    # Assert
    assert response.status_code == 404  # Not found

@pytest.mark.asyncio
async def test_create_workflow_instance(db_session):
    # Arrange: First create a definition
    definition_data = {
        "name": "Workflow for Instance",
        "description": "Workflow to start an instance",
        "task_names": ["Task 1", "Task 2"]
    }
    create_response = client.post("/api/workflow-definitions", json=definition_data)
    assert create_response.status_code == 201
    definition_id = create_response.json()["id"]

    # Data for creating an instance
    instance_data = {
        "definition_id": definition_id
    }

    # Act
    response = client.post("/api/workflow-instances", json=instance_data)

    # Assert
    assert response.status_code == 201  # Created
    assert response.json()["workflow_definition_id"] == definition_id

@pytest.mark.asyncio
async def test_create_workflow_instance_invalid_definition(db_session):
    # Arrange
    instance_data = {
        "definition_id": "nonexistent_id"
    }

    # Act
    response = client.post("/api/workflow-instances", json=instance_data)

    # Assert
    assert response.status_code == 400  # Bad request due to invalid definition ID

@pytest.mark.asyncio
async def test_get_workflow_instance(db_session):
    # Arrange: First create a definition and an instance
    definition_data = {
        "name": "Workflow for Instance",
        "description": "Workflow to start an instance",
        "task_names": ["Task 1", "Task 2"]
    }
    create_def_response = client.post("/api/workflow-definitions", json=definition_data)
    assert create_def_response.status_code == 201
    definition_id = create_def_response.json()["id"]

    instance_data = {
        "definition_id": definition_id
    }
    create_inst_response = client.post("/api/workflow-instances", json=instance_data)
    assert create_inst_response.status_code == 201
    instance_id = create_inst_response.json()["id"]

    # Act
    response = client.get(f"/api/workflow-instances/{instance_id}")

    # Assert
    assert response.status_code == 200
    assert "instance" in response.json()
    assert "tasks" in response.json()
    assert response.json()["instance"]["id"] == instance_id

@pytest.mark.asyncio
async def test_get_workflow_instance_not_found(db_session):
    # Act
    response = client.get("/api/workflow-instances/nonexistent_id")

    # Assert
    assert response.status_code == 404  # Not found

@pytest.mark.asyncio
async def test_complete_task(db_session):
    # Arrange: First create a definition and an instance with tasks
    definition_data = {
        "name": "Workflow for Task Completion",
        "description": "Workflow to test task completion",
        "task_names": ["Task 1", "Task 2"]
    }
    create_def_response = client.post("/api/workflow-definitions", json=definition_data)
    assert create_def_response.status_code == 201
    definition_id = create_def_response.json()["id"]

    instance_data = {
        "definition_id": definition_id
    }
    create_inst_response = client.post("/api/workflow-instances", json=instance_data)
    assert create_inst_response.status_code == 201
    instance_id = create_inst_response.json()["id"]

    # Get the tasks for the instance
    instance_response = client.get(f"/api/workflow-instances/{instance_id}")
    tasks = instance_response.json()["tasks"]
    task_id = tasks[0]["id"]

    # Act
    response = client.post(f"/api/task-instances/{task_id}/complete")

    # Assert
    assert response.status_code == 200
    assert response.json()["status"] == "completed"

@pytest.mark.asyncio
async def test_complete_task_not_found(db_session):
    # Act
    response = client.post("/api/task-instances/nonexistent_id/complete")

    # Assert
    assert response.status_code == 400  # Bad request due to task not found

@pytest.mark.asyncio
async def test_list_user_workflows(db_session):
    # Clean up existing instances for test_user to ensure a known starting state
    from app.db_models.workflow import WorkflowInstance as WorkflowInstanceORM
    db_session.query(WorkflowInstanceORM).filter(WorkflowInstanceORM.user_id == "test_user").delete()
    db_session.commit()

    # Arrange: Create a workflow instance for the user
    definition_data = {
        "name": "User Workflow",
        "description": "Workflow for user",
        "task_names": ["Task 1"]
    }
    create_def_response = client.post("/api/workflow-definitions", json=definition_data)
    assert create_def_response.status_code == 201
    definition_id = create_def_response.json()["id"]

    instance_data = {
        "definition_id": definition_id
    }
    create_inst_response = client.post("/api/workflow-instances", json=instance_data)
    assert create_inst_response.status_code == 201

    # Act
    response = client.get("/api/my-workflows")

    # Assert
    assert response.status_code == 200
    assert len(response.json()["instances"]) == 1


# --- Tests for /my-workflows HTML Endpoint ---

@pytest.fixture
def mock_dependencies_for_my_workflows(monkeypatch):
    # Create fresh mocks for each test run using this fixture
    mock_service = MagicMock(spec=WorkflowService)
    mock_service.list_instances_for_user = AsyncMock(return_value=[]) # Default empty list

    mock_renderer_instance = MagicMock(spec=HtmlRendererInterface)
    mock_renderer_instance.render = AsyncMock(return_value="Mocked HTML") # Default render response
    
    # Store mocks to access them in tests if needed (e.g. via request.app.state or by returning them)
    # For simplicity here, we'll rely on them being the ones used by the overridden dependencies.
    # If we needed to access the mocks directly from the test function, this fixture would return them.

    # Apply overrides using monkeypatch for the app's dependency_overrides
    # This is cleaner than globally modifying app.dependency_overrides for specific tests.
    monkeypatch.setitem(app.dependency_overrides, get_workflow_service, lambda: mock_service)
    monkeypatch.setitem(app.dependency_overrides, get_html_renderer, lambda: mock_renderer_instance)
    
    # Yield the mocks if tests need to directly inspect them, e.g., for call counts after request
    yield mock_service, mock_renderer_instance
    
    # Clean up overrides after the test
    monkeypatch.delitem(app.dependency_overrides, get_workflow_service, raising=False)
    monkeypatch.delitem(app.dependency_overrides, get_html_renderer, raising=False)


@pytest.mark.asyncio
async def test_my_workflows_no_query_parameters(mock_dependencies_for_my_workflows):
    client = TestClient(app) # Fresh client to ensure overrides are clean if not using monkeypatch correctly
    mock_service, mock_renderer = mock_dependencies_for_my_workflows

    response = client.get("/my-workflows")
    assert response.status_code == 200

    mock_service.list_instances_for_user.assert_called_once_with(
        user_id=mock_user.user_id, # from global mock_user via override_get_current_active_user
        created_at_date=date.today(),
        status=WorkflowStatus.active
    )
    mock_renderer.render.assert_called_once_with(
        "my_workflows.html",
        ANY, # request object
        {
            "instances": [], # Default return from mock_service.list_instances_for_user
            "selected_created_at": date.today().isoformat(),
            "selected_status": "active",
            "workflow_statuses": [s.value for s in WorkflowStatus]
        }
    )

@pytest.mark.asyncio
async def test_my_workflows_with_created_at(mock_dependencies_for_my_workflows):
    client = TestClient(app)
    mock_service, mock_renderer = mock_dependencies_for_my_workflows
    
    test_date_str = "2023-01-15"
    test_date_obj = date(2023, 1, 15)

    response = client.get(f"/my-workflows?created_at={test_date_str}")
    assert response.status_code == 200

    mock_service.list_instances_for_user.assert_called_once_with(
        user_id=mock_user.user_id,
        created_at_date=test_date_obj,
        status=WorkflowStatus.active
    )
    mock_renderer.render.assert_called_once_with(
        "my_workflows.html",
        ANY,
        {
            "instances": [],
            "selected_created_at": test_date_str,
            "selected_status": "active",
            "workflow_statuses": [s.value for s in WorkflowStatus]
        }
    )

@pytest.mark.asyncio
async def test_my_workflows_with_status(mock_dependencies_for_my_workflows):
    client = TestClient(app)
    mock_service, mock_renderer = mock_dependencies_for_my_workflows

    response = client.get("/my-workflows?status=completed")
    assert response.status_code == 200

    mock_service.list_instances_for_user.assert_called_once_with(
        user_id=mock_user.user_id,
        created_at_date=date.today(),
        status=WorkflowStatus.completed
    )
    mock_renderer.render.assert_called_once_with(
        "my_workflows.html",
        ANY,
        {
            "instances": [],
            "selected_created_at": date.today().isoformat(),
            "selected_status": "completed",
            "workflow_statuses": [s.value for s in WorkflowStatus]
        }
    )

@pytest.mark.asyncio
async def test_my_workflows_with_all_statuses(mock_dependencies_for_my_workflows):
    client = TestClient(app)
    mock_service, mock_renderer = mock_dependencies_for_my_workflows

    response = client.get("/my-workflows?status=") # Empty status for "All Statuses"
    assert response.status_code == 200

    mock_service.list_instances_for_user.assert_called_once_with(
        user_id=mock_user.user_id,
        created_at_date=date.today(),
        status=None # Service receives None for "All Statuses"
    )
    mock_renderer.render.assert_called_once_with(
        "my_workflows.html",
        ANY,
        {
            "instances": [],
            "selected_created_at": date.today().isoformat(),
            "selected_status": "", # Template receives empty string
            "workflow_statuses": [s.value for s in WorkflowStatus]
        }
    )

@pytest.mark.asyncio
async def test_my_workflows_with_created_at_and_status(mock_dependencies_for_my_workflows):
    client = TestClient(app)
    mock_service, mock_renderer = mock_dependencies_for_my_workflows

    test_date_str = "2023-02-20"
    test_date_obj = date(2023, 2, 20)

    response = client.get(f"/my-workflows?created_at={test_date_str}&status=pending")
    assert response.status_code == 200

    mock_service.list_instances_for_user.assert_called_once_with(
        user_id=mock_user.user_id,
        created_at_date=test_date_obj,
        status=WorkflowStatus.pending
    )
    mock_renderer.render.assert_called_once_with(
        "my_workflows.html",
        ANY,
        {
            "instances": [],
            "selected_created_at": test_date_str,
            "selected_status": "pending",
            "workflow_statuses": [s.value for s in WorkflowStatus]
        }
    )

@pytest.mark.asyncio
async def test_my_workflows_invalid_created_at(mock_dependencies_for_my_workflows):
    client = TestClient(app)
    mock_service, mock_renderer = mock_dependencies_for_my_workflows

    response = client.get("/my-workflows?created_at=invalid-date")
    assert response.status_code == 200

    # Defaults to today's date
    mock_service.list_instances_for_user.assert_called_once_with(
        user_id=mock_user.user_id,
        created_at_date=date.today(),
        status=WorkflowStatus.active
    )
    mock_renderer.render.assert_called_once_with(
        "my_workflows.html",
        ANY,
        {
            "instances": [],
            "selected_created_at": date.today().isoformat(),
            "selected_status": "active",
            "workflow_statuses": [s.value for s in WorkflowStatus]
        }
    )

@pytest.mark.asyncio
async def test_my_workflows_invalid_status(mock_dependencies_for_my_workflows):
    client = TestClient(app)
    mock_service, mock_renderer = mock_dependencies_for_my_workflows

    response = client.get("/my-workflows?status=invalidstatus")
    assert response.status_code == 200

    # Defaults to active status
    mock_service.list_instances_for_user.assert_called_once_with(
        user_id=mock_user.user_id,
        created_at_date=date.today(),
        status=WorkflowStatus.active # Default for invalid status string
    )
    mock_renderer.render.assert_called_once_with(
        "my_workflows.html",
        ANY,
        {
            "instances": [],
            "selected_created_at": date.today().isoformat(),
            "selected_status": "active", # Reflects the default used
            "workflow_statuses": [s.value for s in WorkflowStatus]
        }
    )
