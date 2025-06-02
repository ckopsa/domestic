import pytest
import sys
import os
from unittest.mock import AsyncMock, MagicMock

# Add the project root to sys.path to ensure 'app' module can be found
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db_models import Base
from app.repository import PostgreSQLWorkflowRepository, DefinitionNotFoundError, DefinitionInUseError
from app.services import WorkflowService
from app.models import WorkflowDefinition, WorkflowInstance, TaskInstance
from app.db_models.enums import WorkflowStatus, TaskStatus

# Setup for in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def mock_repositories():
    definition_repo = MagicMock()
    instance_repo = MagicMock()
    task_repo = MagicMock()
    return definition_repo, instance_repo, task_repo

@pytest.fixture
def workflow_service(mock_repositories):
    definition_repo, instance_repo, task_repo = mock_repositories
    return WorkflowService(definition_repo, instance_repo, task_repo)

@pytest.mark.asyncio
async def test_create_workflow_instance_success(workflow_service, mock_repositories):
    # Arrange
    definition_repo, instance_repo, task_repo = mock_repositories
    definition = WorkflowDefinition(
        id="test_def_1",
        name="Test Workflow",
        description="A test workflow definition",
        task_names=["Task 1", "Task 2"]
    )
    definition_repo.get_workflow_definition_by_id = AsyncMock(return_value=definition)
    instance = WorkflowInstance(
        id="test_inst_1",
        workflow_definition_id="test_def_1",
        name="Test Workflow",
        user_id="test_user",
        status=WorkflowStatus.active
    )
    instance_repo.create_workflow_instance = AsyncMock(return_value=instance)
    task_repo.create_task_instance = AsyncMock(side_effect=lambda task: task)

    # Act
    result = await workflow_service.create_workflow_instance("test_def_1", user_id="test_user")

    # Assert
    assert result is not None
    assert result.id == "test_inst_1"
    assert result.workflow_definition_id == "test_def_1"
    assert result.name == "Test Workflow"
    assert result.user_id == "test_user"
    assert result.status == WorkflowStatus.active
    assert task_repo.create_task_instance.call_count == 2
    task_calls = task_repo.create_task_instance.call_args_list
    assert task_calls[0][0][0].name == "Task 1"
    assert task_calls[0][0][0].order == 0
    assert task_calls[1][0][0].name == "Task 2"
    assert task_calls[1][0][0].order == 1

@pytest.mark.asyncio
async def test_create_workflow_instance_definition_not_found(workflow_service, mock_repositories):
    # Arrange
    definition_repo, _, _ = mock_repositories
    definition_repo.get_workflow_definition_by_id = AsyncMock(return_value=None)

    # Act
    result = await workflow_service.create_workflow_instance("test_def_1", user_id="test_user")

    # Assert
    assert result is None

@pytest.mark.asyncio
async def test_complete_task_success(workflow_service, mock_repositories):
    # Arrange
    definition_repo, instance_repo, task_repo = mock_repositories
    task = TaskInstance(
        id="test_task_1",
        workflow_instance_id="test_inst_1",
        name="Test Task",
        order=0,
        status=TaskStatus.pending
    )
    instance = WorkflowInstance(
        id="test_inst_1",
        workflow_definition_id="test_def_1",
        name="Test Workflow",
        user_id="test_user",
        status=WorkflowStatus.active
    )
    tasks = [
        TaskInstance(
            id="test_task_1",
            workflow_instance_id="test_inst_1",
            name="Test Task 1",
            order=0,
            status=TaskStatus.pending
        ),
        TaskInstance(
            id="test_task_2",
            workflow_instance_id="test_inst_1",
            name="Test Task 2",
            order=1,
            status=TaskStatus.completed
        )
    ]
    task_repo.get_task_instance_by_id = AsyncMock(return_value=task)
    instance_repo.get_workflow_instance_by_id = AsyncMock(return_value=instance)
    task_repo.update_task_instance = AsyncMock(return_value=task)
    task_repo.get_tasks_for_workflow_instance = AsyncMock(return_value=tasks)
    instance_repo.update_workflow_instance = AsyncMock(return_value=instance)

    # Act
    result = await workflow_service.complete_task("test_task_1", user_id="test_user")

    # Assert
    assert result is not None
    assert result.status == TaskStatus.completed
    assert instance_repo.update_workflow_instance.call_count == 0  # Not all tasks completed yet

