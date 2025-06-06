from unittest.mock import AsyncMock, MagicMock

import pytest
from db_models import Base
from models import WorkflowDefinition, WorkflowInstance, TaskInstance, TaskDefinitionBase, WorkflowStatus, TaskStatus
from services import WorkflowService
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from repository import DefinitionNotFoundError, DefinitionInUseError, WorkflowDefinitionRepository, \
    WorkflowInstanceRepository, TaskInstanceRepository

# Added for new tests
from datetime import datetime, timedelta # Existing file has DateObject, this adds datetime, timedelta
from typing import Optional # Existing file uses Optional implicitly, adding explicit import

SQLALCHEMY_DATABASE_URL_SVC_TEST = "sqlite:///./test_services_db.db" # Unique name for this test file's DB
engine_svc_test = create_engine(SQLALCHEMY_DATABASE_URL_SVC_TEST, connect_args={"check_same_thread": False})
TestingSessionLocal_svc_test = sessionmaker(autocommit=False, autoflush=False, bind=engine_svc_test)

@pytest.fixture(scope="module")
def db_session_svc():
    Base.metadata.create_all(bind=engine_svc_test)
    session = TestingSessionLocal_svc_test()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine_svc_test)

@pytest.fixture
def mock_repositories():
    definition_repo = MagicMock(spec=WorkflowDefinitionRepository)
    instance_repo = MagicMock(spec=WorkflowInstanceRepository)
    task_repo = MagicMock(spec=TaskInstanceRepository)
    return definition_repo, instance_repo, task_repo

@pytest.fixture
def workflow_service_existing(mock_repositories): # Renamed to avoid conflict if needed, though pytest uses specific fixture names
    definition_repo, instance_repo, task_repo = mock_repositories
    return WorkflowService(definition_repo, instance_repo, task_repo)

@pytest.mark.asyncio
async def test_create_workflow_instance_success(workflow_service_existing, mock_repositories): # Uses renamed fixture
    definition_repo, instance_repo, task_repo = mock_repositories
    definition = WorkflowDefinition(
        id="test_def_1", name="Test Workflow", description="A test workflow definition",
        task_definitions=[TaskDefinitionBase(name="Task 1", order=0), TaskDefinitionBase(name="Task 2", order=1)]
    )
    definition_repo.get_workflow_definition_by_id = AsyncMock(return_value=definition)
    instance = WorkflowInstance(
        id="test_inst_1", workflow_definition_id="test_def_1", name="Test Workflow",
        user_id="test_user", status=WorkflowStatus.active
    )
    instance_repo.create_workflow_instance = AsyncMock(return_value=instance)
    task_repo.create_task_instance = AsyncMock(side_effect=lambda task: task)

    # Construct WorkflowInstance model for the service call
    input_instance_data = WorkflowInstance(
        workflow_definition_id="test_def_1",
        user_id="test_user",
        name="Test Workflow" # Provide a name, or service will use definition name
    )
    result = await workflow_service_existing.create_workflow_instance(input_instance_data)
    assert result is not None
    assert result.id == "test_inst_1"
    assert task_repo.create_task_instance.call_count == 2

@pytest.mark.asyncio
async def test_create_new_definition_success(workflow_service_existing, mock_repositories): # Uses renamed fixture
    definition_repo, _, _ = mock_repositories
    task_defs_input = [TaskDefinitionBase(name="Task 1", order=0), TaskDefinitionBase(name="Task 2", order=1)]
    expected_pydantic_definition_arg = WorkflowDefinition(
        name="Test Workflow", description="A test workflow", task_definitions=task_defs_input
    )
    returned_definition_from_repo = expected_pydantic_definition_arg.model_copy(update={"id": "test_def_1"})
    definition_repo.create_workflow_definition = AsyncMock(return_value=returned_definition_from_repo)

    result = await workflow_service_existing.create_new_definition( # Uses renamed fixture
        name="Test Workflow", description="A test workflow",
        task_definitions=task_defs_input
    )
    assert result is not None
    assert result.name == "Test Workflow"
    assert result.id == "test_def_1"
    assert len(result.task_definitions) == 2
    definition_repo.create_workflow_definition.assert_called_once()
    called_with_arg = definition_repo.create_workflow_definition.call_args[0][0]
    assert called_with_arg.task_definitions == task_defs_input

@pytest.mark.asyncio
async def test_create_new_definition_empty_name(workflow_service_existing, mock_repositories): # Uses renamed fixture
    with pytest.raises(ValueError, match="Definition name cannot be empty."):
        await workflow_service_existing.create_new_definition( # Uses renamed fixture
            name="", description="A test workflow",
            task_definitions=[TaskDefinitionBase(name="Task 1", order=0)]
        )

@pytest.mark.asyncio
async def test_create_new_definition_empty_task_list(workflow_service_existing, mock_repositories): # Uses renamed fixture
    with pytest.raises(ValueError, match="A definition must have at least one task."):
        await workflow_service_existing.create_new_definition( # Uses renamed fixture
            name="Test Workflow", description="A test workflow",
            task_definitions=[]
        )

