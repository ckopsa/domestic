import pytest
import sys
import os
from datetime import date as DateObject

# Add the project root to sys.path to ensure 'app' module can be found
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db_models import Base
from app.repository import PostgreSQLWorkflowRepository, DefinitionNotFoundError, DefinitionInUseError
from app.models import WorkflowDefinition, TaskInstance, WorkflowInstance
from app.db_models.enums import WorkflowStatus, TaskStatus

# Setup for in-memory SQLite database for testing
# Note: For CI environment, this should be changed to a PostgreSQL test database URL
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
async def test_list_workflow_definitions(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)
    from app.db_models.workflow import WorkflowDefinition as WorkflowDefinitionORM
    defn1 = WorkflowDefinitionORM(
        id="test_def_1",
        name="Test Workflow 1",
        description="First test workflow",
        task_names=["Task 1", "Task 2"]
    )
    defn2 = WorkflowDefinitionORM(
        id="test_def_2",
        name="Test Workflow 2",
        description="Second test workflow",
        task_names=["Task 3", "Task 4"]
    )
    db_session.add(defn1)
    db_session.add(defn2)
    db_session.commit()

    # Act
    result = await repo.list_workflow_definitions()

    # Assert
    assert len(result) == 2
    assert result[0].id == "test_def_1"
    assert result[1].id == "test_def_2"
    assert result[0].task_names == ["Task 1", "Task 2"]
    assert result[1].task_names == ["Task 3", "Task 4"]