@pytest.mark.asyncio
async def test_complete_task_all_tasks_completed(workflow_service, mock_repositories):
    # Arrange
    definition_repo, instance_repo, task_repo = mock_repositories
    task = TaskInstance(
        id="test_task_1",
        workflow_instance_id="test_inst_1",
        name="Test Task",
        order=0,
        status=TaskStatus.pending
    )
    instance = WorkflowInstance(
        id="test_inst_1",
        workflow_definition_id="test_def_1",
        name="Test Workflow",
        user_id="test_user",
        status=WorkflowStatus.active
    )
    tasks = [
        TaskInstance(
            id="test_task_1",
            workflow_instance_id="test_inst_1",
            name="Test Task 1",
            order=0,
            status=TaskStatus.pending
        )
    ]
    task_repo.get_task_instance_by_id = AsyncMock(return_value=task)
    instance_repo.get_workflow_instance_by_id = AsyncMock(return_value=instance)
    updated_task = TaskInstance(
        id="test_task_1",
        workflow_instance_id="test_inst_1",
        name="Test Task",
        order=0,
        status=TaskStatus.completed
    )
    task_repo.update_task_instance = AsyncMock(return_value=updated_task)
    task_repo.get_tasks_for_workflow_instance = AsyncMock(return_value=[updated_task])
    instance_repo.update_workflow_instance = AsyncMock(return_value=instance)

    # Act
    result = await workflow_service.complete_task("test_task_1", user_id="test_user")

    # Assert
    assert result is not None
    assert result.status == TaskStatus.completed
    assert instance_repo.update_workflow_instance.call_count == 1
    updated_instance = instance_repo.update_workflow_instance.call_args[0][1]
    assert updated_instance.status == WorkflowStatus.completed

@pytest.mark.asyncio
async def test_complete_task_already_completed(workflow_service, mock_repositories):
    # Arrange
    definition_repo, instance_repo, task_repo = mock_repositories
    task = TaskInstance(
        id="test_task_1",
        workflow_instance_id="test_inst_1",
        name="Test Task",
        order=0,
        status=TaskStatus.completed
    )
    task_repo.get_task_instance_by_id = AsyncMock(return_value=task)

    # Act
    result = await workflow_service.complete_task("test_task_1", user_id="test_user")

    # Assert
    assert result is None

@pytest.mark.asyncio
async def test_complete_task_unauthorized_user(workflow_service, mock_repositories):
    # Arrange
    definition_repo, instance_repo, task_repo = mock_repositories
    task = TaskInstance(
        id="test_task_1",
        workflow_instance_id="test_inst_1",
        name="Test Task",
        order=0,
        status=TaskStatus.pending
    )
    instance = WorkflowInstance(
        id="test_inst_1",
        workflow_definition_id="test_def_1",
        name="Test Workflow",
        user_id="different_user",
        status=WorkflowStatus.active
    )
    task_repo.get_task_instance_by_id = AsyncMock(return_value=task)
    instance_repo.get_workflow_instance_by_id = AsyncMock(return_value=instance)

    # Act
    result = await workflow_service.complete_task("test_task_1", user_id="test_user")

    # Assert
    assert result is None

@pytest.mark.asyncio
async def test_create_new_definition_success(workflow_service, mock_repositories):
    # Arrange
    definition_repo, _, _ = mock_repositories
    definition = WorkflowDefinition(
        id="test_def_1",
        name="Test Workflow",
        description="A test workflow",
        task_names=["Task 1", "Task 2"]
    )
    definition_repo.create_workflow_definition = AsyncMock(return_value=definition)

    # Act
    result = await workflow_service.create_new_definition(
        name="Test Workflow",
        description="A test workflow",
        task_names=["Task 1", "Task 2"]
    )

    # Assert
    assert result is not None
    assert result.name == "Test Workflow"
    assert result.task_names == ["Task 1", "Task 2"]

