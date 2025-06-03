import os
import sys
from datetime import date
from unittest.mock import AsyncMock, MagicMock, ANY

import pytest
from fastapi.testclient import TestClient

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from app.main import app
from app.database import get_db, engine  # get_db might not be directly used by these new tests
from app.dependencies import get_workflow_service, get_html_renderer  # For overriding
from app.services import WorkflowService  # For spec
from app.core.html_renderer import HtmlRendererInterface  # For spec
from app.core.security import AuthenticatedUser, get_current_active_user
from app.db_models.enums import WorkflowStatus  # For test cases

# Test client - can be initialized per test or per module if state is managed
client = TestClient(app)  # Will re-initialize client in fixture for overrides

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
async def test_healthcheck():
    # Act
    response = client.get("/api/healthz")

    # Assert
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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
    assert response_beta.json()["id"] in all_returned_ids  # Get id_beta here
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
async def test_get_workflow_dashboard_page(db_session):
    # Arrange: Create a definition
    definition_data = {
        "name": "Dashboard Test Workflow",
        "description": "Workflow for dashboard test",
        "task_names": ["Task Alpha"]
    }
    # Ensure the API endpoint for creating definitions is correct
    create_def_response = client.post("/api/workflow-definitions", json=definition_data)
    assert create_def_response.status_code == 201
    definition_id = create_def_response.json()["id"]

    # Arrange: Create an instance for the mock_user
    # The user_id for the instance will be 'test_user' due to override_get_current_active_user
    instance_data = {
        "definition_id": definition_id
    }
    # The mock_user's ID 'test_user' will be associated with this instance by the service.
    create_inst_response = client.post(f"/api/workflow-instances", json={"definition_id": definition_id})
    assert create_inst_response.status_code == 201
    instance_json = create_inst_response.json()
    instance_id = instance_json["id"]
    instance_name = instance_json["name"] # Should be "Dashboard Test Workflow"

    # Act: Get the dashboard page
    response = client.get("/workflow-instances/dashboard")

    # Assert: Basic page structure and content
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "My Workflows Dashboard" in response.text
    assert "<th>Name</th>" in response.text
    assert "<th>Status</th>" in response.text
    assert "<th>Actions</th>" in response.text

    # Assert: Check if the created instance is listed
    assert instance_name in response.text
    assert instance_id in response.text
    assert f'<a href="/workflow-instances/{instance_id}" class="action-button">View Details</a>' in response.text