@pytest.mark.asyncio
async def test_update_definition_success(workflow_service_existing, mock_repositories): # Uses renamed fixture
    definition_repo, _, _ = mock_repositories
    task_defs_input = [TaskDefinitionBase(name="Updated Task 1", order=0)]
    expected_returned_definition = WorkflowDefinition(
        id="test_def_1", name="Updated Workflow", description="Updated description",
        task_definitions=task_defs_input
    )
    definition_repo.update_workflow_definition = AsyncMock(return_value=expected_returned_definition)

    result = await workflow_service_existing.update_definition( # Uses renamed fixture
        definition_id="test_def_1", name="Updated Workflow", description="Updated description",
        task_definitions=task_defs_input
    )
    assert result is not None
    assert result.name == "Updated Workflow"
    definition_repo.update_workflow_definition.assert_called_once_with(
        "test_def_1", "Updated Workflow", "Updated description", task_defs_input
    )

@pytest.mark.asyncio
async def test_update_definition_empty_name(workflow_service_existing, mock_repositories): # Uses renamed fixture
    with pytest.raises(ValueError, match="Definition name cannot be empty."):
        await workflow_service_existing.update_definition( # Uses renamed fixture
            definition_id="test_def_1", name="", description="Updated description",
            task_definitions=[TaskDefinitionBase(name="Updated Task 1", order=0)]
        )

@pytest.mark.asyncio
async def test_update_definition_empty_task_list(workflow_service_existing, mock_repositories): # Uses renamed fixture
    with pytest.raises(ValueError, match="A definition must have at least one task."):
        await workflow_service_existing.update_definition( # Uses renamed fixture
            definition_id="test_def_1", name="Updated Workflow", description="Updated description",
            task_definitions=[]
        )

@pytest.mark.asyncio
async def test_create_workflow_instance_definition_not_found(workflow_service_existing, mock_repositories): # Uses renamed fixture
    definition_repo, _, _ = mock_repositories
    definition_repo.get_workflow_definition_by_id = AsyncMock(return_value=None)
    input_instance_data = WorkflowInstance(
        workflow_definition_id="test_def_1",
        user_id="test_user",
        name="Test WF if Def Not Found" # Name is needed for WorkflowInstance model
    )
    result = await workflow_service_existing.create_workflow_instance(input_instance_data) # Uses renamed fixture
    assert result is None

@pytest.mark.asyncio
async def test_complete_task_success(workflow_service_existing, mock_repositories): # Uses renamed fixture
    _, instance_repo, task_repo = mock_repositories
    task = TaskInstance(id="test_task_1", workflow_instance_id="test_inst_1", name="Test Task", order=0, status=TaskStatus.pending)
    instance = WorkflowInstance(id="test_inst_1", workflow_definition_id="test_def_1", name="Test Workflow", user_id="test_user", status=WorkflowStatus.active)
    # tasks_in_db = [task, TaskInstance(id="test_task_2", workflow_instance_id="test_inst_1", name="Test Task 2", order=1, status=TaskStatus.pending)] # Original, unused
    task_repo.get_task_instance_by_id = AsyncMock(return_value=task)
    instance_repo.get_workflow_instance_by_id = AsyncMock(return_value=instance)
    async def update_task_side_effect(task_id, task_data_pydantic): task_data_pydantic.status = TaskStatus.completed; return task_data_pydantic
    task_repo.update_task_instance = AsyncMock(side_effect=update_task_side_effect)
    tasks_after_completion = [TaskInstance(id="test_task_1", workflow_instance_id="test_inst_1", name="Test Task", order=0, status=TaskStatus.completed), TaskInstance(id="test_task_2", workflow_instance_id="test_inst_1", name="Test Task 2", order=1, status=TaskStatus.pending)]
    task_repo.get_tasks_for_workflow_instance = AsyncMock(return_value=tasks_after_completion) # Used by service.get_workflow_instance_with_tasks
    instance_repo.update_workflow_instance = AsyncMock(return_value=instance)
    result = await workflow_service_existing.complete_task("test_task_1", user_id="test_user") # Uses renamed fixture
    assert result is not None; assert result.status == TaskStatus.completed
    # Original assertion was instance_repo.update_workflow_instance.assert_not_called()
    # This depends on whether all tasks are completed or not.
    # If tasks_after_completion implies not all tasks are done, then this is correct.
    # Assuming 'tasks_after_completion' has one pending, so workflow status not updated.
    instance_repo.update_workflow_instance.assert_not_called()


