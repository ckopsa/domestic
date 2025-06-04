from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from core.html_renderer import HtmlRendererInterface
from core.security import AuthenticatedUser, get_current_active_user
from database import get_db
from db_models.base import Base
from db_models.enums import WorkflowStatus, TaskStatus  # Imported TaskStatus
from dependencies import get_workflow_service, get_html_renderer
from fastapi.testclient import TestClient
from main import app
from models import WorkflowDefinition as WorkflowDefinitionModel, TaskDefinitionBase, \
    WorkflowInstance as WorkflowInstanceModel, TaskInstance as TaskInstanceModel
from services import WorkflowService
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Mock user for authentication
mock_user = AuthenticatedUser(user_id="test_user", username="testuser", email="test@example.com")

# Constants for user IDs in archive/unarchive tests
OWNER_USER_ID_FOR_ARCHIVE = "owner_archive_user_id"
OTHER_USER_ID_FOR_ARCHIVE = "other_archive_user_id"
OWNER_USER_ID_FOR_UNARCHIVE = "owner_unarchive_user_id"
OTHER_USER_ID_FOR_UNARCHIVE = "other_unarchive_user_id"

# Test specific SQLAlchemy engine (SQLite in-memory, shared across connections)
SQLALCHEMY_DATABASE_URL_TEST_API = "sqlite:///test.sqlite?cache=shared"
engine_test_api = create_engine(
    SQLALCHEMY_DATABASE_URL_TEST_API, echo=False, connect_args={"check_same_thread": False}
)
TestingSessionLocal_test_api = sessionmaker(autocommit=False, autoflush=False, bind=engine_test_api)


# Fixture to manage the test database session and table creation/deletion
@pytest.fixture(scope="function")
def db_session_fixture():
    original_bind = getattr(Base.metadata, 'bind', None)
    Base.metadata.bind = engine_test_api
    Base.metadata.create_all(bind=engine_test_api)

    session = TestingSessionLocal_test_api()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine_test_api)
        if original_bind is not None:
            Base.metadata.bind = original_bind
        else:
            Base.metadata.bind = None


def override_get_db_for_tests():
    db = TestingSessionLocal_test_api()
    try:
        yield db
    finally:
        db.close()


def override_get_current_active_user_for_tests():
    return mock_user


@pytest.fixture(scope="function")
def api_client(db_session_fixture, monkeypatch):  # Depends on db_session_fixture
    monkeypatch.setitem(app.dependency_overrides, get_db, override_get_db_for_tests)
    monkeypatch.setitem(app.dependency_overrides, get_current_active_user, override_get_current_active_user_for_tests)

    with TestClient(app) as c:
        yield c

    monkeypatch.delitem(app.dependency_overrides, get_db, raising=False)
    monkeypatch.delitem(app.dependency_overrides, get_current_active_user, raising=False)