@pytest.mark.asyncio
async def test_get_single_instance_dashboard_page(db_session):
    # Arrange: Create a definition
    definition_data = {
        "name": "Single Dashboard Test Workflow",
        "description": "Workflow for single dashboard test",
        "task_names": ["Task A - Done", "Task B - Next", "Task C - Later"]
    }
    create_def_response = client.post("/api/workflow-definitions", json=definition_data)
    assert create_def_response.status_code == 201
    definition_id = create_def_response.json()["id"]

    # Arrange: Create an instance for the mock_user
    create_inst_response = client.post(f"/api/workflow-instances", json={"definition_id": definition_id})
    assert create_inst_response.status_code == 201
    instance_json = create_inst_response.json()
    instance_id = instance_json["id"]
    instance_name = instance_json["name"] # Should be "Single Dashboard Test Workflow"

    # Arrange: Get tasks and complete the first one ("Task A - Done")
    instance_details_response = client.get(f"/api/workflow-instances/{instance_id}")
    assert instance_details_response.status_code == 200
    tasks_from_api = instance_details_response.json()["tasks"] # Renamed to avoid conflict
    
    task_a_id = None
    task_a_name = "Task A - Done"
    task_b_name = "Task B - Next"
    task_c_name = "Task C - Later"

    for task_api_item in tasks_from_api: # Renamed to avoid conflict
        if task_api_item["name"] == task_a_name:
            task_a_id = task_api_item["id"]
            break
    assert task_a_id is not None, f"{task_a_name} not found in instance tasks"

    complete_task_a_response = client.post(f"/api/task-instances/{task_a_id}/complete")
    assert complete_task_a_response.status_code == 200
    assert complete_task_a_response.json()["status"].lower() == "completed"

    # Act: Get the single instance dashboard page
    dashboard_response = client.get(f"/workflow-instances/{instance_id}/dashboard")

    # Assert: Basic page structure and content
    assert dashboard_response.status_code == 200
    assert "text/html" in dashboard_response.headers["content-type"]
    response_text = dashboard_response.text # Get text once for multiple assertions
    assert f"Dashboard: {instance_name}" in response_text
    
    # Assert: Task information and highlighting
    # Check for Task A - Done (Completed)
    assert task_a_name in response_text
    assert f'<li class="task-item-dashboard completed-task">' in response_text # More specific
    assert f'<span class="task-name">{task_a_name}</span> - <span class="task-status">COMPLETED</span>' in response_text

    # Check for Task B - Next (Priority)
    assert task_b_name in response_text
    assert f'<li class="task-item-dashboard priority-task">' in response_text # More specific
    assert f'<span class="task-name">{task_b_name}</span> - <span class="task-status">PENDING</span><span class="priority-tag"> (Next Up)</span>' in response_text
    
    # Check for Task C - Later (Pending)
    assert task_c_name in response_text
    assert f'<li class="task-item-dashboard pending-task">' in response_text # More specific
    assert f'<span class="task-name">{task_c_name}</span> - <span class="task-status">PENDING</span>' in response_text
    assert "(Next Up)" not in response_text[response_text.find(task_c_name):] # Ensure (Next Up) is not after Task C

    # Assert: Read-only (no interactive forms for task completion)
    assert "Mark Complete</button>" not in response_text
    assert "<form action=\"/task-instances/" not in response_text 

    # Assert: Navigation links
    assert f'<a href="/workflow-instances/{instance_id}" class="action-button">View Interactive Workflow</a>' in response_text
    assert '<a href="/workflow-instances/dashboard" class="back-link"' in response_text
    assert '<a href="/" class="back-link"' in response_text

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
    mock_service.list_instances_for_user = AsyncMock(return_value=[])  # Default empty list

    mock_renderer_instance = MagicMock(spec=HtmlRendererInterface)
    mock_renderer_instance.render = AsyncMock(return_value="Mocked HTML")  # Default render response

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
    client = TestClient(app)  # Fresh client to ensure overrides are clean if not using monkeypatch correctly
    mock_service, mock_renderer = mock_dependencies_for_my_workflows

    response = client.get("/my-workflows")
    assert response.status_code == 200

    mock_service.list_instances_for_user.assert_called_once_with(
        user_id=mock_user.user_id,  # from global mock_user via override_get_current_active_user
        created_at_date=date.today(),
        status=WorkflowStatus.active
    )
    mock_renderer.render.assert_called_once_with(
        "my_workflows.html",
        ANY,  # request object
        {
            "instances": [],  # Default return from mock_service.list_instances_for_user
            "selected_created_at": date.today().isoformat(),
            "selected_status": "active",
            "workflow_statuses": [s.value for s in WorkflowStatus]
        }
    )

# --- Tests for Shareable Link API Endpoints ---

MOCK_INSTANCE_ID_SHARE = "share_inst_001"
MOCK_SHARE_TOKEN = "public_share_token_xyz"
OWNER_USER_SHARE = AuthenticatedUser(user_id="owner_of_share_instance", username="shareowner", email="share@owner.com")
NON_OWNER_USER_SHARE = AuthenticatedUser(user_id="non_owner_of_share_instance", username="sharenotowner", email="sharenon@owner.com")

@pytest.fixture
def mock_workflow_service_for_share(monkeypatch):
    mock_service = MagicMock(spec=WorkflowService)
    monkeypatch.setitem(app.dependency_overrides, get_workflow_service, lambda: mock_service)
    yield mock_service # Use yield to allow cleanup if monkeypatch needs it, though setitem is usually fine
    monkeypatch.delitem(app.dependency_overrides, get_workflow_service, raising=False)


