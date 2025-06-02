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


# --- Tests for /workflow-instances/{instance_id}/archive ---

# Constants for archive API tests
OWNER_USER_ID_FOR_ARCHIVE = "owner_archive_api"
OTHER_USER_ID_FOR_ARCHIVE = "other_archive_api"

@pytest.fixture
def client_as_user_archive(monkeypatch): # Renamed to avoid conflict if other client_as_user exists
    clients_created = []
    original_override = app.dependency_overrides.get(get_current_active_user)

    def _client_as_user(user: AuthenticatedUser = None):
        if user:
            monkeypatch.setitem(app.dependency_overrides, get_current_active_user, lambda: user)
        else: # No user / unauthenticated
            if get_current_active_user in app.dependency_overrides:
                monkeypatch.delitem(app.dependency_overrides, get_current_active_user)
        
        client = TestClient(app)
        clients_created.append(client) # Keep track if needed, though TestClient instances are independent
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
    client_for_creation: TestClient, # Client authenticated as the user who should own the instance
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
            db_instance = temp_db_session.query(WorkflowInstanceORM).filter(WorkflowInstanceORM.id == instance_id).first()
            assert db_instance is not None
            db_instance.status = status # This should be the WorkflowStatus enum member, not string
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
    instance = create_test_workflow_instance_for_archive(setup_client, owner.user_id, status=WorkflowStatus.active, def_name_suffix="success")
    instance_id = instance["id"]
    
    # Client for the actual test call, also authenticated as owner
    client = client_as_user_archive(owner) # This will re-apply the override via monkeypatch

    response = client.post(f"/workflow-instances/{instance_id}/archive", follow_redirects=False)

    assert response.status_code == 303 # Redirect
    assert response.headers["location"] == f"/workflow-instances/{instance_id}"

    # Verify status using the API (client is still authenticated as owner)
    updated_instance_response = client.get(f"/api/workflow-instances/{instance_id}")
    assert updated_instance_response.status_code == 200
    assert updated_instance_response.json()["instance"]["status"] == WorkflowStatus.ARCHIVED.value


@pytest.mark.asyncio
async def test_archive_instance_not_authenticated(db_session, client_as_user_archive, monkeypatch):
    owner = AuthenticatedUser(user_id=OWNER_USER_ID_FOR_ARCHIVE, username="owner_archive_auth", email="owner_auth@archive.com")
    
    # Setup client for creating instance (as owner)
    monkeypatch.setitem(app.dependency_overrides, get_current_active_user, lambda: owner)
    setup_client = TestClient(app)
    instance = create_test_workflow_instance_for_archive(setup_client, owner.user_id, status=WorkflowStatus.active, def_name_suffix="notauth")
    instance_id = instance["id"]

    # Client for test is unauthenticated
    client = client_as_user_archive(None) 
    
    response = client.post(f"/workflow-instances/{instance_id}/archive", follow_redirects=False)

    assert response.status_code == 307 # Temporary Redirect to login as per FastAPI default for unauthenticated HTML form posts
    assert "/login" in response.headers["location"].lower() 

@pytest.mark.asyncio
async def test_archive_instance_other_user(db_session, client_as_user_archive, monkeypatch):
    owner = AuthenticatedUser(user_id=OWNER_USER_ID_FOR_ARCHIVE, username="owner_archive_other", email="owner_other@archive.com")
    other = AuthenticatedUser(user_id=OTHER_USER_ID_FOR_ARCHIVE, username="other_archive", email="other@archive.com")

    # Setup client for creating instance (as owner)
    monkeypatch.setitem(app.dependency_overrides, get_current_active_user, lambda: owner)
    setup_client = TestClient(app)
    instance = create_test_workflow_instance_for_archive(setup_client, owner.user_id, status=WorkflowStatus.active, def_name_suffix="otheruser")
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
    monkeypatch.setitem(app.dependency_overrides, get_current_active_user, lambda: owner) # Switch auth to owner
    owner_client = TestClient(app) # New client with owner auth
    original_instance_response = owner_client.get(f"/api/workflow-instances/{instance_id}")
    assert original_instance_response.status_code == 200
    assert original_instance_response.json()["instance"]["status"] == WorkflowStatus.active.value