@pytest.mark.asyncio
async def test_create_new_definition_empty_name(workflow_service, mock_repositories):
    # Arrange
    definition_repo, _, _ = mock_repositories

    # Act & Assert
    with pytest.raises(ValueError, match="Definition name cannot be empty."):
        await workflow_service.create_new_definition(
            name="",
            description="A test workflow",
            task_names=["Task 1"]
        )

@pytest.mark.asyncio
async def test_create_new_definition_empty_task_list(workflow_service, mock_repositories):
    # Arrange
    definition_repo, _, _ = mock_repositories

    # Act & Assert
    with pytest.raises(ValueError, match="A definition must have at least one task name."):
        await workflow_service.create_new_definition(
            name="Test Workflow",
            description="A test workflow",
            task_names=[]
        )

@pytest.mark.asyncio
async def test_update_definition_success(workflow_service, mock_repositories):
    # Arrange
    definition_repo, _, _ = mock_repositories
    updated_definition = WorkflowDefinition(
        id="test_def_1",
        name="Updated Workflow",
        description="Updated description",
        task_names=["Updated Task 1"]
    )
    definition_repo.update_workflow_definition = AsyncMock(return_value=updated_definition)

    # Act
    result = await workflow_service.update_definition(
        definition_id="test_def_1",
        name="Updated Workflow",
        description="Updated description",
        task_names=["Updated Task 1"]
    )

    # Assert
    assert result is not None
    assert result.name == "Updated Workflow"
    assert result.task_names == ["Updated Task 1"]

@pytest.mark.asyncio
async def test_update_definition_empty_name(workflow_service, mock_repositories):
    # Arrange
    definition_repo, _, _ = mock_repositories

    # Act & Assert
    with pytest.raises(ValueError, match="Definition name cannot be empty."):
        await workflow_service.update_definition(
            definition_id="test_def_1",
            name="",
            description="Updated description",
            task_names=["Updated Task 1"]
        )

@pytest.mark.asyncio
async def test_update_definition_empty_task_list(workflow_service, mock_repositories):
    # Arrange
    definition_repo, _, _ = mock_repositories

    # Act & Assert
    with pytest.raises(ValueError, match="A definition must have at least one task name."):
        await workflow_service.update_definition(
            definition_id="test_def_1",
            name="Updated Workflow",
            description="Updated description",
            task_names=[]
        )

@pytest.mark.asyncio
async def test_delete_definition_success(workflow_service, mock_repositories):
    # Arrange
    definition_repo, _, _ = mock_repositories
    definition_repo.delete_workflow_definition = AsyncMock(return_value=None)

    # Act
    await workflow_service.delete_definition("test_def_1")

    # Assert
    definition_repo.delete_workflow_definition.assert_called_once_with("test_def_1")

@pytest.mark.asyncio
async def test_delete_definition_not_found(workflow_service, mock_repositories):
    # Arrange
    definition_repo, _, _ = mock_repositories
    definition_repo.delete_workflow_definition = AsyncMock(side_effect=DefinitionNotFoundError("Definition not found"))

    # Act & Assert
    with pytest.raises(ValueError, match="Definition not found"):
        await workflow_service.delete_definition("test_def_1")

@pytest.mark.asyncio
async def test_delete_definition_in_use(workflow_service, mock_repositories):
    # Arrange
    definition_repo, _, _ = mock_repositories
    definition_repo.delete_workflow_definition = AsyncMock(side_effect=DefinitionInUseError("Definition in use"))

    # Act & Assert
    with pytest.raises(ValueError, match="Definition in use"):
        await workflow_service.delete_definition("test_def_1")