# Tests for POST /workflow-instances/{instance_id}/share
@pytest.mark.asyncio
async def test_generate_share_link_authenticated_owner(client_as_user_archive, mock_workflow_service_for_share, monkeypatch):
    # client_as_user_archive fixture can be reused; it sets current_user via monkeypatch
    client = client_as_user_archive(OWNER_USER_SHARE) # Authenticate as owner

    # Mock service method
    mock_workflow_service_for_share.generate_shareable_link = AsyncMock(
        return_value=MagicMock(share_token=MOCK_SHARE_TOKEN) # Return a mock instance with a share_token
    )

    response = client.post(f"/workflow-instances/{MOCK_INSTANCE_ID_SHARE}/share", follow_redirects=False)

    assert response.status_code == 303 # Redirect
    assert response.headers["location"] == f"/workflow-instances/{MOCK_INSTANCE_ID_SHARE}"
    mock_workflow_service_for_share.generate_shareable_link.assert_called_once_with(
        MOCK_INSTANCE_ID_SHARE, OWNER_USER_SHARE.user_id
    )

@pytest.mark.asyncio
async def test_generate_share_link_service_returns_none(client_as_user_archive, mock_workflow_service_for_share, monkeypatch):
    client = client_as_user_archive(OWNER_USER_SHARE) # Authenticate as owner
    mock_workflow_service_for_share.generate_shareable_link = AsyncMock(return_value=None) # Simulate instance not found or not owner

    response = client.post(f"/workflow-instances/{MOCK_INSTANCE_ID_SHARE}/share", follow_redirects=False)

    assert response.status_code == 303 # Still redirects back
    assert response.headers["location"] == f"/workflow-instances/{MOCK_INSTANCE_ID_SHARE}"
    mock_workflow_service_for_share.generate_shareable_link.assert_called_once_with(
        MOCK_INSTANCE_ID_SHARE, OWNER_USER_SHARE.user_id
    )

@pytest.mark.asyncio
async def test_generate_share_link_unauthenticated(client_as_user_archive, mock_workflow_service_for_share, monkeypatch):
    client = client_as_user_archive(None) # Unauthenticated

    response = client.post(f"/workflow-instances/{MOCK_INSTANCE_ID_SHARE}/share", follow_redirects=False)

    assert response.status_code == 307 # Redirect to login
    assert "/login" in response.headers["location"].lower()
    mock_workflow_service_for_share.generate_shareable_link.assert_not_called()

@pytest.mark.asyncio
async def test_generate_share_link_non_owner(client_as_user_archive, mock_workflow_service_for_share, monkeypatch):
    client = client_as_user_archive(NON_OWNER_USER_SHARE) # Authenticated as non-owner
    # Service should handle non-owner logic and return None
    mock_workflow_service_for_share.generate_shareable_link = AsyncMock(return_value=None)

    response = client.post(f"/workflow-instances/{MOCK_INSTANCE_ID_SHARE}/share", follow_redirects=False)

    assert response.status_code == 303 # Redirects back
    assert response.headers["location"] == f"/workflow-instances/{MOCK_INSTANCE_ID_SHARE}"
    mock_workflow_service_for_share.generate_shareable_link.assert_called_once_with(
        MOCK_INSTANCE_ID_SHARE, NON_OWNER_USER_SHARE.user_id
    )