@pytest.mark.asyncio
async def test_complete_task_all_tasks_completed(workflow_service_existing, mock_repositories): # Uses renamed fixture
    _, instance_repo, task_repo = mock_repositories
    task_to_complete = TaskInstance(id="test_task_1", workflow_instance_id="test_inst_1", name="Test Task", order=0, status=TaskStatus.pending)
    instance = WorkflowInstance(id="test_inst_1", workflow_definition_id="test_def_1", name="Test Workflow", user_id="test_user", status=WorkflowStatus.active)
    task_repo.get_task_instance_by_id = AsyncMock(return_value=task_to_complete)
    instance_repo.get_workflow_instance_by_id = AsyncMock(return_value=instance)
    updated_task_mock = task_to_complete.model_copy(update={"status": TaskStatus.completed})
    task_repo.update_task_instance = AsyncMock(return_value=updated_task_mock)
    task_repo.get_tasks_for_workflow_instance = AsyncMock(return_value=[updated_task_mock]) # Only one task, now completed
    async def update_instance_side_effect(instance_id, instance_data_pydantic): instance_data_pydantic.status = WorkflowStatus.completed; return instance_data_pydantic
    instance_repo.update_workflow_instance = AsyncMock(side_effect=update_instance_side_effect)
    result = await workflow_service_existing.complete_task("test_task_1", user_id="test_user") # Uses renamed fixture
    assert result is not None; assert result.status == TaskStatus.completed
    instance_repo.update_workflow_instance.assert_called_once()
    assert instance_repo.update_workflow_instance.call_args[0][1].status == WorkflowStatus.completed

@pytest.mark.asyncio
async def test_complete_task_already_completed(workflow_service_existing, mock_repositories): # Uses renamed fixture
    _, _, task_repo = mock_repositories
    task = TaskInstance(id="test_task_1", workflow_instance_id="test_inst_1", name="Test Task", order=0, status=TaskStatus.completed)
    task_repo.get_task_instance_by_id = AsyncMock(return_value=task)
    result = await workflow_service_existing.complete_task("test_task_1", user_id="test_user") # Uses renamed fixture
    assert result is None

@pytest.mark.asyncio
async def test_complete_task_unauthorized_user(workflow_service_existing, mock_repositories): # Uses renamed fixture
    _, instance_repo, task_repo = mock_repositories
    task = TaskInstance(id="test_task_1", workflow_instance_id="test_inst_1", name="Test Task", order=0, status=TaskStatus.pending)
    instance = WorkflowInstance(id="test_inst_1", workflow_definition_id="test_def_1", name="Test Workflow", user_id="different_user", status=WorkflowStatus.active)
    task_repo.get_task_instance_by_id = AsyncMock(return_value=task)
    instance_repo.get_workflow_instance_by_id = AsyncMock(return_value=instance)
    result = await workflow_service_existing.complete_task("test_task_1", user_id="test_user") # Uses renamed fixture
    assert result is None

@pytest.mark.asyncio
async def test_delete_definition_success(workflow_service_existing, mock_repositories): # Uses renamed fixture
    definition_repo, _, _ = mock_repositories
    definition_repo.delete_workflow_definition = AsyncMock(return_value=None)
    await workflow_service_existing.delete_definition("test_def_1") # Uses renamed fixture
    definition_repo.delete_workflow_definition.assert_called_once_with("test_def_1")

@pytest.mark.asyncio
async def test_delete_definition_not_found(workflow_service_existing, mock_repositories): # Uses renamed fixture
    definition_repo, _, _ = mock_repositories
    definition_repo.delete_workflow_definition = AsyncMock(side_effect=DefinitionNotFoundError("Definition not found"))
    with pytest.raises(ValueError, match="Definition not found"):
        await workflow_service_existing.delete_definition("test_def_1") # Uses renamed fixture

@pytest.mark.asyncio
async def test_delete_definition_in_use(workflow_service_existing, mock_repositories): # Uses renamed fixture
    definition_repo, _, _ = mock_repositories
    definition_repo.delete_workflow_definition = AsyncMock(side_effect=DefinitionInUseError("Definition in use"))
    with pytest.raises(ValueError, match="Definition in use"):
        await workflow_service_existing.delete_definition("test_def_1") # Uses renamed fixture

@pytest.mark.asyncio
async def test_get_workflow_instance_with_tasks_success(workflow_service_existing, mock_repositories): # Uses renamed fixture
    _, instance_repo, task_repo = mock_repositories
    instance = WorkflowInstance(id="test_inst_1", workflow_definition_id="test_def_1", name="Test Workflow", user_id="test_user", status=WorkflowStatus.active)
    tasks = [TaskInstance(id="test_task_1", workflow_instance_id="test_inst_1", name="Test Task 1", order=0, status=TaskStatus.pending)]
    instance_repo.get_workflow_instance_by_id = AsyncMock(return_value=instance)
    task_repo.get_tasks_for_workflow_instance = AsyncMock(return_value=tasks)
    result = await workflow_service_existing.get_workflow_instance_with_tasks("test_inst_1", user_id="test_user") # Uses renamed fixture
    assert result is not None; assert result["instance"] == instance; assert result["tasks"] == tasks

