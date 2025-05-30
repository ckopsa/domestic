import pytest
import sys
import os
import json
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from app.db_models import Base
from app.main import app
from app.database import get_db
from app.core.security import AuthenticatedUser

# Add the project root to sys.path to ensure 'app' module can be found

# Setup for in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Override the get_db dependency to use the test database
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

# Test client
client = TestClient(app)

# Mock user for authentication
mock_user = AuthenticatedUser(user_id="test_user", username="testuser", email="test@example.com")

# Fixture to setup and teardown the database
@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)

# Mock the get_current_active_user dependency
def override_get_current_active_user():
    return mock_user

# Override the dependency in the app for testing
app.dependency_overrides[lambda: override_get_db] = override_get_db

@pytest.mark.asyncio
def test_list_workflow_definitions(db_session):
    # Act
    response = client.get("/workflow-definitions/")

    # Assert
    assert response.status_code == 200
    assert isinstance(response.json(), list)

@pytest.mark.asyncio
def test_create_workflow_definition(db_session):
    # Arrange
    data = {
        "name": "Test Workflow",
        "description": "A test workflow",
        "task_names_str": "Task 1\nTask 2\nTask 3"
    }

    # Act
    response = client.post("/workflow-definitions/create", data=data)

    # Assert
    assert response.status_code == 303  # Redirect after successful creation
    assert response.headers['location'] == "/workflow-definitions"

@pytest.mark.asyncio
def test_create_workflow_definition_invalid_data(db_session):
    # Arrange
    data = {
        "name": "",  # Empty name should fail validation
        "description": "A test workflow",
        "task_names_str": "Task 1\nTask 2"
    }

    # Act
    response = client.post("/workflow-definitions/create", data=data)

    # Assert
    assert response.status_code == 400  # Bad request due to validation error

@pytest.mark.asyncio
def test_edit_workflow_definition(db_session):
    # Arrange: First create a definition
    definition_data = {
        "name": "Original Workflow",
        "description": "Original description",
        "task_names_str": "Original Task 1\nOriginal Task 2"
    }
    create_response = client.post("/workflow-definitions/create", data=definition_data)
    assert create_response.status_code == 303

    # Get the list to find the ID of the created definition
    list_response = client.get("/workflow-definitions/")
    definition_id = list_response.json()[0]["id"]

    # Update data
    update_data = {
        "name": "Updated Workflow",
        "description": "Updated description",
        "task_names_str": "Updated Task 1\nUpdated Task 2"
    }

    # Act
    response = client.post(f"/workflow-definitions/edit/{definition_id}", data=update_data)

    # Assert
    assert response.status_code == 303  # Redirect after successful update
    assert response.headers['location'] == "/workflow-definitions"

@pytest.mark.asyncio
def test_edit_workflow_definition_not_found(db_session):
    # Arrange
    data = {
        "name": "Updated Workflow",
        "description": "Updated description",
        "task_names_str": "Updated Task 1"
    }

    # Act
    response = client.post("/workflow-definitions/edit/nonexistent_id", data=data)

    # Assert
    assert response.status_code == 404  # Not found

@pytest.mark.asyncio
def test_delete_workflow_definition(db_session):
    # Arrange: First create a definition
    definition_data = {
        "name": "Workflow to Delete",
        "description": "This will be deleted",
        "task_names_str": "Task 1\nTask 2"
    }
    create_response = client.post("/workflow-definitions/create", data=definition_data)
    assert create_response.status_code == 303

    # Get the list to find the ID of the created definition
    list_response = client.get("/workflow-definitions/")
    definition_id = list_response.json()[0]["id"]

    # Act
    response = client.post(f"/workflow-definitions/delete/{definition_id}")

    # Assert
    assert response.status_code == 303  # Redirect after successful deletion
    assert response.headers['location'] == "/workflow-definitions"

@pytest.mark.asyncio
def test_delete_workflow_definition_not_found(db_session):
    # Act
    response = client.post("/workflow-definitions/delete/nonexistent_id")

    # Assert
    assert response.status_code == 404  # Not found