# Tests for GET /share/workflow/{share_token}
@pytest.mark.asyncio
async def test_view_shared_workflow_valid_token(client, mock_workflow_service_for_share, monkeypatch):
    # For this public endpoint, ensure no authentication override is active from other fixtures like client_as_user_archive
    # A clean way is to directly manage app.dependency_overrides for get_current_active_user here.
    original_auth_override = app.dependency_overrides.pop(get_current_active_user, None)
    
    mock_instance_data = MagicMock(name="WorkflowInstanceData") # Using MagicMock to simulate Pydantic model
    mock_instance_data.name = "My Shared Workflow"
    # Add other fields if template uses them directly from instance, e.g. id, status, created_at
    mock_instance_data.id = MOCK_INSTANCE_ID_SHARE 
    mock_instance_data.status = WorkflowStatus.active 
    from datetime import date
    mock_instance_data.created_at = date.today()


    mock_tasks_data = [MagicMock(name="Task1"), MagicMock(name="Task2")]

    mock_workflow_service_for_share.get_workflow_instance_by_share_token = AsyncMock(
        return_value={"instance": mock_instance_data, "tasks": mock_tasks_data}
    )
    
    mock_renderer_instance = MagicMock(spec=HtmlRendererInterface)
    async def mock_render_func(template_name, request_obj, context):
        mock_renderer_instance.last_template_name = template_name
        mock_renderer_instance.last_context = context
        from fastapi.responses import HTMLResponse
        # Simulate checking for absence of action buttons by looking for a known button's text
        # This is a simple check; more robust would be parsing HTML or specific sentinels
        content_html = f"Mock render of {template_name}. Instance: {context['instance'].name}."
        if context.get("is_shared_view"):
            # Check if some known non-shared elements are NOT in a simple representation of context
            # This is a proxy, real check would be on rendered HTML for specific button non-existence.
            # For now, we rely on the is_shared_view flag being correctly used by the template.
             pass # Test will check is_shared_view flag in context
        return HTMLResponse(content_html)
    mock_renderer_instance.render = AsyncMock(side_effect=mock_render_func)
    monkeypatch.setitem(app.dependency_overrides, get_html_renderer, lambda: mock_renderer_instance)

    response = client.get(f"/share/workflow/{MOCK_SHARE_TOKEN}")

    assert response.status_code == 200
    assert "My Shared Workflow" in response.text 
    mock_workflow_service_for_share.get_workflow_instance_by_share_token.assert_called_once_with(MOCK_SHARE_TOKEN)
    
    assert mock_renderer_instance.last_template_name == "workflow_instance.html"
    assert mock_renderer_instance.last_context["instance"] == mock_instance_data
    assert mock_renderer_instance.last_context["tasks"] == mock_tasks_data
    assert mock_renderer_instance.last_context["is_shared_view"] is True
    
    if original_auth_override: # Restore auth override
        app.dependency_overrides[get_current_active_user] = original_auth_override
    monkeypatch.delitem(app.dependency_overrides, get_html_renderer, raising=False)


@pytest.mark.asyncio
async def test_view_shared_workflow_invalid_token(client, mock_workflow_service_for_share, monkeypatch):
    original_auth_override = app.dependency_overrides.pop(get_current_active_user, None)
    mock_workflow_service_for_share.get_workflow_instance_by_share_token = AsyncMock(return_value=None)

    mock_renderer_instance_error = MagicMock(spec=HtmlRendererInterface)
    async def mock_render_error_func(template_name, request_obj, context):
        mock_renderer_instance_error.last_template_name = template_name
        mock_renderer_instance_error.last_context = context
        from fastapi.responses import HTMLResponse
        if template_name == "message.html" and context.get("title") == "Not Found":
             response = HTMLResponse(f"Mock error page: {context.get('message')}", status_code=404)
             # To make it behave like the actual create_message_page's response for status code
             response.status_code = context.get("status_code", 404)
             return response
        return HTMLResponse("Unexpected template render for error", status_code=500)

    mock_renderer_instance_error.render = AsyncMock(side_effect=mock_render_error_func)
    monkeypatch.setitem(app.dependency_overrides, get_html_renderer, lambda: mock_renderer_instance_error)

    response = client.get(f"/share/workflow/invalid_{MOCK_SHARE_TOKEN}")

    assert response.status_code == 404
    assert "Mock error page: The shared workflow link is invalid or the workflow was not found." in response.text
    mock_workflow_service_for_share.get_workflow_instance_by_share_token.assert_called_once_with(f"invalid_{MOCK_SHARE_TOKEN}")

    if original_auth_override:
        app.dependency_overrides[get_current_active_user] = original_auth_override
    monkeypatch.delitem(app.dependency_overrides, get_html_renderer, raising=False)


# --- Tests for /workflow-instances/{instance_id}/archive ---

# Constants for archive API tests
OWNER_USER_ID_FOR_ARCHIVE = "owner_archive_api"
OTHER_USER_ID_FOR_ARCHIVE = "other_archive_api"


