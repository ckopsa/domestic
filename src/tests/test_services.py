from unittest.mock import AsyncMock, MagicMock

import pytest
from db_models import Base
from models import WorkflowDefinition, WorkflowInstance, TaskInstance, TaskDefinitionBase, WorkflowStatus, TaskStatus
from services import WorkflowService
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from repository import DefinitionNotFoundError, DefinitionInUseError, WorkflowDefinitionRepository, \
    WorkflowInstanceRepository, TaskInstanceRepository

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
def workflow_service(mock_repositories):
    definition_repo, instance_repo, task_repo = mock_repositories
    return WorkflowService(definition_repo, instance_repo, task_repo)

@pytest.mark.asyncio
async def test_create_workflow_instance_success(workflow_service, mock_repositories):
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
    result = await workflow_service.create_workflow_instance("test_def_1", user_id="test_user")
    assert result is not None
    assert result.id == "test_inst_1"
    assert task_repo.create_task_instance.call_count == 2

@pytest.mark.asyncio
async def test_create_new_definition_success(workflow_service, mock_repositories):
    definition_repo, _, _ = mock_repositories
    task_defs_input = [TaskDefinitionBase(name="Task 1", order=0), TaskDefinitionBase(name="Task 2", order=1)]
    expected_pydantic_definition_arg = WorkflowDefinition(
        name="Test Workflow", description="A test workflow", task_definitions=task_defs_input
    )
    returned_definition_from_repo = expected_pydantic_definition_arg.model_copy(update={"id": "test_def_1"})
    definition_repo.create_workflow_definition = AsyncMock(return_value=returned_definition_from_repo)

    result = await workflow_service.create_new_definition(
        name="Test Workflow", description="A test workflow",
        task_definitions=task_defs_input # Changed from task_names
    )
    assert result is not None
    assert result.name == "Test Workflow"
    assert result.id == "test_def_1"
    assert len(result.task_definitions) == 2
    definition_repo.create_workflow_definition.assert_called_once()
    called_with_arg = definition_repo.create_workflow_definition.call_args[0][0]
    assert called_with_arg.task_definitions == task_defs_input

@pytest.mark.asyncio
async def test_create_new_definition_empty_name(workflow_service, mock_repositories):
    with pytest.raises(ValueError, match="Definition name cannot be empty."):
        await workflow_service.create_new_definition(
            name="", description="A test workflow",
            task_definitions=[TaskDefinitionBase(name="Task 1", order=0)] # Changed from task_names
        )

@pytest.mark.asyncio
async def test_create_new_definition_empty_task_list(workflow_service, mock_repositories):
    with pytest.raises(ValueError, match="A definition must have at least one task."): # Message updated
        await workflow_service.create_new_definition(
            name="Test Workflow", description="A test workflow",
            task_definitions=[] # Changed from task_names
        )

@pytest.mark.asyncio
async def test_update_definition_success(workflow_service, mock_repositories):
    definition_repo, _, _ = mock_repositories
    task_defs_input = [TaskDefinitionBase(name="Updated Task 1", order=0)]
    expected_returned_definition = WorkflowDefinition(
        id="test_def_1", name="Updated Workflow", description="Updated description",
        task_definitions=task_defs_input
    )
    definition_repo.update_workflow_definition = AsyncMock(return_value=expected_returned_definition)

    result = await workflow_service.update_definition(
        definition_id="test_def_1", name="Updated Workflow", description="Updated description",
        task_definitions=task_defs_input # Changed from task_names
    )
    assert result is not None
    assert result.name == "Updated Workflow"
    definition_repo.update_workflow_definition.assert_called_once_with(
        "test_def_1", "Updated Workflow", "Updated description", task_defs_input
    )

@pytest.mark.asyncio
async def test_update_definition_empty_name(workflow_service, mock_repositories):
    with pytest.raises(ValueError, match="Definition name cannot be empty."):
        await workflow_service.update_definition(
            definition_id="test_def_1", name="", description="Updated description",
            task_definitions=[TaskDefinitionBase(name="Updated Task 1", order=0)] # Changed from task_names
        )

@pytest.mark.asyncio
async def test_update_definition_empty_task_list(workflow_service, mock_repositories):
    with pytest.raises(ValueError, match="A definition must have at least one task."): # Message updated
        await workflow_service.update_definition(
            definition_id="test_def_1", name="Updated Workflow", description="Updated description",
            task_definitions=[] # Changed from task_names
        )