@pytest.mark.asyncio
async def test_get_workflow_instance_with_tasks_unauthorized(workflow_service_existing, mock_repositories): # Uses renamed fixture
    _, instance_repo, _ = mock_repositories
    instance = WorkflowInstance(id="test_inst_1", workflow_definition_id="test_def_1", name="Test Workflow", user_id="different_user", status=WorkflowStatus.active)
    instance_repo.get_workflow_instance_by_id = AsyncMock(return_value=instance)
    result = await workflow_service_existing.get_workflow_instance_with_tasks("test_inst_1", user_id="test_user") # Uses renamed fixture
    assert result is None

@pytest.mark.asyncio
async def test_list_instances_for_user(workflow_service_existing, mock_repositories): # Uses renamed fixture
    _, instance_repo, _ = mock_repositories
    instances = [WorkflowInstance(id="test_inst_1", workflow_definition_id="test_def_1", name="Test Workflow 1", user_id="test_user", status=WorkflowStatus.active)]
    instance_repo.list_workflow_instances_by_user = AsyncMock(return_value=instances)
    result = await workflow_service_existing.list_instances_for_user("test_user") # Uses renamed fixture
    assert len(result) == 1
    instance_repo.list_workflow_instances_by_user.assert_called_once_with("test_user", created_at_date=None, status=None, definition_id=None)

from datetime import date as DateObject # Already in existing code, but ensure it's available for constants below if needed by them.
LIST_USER_ID = "list_test_user"
USER_ID = "test_user_123" # Note: this USER_ID is defined in existing tests as well.
# OTHER_USER_ID = "other_user_456" # Defined in existing
WF_INSTANCE_ID = "wf_inst_abc" # Defined in existing
TASK_ID_1 = "task_def_123" # Defined in existing
ARCHIVE_USER_ID = "archive_user" # Defined in existing
ARCHIVE_INSTANCE_ID = "archive_instance_id" # Defined in existing
# OTHER_USER_ID_ARCHIVE = "other_archive_user" # Defined in existing
UNARCHIVE_USER_ID = "unarchive_user" # Defined in existing
UNARCHIVE_INSTANCE_ID = "unarchive_instance_id" # Defined in existing
# OTHER_USER_ID_UNARCHIVE = "other_unarchive_user" # Defined in existing
SHARE_USER_ID = "share_user_1" # Defined in existing
SHARE_INSTANCE_ID = "share_instance_1" # Defined in existing
SHARE_TOKEN = "test_share_token_123" # Defined in existing

@pytest.mark.asyncio
async def test_list_instances_for_user_passthrough_no_filters(workflow_service_existing, mock_repositories): # Uses renamed fixture
    _, instance_repo, _ = mock_repositories; expected_result = [MagicMock(spec=WorkflowInstance)]; instance_repo.list_workflow_instances_by_user = AsyncMock(return_value=expected_result); user_id = "test_user_no_filters"
    await workflow_service_existing.list_instances_for_user(user_id=user_id) # Uses renamed fixture
    result = await workflow_service_existing.list_instances_for_user(user_id=user_id, created_at_date=None, status=None, definition_id=None) # Uses renamed fixture
    instance_repo.list_workflow_instances_by_user.assert_called_with(user_id, created_at_date=None, status=None, definition_id=None)
    assert result == expected_result

@pytest.mark.asyncio
async def test_list_instances_for_user_passthrough_with_date(workflow_service_existing, mock_repositories): # Uses renamed fixture
    _, instance_repo, _ = mock_repositories; expected_result = [MagicMock(spec=WorkflowInstance)]; instance_repo.list_workflow_instances_by_user = AsyncMock(return_value=expected_result); user_id = "test_user_date_filter"; test_date = DateObject(2023, 1, 15)
    result = await workflow_service_existing.list_instances_for_user(user_id=user_id, created_at_date=test_date, definition_id=None) # Uses renamed fixture
    instance_repo.list_workflow_instances_by_user.assert_called_once_with(user_id, created_at_date=test_date, status=None, definition_id=None); assert result == expected_result

@pytest.mark.asyncio
async def test_list_instances_for_user_passthrough_with_status(workflow_service_existing, mock_repositories): # Uses renamed fixture
    _, instance_repo, _ = mock_repositories; expected_result = [MagicMock(spec=WorkflowInstance)]; instance_repo.list_workflow_instances_by_user = AsyncMock(return_value=expected_result); user_id = "test_user_status_filter"; test_status = WorkflowStatus.active
    result = await workflow_service_existing.list_instances_for_user(user_id=user_id, status=test_status, definition_id=None) # Uses renamed fixture
    instance_repo.list_workflow_instances_by_user.assert_called_once_with(user_id, created_at_date=None, status=test_status, definition_id=None); assert result == expected_result