@pytest.fixture
def client_as_user_archive(monkeypatch):  # Renamed to avoid conflict if other client_as_user exists
    clients_created = []
    original_override = app.dependency_overrides.get(get_current_active_user)

    def _client_as_user(user: AuthenticatedUser = None):
        if user:
            monkeypatch.setitem(app.dependency_overrides, get_current_active_user, lambda: user)
        else:  # No user / unauthenticated
            if get_current_active_user in app.dependency_overrides:
                monkeypatch.delitem(app.dependency_overrides, get_current_active_user)

        client = TestClient(app)
        clients_created.append(client)  # Keep track if needed, though TestClient instances are independent
        return client

    yield _client_as_user

    # Cleanup: restore original override or remove if it was added by this fixture
    if original_override:
        monkeypatch.setitem(app.dependency_overrides, get_current_active_user, original_override)
    elif get_current_active_user in app.dependency_overrides:
        monkeypatch.delitem(app.dependency_overrides, get_current_active_user)


# Helper to create a workflow definition and instance for testing archive functionality
# Uses direct DB manipulation for status to simplify setup and avoid complex API chaining for status changes.
def create_test_workflow_instance_for_archive(
        client_for_creation: TestClient,  # Client authenticated as the user who should own the instance
        owner_user_id: str,
        status: WorkflowStatus = WorkflowStatus.active,
        def_name_suffix: str = ""
) -> dict:
    definition_data = {
        "name": f"Archive Test Def {def_name_suffix}",
        "description": "Def for archive testing",
        "task_names": ["Task 1"]
    }
    # client_for_creation is already authenticated as owner_user_id
    create_def_response = client_for_creation.post("/api/workflow-definitions", json=definition_data)
    assert create_def_response.status_code == 201
    definition_id = create_def_response.json()["id"]

    instance_data = {"definition_id": definition_id}
    create_inst_response = client_for_creation.post("/api/workflow-instances", json=instance_data)
    assert create_inst_response.status_code == 201
    instance_id = create_inst_response.json()["id"]
    created_instance = create_inst_response.json()

    # Manually update status in DB if needed, as API create defaults to 'active' and user_id from auth
    # The instance created via API will have user_id from client_for_creation's auth.
    # We need to ensure this matches owner_user_id passed.
    assert created_instance["user_id"] == owner_user_id

    if status != WorkflowStatus.active:
        from app.db_models.workflow import WorkflowInstance as WorkflowInstanceORM
        # Use a new DB session for this direct modification
        temp_db_session = next(get_db())
        try:
            db_instance = temp_db_session.query(WorkflowInstanceORM).filter(
                WorkflowInstanceORM.id == instance_id).first()
            assert db_instance is not None
            db_instance.status = status  # This should be the WorkflowStatus enum member, not string
            temp_db_session.commit()
            temp_db_session.refresh(db_instance)
            # Update the created_instance dict with the new status
            created_instance = client_for_creation.get(f"/api/workflow-instances/{instance_id}").json()["instance"]
        finally:
            temp_db_session.close()

    return created_instance


@pytest.mark.asyncio
async def test_archive_instance_success(db_session, client_as_user_archive, monkeypatch):
    owner = AuthenticatedUser(user_id=OWNER_USER_ID_FOR_ARCHIVE, username="owner_archive", email="owner@archive.com")

    # Client for setup, authenticated as owner
    monkeypatch.setitem(app.dependency_overrides, get_current_active_user, lambda: owner)
    setup_client = TestClient(app)
    instance = create_test_workflow_instance_for_archive(setup_client, owner.user_id, status=WorkflowStatus.active,
                                                         def_name_suffix="success")
    instance_id = instance["id"]

    # Client for the actual test call, also authenticated as owner
    client = client_as_user_archive(owner)  # This will re-apply the override via monkeypatch

    response = client.post(f"/workflow-instances/{instance_id}/archive", follow_redirects=False)

    assert response.status_code == 303  # Redirect
    assert response.headers["location"] == f"/workflow-instances/{instance_id}"

    # Verify status using the API (client is still authenticated as owner)
    updated_instance_response = client.get(f"/api/workflow-instances/{instance_id}")
    assert updated_instance_response.status_code == 200
    assert updated_instance_response.json()["instance"]["status"] == WorkflowStatus.archived.value