@pytest.mark.asyncio
async def test_create_workflow_instance_definition_not_found(workflow_service, mock_repositories):
    definition_repo, _, _ = mock_repositories
    definition_repo.get_workflow_definition_by_id = AsyncMock(return_value=None)
    result = await workflow_service.create_workflow_instance("test_def_1", user_id="test_user")
    assert result is None

@pytest.mark.asyncio
async def test_complete_task_success(workflow_service, mock_repositories):
    _, instance_repo, task_repo = mock_repositories
    task = TaskInstance(id="test_task_1", workflow_instance_id="test_inst_1", name="Test Task", order=0, status=TaskStatus.pending)
    instance = WorkflowInstance(id="test_inst_1", workflow_definition_id="test_def_1", name="Test Workflow", user_id="test_user", status=WorkflowStatus.active)
    tasks_in_db = [task, TaskInstance(id="test_task_2", workflow_instance_id="test_inst_1", name="Test Task 2", order=1, status=TaskStatus.pending)]
    task_repo.get_task_instance_by_id = AsyncMock(return_value=task)
    instance_repo.get_workflow_instance_by_id = AsyncMock(return_value=instance)
    async def update_task_side_effect(task_id, task_data_pydantic): task_data_pydantic.status = TaskStatus.completed; return task_data_pydantic
    task_repo.update_task_instance = AsyncMock(side_effect=update_task_side_effect)
    tasks_after_completion = [TaskInstance(id="test_task_1", workflow_instance_id="test_inst_1", name="Test Task", order=0, status=TaskStatus.completed), TaskInstance(id="test_task_2", workflow_instance_id="test_inst_1", name="Test Task 2", order=1, status=TaskStatus.pending)]
    task_repo.get_tasks_for_workflow_instance = AsyncMock(return_value=tasks_after_completion)
    instance_repo.update_workflow_instance = AsyncMock(return_value=instance)
    result = await workflow_service.complete_task("test_task_1", user_id="test_user")
    assert result is not None; assert result.status == TaskStatus.completed
    instance_repo.update_workflow_instance.assert_not_called()

@pytest.mark.asyncio
async def test_complete_task_all_tasks_completed(workflow_service, mock_repositories):
    _, instance_repo, task_repo = mock_repositories
    task_to_complete = TaskInstance(id="test_task_1", workflow_instance_id="test_inst_1", name="Test Task", order=0, status=TaskStatus.pending)
    instance = WorkflowInstance(id="test_inst_1", workflow_definition_id="test_def_1", name="Test Workflow", user_id="test_user", status=WorkflowStatus.active)
    task_repo.get_task_instance_by_id = AsyncMock(return_value=task_to_complete)
    instance_repo.get_workflow_instance_by_id = AsyncMock(return_value=instance)
    updated_task_mock = task_to_complete.model_copy(update={"status": TaskStatus.completed})
    task_repo.update_task_instance = AsyncMock(return_value=updated_task_mock)
    task_repo.get_tasks_for_workflow_instance = AsyncMock(return_value=[updated_task_mock])
    async def update_instance_side_effect(instance_id, instance_data_pydantic): instance_data_pydantic.status = WorkflowStatus.completed; return instance_data_pydantic
    instance_repo.update_workflow_instance = AsyncMock(side_effect=update_instance_side_effect)
    result = await workflow_service.complete_task("test_task_1", user_id="test_user")
    assert result is not None; assert result.status == TaskStatus.completed
    instance_repo.update_workflow_instance.assert_called_once()
    assert instance_repo.update_workflow_instance.call_args[0][1].status == WorkflowStatus.completed

@pytest.mark.asyncio
async def test_complete_task_already_completed(workflow_service, mock_repositories):
    _, _, task_repo = mock_repositories
    task = TaskInstance(id="test_task_1", workflow_instance_id="test_inst_1", name="Test Task", order=0, status=TaskStatus.completed)
    task_repo.get_task_instance_by_id = AsyncMock(return_value=task)
    result = await workflow_service.complete_task("test_task_1", user_id="test_user")
    assert result is None