@pytest.mark.asyncio
async def test_list_instances_for_user_passthrough_with_all_filters(workflow_service_existing, mock_repositories): # Uses renamed fixture
    _, instance_repo, _ = mock_repositories; expected_result = [MagicMock(spec=WorkflowInstance)]; instance_repo.list_workflow_instances_by_user = AsyncMock(return_value=expected_result); user_id = "test_user_all_filters"; test_date = DateObject(2023, 3, 20); test_status = WorkflowStatus.completed
    result = await workflow_service_existing.list_instances_for_user(user_id=user_id, created_at_date=test_date, status=test_status, definition_id=None) # Uses renamed fixture
    instance_repo.list_workflow_instances_by_user.assert_called_once_with(user_id, created_at_date=test_date, status=test_status, definition_id=None); assert result == expected_result

@pytest.mark.asyncio
async def test_list_instances_for_user_passthrough_with_definition_id(workflow_service_existing, mock_repositories): # Uses renamed fixture
    _, instance_repo, _ = mock_repositories; expected_result = [MagicMock(spec=WorkflowInstance)]; instance_repo.list_workflow_instances_by_user = AsyncMock(return_value=expected_result); user_id = "test_user_def_id_filter"; test_definition_id = "def_filter_services_test"
    result = await workflow_service_existing.list_instances_for_user(user_id=user_id, definition_id=test_definition_id) # Uses renamed fixture
    instance_repo.list_workflow_instances_by_user.assert_called_once_with(user_id, created_at_date=None, status=None, definition_id=test_definition_id); assert result == expected_result

@pytest.mark.asyncio
async def test_list_instances_for_user_passthrough_with_all_filters_including_definition_id(workflow_service_existing, mock_repositories): # Uses renamed fixture
    _, instance_repo, _ = mock_repositories; expected_result = [MagicMock(spec=WorkflowInstance)]; instance_repo.list_workflow_instances_by_user = AsyncMock(return_value=expected_result); user_id = "test_user_all_filters_def_id"; test_date = DateObject(2023, 4, 25); test_status = WorkflowStatus.active; test_definition_id = "def_filter_services_test_all"
    result = await workflow_service_existing.list_instances_for_user(user_id=user_id, created_at_date=test_date, status=test_status, definition_id=test_definition_id) # Uses renamed fixture
    instance_repo.list_workflow_instances_by_user.assert_called_once_with(user_id, created_at_date=test_date, status=test_status, definition_id=test_definition_id); assert result == expected_result

@pytest.mark.asyncio
async def test_list_instances_for_user_filters_archived_status(workflow_service_existing, mock_repositories): # Uses renamed fixture
    _, instance_repo, _ = mock_repositories; archived_instance_mock = WorkflowInstance(id="inst_archived_1", user_id=LIST_USER_ID, status=WorkflowStatus.archived, name="Archived Wf", workflow_definition_id="def_1"); instance_repo.list_workflow_instances_by_user = AsyncMock(return_value=[archived_instance_mock])
    result = await workflow_service_existing.list_instances_for_user(user_id=LIST_USER_ID, status=WorkflowStatus.archived, definition_id=None) # Uses renamed fixture
    assert len(result) == 1; instance_repo.list_workflow_instances_by_user.assert_called_once_with(LIST_USER_ID, created_at_date=None, status=WorkflowStatus.archived, definition_id=None)

@pytest.mark.asyncio
async def test_list_instances_for_user_active_status_excludes_archived(workflow_service_existing, mock_repositories): # Uses renamed fixture
    _, instance_repo, _ = mock_repositories; active_instance_mock = WorkflowInstance(id="inst_active_1", user_id=LIST_USER_ID, status=WorkflowStatus.active, name="Active Wf", workflow_definition_id="def_2"); instance_repo.list_workflow_instances_by_user = AsyncMock(return_value=[active_instance_mock])
    result = await workflow_service_existing.list_instances_for_user(user_id=LIST_USER_ID, status=WorkflowStatus.active, definition_id=None) # Uses renamed fixture
    assert len(result) == 1; instance_repo.list_workflow_instances_by_user.assert_called_once_with(LIST_USER_ID, created_at_date=None, status=WorkflowStatus.active, definition_id=None)

@pytest.mark.asyncio
async def test_list_instances_for_user_no_status_filter_passes_none_to_repo(workflow_service_existing, mock_repositories): # Uses renamed fixture
    _, instance_repo, _ = mock_repositories; mixed_instances = [MagicMock(spec=WorkflowInstance)]; instance_repo.list_workflow_instances_by_user = AsyncMock(return_value=mixed_instances)
    result = await workflow_service_existing.list_instances_for_user(user_id=LIST_USER_ID, status=None, definition_id=None) # Uses renamed fixture
    instance_repo.list_workflow_instances_by_user.assert_called_once_with(LIST_USER_ID, created_at_date=None, status=None, definition_id=None); assert result == mixed_instances