@pytest.mark.asyncio
async def test_archive_instance_not_authenticated(db_session, client_as_user_archive, monkeypatch):
    owner = AuthenticatedUser(user_id=OWNER_USER_ID_FOR_ARCHIVE, username="owner_archive_auth",
                              email="owner_auth@archive.com")

    # Setup client for creating instance (as owner)
    monkeypatch.setitem(app.dependency_overrides, get_current_active_user, lambda: owner)
    setup_client = TestClient(app)
    instance = create_test_workflow_instance_for_archive(setup_client, owner.user_id, status=WorkflowStatus.active,
                                                         def_name_suffix="notauth")
    instance_id = instance["id"]

    # Client for test is unauthenticated
    client = client_as_user_archive(None)

    response = client.post(f"/workflow-instances/{instance_id}/archive", follow_redirects=False)

    assert response.status_code == 307  # Temporary Redirect to login as per FastAPI default for unauthenticated HTML form posts
    assert "/login" in response.headers["location"].lower()


@pytest.mark.asyncio
async def test_archive_instance_other_user(db_session, client_as_user_archive, monkeypatch):
    owner = AuthenticatedUser(user_id=OWNER_USER_ID_FOR_ARCHIVE, username="owner_archive_other",
                              email="owner_other@archive.com")
    other = AuthenticatedUser(user_id=OTHER_USER_ID_FOR_ARCHIVE, username="other_archive", email="other@archive.com")

    # Setup client for creating instance (as owner)
    monkeypatch.setitem(app.dependency_overrides, get_current_active_user, lambda: owner)
    setup_client = TestClient(app)
    instance = create_test_workflow_instance_for_archive(setup_client, owner.user_id, status=WorkflowStatus.active,
                                                         def_name_suffix="otheruser")
    instance_id = instance["id"]

    # Client for test is authenticated as other_user
    client = client_as_user_archive(other)

    response = client.post(f"/workflow-instances/{instance_id}/archive", follow_redirects=False)

    # Based on the endpoint logic, if service.archive_workflow_instance returns None (e.g. due to user mismatch)
    # it then tries to fetch the instance (service.get_workflow_instance_with_tasks) which would also fail for other_user
    # leading to a 404 from create_message_page.
    assert response.status_code == 404
    assert "not found or you do not have permission to view it" in response.text.lower()

    # Verify instance in DB is NOT archived (check via API as owner)
    monkeypatch.setitem(app.dependency_overrides, get_current_active_user, lambda: owner)  # Switch auth to owner
    owner_client = TestClient(app)  # New client with owner auth
    original_instance_response = owner_client.get(f"/api/workflow-instances/{instance_id}")
    assert original_instance_response.status_code == 200
    assert original_instance_response.json()["instance"]["status"] == WorkflowStatus.active.value


@pytest.mark.asyncio
async def test_archive_instance_already_completed(db_session, client_as_user_archive, monkeypatch):
    owner = AuthenticatedUser(user_id=OWNER_USER_ID_FOR_ARCHIVE, username="owner_archive_completed",
                              email="owner_completed@archive.com")

    monkeypatch.setitem(app.dependency_overrides, get_current_active_user, lambda: owner)
    setup_client = TestClient(app)  # Client for setup, authenticated as owner
    instance = create_test_workflow_instance_for_archive(setup_client, owner.user_id, status=WorkflowStatus.completed,
                                                         def_name_suffix="completed")
    instance_id = instance["id"]

    client = client_as_user_archive(owner)  # Client for test, also as owner
    response = client.post(f"/workflow-instances/{instance_id}/archive", follow_redirects=False)

    assert response.status_code == 400  # Bad Request
    assert "cannot archive a workflow instance that is already completed" in response.text.lower()


@pytest.mark.asyncio
async def test_archive_instance_non_existent(db_session, client_as_user_archive, monkeypatch):
    owner = AuthenticatedUser(user_id=OWNER_USER_ID_FOR_ARCHIVE, username="owner_archive_nonexist",
                              email="owner_nonexist@archive.com")
    client = client_as_user_archive(owner)
    instance_id = "non_existent_instance_id_12345abc"

    response = client.post(f"/workflow-instances/{instance_id}/archive", follow_redirects=False)

    assert response.status_code == 404  # Not Found
    # Message comes from service.archive returning None, then router trying get_workflow_instance_with_tasks, which also fails for non-existent.
    assert f"workflow instance with id '{instance_id}' not found or you do not have permission to view it" in response.text.lower()