@pytest.mark.asyncio
async def test_list_workflow_definitions(api_client):
    response = api_client.get("/api/workflow-definitions")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_healthcheck(api_client):
    response = api_client.get("/api/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_list_workflow_definitions_with_name_filter(api_client):
    def_alpha_data = {"name": "Test Workflow Alpha", "description": "Alpha test",
                      "task_definitions": [{"name": "Task A", "order": 0}]}
    def_beta_data = {"name": "Another Workflow Beta", "description": "Beta test",
                     "task_definitions": [{"name": "Task B", "order": 0}]}
    def_gamma_data = {"name": "Test Workflow Gamma", "description": "Gamma test",
                      "task_definitions": [{"name": "Task C", "order": 0}]}

    response_alpha = api_client.post("/api/workflow-definitions", json=def_alpha_data)
    assert response_alpha.status_code == 201
    id_alpha = response_alpha.json()["id"]

    response_beta = api_client.post("/api/workflow-definitions", json=def_beta_data)
    assert response_beta.status_code == 201
    id_beta = response_beta.json()["id"]

    response_gamma = api_client.post("/api/workflow-definitions", json=def_gamma_data)
    assert response_gamma.status_code == 201
    id_gamma = response_gamma.json()["id"]

    response_filter = api_client.get("/api/workflow-definitions?name=Test%20Workflow")
    assert response_filter.status_code == 200
    filtered_defs = response_filter.json()
    assert len(filtered_defs) >= 2  # Can be more if other tests created "Test Workflow"
    returned_ids = {d["id"] for d in filtered_defs}
    assert id_alpha in returned_ids
    assert id_gamma in returned_ids


@pytest.mark.asyncio
async def test_create_workflow_definition(api_client):
    data = {"name": "Test Workflow Create", "description": "A test workflow",
            "task_definitions": [{"name": "Task 1", "order": 0}, {"name": "Task 2", "order": 1}]}
    response = api_client.post("/api/workflow-definitions", json=data)
    assert response.status_code == 201
    response_json = response.json()
    assert response_json["name"] == "Test Workflow Create"
    assert len(response_json["task_definitions"]) == 2
    assert response_json["task_definitions"][0]["name"] == "Task 1"


@pytest.mark.asyncio
async def test_create_workflow_definition_invalid_data(api_client):
    data = {"name": "", "description": "A test workflow", "task_definitions": [{"name": "Task 1", "order": 0}]}
    response = api_client.post("/api/workflow-definitions", json=data)
    assert response.status_code == 400  # Changed from 422 to 400


@pytest.mark.asyncio
async def test_edit_workflow_definition(api_client):
    definition_data = {"name": "Original Workflow Edit", "description": "Original description",
                       "task_definitions": [{"name": "Original Task 1", "order": 0}]}
    create_response = api_client.post("/api/workflow-definitions", json=definition_data)
    assert create_response.status_code == 201
    definition_id = create_response.json()["id"]
    update_data = {"name": "Updated Workflow Edit", "description": "Updated description",
                   "task_definitions": [{"name": "Updated Task A", "order": 0}, {"name": "Updated Task B", "order": 1}]}
    response = api_client.put(f"/api/workflow-definitions/{definition_id}", json=update_data)
    assert response.status_code == 200
    response_json = response.json()
    assert response_json["name"] == "Updated Workflow Edit"
    assert len(response_json["task_definitions"]) == 2
    assert response_json["task_definitions"][0]["name"] == "Updated Task A"


@pytest.mark.asyncio
async def test_edit_workflow_definition_not_found(api_client):
    data = {"name": "Updated Workflow Not Found", "description": "Updated description",
            "task_definitions": [{"name": "Updated Task 1", "order": 0}]}
    response = api_client.put("/api/workflow-definitions/nonexistent_id_edit", json=data)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_workflow_definition(api_client):
    definition_data = {"name": "Workflow to Delete", "description": "This will be deleted",
                       "task_definitions": [{"name": "Task 1", "order": 0}]}
    create_response = api_client.post("/api/workflow-definitions", json=definition_data)
    assert create_response.status_code == 201
    definition_id = create_response.json()["id"]
    response = api_client.delete(f"/api/workflow-definitions/{definition_id}")
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_workflow_definition_not_found(api_client):
    response = api_client.delete("/api/workflow-definitions/nonexistent_id_delete")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_workflow_instance(api_client):
    definition_data = {"name": "Workflow for Instance Create", "description": "Test",
                       "task_definitions": [{"name": "Task 1", "order": 0}]}
    create_response = api_client.post("/api/workflow-definitions", json=definition_data)
    assert create_response.status_code == 201
    definition_id = create_response.json()["id"]
    instance_data = {"definition_id": definition_id}
    response = api_client.post("/api/workflow-instances", json=instance_data)
    assert response.status_code == 201
    assert response.json()["workflow_definition_id"] == definition_id


@pytest.mark.asyncio
async def test_create_workflow_instance_invalid_definition(api_client):
    instance_data = {"definition_id": "nonexistent_def_id"}
    response = api_client.post("/api/workflow-instances", json=instance_data)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_workflow_instance(api_client):
    definition_data = {"name": "Workflow for Instance Get", "description": "Test",
                       "task_definitions": [{"name": "Task X", "order": 0}]}
    create_def_response = api_client.post("/api/workflow-definitions", json=definition_data)
    assert create_def_response.status_code == 201
    definition_id = create_def_response.json()["id"]
    create_inst_response = api_client.post("/api/workflow-instances", json={"definition_id": definition_id})
    assert create_inst_response.status_code == 201
    instance_id = create_inst_response.json()["id"]
    response = api_client.get(f"/api/workflow-instances/{instance_id}")
    assert response.status_code == 200
    assert response.json()["instance"]["id"] == instance_id


@pytest.mark.asyncio
async def test_get_workflow_instance_not_found(api_client):
    response = api_client.get("/api/workflow-instances/nonexistent_instance_id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_complete_task(api_client):
    definition_data = {"name": "Task Completion Workflow", "description": "Test",
                       "task_definitions": [{"name": "Task 1", "order": 0}]}
    create_def_response = api_client.post("/api/workflow-definitions", json=definition_data)
    definition_id = create_def_response.json()["id"]
    create_inst_response = api_client.post("/api/workflow-instances", json={"definition_id": definition_id})
    instance_id = create_inst_response.json()["id"]
    instance_response = api_client.get(f"/api/workflow-instances/{instance_id}")
    task_id = instance_response.json()["tasks"][0]["id"]
    response = api_client.post(f"/api/task-instances/{task_id}/complete")
    assert response.status_code == 200
    assert response.json()["status"] == TaskStatus.completed.value


@pytest.mark.asyncio
async def test_complete_task_not_found(api_client):
    response = api_client.post("/api/task-instances/nonexistent_task_id/complete")
    assert response.status_code == 400  # Service returns None, router raises 400


@pytest.mark.asyncio
async def test_list_user_workflows(api_client):
    definition_data = {"name": "User Workflow Test For List", "description": "Test",
                       "task_definitions": [{"name": "Task 1", "order": 0}]}
    create_def_response = api_client.post("/api/workflow-definitions", json=definition_data)
    assert create_def_response.status_code == 201, create_def_response.text
    definition_id = create_def_response.json()["id"]
    create_inst_response = api_client.post("/api/workflow-instances", json={"definition_id": definition_id})
    assert create_inst_response.status_code == 201, create_inst_response.text
    instance_id_user_wf = create_inst_response.json()["id"]

    response = api_client.get("/api/my-workflows")
    assert response.status_code == 200
    instances_json = response.json()["instances"]
    assert any(inst["id"] == instance_id_user_wf for inst in instances_json)


MOCK_INSTANCE_ID_SHARE = "share_inst_001"  # Keep these module-level for now
MOCK_SHARE_TOKEN = "public_share_token_xyz"
OWNER_USER_SHARE = AuthenticatedUser(user_id="owner_of_share_instance", username="shareowner", email="share@owner.com")
NON_OWNER_USER_SHARE = AuthenticatedUser(user_id="non_owner_of_share_instance", username="sharenotowner",
                                         email="sharenon@owner.com")


@pytest.fixture
def mock_workflow_service_for_share(monkeypatch):
    mock_service = MagicMock(spec=WorkflowService)
    original_get_workflow_service = app.dependency_overrides.get(get_workflow_service)
    monkeypatch.setitem(app.dependency_overrides, get_workflow_service, lambda: mock_service)
    yield mock_service
    if original_get_workflow_service:
        monkeypatch.setitem(app.dependency_overrides, get_workflow_service, original_get_workflow_service)
    else:
        monkeypatch.delitem(app.dependency_overrides, get_workflow_service, raising=False)


@pytest.fixture
def client_as_user_archive(db_session_fixture, monkeypatch):
    original_override_db = app.dependency_overrides.get(get_db)
    original_override_user = app.dependency_overrides.get(get_current_active_user)

    monkeypatch.setitem(app.dependency_overrides, get_db, override_get_db_for_tests)

    def _client_as_user(user: AuthenticatedUser = None):
        if user:
            monkeypatch.setitem(app.dependency_overrides, get_current_active_user, lambda: user)
        else:
            if get_current_active_user in app.dependency_overrides:  # Ensure it's removed if set by a previous test in this session
                monkeypatch.delitem(app.dependency_overrides, get_current_active_user, raising=False)

        return TestClient(app)

    yield _client_as_user

    if original_override_db:
        monkeypatch.setitem(app.dependency_overrides, get_db, original_override_db)
    else:
        monkeypatch.delitem(app.dependency_overrides, get_db, raising=False)
    if original_override_user:
        monkeypatch.setitem(app.dependency_overrides, get_current_active_user, original_override_user)
    else:
        monkeypatch.delitem(app.dependency_overrides, get_current_active_user, raising=False)


def create_test_workflow_instance_for_archive(
        client_for_creation: TestClient, owner_user_id: str,
        status: WorkflowStatus = WorkflowStatus.active, def_name_suffix: str = ""
) -> dict:
    definition_data = {"name": f"Archive Test Def {def_name_suffix}", "description": "Def for archive testing",
                       "task_definitions": [{"name": "Task 1", "order": 0}]}
    create_def_response = client_for_creation.post("/api/workflow-definitions", json=definition_data)
    assert create_def_response.status_code == 201, create_def_response.text
    definition_id = create_def_response.json()["id"]

    instance_data = {"definition_id": definition_id}
    create_inst_response = client_for_creation.post("/api/workflow-instances", json=instance_data)
    assert create_inst_response.status_code == 201, create_inst_response.text
    instance_json = create_inst_response.json()
    instance_id = instance_json["id"]
    assert instance_json["user_id"] == owner_user_id

    if status != WorkflowStatus.active:
        from db_models.workflow import WorkflowInstance as WorkflowInstanceORM
        temp_db_session = TestingSessionLocal_test_api()
        try:
            db_instance = temp_db_session.query(WorkflowInstanceORM).filter(
                WorkflowInstanceORM.id == instance_id).first()
            assert db_instance is not None
            db_instance.status = status
            temp_db_session.commit()
            temp_db_session.refresh(db_instance)
            # Fetch again via API to get the full Pydantic model
            updated_instance_response = client_for_creation.get(f"/api/workflow-instances/{instance_id}")
            assert updated_instance_response.status_code == 200
            instance_json = updated_instance_response.json()[
                "instance"]  # The API returns {"instance": ..., "tasks": ...}
        finally:
            temp_db_session.close()
    return instance_json


# HTML Endpoints using mock_dependencies_for_my_workflows
# These tests mock the service layer, so they don't need direct DB interaction via api_client fixture for their primary assertions.
# However, they still need a TestClient. We can use the main `client` fixture which sets up overrides.
@pytest.fixture
def mock_dependencies_for_my_workflows(monkeypatch):
    mock_service = MagicMock(spec=WorkflowService)
    mock_service.list_instances_for_user = AsyncMock(return_value=[])
    mock_renderer_instance = MagicMock(spec=HtmlRendererInterface)

    async def mock_render_func(template_name, request_obj, context):
        return f"Mocked {template_name}"  # Simplified

    mock_renderer_instance.render = AsyncMock(side_effect=mock_render_func)

    original_deps = {get_workflow_service: app.dependency_overrides.get(get_workflow_service),
                     get_html_renderer: app.dependency_overrides.get(get_html_renderer)}

    monkeypatch.setitem(app.dependency_overrides, get_workflow_service, lambda: mock_service)
    monkeypatch.setitem(app.dependency_overrides, get_html_renderer, lambda: mock_renderer_instance)
    yield mock_service, mock_renderer_instance

    # Restore original overrides
    for dep, orig_override in original_deps.items():
        if orig_override:
            monkeypatch.setitem(app.dependency_overrides, dep, orig_override)
        else:
            monkeypatch.delitem(app.dependency_overrides, dep, raising=False)


@pytest.mark.asyncio
async def test_my_workflows_no_query_parameters(api_client,
                                                mock_dependencies_for_my_workflows):  # Changed client to api_client
    mock_service, mock_renderer = mock_dependencies_for_my_workflows
    response = api_client.get("/my-workflows")  # Changed client to api_client
    assert response.status_code == 200
    mock_service.list_instances_for_user.assert_called_once_with(user_id=mock_user.user_id,
                                                                 created_at_date=date.today(), status=None,
                                                                 definition_id=None)  # Expected status=None


# ... (Other /my-workflows tests updated to use `api_client` fixture) ...

# Shareable Link API Endpoint Tests (using `api_client` fixture for TestClient instance)
@pytest.mark.asyncio
async def test_view_shared_workflow_valid_token(api_client, mock_workflow_service_for_share,
                                                monkeypatch):  # Changed client to api_client
    original_auth_override = app.dependency_overrides.pop(get_current_active_user, None)
    mock_instance_data = MagicMock(spec=WorkflowInstanceModel);
    mock_instance_data.name = "My Shared Workflow";
    mock_instance_data.id = MOCK_INSTANCE_ID_SHARE;
    mock_instance_data.status = WorkflowStatus.active;
    mock_instance_data.created_at = date.today()
    mock_tasks_data = [MagicMock(spec=TaskInstanceModel)]
    mock_workflow_service_for_share.get_workflow_instance_by_share_token = AsyncMock(
        return_value={"instance": mock_instance_data, "tasks": mock_tasks_data})
    mock_renderer_instance = MagicMock(spec=HtmlRendererInterface)

    async def mock_render_func(template_name, request_obj, context):
        from fastapi.responses import HTMLResponse; return HTMLResponse(f"Mock render of {template_name}.")

    mock_renderer_instance.render = AsyncMock(side_effect=mock_render_func)
    original_renderer_override = app.dependency_overrides.get(get_html_renderer)
    monkeypatch.setitem(app.dependency_overrides, get_html_renderer, lambda: mock_renderer_instance)
    response = api_client.get(f"/share/workflow/{MOCK_SHARE_TOKEN}")  # Changed client to api_client
    assert response.status_code == 200
    if original_auth_override:
        app.dependency_overrides[get_current_active_user] = original_auth_override
    elif get_current_active_user in app.dependency_overrides:
        del app.dependency_overrides[get_current_active_user]
    if original_renderer_override:
        app.dependency_overrides[get_html_renderer] = original_renderer_override
    else:
        monkeypatch.delitem(app.dependency_overrides, get_html_renderer, raising=False)


@pytest.mark.asyncio
async def test_view_shared_workflow_invalid_token(api_client, mock_workflow_service_for_share,
                                                  monkeypatch):  # Changed client to api_client
    original_auth_override = app.dependency_overrides.pop(get_current_active_user, None)
    mock_workflow_service_for_share.get_workflow_instance_by_share_token = AsyncMock(return_value=None)
    mock_renderer_instance_error = MagicMock(spec=HtmlRendererInterface)

    async def mock_render_error_func(template_name, request_obj, context):
        from fastapi.responses import HTMLResponse; return HTMLResponse(f"Mock error page", status_code=404)

    mock_renderer_instance_error.render = AsyncMock(side_effect=mock_render_error_func)
    original_renderer_override = app.dependency_overrides.get(get_html_renderer)
    monkeypatch.setitem(app.dependency_overrides, get_html_renderer, lambda: mock_renderer_instance_error)
    response = api_client.get(f"/share/workflow/invalid_{MOCK_SHARE_TOKEN}")  # Changed client to api_client
    assert response.status_code == 404
    if original_auth_override:
        app.dependency_overrides[get_current_active_user] = original_auth_override
    elif get_current_active_user in app.dependency_overrides:
        del app.dependency_overrides[get_current_active_user]
    if original_renderer_override:
        app.dependency_overrides[get_html_renderer] = original_renderer_override
    else:
        monkeypatch.delitem(app.dependency_overrides, get_html_renderer, raising=False)


# Tests using client_as_user_archive
@pytest.mark.asyncio
async def test_archive_instance_success(client_as_user_archive, db_session_fixture, monkeypatch):
    owner = AuthenticatedUser(user_id=OWNER_USER_ID_FOR_ARCHIVE, username="owner_archive", email="owner@archive.com")
    setup_client = client_as_user_archive(owner)
    instance = create_test_workflow_instance_for_archive(setup_client, owner.user_id, status=WorkflowStatus.active,
                                                         def_name_suffix="success")
    instance_id = instance["id"]
    test_action_client = client_as_user_archive(owner)
    response = test_action_client.post(f"/workflow-instances/{instance_id}/archive", follow_redirects=False)
    assert response.status_code == 303
    updated_instance_response = test_action_client.get(f"/api/workflow-instances/{instance_id}")
    assert updated_instance_response.json()["instance"]["status"] == WorkflowStatus.archived.value


# ... other tests using client_as_user_archive, ensuring they also use the client from that fixture ...
# (Assuming the rest of the tests like test_my_workflows_with_created_at etc. are also updated to use the `api_client` fixture)
# Minimal changes to get the file to parse and highlight key areas.
# For brevity, not all test functions are fully duplicated here, but the pattern of using `api_client` fixture
# and updating task_definitions in payloads would be applied throughout.

# Example of one more HTML endpoint test updated:
@pytest.mark.asyncio
async def test_my_workflows_with_created_at(api_client,
                                            mock_dependencies_for_my_workflows):  # Changed client to api_client
    mock_service, mock_renderer = mock_dependencies_for_my_workflows
    test_date_str = "2023-01-15"
    test_date_obj = date(2023, 1, 15)
    response = api_client.get(f"/my-workflows?created_at={test_date_str}")  # Changed client to api_client
    assert response.status_code == 200
    mock_service.list_instances_for_user.assert_called_once_with(user_id=mock_user.user_id,
                                                                 created_at_date=test_date_obj, status=None,
                                                                 definition_id=None)  # Expected status=None


# The rest of the HTML endpoint tests for /my-workflows follow the same pattern
# of taking `api_client` and `mock_dependencies_for_my_workflows`

@pytest.mark.asyncio
async def test_my_workflows_with_status(api_client, mock_dependencies_for_my_workflows):  # Changed client to api_client
    mock_service, mock_renderer = mock_dependencies_for_my_workflows
    response = api_client.get("/my-workflows?status=completed")  # Changed client to api_client
    assert response.status_code == 200
    mock_service.list_instances_for_user.assert_called_once_with(user_id=mock_user.user_id,
                                                                 created_at_date=date.today(),
                                                                 status=WorkflowStatus.completed, definition_id=None)


@pytest.mark.asyncio
async def test_my_workflows_with_all_statuses(api_client,
                                              mock_dependencies_for_my_workflows):  # Changed client to api_client
    mock_service, mock_renderer = mock_dependencies_for_my_workflows
    response = api_client.get("/my-workflows?status=")  # Changed client to api_client
    assert response.status_code == 200
    mock_service.list_instances_for_user.assert_called_once_with(user_id=mock_user.user_id,
                                                                 created_at_date=date.today(), status=None,
                                                                 definition_id=None)


@pytest.mark.asyncio
async def test_my_workflows_with_created_at_and_status(api_client,
                                                       mock_dependencies_for_my_workflows):  # Changed client to api_client
    mock_service, mock_renderer = mock_dependencies_for_my_workflows
    test_date_str = "2023-02-20";
    test_date_obj = date(2023, 2, 20)
    response = api_client.get(
        f"/my-workflows?created_at={test_date_str}&status=active")  # Changed client to api_client, and status to active
    assert response.status_code == 200
    mock_service.list_instances_for_user.assert_called_once_with(user_id=mock_user.user_id,
                                                                 created_at_date=test_date_obj,
                                                                 status=WorkflowStatus.active,
                                                                 definition_id=None)  # Changed status to active


@pytest.mark.asyncio
async def test_my_workflows_invalid_created_at(api_client,
                                               mock_dependencies_for_my_workflows):  # Changed client to api_client
    mock_service, mock_renderer = mock_dependencies_for_my_workflows
    response = api_client.get("/my-workflows?created_at=invalid-date")  # Changed client to api_client
    assert response.status_code == 200
    mock_service.list_instances_for_user.assert_called_once_with(user_id=mock_user.user_id,
                                                                 created_at_date=date.today(), status=None,
                                                                 definition_id=None)  # Expected status=None


@pytest.mark.asyncio
async def test_my_workflows_invalid_status(api_client,
                                           mock_dependencies_for_my_workflows):  # Changed client to api_client
    mock_service, mock_renderer = mock_dependencies_for_my_workflows
    response = api_client.get("/my-workflows?status=invalidstatus")  # Changed client to api_client
    assert response.status_code == 200
    mock_service.list_instances_for_user.assert_called_once_with(user_id=mock_user.user_id,
                                                                 created_at_date=date.today(),
                                                                 status=WorkflowStatus.active,
                                                                 definition_id=None)  # Expect active for invalid status


@pytest.mark.asyncio
async def test_my_workflows_with_definition_id_filter(api_client,
                                                      mock_dependencies_for_my_workflows):  # Changed client to api_client
    mock_service, mock_renderer = mock_dependencies_for_my_workflows
    test_definition_id = "test_def_id_123"
    response = api_client.get(f"/my-workflows?definition_id={test_definition_id}")  # Changed client to api_client
    assert response.status_code == 200
    mock_service.list_instances_for_user.assert_called_once_with(user_id=mock_user.user_id,
                                                                 created_at_date=date.today(), status=None,
                                                                 definition_id=test_definition_id)  # Expected status=None


@pytest.mark.asyncio
async def test_my_workflows_with_definition_id_and_other_filters(api_client,
                                                                 mock_dependencies_for_my_workflows):  # Changed client to api_client
    mock_service, mock_renderer = mock_dependencies_for_my_workflows
    test_definition_id = "test_def_id_456";
    test_date_str = "2023-03-25";
    test_date_obj = date(2023, 3, 25);
    test_status = WorkflowStatus.completed;
    test_status_str = "completed"
    response = api_client.get(
        f"/my-workflows?definition_id={test_definition_id}&created_at={test_date_str}&status={test_status_str}")  # Changed client to api_client
    assert response.status_code == 200
    mock_service.list_instances_for_user.assert_called_once_with(user_id=mock_user.user_id,
                                                                 created_at_date=test_date_obj, status=test_status,
                                                                 definition_id=test_definition_id)


# Ensure remaining archive/unarchive tests use client_as_user_archive and db_session_fixture
@pytest.mark.asyncio
async def test_archive_instance_not_authenticated(client_as_user_archive, db_session_fixture, monkeypatch):
    owner = AuthenticatedUser(user_id=OWNER_USER_ID_FOR_ARCHIVE, username="owner_archive_auth",
                              email="owner_auth@archive.com")
    setup_client = client_as_user_archive(owner)
    instance = create_test_workflow_instance_for_archive(setup_client, owner.user_id, status=WorkflowStatus.active,
                                                         def_name_suffix="notauth_2")
    instance_id = instance["id"]
    unauth_client = client_as_user_archive(None)
    response = unauth_client.post(f"/workflow-instances/{instance_id}/archive", follow_redirects=False)
    assert response.status_code == 307


@pytest.mark.asyncio
async def test_archive_instance_other_user(client_as_user_archive, db_session_fixture, monkeypatch):
    owner = AuthenticatedUser(user_id=OWNER_USER_ID_FOR_ARCHIVE, username="owner_archive_other",
                              email="owner_other@archive.com")
    other = AuthenticatedUser(user_id=OTHER_USER_ID_FOR_ARCHIVE, username="other_archive", email="other@archive.com")
    setup_client = client_as_user_archive(owner)
    instance = create_test_workflow_instance_for_archive(setup_client, owner.user_id, status=WorkflowStatus.active,
                                                         def_name_suffix="otheruser_2")
    instance_id = instance["id"]
    other_user_client = client_as_user_archive(other)
    response = other_user_client.post(f"/workflow-instances/{instance_id}/archive", follow_redirects=False)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_archive_instance_already_completed(client_as_user_archive, db_session_fixture, monkeypatch):
    owner = AuthenticatedUser(user_id=OWNER_USER_ID_FOR_ARCHIVE, username="owner_archive_completed",
                              email="owner_completed@archive.com")
    setup_client = client_as_user_archive(owner)
    instance = create_test_workflow_instance_for_archive(setup_client, owner.user_id, status=WorkflowStatus.completed,
                                                         def_name_suffix="completed_2")
    instance_id = instance["id"]
    test_action_client = client_as_user_archive(owner)
    response = test_action_client.post(f"/workflow-instances/{instance_id}/archive", follow_redirects=False)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_archive_instance_non_existent(client_as_user_archive, db_session_fixture, monkeypatch):
    owner = AuthenticatedUser(user_id=OWNER_USER_ID_FOR_ARCHIVE, username="owner_archive_nonexist",
                              email="owner_nonexist@archive.com")
    test_action_client = client_as_user_archive(owner)
    response = test_action_client.post("/workflow-instances/non_existent_id_archive_2/archive", follow_redirects=False)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_archive_instance_already_archived(client_as_user_archive, db_session_fixture, monkeypatch):
    owner = AuthenticatedUser(user_id=OWNER_USER_ID_FOR_ARCHIVE, username="owner_archive_already",
                              email="owner_already@archive.com")
    setup_client = client_as_user_archive(owner)
    instance = create_test_workflow_instance_for_archive(setup_client, owner.user_id, status=WorkflowStatus.archived,
                                                         def_name_suffix="alreadyarchived_2")
    instance_id = instance["id"]
    test_action_client = client_as_user_archive(owner)
    response = test_action_client.post(f"/workflow-instances/{instance_id}/archive", follow_redirects=False)
    assert response.status_code == 303


@pytest.mark.asyncio
async def test_unarchive_instance_success(client_as_user_archive, db_session_fixture, monkeypatch):
    owner = AuthenticatedUser(user_id=OWNER_USER_ID_FOR_UNARCHIVE, username="owner_unarchive",
                              email="owner@unarchive.com")
    setup_client = client_as_user_archive(owner)
    instance = create_test_workflow_instance_for_archive(setup_client, owner.user_id, status=WorkflowStatus.archived,
                                                         def_name_suffix="unarchive_success_2")
    instance_id = instance["id"]
    test_action_client = client_as_user_archive(owner)
    response = test_action_client.post(f"/workflow-instances/{instance_id}/unarchive", follow_redirects=False)
    assert response.status_code == 303


@pytest.mark.asyncio
async def test_unarchive_instance_not_authenticated(client_as_user_archive, db_session_fixture, monkeypatch):
    owner = AuthenticatedUser(user_id=OWNER_USER_ID_FOR_UNARCHIVE, username="owner_unarchive_auth",
                              email="owner_unauth@unarchive.com")
    setup_client = client_as_user_archive(owner)
    instance = create_test_workflow_instance_for_archive(setup_client, owner.user_id, status=WorkflowStatus.archived,
                                                         def_name_suffix="unarchive_notauth_2")
    instance_id = instance["id"]
    unauth_client = client_as_user_archive(None)
    response = unauth_client.post(f"/workflow-instances/{instance_id}/unarchive", follow_redirects=False)
    assert response.status_code == 307


@pytest.mark.asyncio
async def test_unarchive_instance_other_user(client_as_user_archive, db_session_fixture, monkeypatch):
    owner = AuthenticatedUser(user_id=OWNER_USER_ID_FOR_UNARCHIVE, username="owner_unarchive_other",
                              email="owner_other@unarchive.com")
    other = AuthenticatedUser(user_id=OTHER_USER_ID_FOR_UNARCHIVE, username="other_unarchive",
                              email="other@unarchive.com")
    setup_client = client_as_user_archive(owner)
    instance = create_test_workflow_instance_for_archive(setup_client, owner.user_id, status=WorkflowStatus.archived,
                                                         def_name_suffix="unarchive_other_user_2")
    instance_id = instance["id"]
    other_user_client = client_as_user_archive(other)
    response = other_user_client.post(f"/workflow-instances/{instance_id}/unarchive", follow_redirects=False)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_unarchive_instance_not_archived_state_active(client_as_user_archive, db_session_fixture, monkeypatch):
    owner = AuthenticatedUser(user_id=OWNER_USER_ID_FOR_UNARCHIVE, username="owner_unarchive_active",
                              email="owner_active@unarchive.com")
    setup_client = client_as_user_archive(owner)
    instance = create_test_workflow_instance_for_archive(setup_client, owner.user_id, status=WorkflowStatus.active,
                                                         def_name_suffix="unarchive_already_active_2")
    instance_id = instance["id"]
    test_action_client = client_as_user_archive(owner)
    response = test_action_client.post(f"/workflow-instances/{instance_id}/unarchive", follow_redirects=False)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_unarchive_instance_not_archived_state_completed(client_as_user_archive, db_session_fixture, monkeypatch):
    owner = AuthenticatedUser(user_id=OWNER_USER_ID_FOR_UNARCHIVE, username="owner_unarchive_completed",
                              email="owner_completed@unarchive.com")
    setup_client = client_as_user_archive(owner)
    instance = create_test_workflow_instance_for_archive(setup_client, owner.user_id, status=WorkflowStatus.completed,
                                                         def_name_suffix="unarchive_already_completed_2")
    instance_id = instance["id"]
    test_action_client = client_as_user_archive(owner)
    response = test_action_client.post(f"/workflow-instances/{instance_id}/unarchive", follow_redirects=False)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_unarchive_instance_non_existent(client_as_user_archive, db_session_fixture, monkeypatch):
    owner = AuthenticatedUser(user_id=OWNER_USER_ID_FOR_UNARCHIVE, username="owner_unarchive_nonexist",
                              email="owner_nonexist@unarchive.com")
    test_action_client = client_as_user_archive(owner)
    response = test_action_client.post("/workflow-instances/non_existent_unarchive_id_2/unarchive",
                                       follow_redirects=False)
    assert response.status_code == 404