@pytest.mark.asyncio
async def test_get_workflow_definition_by_id(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)
    from app.db_models.workflow import WorkflowDefinition as WorkflowDefinitionORM
    defn = WorkflowDefinitionORM(
        id="test_def_1",
        name="Test Workflow",
        description="A test workflow definition",
        task_names=["Task 1", "Task 2"]
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
async def test_create_workflow_definition(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)
    definition_data = WorkflowDefinition(
        id="test_def_1",
        name="Test Workflow",
        description="A test workflow",
        task_names=["Task 1", "Task 2"]
    )

    # Act
    created_definition = await repo.create_workflow_definition(definition_data)

    # Assert
    assert created_definition is not None
    assert created_definition.id == "test_def_1"
    assert created_definition.name == "Test Workflow"
    assert created_definition.description == "A test workflow"
    assert created_definition.task_names == ["Task 1", "Task 2"]

    # Verify in database
    from app.db_models.workflow import WorkflowDefinition as WorkflowDefinitionORM
    db_defn = db_session.query(WorkflowDefinitionORM).filter(WorkflowDefinitionORM.id == "test_def_1").first()
    assert db_defn is not None
    assert db_defn.name == "Test Workflow"
    assert db_defn.task_names == ["Task 1", "Task 2"]

@pytest.mark.asyncio
async def test_update_workflow_definition(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)
    from app.db_models.workflow import WorkflowDefinition as WorkflowDefinitionORM
    defn = WorkflowDefinitionORM(
        id="test_def_1",
        name="Original Workflow",
        description="Original description",
        task_names=["Original Task 1"]
    )
    db_session.add(defn)
    db_session.commit()

    # Act
    result = await repo.update_workflow_definition(
        definition_id="test_def_1",
        name="Updated Workflow",
        description="Updated description",
        task_names=["Updated Task 1", "Updated Task 2"]
    )

    # Assert
    assert result is not None
    assert result.id == "test_def_1"
    assert result.name == "Updated Workflow"
    assert result.description == "Updated description"
    assert result.task_names == ["Updated Task 1", "Updated Task 2"]

    # Verify in database
    db_defn = db_session.query(WorkflowDefinitionORM).filter(WorkflowDefinitionORM.id == "test_def_1").first()
    assert db_defn.name == "Updated Workflow"
    assert db_defn.task_names == ["Updated Task 1", "Updated Task 2"]

@pytest.mark.asyncio
async def test_update_workflow_definition_not_found(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)

    # Act
    result = await repo.update_workflow_definition(
        definition_id="non_existent_id",
        name="Updated Workflow",
        description="Updated description",
        task_names=["Updated Task 1"]
    )

    # Assert
    assert result is None

@pytest.mark.asyncio
async def test_delete_workflow_definition(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)
    from app.db_models.workflow import WorkflowDefinition as WorkflowDefinitionORM
    defn = WorkflowDefinitionORM(
        id="test_def_1",
        name="Test Workflow",
        description="A test workflow",
        task_names=["Task 1"]
    )
    db_session.add(defn)
    db_session.commit()

    # Act
    await repo.delete_workflow_definition("test_def_1")

    # Assert
    db_defn = db_session.query(WorkflowDefinitionORM).filter(WorkflowDefinitionORM.id == "test_def_1").first()
    assert db_defn is None

@pytest.mark.asyncio
async def test_delete_workflow_definition_not_found(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)

    # Act & Assert
    with pytest.raises(DefinitionNotFoundError, match="Workflow Definition with ID 'non_existent_id' not found."):
        await repo.delete_workflow_definition("non_existent_id")

@pytest.mark.asyncio
async def test_delete_workflow_definition_in_use(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)
    from app.db_models.workflow import WorkflowDefinition as WorkflowDefinitionORM
    from app.db_models.workflow import WorkflowInstance as WorkflowInstanceORM
    defn = WorkflowDefinitionORM(
        id="test_def_1",
        name="Test Workflow",
        description="A test workflow",
        task_names=["Task 1"]
    )
    instance = WorkflowInstanceORM(
        id="test_wf_1",
        workflow_definition_id="test_def_1",
        name="Test Instance",
        user_id="test_user",
        status=WorkflowStatus.active,
        created_at=DateObject.today()
    )
    db_session.add(defn)
    db_session.add(instance)
    db_session.commit()

    # Act & Assert
    with pytest.raises(DefinitionInUseError, match="Cannot delete definition: It is currently used by 1 workflow instance\\(s\\)."):
        await repo.delete_workflow_definition("test_def_1")

@pytest.mark.asyncio
async def test_get_workflow_instance_by_id(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)
    from app.db_models.workflow import WorkflowInstance as WorkflowInstanceORM
    instance = WorkflowInstanceORM(
        id="test_wf_1",
        workflow_definition_id="test_def_1",
        name="Test Workflow Instance",
        user_id="test_user",
        status=WorkflowStatus.active,
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
    assert result.status == WorkflowStatus.active
    assert result.user_id == "test_user"

@pytest.mark.asyncio
async def test_get_workflow_instance_by_id_not_found(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)

    # Act
    result = await repo.get_workflow_instance_by_id("non_existent_id")

    # Assert
    assert result is None

@pytest.mark.asyncio
async def test_create_workflow_instance(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)
    instance_data = WorkflowInstance(
        id="test_wf_1",
        workflow_definition_id="test_def_1",
        name="Test Workflow Instance",
        user_id="test_user",
        status=WorkflowStatus.active,
        created_at=DateObject.today()
    )

    # Act
    created_instance = await repo.create_workflow_instance(instance_data)

    # Assert
    assert created_instance is not None
    assert created_instance.id == "test_wf_1"
    assert created_instance.workflow_definition_id == "test_def_1"
    assert created_instance.name == "Test Workflow Instance"
    assert created_instance.user_id == "test_user"
    assert created_instance.status == WorkflowStatus.active

    # Verify in database
    from app.db_models.workflow import WorkflowInstance as WorkflowInstanceORM
    db_instance = db_session.query(WorkflowInstanceORM).filter(WorkflowInstanceORM.id == "test_wf_1").first()
    assert db_instance is not None
    assert db_instance.user_id == "test_user"
    assert db_instance.status == WorkflowStatus.active

@pytest.mark.asyncio
async def test_update_workflow_instance(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)
    from app.db_models.workflow import WorkflowInstance as WorkflowInstanceORM
    instance = WorkflowInstanceORM(
        id="test_wf_1",
        workflow_definition_id="test_def_1",
        name="Test Workflow Instance",
        user_id="test_user",
        status=WorkflowStatus.active,
        created_at=DateObject.today()
    )
    db_session.add(instance)
    db_session.commit()

    updated_instance_data = WorkflowInstance(
        id="test_wf_1",
        workflow_definition_id="test_def_1",
        name="Updated Workflow Instance",
        user_id="test_user",
        status=WorkflowStatus.completed,
        created_at=DateObject.today()
    )

    # Act
    result = await repo.update_workflow_instance("test_wf_1", updated_instance_data)

    # Assert
    assert result is not None
    assert result.id == "test_wf_1"
    assert result.name == "Updated Workflow Instance"
    assert result.status == WorkflowStatus.completed

    # Verify in database
    db_instance = db_session.query(WorkflowInstanceORM).filter(WorkflowInstanceORM.id == "test_wf_1").first()
    assert db_instance.name == "Updated Workflow Instance"
    assert db_instance.status == WorkflowStatus.completed

@pytest.mark.asyncio
async def test_update_workflow_instance_not_found(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)
    updated_instance_data = WorkflowInstance(
        id="non_existent_wf",
        workflow_definition_id="test_def_1",
        name="Updated Workflow Instance",
        user_id="test_user",
        status=WorkflowStatus.completed,
        created_at=DateObject.today()
    )

    # Act
    result = await repo.update_workflow_instance("non_existent_wf", updated_instance_data)

    # Assert
    assert result is None

@pytest.mark.asyncio
async def test_list_workflow_instances_by_user(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)
    from app.db_models.workflow import WorkflowInstance as WorkflowInstanceORM
    instance1 = WorkflowInstanceORM(
        id="test_wf_1",
        workflow_definition_id="test_def_1",
        name="Test Instance 1",
        user_id="test_user",
        status=WorkflowStatus.active,
        created_at=DateObject.fromisoformat("2023-01-01")
    )
    instance2 = WorkflowInstanceORM(
        id="test_wf_2",
        workflow_definition_id="test_def_2",
        name="Test Instance 2",
        user_id="test_user",
        status=WorkflowStatus.completed,
        created_at=DateObject.fromisoformat("2023-01-02")
    )
    instance3 = WorkflowInstanceORM(
        id="test_wf_3",
        workflow_definition_id="test_def_3",
        name="Test Instance 3",
        user_id="different_user",
        status=WorkflowStatus.active,
        created_at=DateObject.today()
    )
    db_session.add(instance1)
    db_session.add(instance2)
    db_session.add(instance3)
    db_session.commit()

    # Act
    result = await repo.list_workflow_instances_by_user("test_user")

    # Assert
    assert len(result) == 2
    assert result[0].id == "test_wf_2"  # Ordered by created_at desc
    assert result[1].id == "test_wf_1"
    assert all(instance.user_id == "test_user" for instance in result)

@pytest.mark.asyncio
async def test_create_task_instance(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)
    from app.db_models.workflow import WorkflowInstance as WorkflowInstanceORM
    workflow_instance = WorkflowInstanceORM(
        id="test_wf_1",
        workflow_definition_id="test_def_1",
        name="Test Workflow Instance",
        user_id="test_user",
        status=WorkflowStatus.active,
        created_at=DateObject.today()
    )
    db_session.add(workflow_instance)
    db_session.commit()

    task_data = TaskInstance(
        id="test_task_1",
        workflow_instance_id="test_wf_1",
        name="Test Task",
        order=0,
        status=TaskStatus.pending
    )

    # Act
    created_task = await repo.create_task_instance(task_data)

    # Assert
    assert created_task is not None
    assert created_task.id == "test_task_1"
    assert created_task.workflow_instance_id == "test_wf_1"
    assert created_task.name == "Test Task"
    assert created_task.order == 0
    assert created_task.status == TaskStatus.pending

    # Verify in database
    from app.db_models.task import TaskInstance as TaskInstanceORM
    db_task = db_session.query(TaskInstanceORM).filter(TaskInstanceORM.id == "test_task_1").first()
    assert db_task is not None
    assert db_task.name == "Test Task"
    assert db_task.status == TaskStatus.pending

@pytest.mark.asyncio
async def test_get_tasks_for_workflow_instance(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)
    from app.db_models.workflow import WorkflowInstance as WorkflowInstanceORM
    from app.db_models.task import TaskInstance as TaskInstanceORM
    workflow_instance = WorkflowInstanceORM(
        id="test_wf_1",
        workflow_definition_id="test_def_1",
        name="Test Workflow Instance",
        user_id="test_user",
        status=WorkflowStatus.active,
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
            status=TaskStatus.pending
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
        assert task.status == TaskStatus.pending

@pytest.mark.asyncio
async def test_get_tasks_for_workflow_instance_no_tasks(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)
    from app.db_models.workflow import WorkflowInstance as WorkflowInstanceORM
    workflow_instance = WorkflowInstanceORM(
        id="test_wf_1",
        workflow_definition_id="test_def_1",
        name="Test Workflow Instance",
        user_id="test_user",
        status=WorkflowStatus.active,
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
    from app.db_models.workflow import WorkflowInstance as WorkflowInstanceORM
    from app.db_models.task import TaskInstance as TaskInstanceORM
    workflow_instance = WorkflowInstanceORM(
        id="test_wf_1",
        workflow_definition_id="test_def_1",
        name="Test Workflow Instance",
        user_id="test_user",
        status=WorkflowStatus.active,
        created_at=DateObject.today()
    )
    db_session.add(workflow_instance)
    db_session.commit()

    task = TaskInstanceORM(
        id="test_task_1",
        workflow_instance_id="test_wf_1",
        name="Test Task",
        order=0,
        status=TaskStatus.pending
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
    assert result.status == TaskStatus.pending

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
    from app.db_models.workflow import WorkflowInstance as WorkflowInstanceORM
    from app.db_models.task import TaskInstance as TaskInstanceORM
    workflow_instance = WorkflowInstanceORM(
        id="test_wf_1",
        workflow_definition_id="test_def_1",
        name="Test Workflow Instance",
        user_id="test_user",
        status=WorkflowStatus.active,
        created_at=DateObject.today()
    )
    db_session.add(workflow_instance)
    db_session.commit()

    task = TaskInstanceORM(
        id="test_task_1",
        workflow_instance_id="test_wf_1",
        name="Test Task",
        order=0,
        status=TaskStatus.pending
    )
    db_session.add(task)
    db_session.commit()

    updated_task_data = TaskInstance(
        id="test_task_1",
        workflow_instance_id="test_wf_1",
        name="Updated Test Task",
        order=1,
        status=TaskStatus.completed
    )

    # Act
    result = await repo.update_task_instance("test_task_1", updated_task_data)

    # Assert
    assert result is not None
    assert result.id == "test_task_1"
    assert result.workflow_instance_id == "test_wf_1"
    assert result.name == "Updated Test Task"
    assert result.order == 1
    assert result.status == TaskStatus.completed

    # Verify in database
    db_task = db_session.query(TaskInstanceORM).filter(TaskInstanceORM.id == "test_task_1").first()
    assert db_task.name == "Updated Test Task"
    assert db_task.status == TaskStatus.completed

@pytest.mark.asyncio
async def test_update_task_instance_not_found(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)
    updated_task_data = TaskInstance(
        id="non_existent_task",
        workflow_instance_id="test_wf_1",
        name="Updated Test Task",
        order=1,
        status=TaskStatus.completed
    )

    # Act
    result = await repo.update_task_instance("non_existent_task", updated_task_data)

    # Assert
    assert result is None