@pytest.mark.asyncio
async def test_archive_instance_already_archived(db_session, client_as_user_archive, monkeypatch):
    owner = AuthenticatedUser(user_id=OWNER_USER_ID_FOR_ARCHIVE, username="owner_archive_already",
                              email="owner_already@archive.com")

    monkeypatch.setitem(app.dependency_overrides, get_current_active_user, lambda: owner)
    setup_client = TestClient(app)
    instance = create_test_workflow_instance_for_archive(setup_client, owner.user_id, status=WorkflowStatus.archived,
                                                         def_name_suffix="alreadyarchived")
    instance_id = instance["id"]

    client = client_as_user_archive(owner)
    response = client.post(f"/workflow-instances/{instance_id}/archive", follow_redirects=False)

    # The service method `archive_workflow_instance` returns the instance if already archived.
    # The router endpoint then treats this as a success and redirects.
    assert response.status_code == 303
    assert response.headers["location"] == f"/workflow-instances/{instance_id}"

    # Verify status is still archived
    updated_instance_response = client.get(f"/api/workflow-instances/{instance_id}")
    assert updated_instance_response.status_code == 200
    assert updated_instance_response.json()["instance"]["status"] == WorkflowStatus.archived.value


# --- Tests for /workflow-instances/{instance_id}/unarchive ---

# Constants for unarchive API tests
OWNER_USER_ID_FOR_UNARCHIVE = "owner_unarchive_api"
OTHER_USER_ID_FOR_UNARCHIVE = "other_unarchive_api"


@pytest.mark.asyncio
async def test_unarchive_instance_success(db_session, client_as_user_archive, monkeypatch):
    owner = AuthenticatedUser(user_id=OWNER_USER_ID_FOR_UNARCHIVE, username="owner_unarchive",
                              email="owner@unarchive.com")

    monkeypatch.setitem(app.dependency_overrides, get_current_active_user, lambda: owner)
    setup_client = TestClient(app)
    instance = create_test_workflow_instance_for_archive(setup_client, owner.user_id, status=WorkflowStatus.archived,
                                                         def_name_suffix="unarchive_success")
    instance_id = instance["id"]

    client = client_as_user_archive(owner)
    response = client.post(f"/workflow-instances/{instance_id}/unarchive", follow_redirects=False)

    assert response.status_code == 303  # Redirect
    assert response.headers["location"] == f"/workflow-instances/{instance_id}"

    updated_instance_response = client.get(f"/api/workflow-instances/{instance_id}")
    assert updated_instance_response.status_code == 200
    assert updated_instance_response.json()["instance"]["status"] == WorkflowStatus.active.value


@pytest.mark.asyncio
async def test_unarchive_instance_not_authenticated(db_session, client_as_user_archive, monkeypatch):
    owner = AuthenticatedUser(user_id=OWNER_USER_ID_FOR_UNARCHIVE, username="owner_unarchive_auth",
                              email="owner_unauth@unarchive.com")

    monkeypatch.setitem(app.dependency_overrides, get_current_active_user, lambda: owner)
    setup_client = TestClient(app)
    instance = create_test_workflow_instance_for_archive(setup_client, owner.user_id, status=WorkflowStatus.archived,
                                                         def_name_suffix="unarchive_notauth")
    instance_id = instance["id"]

    client = client_as_user_archive(None)  # Unauthenticated client
    response = client.post(f"/workflow-instances/{instance_id}/unarchive", follow_redirects=False)

    assert response.status_code == 307  # Redirect to login
    assert "/login" in response.headers["location"].lower()


