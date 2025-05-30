import pytest
import sys
import os
from datetime import date as DateObject

# Add the project root to sys.path to ensure 'app' module can be found
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base
from app.repository import PostgreSQLWorkflowRepository
from app.models import WorkflowDefinition, TaskInstance, WorkflowInstance

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

@pytest.mark.asyncio
async def test_get_workflow_definition_by_id(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)
    # Add a workflow definition to the database
    from app.models.workflow import WorkflowDefinition as WorkflowDefinitionORM
    defn = WorkflowDefinitionORM(
        id="test_def_1",
        name="Test Workflow",
        description="A test workflow definition",
        task_names='["Task 1", "Task 2"]'
    )
    db_session.add(defn)
    db_session.commit()

    # Act
    result = await repo.get_workflow_definition_by_id("test_def_1")

    # Assert
    assert result is not None
    assert result.id == "test_def_1"
    assert result.name == "Test Workflow"
    assert result.description == "A test workflow definition"
    assert result.task_names == ["Task 1", "Task 2"]

@pytest.mark.asyncio
async def test_get_workflow_definition_by_id_not_found(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)

    # Act
    result = await repo.get_workflow_definition_by_id("non_existent_id")

    # Assert
    assert result is None

@pytest.mark.asyncio
async def test_get_workflow_instance_by_id(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)
    from app.models.workflow import WorkflowInstance as WorkflowInstanceORM
    instance = WorkflowInstanceORM(
        id="test_wf_1",
        workflow_definition_id="test_def_1",
        name="Test Workflow Instance",
        status="active",
        created_at=DateObject.today()
    )
    db_session.add(instance)
    db_session.commit()

    # Act
    result = await repo.get_workflow_instance_by_id("test_wf_1")

    # Assert
    assert result is not None
    assert result.id == "test_wf_1"
    assert result.workflow_definition_id == "test_def_1"
    assert result.name == "Test Workflow Instance"
    assert result.status == "active"

@pytest.mark.asyncio
async def test_get_workflow_instance_by_id_not_found(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)

    # Act
    result = await repo.get_workflow_instance_by_id("non_existent_id")

    # Assert
    assert result is None

@pytest.mark.asyncio
async def test_create_task_instance(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)
    # First, create a workflow instance to associate the task with
    from app.models.workflow import WorkflowInstance as WorkflowInstanceORM
    workflow_instance = WorkflowInstanceORM(
        id="test_wf_1",
        workflow_definition_id="test_def_1",
        name="Test Workflow Instance",
        status="active",
        created_at=DateObject.today()
    )
    db_session.add(workflow_instance)
    db_session.commit()

    task_data = TaskInstance(
        id="test_task_1",
        workflow_instance_id="test_wf_1",
        name="Test Task",
        order=0,
        status="pending"
    )

    # Act
    created_task = await repo.create_task_instance(task_data)

    # Assert
    assert created_task is not None
    assert created_task.id == "test_task_1"
    assert created_task.workflow_instance_id == "test_wf_1"
    assert created_task.name == "Test Task"
    assert created_task.order == 0
    assert created_task.status == "pending"

@pytest.mark.asyncio
async def test_get_tasks_for_workflow_instance(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)
    from app.models.workflow import WorkflowInstance as WorkflowInstanceORM
    from app.models.task import TaskInstance as TaskInstanceORM
    workflow_instance = WorkflowInstanceORM(
        id="test_wf_1",
        workflow_definition_id="test_def_1",
        name="Test Workflow Instance",
        status="active",
        created_at=DateObject.today()
    )
    db_session.add(workflow_instance)
    db_session.commit()

    tasks = [
        TaskInstanceORM(
            id=f"test_task_{i}",
            workflow_instance_id="test_wf_1",
            name=f"Task {i}",
            order=i,
            status="pending"
        ) for i in range(3)
    ]
    for task in tasks:
        db_session.add(task)
    db_session.commit()

    # Act
    result = await repo.get_tasks_for_workflow_instance("test_wf_1")

    # Assert
    assert len(result) == 3
    for i, task in enumerate(result):
        assert task.id == f"test_task_{i}"
        assert task.workflow_instance_id == "test_wf_1"
        assert task.name == f"Task {i}"
        assert task.order == i
        assert task.status == "pending"

