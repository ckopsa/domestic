import pytest
import sys
import os
import json
from fastapi.testclient import TestClient
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from app.db_models import Base
from app.main import app
from app.database import get_db, engine
from app.core.security import AuthenticatedUser, get_current_active_user

# Test client
client = TestClient(app)

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
