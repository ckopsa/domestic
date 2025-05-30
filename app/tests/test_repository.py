import pytest
from datetime import date as DateObject
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base
from app.repository import PostgreSQLWorkflowRepository
from app.models import WorkflowDefinition, TaskInstance

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