@pytest.mark.asyncio
async def test_get_tasks_for_workflow_instance_no_tasks(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)
    from app.models.workflow import WorkflowInstance as WorkflowInstanceORM
    workflow_instance = WorkflowInstanceORM(
        id="test_wf_1",
        workflow_definition_id="test_def_1",
        name="Test Workflow Instance",
        status="active",
        created_at=DateObject.today()
    )
    db_session.add(workflow_instance)
    db_session.commit()

    # Act
    result = await repo.get_tasks_for_workflow_instance("test_wf_1")

    # Assert
    assert len(result) == 0

@pytest.mark.asyncio
async def test_get_task_instance_by_id(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)
    from app.models.workflow import WorkflowInstance as WorkflowInstanceORM
    from app.models.task import TaskInstance as TaskInstanceORM
    workflow_instance = WorkflowInstanceORM(
        id="test_wf_1",
        workflow_definition_id="test_def_1",
        name="Test Workflow Instance",
        status="active",
        created_at=DateObject.today()
    )
    db_session.add(workflow_instance)
    db_session.commit()

    task = TaskInstanceORM(
        id="test_task_1",
        workflow_instance_id="test_wf_1",
        name="Test Task",
        order=0,
        status="pending"
    )
    db_session.add(task)
    db_session.commit()

    # Act
    result = await repo.get_task_instance_by_id("test_task_1")

    # Assert
    assert result is not None
    assert result.id == "test_task_1"
    assert result.workflow_instance_id == "test_wf_1"
    assert result.name == "Test Task"
    assert result.order == 0
    assert result.status == "pending"

@pytest.mark.asyncio
async def test_get_task_instance_by_id_not_found(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)

    # Act
    result = await repo.get_task_instance_by_id("non_existent_id")

    # Assert
    assert result is None

@pytest.mark.asyncio
async def test_update_task_instance(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)
    from app.models.workflow import WorkflowInstance as WorkflowInstanceORM
    from app.models.task import TaskInstance as TaskInstanceORM
    workflow_instance = WorkflowInstanceORM(
        id="test_wf_1",
        workflow_definition_id="test_def_1",
        name="Test Workflow Instance",
        status="active",
        created_at=DateObject.today()
    )
    db_session.add(workflow_instance)
    db_session.commit()

    task = TaskInstanceORM(
        id="test_task_1",
        workflow_instance_id="test_wf_1",
        name="Test Task",
        order=0,
        status="pending"
    )
    db_session.add(task)
    db_session.commit()

    updated_task_data = TaskInstance(
        id="test_task_1",
        workflow_instance_id="test_wf_1",
        name="Updated Test Task",
        order=1,
        status="completed"
    )

    # Act
    result = await repo.update_task_instance("test_task_1", updated_task_data)

    # Assert
    assert result is not None
    assert result.id == "test_task_1"
    assert result.workflow_instance_id == "test_wf_1"
    assert result.name == "Updated Test Task"
    assert result.order == 1
    assert result.status == "completed"

@pytest.mark.asyncio
async def test_update_task_instance_not_found(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)
    updated_task_data = TaskInstance(
        id="non_existent_task",
        workflow_instance_id="test_wf_1",
        name="Updated Test Task",
        order=1,
        status="completed"
    )

    # Act
    result = await repo.update_task_instance("non_existent_task", updated_task_data)

    # Assert
    assert result is None

@pytest.mark.asyncio
async def test_update_workflow_instance(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)
    from app.models.workflow import WorkflowInstance as WorkflowInstanceORM
    instance = WorkflowInstanceORM(
        id="test_wf_1",
        workflow_definition_id="test_def_1",
        name="Test Workflow Instance",
        status="active",
        created_at=DateObject.today()
    )
    db_session.add(instance)
    db_session.commit()

    updated_instance_data = WorkflowInstance(
        id="test_wf_1",
        workflow_definition_id="test_def_1",
        name="Updated Workflow Instance",
        status="completed",
        created_at=DateObject.today()
    )

    # Act
    result = await repo.update_workflow_instance("test_wf_1", updated_instance_data)

    # Assert
    assert result is not None
    assert result.id == "test_wf_1"
    assert result.workflow_definition_id == "test_def_1"
    assert result.name == "Updated Workflow Instance"
    assert result.status == "completed"

@pytest.mark.asyncio
async def test_update_workflow_instance_not_found(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)
    updated_instance_data = WorkflowInstance(
        id="non_existent_wf",
        workflow_definition_id="test_def_1",
        name="Updated Workflow Instance",
        status="completed",
        created_at=DateObject.today()
    )

    # Act
    result = await repo.update_workflow_instance("non_existent_wf", updated_instance_data)

    # Assert
    assert result is None