@pytest.mark.asyncio
async def test_get_workflow_instance_with_tasks_success(workflow_service, mock_repositories):
    # Arrange
    definition_repo, instance_repo, task_repo = mock_repositories
    instance = WorkflowInstance(
        id="test_inst_1",
        workflow_definition_id="test_def_1",
        name="Test Workflow",
        user_id="test_user",
        status=WorkflowStatus.active
    )
    tasks = [
        TaskInstance(
            id="test_task_1",
            workflow_instance_id="test_inst_1",
            name="Test Task 1",
            order=0,
            status=TaskStatus.pending
        )
    ]
    instance_repo.get_workflow_instance_by_id = AsyncMock(return_value=instance)
    task_repo.get_tasks_for_workflow_instance = AsyncMock(return_value=tasks)

    # Act
    result = await workflow_service.get_workflow_instance_with_tasks("test_inst_1", user_id="test_user")

    # Assert
    assert result is not None
    assert result["instance"] == instance
    assert result["tasks"] == tasks

@pytest.mark.asyncio
async def test_get_workflow_instance_with_tasks_unauthorized(workflow_service, mock_repositories):
    # Arrange
    definition_repo, instance_repo, task_repo = mock_repositories
    instance = WorkflowInstance(
        id="test_inst_1",
        workflow_definition_id="test_def_1",
        name="Test Workflow",
        user_id="different_user",
        status=WorkflowStatus.active
    )
    instance_repo.get_workflow_instance_by_id = AsyncMock(return_value=instance)

    # Act
    result = await workflow_service.get_workflow_instance_with_tasks("test_inst_1", user_id="test_user")

    # Assert
    assert result is None

@pytest.mark.asyncio
async def test_list_instances_for_user(workflow_service, mock_repositories):
    # Arrange
    definition_repo, instance_repo, task_repo = mock_repositories
    instances = [
        WorkflowInstance(
            id="test_inst_1",
            workflow_definition_id="test_def_1",
            name="Test Workflow 1",
            user_id="test_user",
            status=WorkflowStatus.active
        ),
        WorkflowInstance(
            id="test_inst_2",
            workflow_definition_id="test_def_2",
            name="Test Workflow 2",
            user_id="test_user",
            status=WorkflowStatus.completed
        )
    ]
    instance_repo.list_workflow_instances_by_user = AsyncMock(return_value=instances)

    # Act
    result = await workflow_service.list_instances_for_user("test_user")

    # Assert
    assert len(result) == 2
    assert result[0].user_id == "test_user"
    assert result[1].user_id == "test_user"
    # Verify the call to the repository method, specifically that default Nones are passed
    instance_repo.list_workflow_instances_by_user.assert_called_once_with(
        user_id="test_user",
        created_at_date=None,
        status=None
    )


# Tests for list_instances_for_user with filters
from datetime import date as DateObject

@pytest.mark.asyncio
async def test_list_instances_for_user_passthrough_no_filters(workflow_service, mock_repositories):
    _, instance_repo, _ = mock_repositories
    expected_result = [MagicMock(spec=WorkflowInstance)]
    instance_repo.list_workflow_instances_by_user = AsyncMock(return_value=expected_result)

    user_id = "test_user_no_filters"
    result = await workflow_service.list_instances_for_user(user_id=user_id)

    instance_repo.list_workflow_instances_by_user.assert_called_once_with(
        user_id=user_id,
        created_at_date=None,
        status=None
    )
    assert result == expected_result

@pytest.mark.asyncio
async def test_list_instances_for_user_passthrough_with_date(workflow_service, mock_repositories):
    _, instance_repo, _ = mock_repositories
    expected_result = [MagicMock(spec=WorkflowInstance)]
    instance_repo.list_workflow_instances_by_user = AsyncMock(return_value=expected_result)

    user_id = "test_user_date_filter"
    test_date = DateObject(2023, 1, 15)
    result = await workflow_service.list_instances_for_user(user_id=user_id, created_at_date=test_date)

    instance_repo.list_workflow_instances_by_user.assert_called_once_with(
        user_id=user_id,
        created_at_date=test_date,
        status=None
    )
    assert result == expected_result

