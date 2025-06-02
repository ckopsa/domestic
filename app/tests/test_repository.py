import os
import sys
from datetime import date as DateObject

import pytest

# Add the project root to sys.path to ensure 'app' module can be found
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from app.db_models import Base
from app.repository import PostgreSQLWorkflowRepository, DefinitionNotFoundError, DefinitionInUseError
from app.models import WorkflowDefinition, TaskInstance, WorkflowInstance
from app.db_models.enums import WorkflowStatus, TaskStatus
from app.db_models import WorkflowInstance as WorkflowInstanceORM

from unittest.mock import MagicMock
# Setup for PostgreSQL database for testing
# Use environment variables or a test-specific configuration for the database connection
from datetime import datetime  # Added for mock ORM objects
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.config import DB_USER, DB_PASS, DB_HOST, DB_PORT, DB_NAME

# Construct the test database URL, appending '_test' to the database name to avoid using the main DB
TEST_DB_NAME = f"{DB_NAME}_test"
# First connect to 'postgres' database to create the test database if it doesn't exist
BASE_DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/postgres"
base_engine = create_engine(BASE_DATABASE_URL, echo=True)
with base_engine.connect() as conn:
    conn.execute(text("COMMIT"))
    # Check if the test database exists, create if it doesn't
    result = conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname = '{TEST_DB_NAME}'"))
    if not result.fetchone():
        conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))
        print(f"Created test database: {TEST_DB_NAME}")
    else:
        print(f"Test database {TEST_DB_NAME} already exists")

base_engine.dispose()

# Now connect to the test database
SQLALCHEMY_DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{TEST_DB_NAME}"
engine = create_engine(SQLALCHEMY_DATABASE_URL, echo=True)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    # Create the test database tables
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.rollback()  # Rollback any changes to ensure a clean state
    session.close()
    # Optionally drop tables after tests if needed, though this can be slow
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