@pytest.mark.asyncio
async def test_undo_complete_task_success_workflow_becomes_active(workflow_service_existing, mock_repositories): # Uses renamed fixture
    _, instance_repo, task_repo = mock_repositories; completed_task = TaskInstance(id=TASK_ID_1, workflow_instance_id=WF_INSTANCE_ID, name="Test Task 1", order=0, status=TaskStatus.completed); workflow_instance = WorkflowInstance(id=WF_INSTANCE_ID, workflow_definition_id="def_id_1", name="Test Workflow", user_id=USER_ID, status=WorkflowStatus.completed); task_repo.get_task_instance_by_id = AsyncMock(return_value=completed_task); instance_repo.get_workflow_instance_by_id = AsyncMock(return_value=workflow_instance)
    async def update_task_side_effect(task_id, task_data): completed_task.status = task_data.status; return completed_task
    async def update_workflow_side_effect(wf_id, wf_data): workflow_instance.status = wf_data.status; return workflow_instance
    task_repo.update_task_instance = AsyncMock(side_effect=update_task_side_effect); instance_repo.update_workflow_instance = AsyncMock(side_effect=update_workflow_side_effect)
    result = await workflow_service_existing.undo_complete_task(TASK_ID_1, USER_ID) # Uses renamed fixture
    assert result.status == TaskStatus.pending; instance_repo.update_workflow_instance.assert_called_once(); assert instance_repo.update_workflow_instance.call_args[0][1].status == WorkflowStatus.active

@pytest.mark.asyncio
async def test_undo_complete_task_workflow_remains_active(workflow_service_existing, mock_repositories): # Uses renamed fixture
    _, instance_repo, task_repo = mock_repositories; completed_task_to_undo = TaskInstance(id=TASK_ID_1, workflow_instance_id=WF_INSTANCE_ID, name="Test Task 1", order=0, status=TaskStatus.completed); workflow_instance = WorkflowInstance(id=WF_INSTANCE_ID, workflow_definition_id="def_id_1", name="Test Workflow", user_id=USER_ID, status=WorkflowStatus.active); task_repo.get_task_instance_by_id = AsyncMock(return_value=completed_task_to_undo); instance_repo.get_workflow_instance_by_id = AsyncMock(return_value=workflow_instance)
    async def update_task_side_effect(task_id, task_data): completed_task_to_undo.status = task_data.status; return completed_task_to_undo
    task_repo.update_task_instance = AsyncMock(side_effect=update_task_side_effect)
    result = await workflow_service_existing.undo_complete_task(TASK_ID_1, USER_ID) # Uses renamed fixture
    assert result.status == TaskStatus.pending; instance_repo.update_workflow_instance.assert_not_called()

@pytest.mark.asyncio
async def test_archive_workflow_instance_success(workflow_service_existing, mock_repositories): # Uses renamed fixture
    _, instance_repo, _ = mock_repositories; active_instance = WorkflowInstance(id=ARCHIVE_INSTANCE_ID, user_id=ARCHIVE_USER_ID, status=WorkflowStatus.active, name="Test Archive", workflow_definition_id="def_archive"); instance_repo.get_workflow_instance_by_id = AsyncMock(return_value=active_instance)
    async def mock_update_instance(instance_id, instance_data): return instance_data
    instance_repo.update_workflow_instance = AsyncMock(side_effect=mock_update_instance)
    result = await workflow_service_existing.archive_workflow_instance(ARCHIVE_INSTANCE_ID, ARCHIVE_USER_ID) # Uses renamed fixture
    assert result.status == WorkflowStatus.archived

@pytest.mark.asyncio
async def test_unarchive_workflow_instance_success(workflow_service_existing, mock_repositories): # Uses renamed fixture
    _, instance_repo, _ = mock_repositories; archived_instance = WorkflowInstance(id=UNARCHIVE_INSTANCE_ID, user_id=UNARCHIVE_USER_ID, status=WorkflowStatus.archived, name="Test Unarchive Success", workflow_definition_id="def_unarchive_succ"); instance_repo.get_workflow_instance_by_id = AsyncMock(return_value=archived_instance)
    async def mock_update_instance(instance_id, instance_data): return instance_data
    instance_repo.update_workflow_instance = AsyncMock(side_effect=mock_update_instance)
    result = await workflow_service_existing.unarchive_workflow_instance(UNARCHIVE_INSTANCE_ID, UNARCHIVE_USER_ID) # Uses renamed fixture
    assert result.status == WorkflowStatus.active

@pytest.mark.asyncio
async def test_generate_shareable_link_new_token(workflow_service_existing, mock_repositories): # Uses renamed fixture
    _, instance_repo, _ = mock_repositories; instance_no_token = WorkflowInstance(id=SHARE_INSTANCE_ID, user_id=SHARE_USER_ID, name="Shareable Workflow", workflow_definition_id="def_share", status=WorkflowStatus.active, share_token=None); instance_repo.get_workflow_instance_by_id = AsyncMock(return_value=instance_no_token)
    async def mock_update(inst_id, inst_data): assert inst_id == SHARE_INSTANCE_ID; assert inst_data.share_token is not None; return inst_data
    instance_repo.update_workflow_instance = AsyncMock(side_effect=mock_update)
    result = await workflow_service_existing.generate_shareable_link(SHARE_INSTANCE_ID, SHARE_USER_ID) # Uses renamed fixture
    assert result.share_token is not None