@pytest.mark.asyncio
async def test_archive_instance_already_completed(db_session, client_as_user_archive, monkeypatch):
    owner = AuthenticatedUser(user_id=OWNER_USER_ID_FOR_ARCHIVE, username="owner_archive_completed", email="owner_completed@archive.com")
    
    monkeypatch.setitem(app.dependency_overrides, get_current_active_user, lambda: owner)
    setup_client = TestClient(app) # Client for setup, authenticated as owner
    instance = create_test_workflow_instance_for_archive(setup_client, owner.user_id, status=WorkflowStatus.completed, def_name_suffix="completed")
    instance_id = instance["id"]
    
    client = client_as_user_archive(owner) # Client for test, also as owner
    response = client.post(f"/workflow-instances/{instance_id}/archive", follow_redirects=False)

    assert response.status_code == 400 # Bad Request
    assert "cannot archive a workflow instance that is already completed" in response.text.lower()

@pytest.mark.asyncio
async def test_archive_instance_non_existent(db_session, client_as_user_archive, monkeypatch):
    owner = AuthenticatedUser(user_id=OWNER_USER_ID_FOR_ARCHIVE, username="owner_archive_nonexist", email="owner_nonexist@archive.com")
    client = client_as_user_archive(owner)
    instance_id = "non_existent_instance_id_12345abc"

    response = client.post(f"/workflow-instances/{instance_id}/archive", follow_redirects=False)

    assert response.status_code == 404 # Not Found
    # Message comes from service.archive returning None, then router trying get_workflow_instance_with_tasks, which also fails for non-existent.
    assert f"workflow instance with id '{instance_id}' not found or you do not have permission to view it" in response.text.lower()

@pytest.mark.asyncio
async def test_archive_instance_already_archived(db_session, client_as_user_archive, monkeypatch):
    owner = AuthenticatedUser(user_id=OWNER_USER_ID_FOR_ARCHIVE, username="owner_archive_already", email="owner_already@archive.com")
    
    monkeypatch.setitem(app.dependency_overrides, get_current_active_user, lambda: owner)
    setup_client = TestClient(app)
    instance = create_test_workflow_instance_for_archive(setup_client, owner.user_id, status=WorkflowStatus.ARCHIVED, def_name_suffix="alreadyarchived")
    instance_id = instance["id"]
    
    client = client_as_user_archive(owner)
    response = client.post(f"/workflow-instances/{instance_id}/archive", follow_redirects=False)

    # The service method `archive_workflow_instance` returns the instance if already archived.
    # The router endpoint then treats this as a success and redirects.
    assert response.status_code == 303 
    assert response.headers["location"] == f"/workflow-instances/{instance_id}"

    # Verify status is still ARCHIVED
    updated_instance_response = client.get(f"/api/workflow-instances/{instance_id}")
    assert updated_instance_response.status_code == 200
    assert updated_instance_response.json()["instance"]["status"] == WorkflowStatus.ARCHIVED.value


# --- Tests for /workflow-instances/{instance_id}/unarchive ---

# Constants for unarchive API tests
OWNER_USER_ID_FOR_UNARCHIVE = "owner_unarchive_api"
OTHER_USER_ID_FOR_UNARCHIVE = "other_unarchive_api"

@pytest.mark.asyncio
async def test_unarchive_instance_success(db_session, client_as_user_archive, monkeypatch):
    owner = AuthenticatedUser(user_id=OWNER_USER_ID_FOR_UNARCHIVE, username="owner_unarchive", email="owner@unarchive.com")
    
    monkeypatch.setitem(app.dependency_overrides, get_current_active_user, lambda: owner)
    setup_client = TestClient(app)
    instance = create_test_workflow_instance_for_archive(setup_client, owner.user_id, status=WorkflowStatus.ARCHIVED, def_name_suffix="unarchive_success")
    instance_id = instance["id"]
    
    client = client_as_user_archive(owner)
    response = client.post(f"/workflow-instances/{instance_id}/unarchive", follow_redirects=False)

    assert response.status_code == 303 # Redirect
    assert response.headers["location"] == f"/workflow-instances/{instance_id}"

    updated_instance_response = client.get(f"/api/workflow-instances/{instance_id}")
    assert updated_instance_response.status_code == 200
    assert updated_instance_response.json()["instance"]["status"] == WorkflowStatus.active.value