# Unit tests for PostgreSQLWorkflowRepository.list_workflow_instances_by_user
# These tests will mock the db_session and verify query construction
class TestUnitPostgreSQLListWorkflowInstancesByUser:

    @pytest.mark.asyncio
    async def test_list_without_filters(self):
        mock_db_session = MagicMock()
        mock_query_chain = MagicMock()

        # Configure the chain of mocks
        mock_db_session.query.return_value = mock_query_chain
        mock_query_chain.filter.return_value = mock_query_chain
        mock_query_chain.order_by.return_value = mock_query_chain

        # Mock ORM instance data
        mock_orm_instance = WorkflowInstanceORM(
            id="wf1",
            user_id="user123",
            name="Test Workflow Instance",
            status=WorkflowStatus.active,
            created_at=datetime(2023, 1, 1, 12, 0, 0),
            workflow_definition_id="def1"
        )
        mock_query_chain.all.return_value = [mock_orm_instance]

        repo = PostgreSQLWorkflowRepository(db_session=mock_db_session)
        results = await repo.list_workflow_instances_by_user(user_id="user123")

        # Assertions
        mock_db_session.query.assert_called_once_with(WorkflowInstanceORM)

        # Check filter calls
        # The first filter is for user_id
        # No other filters should be applied for this test case
        # We need to inspect the calls to mock_query_chain.filter
        # call_args_list[0] should be the user_id filter
        # and there should be only one call to filter in this specific scenario setup (before order_by)
        # However, the implementation applies filters sequentially.

        # Let's verify the structure of the calls.
        # The actual filter calls are on the instance returned by query.filter().filter()...
        # So, mock_query_chain.filter is called.

        # First call to filter is for user_id
        actual_call = mock_query_chain.filter.call_args_list[0]
        # The argument to filter is a SQLAlchemy binary expression.
        # We need to compare its string representation or structure.
        # This is the tricky part with SQLAlchemy expressions.
        # For now, let's check it was called. A more robust check would compare the expression.
        assert str(actual_call[0][0]) == str(WorkflowInstanceORM.user_id == "user123")
        assert mock_query_chain.filter.call_count == 1  # Only user_id filter

        # Ensure order_by is called correctly
        # This also involves comparing SQLAlchemy expressions.
        # WorkflowInstanceORM.created_at.desc()
        mock_query_chain.order_by.assert_called_once()
        order_by_call_arg = mock_query_chain.order_by.call_args[0][0]
        assert str(order_by_call_arg) == str(WorkflowInstanceORM.created_at.desc())

        mock_query_chain.all.assert_called_once()

        assert len(results) == 1
        assert isinstance(results[0], WorkflowInstance)
        assert results[0].id == "wf1"
        assert results[0].user_id == "user123"

    @pytest.mark.asyncio
    async def test_list_with_created_at_filter(self):
        mock_db_session = MagicMock()
        mock_query_chain = MagicMock()
        mock_db_session.query.return_value = mock_query_chain
        mock_query_chain.filter.return_value = mock_query_chain
        mock_query_chain.order_by.return_value = mock_query_chain
        mock_query_chain.all.return_value = []  # Actual data not important for filter assertion

        repo = PostgreSQLWorkflowRepository(db_session=mock_db_session)
        test_date = DateObject(2023, 5, 15)
        await repo.list_workflow_instances_by_user(user_id="user123", created_at_date=test_date)

        # Assertions
        # filter calls: user_id filter, then created_at filter
        assert mock_query_chain.filter.call_count == 2
        user_id_filter_call = mock_query_chain.filter.call_args_list[0]
        created_at_filter_call = mock_query_chain.filter.call_args_list[1]

        assert str(user_id_filter_call[0][0]) == str(WorkflowInstanceORM.user_id == "user123")
        assert str(created_at_filter_call[0][0]) == str(WorkflowInstanceORM.created_at == test_date)
        mock_query_chain.order_by.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_with_status_filter(self):
        mock_db_session = MagicMock()
        mock_query_chain = MagicMock()
        mock_db_session.query.return_value = mock_query_chain
        mock_query_chain.filter.return_value = mock_query_chain
        mock_query_chain.order_by.return_value = mock_query_chain
        mock_query_chain.all.return_value = []

        repo = PostgreSQLWorkflowRepository(db_session=mock_db_session)
        test_status = WorkflowStatus.completed
        await repo.list_workflow_instances_by_user(user_id="user123", status=test_status)

        # Assertions
        # filter calls: user_id filter, then status filter
        assert mock_query_chain.filter.call_count == 2
        user_id_filter_call = mock_query_chain.filter.call_args_list[0]
        status_filter_call = mock_query_chain.filter.call_args_list[1]

        assert str(user_id_filter_call[0][0]) == str(WorkflowInstanceORM.user_id == "user123")
        assert str(status_filter_call[0][0]) == str(WorkflowInstanceORM.status == test_status)
        mock_query_chain.order_by.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_with_all_filters(self):
        mock_db_session = MagicMock()
        mock_query_chain = MagicMock()
        mock_db_session.query.return_value = mock_query_chain
        mock_query_chain.filter.return_value = mock_query_chain
        mock_query_chain.order_by.return_value = mock_query_chain
        mock_query_chain.all.return_value = []

        repo = PostgreSQLWorkflowRepository(db_session=mock_db_session)
        test_date = DateObject(2023, 6, 20)
        test_status = WorkflowStatus.active
        await repo.list_workflow_instances_by_user(user_id="user123", created_at_date=test_date, status=test_status)

        # Assertions
        # filter calls: user_id, then created_at, then status
        assert mock_query_chain.filter.call_count == 3
        user_id_filter_call = mock_query_chain.filter.call_args_list[0]
        created_at_filter_call = mock_query_chain.filter.call_args_list[1]
        status_filter_call = mock_query_chain.filter.call_args_list[2]

        assert str(user_id_filter_call[0][0]) == str(WorkflowInstanceORM.user_id == "user123")
        assert str(created_at_filter_call[0][0]) == str(WorkflowInstanceORM.created_at == test_date)
        assert str(status_filter_call[0][0]) == str(WorkflowInstanceORM.status == test_status)
        mock_query_chain.order_by.assert_called_once()

    @pytest.mark.asyncio
    async def test_user_isolation_with_filters(self):
        # This test ensures the user_id filter is always primary.
        # It's effectively covered by asserting the first filter call in other tests,
        # but we can make it explicit.
        mock_db_session = MagicMock()
        mock_query_chain = MagicMock()
        mock_db_session.query.return_value = mock_query_chain
        mock_query_chain.filter.return_value = mock_query_chain  # filter returns itself
        mock_query_chain.order_by.return_value = mock_query_chain

        mock_orm_instance = WorkflowInstanceORM(
            id="wf2", user_id="isolated_user", name="Isolated Workflow",
            status=WorkflowStatus.active, created_at=datetime(2023, 1, 2, 12, 0, 0), workflow_definition_id="def2"
        )
        mock_query_chain.all.return_value = [mock_orm_instance]

        repo = PostgreSQLWorkflowRepository(db_session=mock_db_session)
        test_date = DateObject(2023, 7, 1)
        test_status = WorkflowStatus.pending

        results = await repo.list_workflow_instances_by_user(
            user_id="isolated_user",
            created_at_date=test_date,
            status=test_status
        )

        mock_db_session.query.assert_called_once_with(WorkflowInstanceORM)

        # Ensure the very first filter applied is for the user_id
        assert mock_query_chain.filter.call_count == 3  # user_id, created_at, status
        first_filter_call_arg = mock_query_chain.filter.call_args_list[0][0][0]
        assert str(first_filter_call_arg) == str(WorkflowInstanceORM.user_id == "isolated_user")

        # Check other filters are also applied
        second_filter_call_arg = mock_query_chain.filter.call_args_list[1][0][0]
        assert str(second_filter_call_arg) == str(WorkflowInstanceORM.created_at == test_date)

        third_filter_call_arg = mock_query_chain.filter.call_args_list[2][0][0]
        assert str(third_filter_call_arg) == str(WorkflowInstanceORM.status == test_status)

        mock_query_chain.order_by.assert_called_once()

        assert len(results) == 1
        assert results[0].id == "wf2"
        assert results[0].user_id == "isolated_user"

    @pytest.mark.asyncio
    async def test_returns_empty_list_if_no_matches(self):
        mock_db_session = MagicMock()
        mock_query_chain = MagicMock()
        mock_db_session.query.return_value = mock_query_chain
        mock_query_chain.filter.return_value = mock_query_chain
        mock_query_chain.order_by.return_value = mock_query_chain
        mock_query_chain.all.return_value = []  # No ORM objects returned

        repo = PostgreSQLWorkflowRepository(db_session=mock_db_session)
        results = await repo.list_workflow_instances_by_user(user_id="user_with_no_workflows")

        assert results == []
        mock_db_session.query.assert_called_once_with(WorkflowInstanceORM)
        mock_query_chain.filter.assert_called_once()  # User ID filter
        mock_query_chain.order_by.assert_called_once()
        mock_query_chain.all.assert_called_once()


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
    db_session.add(defn)
    db_session.commit()

    instance = WorkflowInstanceORM(
        id="test_wf_1",
        workflow_definition_id="test_def_1",
        name="Test Instance",
        user_id="test_user",
        status=WorkflowStatus.active,
        created_at=DateObject.today()
    )
    db_session.add(instance)
    db_session.commit()

    # Act & Assert
    with pytest.raises(DefinitionInUseError,
                       match="Cannot delete definition: It is currently used by 1 workflow instance\\(s\\)."):
        await repo.delete_workflow_definition("test_def_1")