@pytest.mark.asyncio
async def test_get_workflow_instance_by_share_token_success(workflow_service_existing, mock_repositories): # Uses renamed fixture
    _, instance_repo, task_repo = mock_repositories; shared_instance = WorkflowInstance(id=SHARE_INSTANCE_ID, user_id=SHARE_USER_ID, name="Shared Workflow", workflow_definition_id="def_share", status=WorkflowStatus.active, share_token=SHARE_TOKEN); tasks_for_instance = [TaskInstance(id="task1", name="Task 1", workflow_instance_id=SHARE_INSTANCE_ID, order=0, status=TaskStatus.pending)]; instance_repo.get_workflow_instance_by_share_token = AsyncMock(return_value=shared_instance); task_repo.get_tasks_for_workflow_instance = AsyncMock(return_value=tasks_for_instance)
    result = await workflow_service_existing.get_workflow_instance_by_share_token(SHARE_TOKEN) # Uses renamed fixture
    assert result["instance"] == shared_instance; assert result["tasks"] == tasks_for_instance

# ----- New tests for due_datetime functionality -----

# Pydantic models used by new tests (already imported at top, but aliased here for clarity if needed)
# from models import WorkflowDefinition as PydanticWorkflowDefinition
# from models import WorkflowInstance as PydanticWorkflowInstance
# from models import TaskInstance as PydanticTaskInstance

BASE_TIME = datetime(2023, 1, 1, 12, 0, 0)

@pytest.fixture
def mock_definition_repo_new(): # New fixture to avoid conflict, uses AsyncMock
    return AsyncMock(spec=WorkflowDefinitionRepository)

@pytest.fixture
def mock_instance_repo_new(): # New fixture
    return AsyncMock(spec=WorkflowInstanceRepository)

@pytest.fixture
def mock_task_repo_new(): # New fixture
    return AsyncMock(spec=TaskInstanceRepository)

@pytest.fixture
def workflow_service_new(mock_definition_repo_new, mock_instance_repo_new, mock_task_repo_new): # New service fixture
    return WorkflowService(mock_definition_repo_new, mock_instance_repo_new, mock_task_repo_new)

@pytest.mark.asyncio
async def test_create_instance_no_dates(workflow_service_new, mock_definition_repo_new, mock_instance_repo_new, mock_task_repo_new):
    # Arrange
    def_id = "def_no_date"
    user_id = "user1"

    mock_definition = WorkflowDefinition( # Using WorkflowDefinition as Pydantic model
        id=def_id, name="Test Def No Date", due_datetime=None,
        task_definitions=[
            TaskDefinitionBase(name="Task 1", order=1, due_datetime_offset_minutes=10)
        ]
    )
    mock_definition_repo_new.get_workflow_definition_by_id.return_value = mock_definition

    async def mock_create_instance_effect(instance_model: WorkflowInstance):
        instance_model.id = "wf_instance_mock_id"
        return instance_model
    mock_instance_repo_new.create_workflow_instance.side_effect = mock_create_instance_effect

    created_tasks_args = []
    async def mock_create_task(task_model: TaskInstance):
        created_tasks_args.append(task_model)
        return task_model
    mock_task_repo_new.create_task_instance.side_effect = mock_create_task

    # Act
    input_instance_data = WorkflowInstance(
            workflow_definition_id=def_id,
            user_id=user_id,
            name="Test Def No Date" # Service will use definition name if this is None and model allows
        )
    # Using workflow_service_new fixture
    created_instance = await workflow_service_new.create_workflow_instance(input_instance_data)

    # Assert
    assert created_instance is not None
    assert created_instance.due_datetime is None
    mock_definition_repo_new.get_workflow_definition_by_id.assert_called_once_with(def_id)

    assert mock_instance_repo_new.create_workflow_instance.call_count == 1
    args_instance_call, _ = mock_instance_repo_new.create_workflow_instance.call_args
    assert args_instance_call[0].due_datetime is None

    assert len(created_tasks_args) == 1
    assert created_tasks_args[0].due_datetime is None


