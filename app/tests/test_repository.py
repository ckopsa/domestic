import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base
from app.repository import PostgreSQLWorkflowRepository
from app.models import WorkflowDefinition

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