@pytest.mark.asyncio
async def test_complete_task_unauthorized_user(workflow_service, mock_repositories):
    _, instance_repo, task_repo = mock_repositories
    task = TaskInstance(id="test_task_1", workflow_instance_id="test_inst_1", name="Test Task", order=0, status=TaskStatus.pending)
    instance = WorkflowInstance(id="test_inst_1", workflow_definition_id="test_def_1", name="Test Workflow", user_id="different_user", status=WorkflowStatus.active)
    task_repo.get_task_instance_by_id = AsyncMock(return_value=task)
    instance_repo.get_workflow_instance_by_id = AsyncMock(return_value=instance)
    result = await workflow_service.complete_task("test_task_1", user_id="test_user")
    assert result is None

@pytest.mark.asyncio
async def test_delete_definition_success(workflow_service, mock_repositories):
    definition_repo, _, _ = mock_repositories
    definition_repo.delete_workflow_definition = AsyncMock(return_value=None)
    await workflow_service.delete_definition("test_def_1")
    definition_repo.delete_workflow_definition.assert_called_once_with("test_def_1")

@pytest.mark.asyncio
async def test_delete_definition_not_found(workflow_service, mock_repositories):
    definition_repo, _, _ = mock_repositories
    definition_repo.delete_workflow_definition = AsyncMock(side_effect=DefinitionNotFoundError("Definition not found"))
    with pytest.raises(ValueError, match="Definition not found"):
        await workflow_service.delete_definition("test_def_1")

@pytest.mark.asyncio
async def test_delete_definition_in_use(workflow_service, mock_repositories):
    definition_repo, _, _ = mock_repositories
    definition_repo.delete_workflow_definition = AsyncMock(side_effect=DefinitionInUseError("Definition in use"))
    with pytest.raises(ValueError, match="Definition in use"):
        await workflow_service.delete_definition("test_def_1")

@pytest.mark.asyncio
async def test_get_workflow_instance_with_tasks_success(workflow_service, mock_repositories):
    _, instance_repo, task_repo = mock_repositories
    instance = WorkflowInstance(id="test_inst_1", workflow_definition_id="test_def_1", name="Test Workflow", user_id="test_user", status=WorkflowStatus.active)
    tasks = [TaskInstance(id="test_task_1", workflow_instance_id="test_inst_1", name="Test Task 1", order=0, status=TaskStatus.pending)]
    instance_repo.get_workflow_instance_by_id = AsyncMock(return_value=instance)
    task_repo.get_tasks_for_workflow_instance = AsyncMock(return_value=tasks)
    result = await workflow_service.get_workflow_instance_with_tasks("test_inst_1", user_id="test_user")
    assert result is not None; assert result["instance"] == instance; assert result["tasks"] == tasks

@pytest.mark.asyncio
async def test_get_workflow_instance_with_tasks_unauthorized(workflow_service, mock_repositories):
    _, instance_repo, _ = mock_repositories
    instance = WorkflowInstance(id="test_inst_1", workflow_definition_id="test_def_1", name="Test Workflow", user_id="different_user", status=WorkflowStatus.active)
    instance_repo.get_workflow_instance_by_id = AsyncMock(return_value=instance)
    result = await workflow_service.get_workflow_instance_with_tasks("test_inst_1", user_id="test_user")
    assert result is None

@pytest.mark.asyncio
async def test_list_instances_for_user(workflow_service, mock_repositories):
    _, instance_repo, _ = mock_repositories
    instances = [WorkflowInstance(id="test_inst_1", workflow_definition_id="test_def_1", name="Test Workflow 1", user_id="test_user", status=WorkflowStatus.active)]
    instance_repo.list_workflow_instances_by_user = AsyncMock(return_value=instances)
    result = await workflow_service.list_instances_for_user("test_user")
    assert len(result) == 1
    instance_repo.list_workflow_instances_by_user.assert_called_once_with("test_user", created_at_date=None, status=None, definition_id=None)

from datetime import date as DateObject
LIST_USER_ID = "list_test_user"
USER_ID = "test_user_123"
OTHER_USER_ID = "other_user_456"
WF_INSTANCE_ID = "wf_inst_abc"
TASK_ID_1 = "task_def_123"
ARCHIVE_USER_ID = "archive_user"
ARCHIVE_INSTANCE_ID = "archive_instance_id"
OTHER_USER_ID_ARCHIVE = "other_archive_user"
UNARCHIVE_USER_ID = "unarchive_user"
UNARCHIVE_INSTANCE_ID = "unarchive_instance_id"
OTHER_USER_ID_UNARCHIVE = "other_unarchive_user"
SHARE_USER_ID = "share_user_1"
SHARE_INSTANCE_ID = "share_instance_1"
SHARE_TOKEN = "test_share_token_123"