@pytest.mark.asyncio
async def test_create_instance_with_definition_date(workflow_service_new, mock_definition_repo_new, mock_instance_repo_new, mock_task_repo_new):
    def_id = "def_with_date"
    user_id = "user1"
    def_due = BASE_TIME

    mock_definition = WorkflowDefinition(
        id=def_id, name="Test Def With Date", due_datetime=def_due,
        task_definitions=[
            TaskDefinitionBase(name="Task 1", order=1, due_datetime_offset_minutes=30),
            TaskDefinitionBase(name="Task 2", order=2, due_datetime_offset_minutes=-15),
            TaskDefinitionBase(name="Task 3", order=3, due_datetime_offset_minutes=None),
            TaskDefinitionBase(name="Task 4", order=4)
        ]
    )
    mock_definition_repo_new.get_workflow_definition_by_id.return_value = mock_definition

    async def mock_create_instance(instance_model: WorkflowInstance):
        instance_model.id = "wf_instance_123"
        return instance_model
    mock_instance_repo_new.create_workflow_instance.side_effect = mock_create_instance

    created_tasks_args = []
    async def mock_create_task(task_model: TaskInstance):
        created_tasks_args.append(task_model)
        return task_model
    mock_task_repo_new.create_task_instance.side_effect = mock_create_task

    input_instance_data = WorkflowInstance(
        workflow_definition_id=def_id,
        user_id=user_id,
        name="Test Def With Date" # Name for the instance
        # Not providing due_datetime, so it should pick up from the definition
    )
    created_instance = await workflow_service_new.create_workflow_instance(input_instance_data)

    assert created_instance is not None
    assert created_instance.due_datetime == def_due

    assert len(created_tasks_args) == 4
    assert created_tasks_args[0].due_datetime == def_due + timedelta(minutes=30)
    assert created_tasks_args[1].due_datetime == def_due + timedelta(minutes=-15)
    assert created_tasks_args[2].due_datetime == def_due + timedelta(minutes=0)
    assert created_tasks_args[3].due_datetime == def_due + timedelta(minutes=0)


@pytest.mark.asyncio
async def test_create_instance_with_override_date(workflow_service_new, mock_definition_repo_new, mock_instance_repo_new, mock_task_repo_new):
    def_id = "def_override"
    user_id = "user1"
    def_due = BASE_TIME
    override_due = BASE_TIME + timedelta(days=1)

    mock_definition = WorkflowDefinition(
        id=def_id, name="Test Def Override", due_datetime=def_due,
        task_definitions=[TaskDefinitionBase(name="Task 1", order=1, due_datetime_offset_minutes=60)]
    )
    mock_definition_repo_new.get_workflow_definition_by_id.return_value = mock_definition

    async def mock_create_instance(instance_model: WorkflowInstance):
        instance_model.id = "wf_instance_override"
        return instance_model
    mock_instance_repo_new.create_workflow_instance.side_effect = mock_create_instance

    created_tasks_args = []
    async def mock_create_task(task_model: TaskInstance):
        created_tasks_args.append(task_model)
        return task_model
    mock_task_repo_new.create_task_instance.side_effect = mock_create_task

    input_instance_data = WorkflowInstance(
        workflow_definition_id=def_id,
        user_id=user_id,
        name="Test Def Override",
        due_datetime=override_due # Pass override_due as due_datetime in the model
    )
    created_instance = await workflow_service_new.create_workflow_instance(input_instance_data)

    assert created_instance is not None
    assert created_instance.due_datetime == override_due

    assert len(created_tasks_args) == 1
    assert created_tasks_args[0].due_datetime == override_due + timedelta(minutes=60)

@pytest.mark.asyncio
async def test_create_instance_override_with_no_def_date(workflow_service_new, mock_definition_repo_new, mock_instance_repo_new, mock_task_repo_new):
    def_id = "def_override_no_def_date"
    user_id = "user1"
    override_due = BASE_TIME + timedelta(hours=2)

    mock_definition = WorkflowDefinition(
        id=def_id, name="Test Def Override No Def Date", due_datetime=None,
        task_definitions=[TaskDefinitionBase(name="Task 1", order=1, due_datetime_offset_minutes=-30)]
    )
    mock_definition_repo_new.get_workflow_definition_by_id.return_value = mock_definition

    async def mock_create_instance(instance_model: WorkflowInstance):
        instance_model.id = "wf_instance_override_ndd"
        return instance_model
    mock_instance_repo_new.create_workflow_instance.side_effect = mock_create_instance

    created_tasks_args = []
    async def mock_create_task(task_model: TaskInstance):
        created_tasks_args.append(task_model)
        return task_model
    mock_task_repo_new.create_task_instance.side_effect = mock_create_task

    input_instance_data = WorkflowInstance(
        workflow_definition_id=def_id,
        user_id=user_id,
        name="Test Def Override No Def Date", # Correct name for this test context
        due_datetime=override_due # Client explicitly sets due_datetime for the instance
    )
    created_instance = await workflow_service_new.create_workflow_instance(input_instance_data)

    assert created_instance is not None
    assert created_instance.due_datetime == override_due # Instance due_datetime is the override

    assert len(created_tasks_args) == 1 # This test's definition has one task
    # Task due_datetime is based on override_due and its offset
    assert created_tasks_args[0].due_datetime == override_due + timedelta(minutes=-30)