@pytest.mark.asyncio
async def test_unarchive_instance_not_authenticated(db_session, client_as_user_archive, monkeypatch):
    owner = AuthenticatedUser(user_id=OWNER_USER_ID_FOR_UNARCHIVE, username="owner_unarchive_auth", email="owner_unauth@unarchive.com")
    
    monkeypatch.setitem(app.dependency_overrides, get_current_active_user, lambda: owner)
    setup_client = TestClient(app)
    instance = create_test_workflow_instance_for_archive(setup_client, owner.user_id, status=WorkflowStatus.ARCHIVED, def_name_suffix="unarchive_notauth")
    instance_id = instance["id"]

    client = client_as_user_archive(None) # Unauthenticated client
    response = client.post(f"/workflow-instances/{instance_id}/unarchive", follow_redirects=False)

    assert response.status_code == 307 # Redirect to login
    assert "/login" in response.headers["location"].lower()

@pytest.mark.asyncio
async def test_unarchive_instance_other_user(db_session, client_as_user_archive, monkeypatch):
    owner = AuthenticatedUser(user_id=OWNER_USER_ID_FOR_UNARCHIVE, username="owner_unarchive_other", email="owner_other@unarchive.com")
    other = AuthenticatedUser(user_id=OTHER_USER_ID_FOR_UNARCHIVE, username="other_unarchive", email="other@unarchive.com")

    monkeypatch.setitem(app.dependency_overrides, get_current_active_user, lambda: owner)
    setup_client = TestClient(app)
    instance = create_test_workflow_instance_for_archive(setup_client, owner.user_id, status=WorkflowStatus.ARCHIVED, def_name_suffix="unarchive_other_user")
    instance_id = instance["id"]

    client = client_as_user_archive(other) # Authenticated as 'other' user
    response = client.post(f"/workflow-instances/{instance_id}/unarchive", follow_redirects=False)
    
    assert response.status_code == 404 # Service returns None, router shows 404 if instance not found for user
    assert "not found or you do not have permission to view it" in response.text.lower()

    monkeypatch.setitem(app.dependency_overrides, get_current_active_user, lambda: owner)
    owner_client = TestClient(app)
    original_instance_response = owner_client.get(f"/api/workflow-instances/{instance_id}")
    assert original_instance_response.json()["instance"]["status"] == WorkflowStatus.ARCHIVED.value # Should still be archived

@pytest.mark.asyncio
async def test_unarchive_instance_not_archived_state_active(db_session, client_as_user_archive, monkeypatch):
    owner = AuthenticatedUser(user_id=OWNER_USER_ID_FOR_UNARCHIVE, username="owner_unarchive_active", email="owner_active@unarchive.com")
    
    monkeypatch.setitem(app.dependency_overrides, get_current_active_user, lambda: owner)
    setup_client = TestClient(app)
    instance = create_test_workflow_instance_for_archive(setup_client, owner.user_id, status=WorkflowStatus.active, def_name_suffix="unarchive_already_active")
    instance_id = instance["id"]
    
    client = client_as_user_archive(owner)
    response = client.post(f"/workflow-instances/{instance_id}/unarchive", follow_redirects=False)

    assert response.status_code == 400 # Bad Request
    assert "cannot unarchive a workflow instance that is not currently archived" in response.text.lower()

@pytest.mark.asyncio
async def test_unarchive_instance_not_archived_state_completed(db_session, client_as_user_archive, monkeypatch):
    owner = AuthenticatedUser(user_id=OWNER_USER_ID_FOR_UNARCHIVE, username="owner_unarchive_completed", email="owner_completed@unarchive.com")
    
    monkeypatch.setitem(app.dependency_overrides, get_current_active_user, lambda: owner)
    setup_client = TestClient(app)
    instance = create_test_workflow_instance_for_archive(setup_client, owner.user_id, status=WorkflowStatus.completed, def_name_suffix="unarchive_already_completed")
    instance_id = instance["id"]
    
    client = client_as_user_archive(owner)
    response = client.post(f"/workflow-instances/{instance_id}/unarchive", follow_redirects=False)

    assert response.status_code == 400 # Bad Request
    assert "cannot unarchive a workflow instance that is not currently archived" in response.text.lower()


@pytest.mark.asyncio
async def test_unarchive_instance_non_existent(db_session, client_as_user_archive, monkeypatch):
    owner = AuthenticatedUser(user_id=OWNER_USER_ID_FOR_UNARCHIVE, username="owner_unarchive_nonexist", email="owner_nonexist@unarchive.com")
    client = client_as_user_archive(owner)
    instance_id = "non_existent_instance_for_unarchive"

    response = client.post(f"/workflow-instances/{instance_id}/unarchive", follow_redirects=False)

    assert response.status_code == 404 # Not Found
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