@pytest.mark.asyncio
async def test_list_instances_for_user_passthrough_no_filters(workflow_service, mock_repositories):
    _, instance_repo, _ = mock_repositories; expected_result = [MagicMock(spec=WorkflowInstance)]; instance_repo.list_workflow_instances_by_user = AsyncMock(return_value=expected_result); user_id = "test_user_no_filters"
    # Call twice to ensure subsequent calls also use positional for user_id if that's the pattern
    await workflow_service.list_instances_for_user(user_id=user_id)
    result = await workflow_service.list_instances_for_user(user_id=user_id, created_at_date=None, status=None, definition_id=None)
    # Last call is what gets asserted by assert_called_with if not using assert_any_call or call_args_list
    instance_repo.list_workflow_instances_by_user.assert_called_with(user_id, created_at_date=None, status=None, definition_id=None)
    assert result == expected_result

@pytest.mark.asyncio
async def test_list_instances_for_user_passthrough_with_date(workflow_service, mock_repositories):
    _, instance_repo, _ = mock_repositories; expected_result = [MagicMock(spec=WorkflowInstance)]; instance_repo.list_workflow_instances_by_user = AsyncMock(return_value=expected_result); user_id = "test_user_date_filter"; test_date = DateObject(2023, 1, 15)
    result = await workflow_service.list_instances_for_user(user_id=user_id, created_at_date=test_date, definition_id=None)
    instance_repo.list_workflow_instances_by_user.assert_called_once_with(user_id, created_at_date=test_date, status=None, definition_id=None); assert result == expected_result

@pytest.mark.asyncio
async def test_list_instances_for_user_passthrough_with_status(workflow_service, mock_repositories):
    _, instance_repo, _ = mock_repositories; expected_result = [MagicMock(spec=WorkflowInstance)]; instance_repo.list_workflow_instances_by_user = AsyncMock(return_value=expected_result); user_id = "test_user_status_filter"; test_status = WorkflowStatus.active
    result = await workflow_service.list_instances_for_user(user_id=user_id, status=test_status, definition_id=None)
    instance_repo.list_workflow_instances_by_user.assert_called_once_with(user_id, created_at_date=None, status=test_status, definition_id=None); assert result == expected_result

@pytest.mark.asyncio
async def test_list_instances_for_user_passthrough_with_all_filters(workflow_service, mock_repositories):
    _, instance_repo, _ = mock_repositories; expected_result = [MagicMock(spec=WorkflowInstance)]; instance_repo.list_workflow_instances_by_user = AsyncMock(return_value=expected_result); user_id = "test_user_all_filters"; test_date = DateObject(2023, 3, 20); test_status = WorkflowStatus.completed
    result = await workflow_service.list_instances_for_user(user_id=user_id, created_at_date=test_date, status=test_status, definition_id=None)
    instance_repo.list_workflow_instances_by_user.assert_called_once_with(user_id, created_at_date=test_date, status=test_status, definition_id=None); assert result == expected_result

@pytest.mark.asyncio
async def test_list_instances_for_user_passthrough_with_definition_id(workflow_service, mock_repositories):
    _, instance_repo, _ = mock_repositories; expected_result = [MagicMock(spec=WorkflowInstance)]; instance_repo.list_workflow_instances_by_user = AsyncMock(return_value=expected_result); user_id = "test_user_def_id_filter"; test_definition_id = "def_filter_services_test"
    result = await workflow_service.list_instances_for_user(user_id=user_id, definition_id=test_definition_id)
    instance_repo.list_workflow_instances_by_user.assert_called_once_with(user_id, created_at_date=None, status=None, definition_id=test_definition_id); assert result == expected_result

@pytest.mark.asyncio
async def test_list_instances_for_user_passthrough_with_all_filters_including_definition_id(workflow_service, mock_repositories):
    _, instance_repo, _ = mock_repositories; expected_result = [MagicMock(spec=WorkflowInstance)]; instance_repo.list_workflow_instances_by_user = AsyncMock(return_value=expected_result); user_id = "test_user_all_filters_def_id"; test_date = DateObject(2023, 4, 25); test_status = WorkflowStatus.active; test_definition_id = "def_filter_services_test_all"
    result = await workflow_service.list_instances_for_user(user_id=user_id, created_at_date=test_date, status=test_status, definition_id=test_definition_id)
    instance_repo.list_workflow_instances_by_user.assert_called_once_with(user_id, created_at_date=test_date, status=test_status, definition_id=test_definition_id); assert result == expected_result