@pytest.mark.asyncio
async def test_get_workflow_instance_by_id(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)
    from app.db_models.workflow import WorkflowDefinition as WorkflowDefinitionORM
    from app.db_models.workflow import WorkflowInstance as WorkflowInstanceORM
    definition = WorkflowDefinitionORM(
        id="test_def_1",
        name="Test Workflow",
        description="A test workflow definition",
        task_names=["Task 1", "Task 2"]
    )
    db_session.add(definition)
    db_session.commit()

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
    from app.db_models.workflow import WorkflowDefinition as WorkflowDefinitionORM
    definition = WorkflowDefinitionORM(
        id="test_def_1",
        name="Test Workflow",
        description="A test workflow",
        task_names=["Task 1", "Task 2"]
    )
    db_session.add(definition)
    db_session.commit()

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
    from app.db_models.workflow import WorkflowDefinition as WorkflowDefinitionORM
    from app.db_models.workflow import WorkflowInstance as WorkflowInstanceORM
    definition = WorkflowDefinitionORM(
        id="test_def_1",
        name="Test Workflow",
        description="A test workflow definition",
        task_names=["Task 1", "Task 2"]
    )
    db_session.add(definition)
    db_session.commit()

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
    from app.db_models.workflow import WorkflowDefinition as WorkflowDefinitionORM
    from app.db_models.workflow import WorkflowInstance as WorkflowInstanceORM
    def1 = WorkflowDefinitionORM(
        id="test_def_1",
        name="Test Workflow 1",
        description="First test workflow",
        task_names=["Task 1", "Task 2"]
    )
    def2 = WorkflowDefinitionORM(
        id="test_def_2",
        name="Test Workflow 2",
        description="Second test workflow",
        task_names=["Task 3", "Task 4"]
    )
    def3 = WorkflowDefinitionORM(
        id="test_def_3",
        name="Test Workflow 3",
        description="Third test workflow",
        task_names=["Task 5", "Task 6"]
    )
    db_session.add(def1)
    db_session.add(def2)
    db_session.add(def3)
    db_session.commit()

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
    from app.db_models.workflow import WorkflowDefinition as WorkflowDefinitionORM
    from app.db_models.workflow import WorkflowInstance as WorkflowInstanceORM
    definition = WorkflowDefinitionORM(
        id="test_def_1",
        name="Test Workflow",
        description="A test workflow",
        task_names=["Task 1", "Task 2"]
    )
    db_session.add(definition)
    db_session.commit()

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
    from app.db_models.workflow import WorkflowDefinition as WorkflowDefinitionORM
    from app.db_models.workflow import WorkflowInstance as WorkflowInstanceORM
    from app.db_models.task import TaskInstance as TaskInstanceORM
    definition = WorkflowDefinitionORM(
        id="test_def_1",
        name="Test Workflow",
        description="A test workflow",
        task_names=["Task 1", "Task 2"]
    )
    db_session.add(definition)
    db_session.commit()

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
    from app.db_models.workflow import WorkflowDefinition as WorkflowDefinitionORM
    from app.db_models.workflow import WorkflowInstance as WorkflowInstanceORM
    definition = WorkflowDefinitionORM(
        id="test_def_1",
        name="Test Workflow",
        description="A test workflow",
        task_names=["Task 1", "Task 2"]
    )
    db_session.add(definition)
    db_session.commit()

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
    from app.db_models.workflow import WorkflowDefinition as WorkflowDefinitionORM
    from app.db_models.workflow import WorkflowInstance as WorkflowInstanceORM
    from app.db_models.task import TaskInstance as TaskInstanceORM
    definition = WorkflowDefinitionORM(
        id="test_def_1",
        name="Test Workflow",
        description="A test workflow",
        task_names=["Task 1", "Task 2"]
    )
    db_session.add(definition)
    db_session.commit()

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
    from app.db_models.workflow import WorkflowDefinition as WorkflowDefinitionORM
    from app.db_models.workflow import WorkflowInstance as WorkflowInstanceORM
    from app.db_models.task import TaskInstance as TaskInstanceORM
    definition = WorkflowDefinitionORM(
        id="test_def_1",
        name="Test Workflow",
        description="A test workflow",
        task_names=["Task 1", "Task 2"]
    )
    db_session.add(definition)
    db_session.commit()

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