@pytest.mark.asyncio
async def test_list_instances_for_user_passthrough_with_status(workflow_service, mock_repositories):
    _, instance_repo, _ = mock_repositories
    expected_result = [MagicMock(spec=WorkflowInstance)]
    instance_repo.list_workflow_instances_by_user = AsyncMock(return_value=expected_result)

    user_id = "test_user_status_filter"
    test_status = WorkflowStatus.pending
    result = await workflow_service.list_instances_for_user(user_id=user_id, status=test_status)

    instance_repo.list_workflow_instances_by_user.assert_called_once_with(
        user_id=user_id,
        created_at_date=None,
        status=test_status
    )
    assert result == expected_result

@pytest.mark.asyncio
async def test_list_instances_for_user_passthrough_with_all_filters(workflow_service, mock_repositories):
    _, instance_repo, _ = mock_repositories
    expected_result = [MagicMock(spec=WorkflowInstance)]
    instance_repo.list_workflow_instances_by_user = AsyncMock(return_value=expected_result)

    user_id = "test_user_all_filters"
    test_date = DateObject(2023, 3, 20)
    test_status = WorkflowStatus.completed
    result = await workflow_service.list_instances_for_user(
        user_id=user_id,
        created_at_date=test_date,
        status=test_status
    )

    instance_repo.list_workflow_instances_by_user.assert_called_once_with(
        user_id=user_id,
        created_at_date=test_date,
        status=test_status
    )
    assert result == expected_result


USER_ID = "test_user_123"
OTHER_USER_ID = "other_user_456"
WF_INSTANCE_ID = "wf_inst_abc"
TASK_ID_1 = "task_def_123"

@pytest.mark.asyncio
async def test_undo_complete_task_success_workflow_becomes_active(workflow_service, mock_repositories):
    # Arrange
    _, instance_repo, task_repo = mock_repositories

    completed_task = TaskInstance(
        id=TASK_ID_1,
        workflow_instance_id=WF_INSTANCE_ID,
        name="Test Task 1",
        order=0,
        status=TaskStatus.completed
    )
    workflow_instance = WorkflowInstance(
        id=WF_INSTANCE_ID,
        workflow_definition_id="def_id_1",
        name="Test Workflow",
        user_id=USER_ID,
        status=WorkflowStatus.completed # Workflow was completed
    )

    task_repo.get_task_instance_by_id = AsyncMock(return_value=completed_task)
    instance_repo.get_workflow_instance_by_id = AsyncMock(return_value=workflow_instance)
    
    # Mock the update methods to return the object passed to them, modified
    async def update_task_side_effect(task_id, task_data):
        # In a real scenario, this would update and return the updated object.
        # For the mock, we'll just reflect the change.
        completed_task.status = task_data.status
        return completed_task
    
    async def update_workflow_side_effect(wf_id, wf_data):
        workflow_instance.status = wf_data.status
        return workflow_instance

    task_repo.update_task_instance = AsyncMock(side_effect=update_task_side_effect)
    instance_repo.update_workflow_instance = AsyncMock(side_effect=update_workflow_side_effect)

    # Act
    result = await workflow_service.undo_complete_task(TASK_ID_1, USER_ID)

    # Assert
    assert result is not None
    assert result.id == TASK_ID_1
    assert result.status == TaskStatus.pending
    task_repo.update_task_instance.assert_called_once()
    assert task_repo.update_task_instance.call_args[0][1].status == TaskStatus.pending
    
    instance_repo.update_workflow_instance.assert_called_once()
    assert instance_repo.update_workflow_instance.call_args[0][1].status == WorkflowStatus.active

@pytest.mark.asyncio
async def test_undo_complete_task_task_not_found(workflow_service, mock_repositories):
    # Arrange
    _, _, task_repo = mock_repositories
    task_repo.get_task_instance_by_id = AsyncMock(return_value=None)

    # Act
    result = await workflow_service.undo_complete_task("non_existent_task_id", USER_ID)

    # Assert
    assert result is None
    task_repo.update_task_instance.assert_not_called()
    mock_repositories[1].update_workflow_instance.assert_not_called() # instance_repo