@pytest.mark.asyncio
async def test_unarchive_instance_other_user(db_session, client_as_user_archive, monkeypatch):
    owner = AuthenticatedUser(user_id=OWNER_USER_ID_FOR_UNARCHIVE, username="owner_unarchive_other",
                              email="owner_other@unarchive.com")
    other = AuthenticatedUser(user_id=OTHER_USER_ID_FOR_UNARCHIVE, username="other_unarchive",
                              email="other@unarchive.com")

    monkeypatch.setitem(app.dependency_overrides, get_current_active_user, lambda: owner)
    setup_client = TestClient(app)
    instance = create_test_workflow_instance_for_archive(setup_client, owner.user_id, status=WorkflowStatus.archived,
                                                         def_name_suffix="unarchive_other_user")
    instance_id = instance["id"]

    client = client_as_user_archive(other)  # Authenticated as 'other' user
    response = client.post(f"/workflow-instances/{instance_id}/unarchive", follow_redirects=False)

    assert response.status_code == 404  # Service returns None, router shows 404 if instance not found for user
    assert "not found or you do not have permission to view it" in response.text.lower()

    monkeypatch.setitem(app.dependency_overrides, get_current_active_user, lambda: owner)
    owner_client = TestClient(app)
    original_instance_response = owner_client.get(f"/api/workflow-instances/{instance_id}")
    assert original_instance_response.json()["instance"][
               "status"] == WorkflowStatus.archived.value  # Should still be archived


@pytest.mark.asyncio
async def test_unarchive_instance_not_archived_state_active(db_session, client_as_user_archive, monkeypatch):
    owner = AuthenticatedUser(user_id=OWNER_USER_ID_FOR_UNARCHIVE, username="owner_unarchive_active",
                              email="owner_active@unarchive.com")

    monkeypatch.setitem(app.dependency_overrides, get_current_active_user, lambda: owner)
    setup_client = TestClient(app)
    instance = create_test_workflow_instance_for_archive(setup_client, owner.user_id, status=WorkflowStatus.active,
                                                         def_name_suffix="unarchive_already_active")
    instance_id = instance["id"]

    client = client_as_user_archive(owner)
    response = client.post(f"/workflow-instances/{instance_id}/unarchive", follow_redirects=False)

    assert response.status_code == 400  # Bad Request
    assert "cannot unarchive a workflow instance that is not currently archived" in response.text.lower()


@pytest.mark.asyncio
async def test_unarchive_instance_not_archived_state_completed(db_session, client_as_user_archive, monkeypatch):
    owner = AuthenticatedUser(user_id=OWNER_USER_ID_FOR_UNARCHIVE, username="owner_unarchive_completed",
                              email="owner_completed@unarchive.com")

    monkeypatch.setitem(app.dependency_overrides, get_current_active_user, lambda: owner)
    setup_client = TestClient(app)
    instance = create_test_workflow_instance_for_archive(setup_client, owner.user_id, status=WorkflowStatus.completed,
                                                         def_name_suffix="unarchive_already_completed")
    instance_id = instance["id"]

    client = client_as_user_archive(owner)
    response = client.post(f"/workflow-instances/{instance_id}/unarchive", follow_redirects=False)

    assert response.status_code == 400  # Bad Request
    assert "cannot unarchive a workflow instance that is not currently archived" in response.text.lower()


@pytest.mark.asyncio
async def test_unarchive_instance_non_existent(db_session, client_as_user_archive, monkeypatch):
    owner = AuthenticatedUser(user_id=OWNER_USER_ID_FOR_UNARCHIVE, username="owner_unarchive_nonexist",
                              email="owner_nonexist@unarchive.com")
    client = client_as_user_archive(owner)
    instance_id = "non_existent_instance_for_unarchive"

    response = client.post(f"/workflow-instances/{instance_id}/unarchive", follow_redirects=False)

    assert response.status_code == 404  # Not Found
    assert f"workflow instance with id '{instance_id}' not found or you do not have permission to view it" in response.text.lower()


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

    response = client.get("/my-workflows?status=")  # Empty status for "All Statuses"
    assert response.status_code == 200

    mock_service.list_instances_for_user.assert_called_once_with(
        user_id=mock_user.user_id,
        created_at_date=date.today(),
        status=None  # Service receives None for "All Statuses"
    )
    mock_renderer.render.assert_called_once_with(
        "my_workflows.html",
        ANY,
        {
            "instances": [],
            "selected_created_at": date.today().isoformat(),
            "selected_status": "",  # Template receives empty string
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
        status=WorkflowStatus.active  # Default for invalid status string
    )
    mock_renderer.render.assert_called_once_with(
        "my_workflows.html",
        ANY,
        {
            "instances": [],
            "selected_created_at": date.today().isoformat(),
            "selected_status": "active",  # Reflects the default used
            "workflow_statuses": [s.value for s in WorkflowStatus]
        }
    )