@pytest.mark.asyncio
def test_create_workflow_instance(db_session):
    # Arrange: First create a definition
    definition_data = {
        "name": "Workflow for Instance",
        "description": "Workflow to start an instance",
        "task_names_str": "Task 1\nTask 2"
    }
    create_response = client.post("/workflow-definitions/create", data=definition_data)
    assert create_response.status_code == 303

    # Get the list to find the ID of the created definition
    list_response = client.get("/workflow-definitions/")
    definition_id = list_response.json()[0]["id"]

    # Data for creating an instance
    instance_data = {
        "definition_id": definition_id
    }

    # Act
    response = client.post("/workflow-instances/", data=instance_data)

    # Assert
    assert response.status_code == 303  # Redirect after successful creation
    assert response.headers['location'].startswith("/workflow-instances/")

@pytest.mark.asyncio
def test_create_workflow_instance_invalid_definition(db_session):
    # Arrange
    instance_data = {
        "definition_id": "nonexistent_id"
    }

    # Act
    response = client.post("/workflow-instances/", data=instance_data)

    # Assert
    assert response.status_code == 500  # Server error due to invalid definition ID

@pytest.mark.asyncio
def test_get_workflow_instance(db_session):
    # Arrange: First create a definition and an instance
    definition_data = {
        "name": "Workflow for Instance",
        "description": "Workflow to start an instance",
        "task_names_str": "Task 1\nTask 2"
    }
    create_def_response = client.post("/workflow-definitions/create", data=definition_data)
    assert create_def_response.status_code == 303

    list_def_response = client.get("/workflow-definitions/")
    definition_id = list_def_response.json()[0]["id"]

    instance_data = {
        "definition_id": definition_id
    }
    create_inst_response = client.post("/workflow-instances/", data=instance_data)
    assert create_inst_response.status_code == 303
    instance_id = create_inst_response.headers['location'].split('/')[-1]

    # Act
    response = client.get(f"/workflow-instances/{instance_id}")

    # Assert
    assert response.status_code == 200
    assert "instance" in response.json()
    assert "tasks" in response.json()
    assert response.json()["instance"]["id"] == instance_id

@pytest.mark.asyncio
def test_get_workflow_instance_not_found(db_session):
    # Act
    response = client.get("/workflow-instances/nonexistent_id")

    # Assert
    assert response.status_code == 404  # Not found

@pytest.mark.asyncio
def test_complete_task(db_session):
    # Arrange: First create a definition and an instance with tasks
    definition_data = {
        "name": "Workflow for Task Completion",
        "description": "Workflow to test task completion",
        "task_names_str": "Task 1\nTask 2"
    }
    create_def_response = client.post("/workflow-definitions/create", data=definition_data)
    assert create_def_response.status_code == 303

    list_def_response = client.get("/workflow-definitions/")
    definition_id = list_def_response.json()[0]["id"]

    instance_data = {
        "definition_id": definition_id
    }
    create_inst_response = client.post("/workflow-instances/", data=instance_data)
    assert create_inst_response.status_code == 303
    instance_id = create_inst_response.headers['location'].split('/')[-1]

    # Get the tasks for the instance
    instance_response = client.get(f"/workflow-instances/{instance_id}")
    tasks = instance_response.json()["tasks"]
    task_id = tasks[0]["id"]

    # Act
    response = client.post(f"/task-instances/{task_id}/complete")

    # Assert
    assert response.status_code == 303  # Redirect after successful task completion
    assert response.headers['location'] == f"/workflow-instances/{instance_id}"

@pytest.mark.asyncio
def test_complete_task_not_found(db_session):
    # Act
    response = client.post("/task-instances/nonexistent_id/complete")

    # Assert
    assert response.status_code == 400  # Bad request due to task not found

@pytest.mark.asyncio
def test_list_user_workflows(db_session):
    # Arrange: Create a workflow instance for the user
    definition_data = {
        "name": "User Workflow",
        "description": "Workflow for user",
        "task_names_str": "Task 1"
    }
    create_def_response = client.post("/workflow-definitions/create", data=definition_data)
    assert create_def_response.status_code == 303

    list_def_response = client.get("/workflow-definitions/")
    definition_id = list_def_response.json()[0]["id"]

    instance_data = {
        "definition_id": definition_id
    }
    create_inst_response = client.post("/workflow-instances/", data=instance_data)
    assert create_inst_response.status_code == 303

    # Act
    response = client.get("/my-workflows")

    # Assert
    assert response.status_code == 200
    assert len(response.json()["instances"]) == 1