@pytest.mark.asyncio
async def test_undo_complete_task_task_not_completed(workflow_service, mock_repositories):
    # Arrange
    _, _, task_repo = mock_repositories
    pending_task = TaskInstance(
        id=TASK_ID_1,
        workflow_instance_id=WF_INSTANCE_ID,
        name="Test Task 1",
        order=0,
        status=TaskStatus.pending # Task is not completed
    )
    task_repo.get_task_instance_by_id = AsyncMock(return_value=pending_task)

    # Act
    result = await workflow_service.undo_complete_task(TASK_ID_1, USER_ID)

    # Assert
    assert result is None
    task_repo.update_task_instance.assert_not_called()
    mock_repositories[1].update_workflow_instance.assert_not_called() # instance_repo

@pytest.mark.asyncio
async def test_undo_complete_task_workflow_not_found(workflow_service, mock_repositories):
    # Arrange
    _, instance_repo, task_repo = mock_repositories
    completed_task = TaskInstance(
        id=TASK_ID_1,
        workflow_instance_id="non_existent_wf_id", # Points to a non-existent workflow
        name="Test Task 1",
        order=0,
        status=TaskStatus.completed
    )
    task_repo.get_task_instance_by_id = AsyncMock(return_value=completed_task)
    instance_repo.get_workflow_instance_by_id = AsyncMock(return_value=None) # Workflow not found

    # Act
    result = await workflow_service.undo_complete_task(TASK_ID_1, USER_ID)

    # Assert
    assert result is None
    task_repo.update_task_instance.assert_not_called()
    instance_repo.update_workflow_instance.assert_not_called()

@pytest.mark.asyncio
async def test_undo_complete_task_user_unauthorized(workflow_service, mock_repositories):
    # Arrange
    _, instance_repo, task_repo = mock_repositories
    completed_task = TaskInstance(
        id=TASK_ID_1,
        workflow_instance_id=WF_INSTANCE_ID,
        name="Test Task 1",
        order=0,
        status=TaskStatus.completed
    )
    workflow_instance = WorkflowInstance(
        id=WF_INSTANCE_ID,
        workflow_definition_id="def_id_1",
        name="Test Workflow",
        user_id=OTHER_USER_ID, # Belongs to a different user
        status=WorkflowStatus.completed
    )
    task_repo.get_task_instance_by_id = AsyncMock(return_value=completed_task)
    instance_repo.get_workflow_instance_by_id = AsyncMock(return_value=workflow_instance)

    # Act
    result = await workflow_service.undo_complete_task(TASK_ID_1, USER_ID) # Current user is USER_ID

    # Assert
    assert result is None
    task_repo.update_task_instance.assert_not_called()
    instance_repo.update_workflow_instance.assert_not_called()

@pytest.mark.asyncio
async def test_undo_complete_task_workflow_remains_active(workflow_service, mock_repositories):
    # Arrange
    _, instance_repo, task_repo = mock_repositories

    completed_task_to_undo = TaskInstance(
        id=TASK_ID_1,
        workflow_instance_id=WF_INSTANCE_ID,
        name="Test Task 1",
        order=0,
        status=TaskStatus.completed
    )
    # This workflow is active because other tasks might still be pending, or it was never completed.
    workflow_instance = WorkflowInstance(
        id=WF_INSTANCE_ID,
        workflow_definition_id="def_id_1",
        name="Test Workflow",
        user_id=USER_ID,
        status=WorkflowStatus.active # Workflow is already active
    )

    task_repo.get_task_instance_by_id = AsyncMock(return_value=completed_task_to_undo)
    instance_repo.get_workflow_instance_by_id = AsyncMock(return_value=workflow_instance)
    
    async def update_task_side_effect(task_id, task_data):
        completed_task_to_undo.status = task_data.status
        return completed_task_to_undo

    task_repo.update_task_instance = AsyncMock(side_effect=update_task_side_effect)

    # Act
    result = await workflow_service.undo_complete_task(TASK_ID_1, USER_ID)

    # Assert
    assert result is not None
    assert result.id == TASK_ID_1
    assert result.status == TaskStatus.pending
    
    task_repo.update_task_instance.assert_called_once()
    assert task_repo.update_task_instance.call_args[0][1].status == TaskStatus.pending
    
    # Crucially, update_workflow_instance should NOT be called if workflow was already active
    instance_repo.update_workflow_instance.assert_not_called()