@pytest.mark.asyncio
async def test_list_instances_for_user_filters_archived_status(workflow_service, mock_repositories):
    _, instance_repo, _ = mock_repositories; archived_instance_mock = WorkflowInstance(id="inst_archived_1", user_id=LIST_USER_ID, status=WorkflowStatus.archived, name="Archived Wf", workflow_definition_id="def_1"); instance_repo.list_workflow_instances_by_user = AsyncMock(return_value=[archived_instance_mock])
    result = await workflow_service.list_instances_for_user(user_id=LIST_USER_ID, status=WorkflowStatus.archived, definition_id=None)
    assert len(result) == 1; instance_repo.list_workflow_instances_by_user.assert_called_once_with(LIST_USER_ID, created_at_date=None, status=WorkflowStatus.archived, definition_id=None)

@pytest.mark.asyncio
async def test_list_instances_for_user_active_status_excludes_archived(workflow_service, mock_repositories):
    _, instance_repo, _ = mock_repositories; active_instance_mock = WorkflowInstance(id="inst_active_1", user_id=LIST_USER_ID, status=WorkflowStatus.active, name="Active Wf", workflow_definition_id="def_2"); instance_repo.list_workflow_instances_by_user = AsyncMock(return_value=[active_instance_mock])
    result = await workflow_service.list_instances_for_user(user_id=LIST_USER_ID, status=WorkflowStatus.active, definition_id=None)
    assert len(result) == 1; instance_repo.list_workflow_instances_by_user.assert_called_once_with(LIST_USER_ID, created_at_date=None, status=WorkflowStatus.active, definition_id=None)

@pytest.mark.asyncio
async def test_list_instances_for_user_no_status_filter_passes_none_to_repo(workflow_service, mock_repositories):
    _, instance_repo, _ = mock_repositories; mixed_instances = [MagicMock(spec=WorkflowInstance)]; instance_repo.list_workflow_instances_by_user = AsyncMock(return_value=mixed_instances)
    result = await workflow_service.list_instances_for_user(user_id=LIST_USER_ID, status=None, definition_id=None)
    instance_repo.list_workflow_instances_by_user.assert_called_once_with(LIST_USER_ID, created_at_date=None, status=None, definition_id=None); assert result == mixed_instances

@pytest.mark.asyncio
async def test_undo_complete_task_success_workflow_becomes_active(workflow_service, mock_repositories):
    _, instance_repo, task_repo = mock_repositories; completed_task = TaskInstance(id=TASK_ID_1, workflow_instance_id=WF_INSTANCE_ID, name="Test Task 1", order=0, status=TaskStatus.completed); workflow_instance = WorkflowInstance(id=WF_INSTANCE_ID, workflow_definition_id="def_id_1", name="Test Workflow", user_id=USER_ID, status=WorkflowStatus.completed); task_repo.get_task_instance_by_id = AsyncMock(return_value=completed_task); instance_repo.get_workflow_instance_by_id = AsyncMock(return_value=workflow_instance)
    async def update_task_side_effect(task_id, task_data): completed_task.status = task_data.status; return completed_task
    async def update_workflow_side_effect(wf_id, wf_data): workflow_instance.status = wf_data.status; return workflow_instance
    task_repo.update_task_instance = AsyncMock(side_effect=update_task_side_effect); instance_repo.update_workflow_instance = AsyncMock(side_effect=update_workflow_side_effect)
    result = await workflow_service.undo_complete_task(TASK_ID_1, USER_ID)
    assert result.status == TaskStatus.pending; instance_repo.update_workflow_instance.assert_called_once(); assert instance_repo.update_workflow_instance.call_args[0][1].status == WorkflowStatus.active

