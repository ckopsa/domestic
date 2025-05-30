import pytest
import sys
import os

# Add the project root to sys.path to ensure 'app' module can be found
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db_models import Base
from app.repository import PostgreSQLWorkflowRepository
from app.services import WorkflowService
from app.db_models import WorkflowDefinition, WorkflowInstance

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
async def test_create_workflow_instance(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)
    service = WorkflowService(repo)
    # Add a workflow definition to the database
    from app.db_models.workflow import WorkflowDefinition as WorkflowDefinitionORM
    defn = WorkflowDefinitionORM(
        id="test_def_1",
        name="Test Workflow",
        description="A test workflow definition",
        task_names='["Task 1", "Task 2"]'
    )
    db_session.add(defn)
    db_session.commit()

    # Act
    instance = await service.create_workflow_instance("test_def_1", user_id="test_user")

    # Assert
    assert instance is not None
    assert instance.workflow_definition_id == "test_def_1"
    assert instance.name == "Test Workflow"
    assert instance.user_id == "test_user"
    assert instance.status == "active"
    # Check if tasks are created
    tasks = await repo.get_tasks_for_workflow_instance(instance.id)
    assert len(tasks) == 2
    assert tasks[0].name == "Task 1"
    assert tasks[1].name == "Task 2"