@pytest.mark.asyncio
async def test_undo_complete_task_workflow_remains_active(workflow_service, mock_repositories):
    _, instance_repo, task_repo = mock_repositories; completed_task_to_undo = TaskInstance(id=TASK_ID_1, workflow_instance_id=WF_INSTANCE_ID, name="Test Task 1", order=0, status=TaskStatus.completed); workflow_instance = WorkflowInstance(id=WF_INSTANCE_ID, workflow_definition_id="def_id_1", name="Test Workflow", user_id=USER_ID, status=WorkflowStatus.active); task_repo.get_task_instance_by_id = AsyncMock(return_value=completed_task_to_undo); instance_repo.get_workflow_instance_by_id = AsyncMock(return_value=workflow_instance)
    async def update_task_side_effect(task_id, task_data): completed_task_to_undo.status = task_data.status; return completed_task_to_undo
    task_repo.update_task_instance = AsyncMock(side_effect=update_task_side_effect)
    result = await workflow_service.undo_complete_task(TASK_ID_1, USER_ID)
    assert result.status == TaskStatus.pending; instance_repo.update_workflow_instance.assert_not_called()

@pytest.mark.asyncio
async def test_archive_workflow_instance_success(workflow_service, mock_repositories):
    _, instance_repo, _ = mock_repositories; active_instance = WorkflowInstance(id=ARCHIVE_INSTANCE_ID, user_id=ARCHIVE_USER_ID, status=WorkflowStatus.active, name="Test Archive", workflow_definition_id="def_archive"); instance_repo.get_workflow_instance_by_id = AsyncMock(return_value=active_instance)
    async def mock_update_instance(instance_id, instance_data): return instance_data
    instance_repo.update_workflow_instance = AsyncMock(side_effect=mock_update_instance)
    result = await workflow_service.archive_workflow_instance(ARCHIVE_INSTANCE_ID, ARCHIVE_USER_ID)
    assert result.status == WorkflowStatus.archived

@pytest.mark.asyncio
async def test_unarchive_workflow_instance_success(workflow_service, mock_repositories):
    _, instance_repo, _ = mock_repositories; archived_instance = WorkflowInstance(id=UNARCHIVE_INSTANCE_ID, user_id=UNARCHIVE_USER_ID, status=WorkflowStatus.archived, name="Test Unarchive Success", workflow_definition_id="def_unarchive_succ"); instance_repo.get_workflow_instance_by_id = AsyncMock(return_value=archived_instance)
    async def mock_update_instance(instance_id, instance_data): return instance_data
    instance_repo.update_workflow_instance = AsyncMock(side_effect=mock_update_instance)
    result = await workflow_service.unarchive_workflow_instance(UNARCHIVE_INSTANCE_ID, UNARCHIVE_USER_ID)
    assert result.status == WorkflowStatus.active

@pytest.mark.asyncio
async def test_generate_shareable_link_new_token(workflow_service, mock_repositories):
    _, instance_repo, _ = mock_repositories; instance_no_token = WorkflowInstance(id=SHARE_INSTANCE_ID, user_id=SHARE_USER_ID, name="Shareable Workflow", workflow_definition_id="def_share", status=WorkflowStatus.active, share_token=None); instance_repo.get_workflow_instance_by_id = AsyncMock(return_value=instance_no_token)
    async def mock_update(inst_id, inst_data): assert inst_id == SHARE_INSTANCE_ID; assert inst_data.share_token is not None; return inst_data
    instance_repo.update_workflow_instance = AsyncMock(side_effect=mock_update)
    result = await workflow_service.generate_shareable_link(SHARE_INSTANCE_ID, SHARE_USER_ID)
    assert result.share_token is not None

@pytest.mark.asyncio
async def test_get_workflow_instance_by_share_token_success(workflow_service, mock_repositories):
    _, instance_repo, task_repo = mock_repositories; shared_instance = WorkflowInstance(id=SHARE_INSTANCE_ID, user_id=SHARE_USER_ID, name="Shared Workflow", workflow_definition_id="def_share", status=WorkflowStatus.active, share_token=SHARE_TOKEN); tasks_for_instance = [TaskInstance(id="task1", name="Task 1", workflow_instance_id=SHARE_INSTANCE_ID, order=0, status=TaskStatus.pending)]; instance_repo.get_workflow_instance_by_share_token = AsyncMock(return_value=shared_instance); task_repo.get_tasks_for_workflow_instance = AsyncMock(return_value=tasks_for_instance)
    result = await workflow_service.get_workflow_instance_by_share_token(SHARE_TOKEN)
    assert result["instance"] == shared_instance; assert result["tasks"] == tasks_for_instance
