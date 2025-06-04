from datetime import date as DateObject
from unittest.mock import MagicMock

import pytest
from db_models import Base
from db_models import WorkflowInstance as WorkflowInstanceORM
from db_models.enums import WorkflowStatus, TaskStatus
from db_models.workflow import \
    WorkflowDefinition as WorkflowDefinitionORM  # Already imported as part of db_models but good to be explicit for ORM usage
from models import WorkflowDefinition, TaskInstance, WorkflowInstance, TaskDefinitionBase
# Setup for SQLite database for testing
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db_models.task_definition import TaskDefinition as TaskDefinitionORM
from repository import PostgreSQLWorkflowRepository, DefinitionNotFoundError, DefinitionInUseError

# Use in-memory SQLite database for tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, echo=True,
                       connect_args={"check_same_thread": False})  # Added connect_args for SQLite
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


# Imports for InMemoryRepository tests
from repository import InMemoryWorkflowRepository, _workflow_instances_db
from datetime import datetime, timedelta  # datetime was already imported, add timedelta


# Fixture to manage in-memory DB state for InMemoryWorkflowRepository tests
@pytest.fixture(autouse=True)
def clear_in_memory_instance_db_for_tests():  # Renamed to be more specific
    _workflow_instances_db.clear()


class TestInMemoryListWorkflowInstancesByUser:
    # Sample data to be used across tests
    common_user_id = "user_common_mem"  # Changed to avoid potential clashes if tests run weirdly
    other_user_id = "user_other_mem"
    def_id_1 = "def_alpha_mem"
    def_id_2 = "def_beta_mem"

    # Define base instances for reuse, ensure created_at is distinct for sorting tests
    instance_1_user_common_def1_active_today = WorkflowInstance(
        id="inst_mem_1", user_id=common_user_id, workflow_definition_id=def_id_1, name="Mem WF1 Active Today",
        status=WorkflowStatus.active, created_at=(datetime.utcnow() - timedelta(hours=2)).date()
    )
    instance_2_user_common_def2_completed_today = WorkflowInstance(
        id="inst_mem_2", user_id=common_user_id, workflow_definition_id=def_id_2, name="Mem WF2 Completed Today",
        status=WorkflowStatus.completed, created_at=(datetime.utcnow() - timedelta(hours=1)).date()
    )
    instance_3_user_common_def1_active_specific_past = WorkflowInstance(
        id="inst_mem_3", user_id=common_user_id, workflow_definition_id=def_id_1, name="Mem WF3 Active PastDate",
        status=WorkflowStatus.active, created_at=datetime(2023, 1, 1, 10, 0, 0).date()
    )
    instance_4_user_other_def1_active_today = WorkflowInstance(
        id="inst_mem_4", user_id=other_user_id, workflow_definition_id=def_id_1, name="Mem WF4 OtherUser Active Today",
        status=WorkflowStatus.active, created_at=datetime.utcnow().date()
    )
    instance_5_user_common_def1_active_very_recent = WorkflowInstance(
        id="inst_mem_5", user_id=common_user_id, workflow_definition_id=def_id_1, name="Mem WF5 Active Very Recent",
        status=WorkflowStatus.active, created_at=datetime.utcnow().date()  # Most recent for sorting
    )

    @pytest.mark.asyncio
    async def test_list_instances_no_filters_for_user(self):
        _workflow_instances_db[
            self.instance_1_user_common_def1_active_today.id] = self.instance_1_user_common_def1_active_today.model_copy(
            deep=True)
        _workflow_instances_db[
            self.instance_2_user_common_def2_completed_today.id] = self.instance_2_user_common_def2_completed_today.model_copy(
            deep=True)
        _workflow_instances_db[
            self.instance_4_user_other_def1_active_today.id] = self.instance_4_user_other_def1_active_today.model_copy(
            deep=True)

        repo = InMemoryWorkflowRepository()
        # Pass None for filters not being tested
        results = await repo.list_workflow_instances_by_user(user_id=self.common_user_id, created_at_date=None,
                                                             status=None, definition_id=None)

        assert len(results) == 2
        returned_ids = {r.id for r in results}
        assert self.instance_1_user_common_def1_active_today.id in returned_ids
        assert self.instance_2_user_common_def2_completed_today.id in returned_ids

    @pytest.mark.asyncio
    async def test_list_instances_with_definition_id_filter(self):
        _workflow_instances_db[
            self.instance_1_user_common_def1_active_today.id] = self.instance_1_user_common_def1_active_today.model_copy(
            deep=True)
        _workflow_instances_db[
            self.instance_2_user_common_def2_completed_today.id] = self.instance_2_user_common_def2_completed_today.model_copy(
            deep=True)

        repo = InMemoryWorkflowRepository()
        results = await repo.list_workflow_instances_by_user(user_id=self.common_user_id, definition_id=self.def_id_1)

        assert len(results) == 1
        assert results[0].id == self.instance_1_user_common_def1_active_today.id
        assert results[0].workflow_definition_id == self.def_id_1

    @pytest.mark.asyncio
    async def test_list_instances_with_date_filter(self):
        _workflow_instances_db[
            self.instance_1_user_common_def1_active_today.id] = self.instance_1_user_common_def1_active_today.model_copy(
            deep=True)
        _workflow_instances_db[
            self.instance_3_user_common_def1_active_specific_past.id] = self.instance_3_user_common_def1_active_specific_past.model_copy(
            deep=True)

        repo = InMemoryWorkflowRepository()
        specific_past_date = self.instance_3_user_common_def1_active_specific_past.created_at
        results = await repo.list_workflow_instances_by_user(user_id=self.common_user_id,
                                                             created_at_date=specific_past_date)

        assert len(results) == 1
        assert results[0].id == self.instance_3_user_common_def1_active_specific_past.id
        assert results[0].created_at == specific_past_date

    @pytest.mark.asyncio
    async def test_list_instances_with_status_filter(self):
        _workflow_instances_db[
            self.instance_1_user_common_def1_active_today.id] = self.instance_1_user_common_def1_active_today.model_copy(
            deep=True)
        _workflow_instances_db[
            self.instance_2_user_common_def2_completed_today.id] = self.instance_2_user_common_def2_completed_today.model_copy(
            deep=True)

        repo = InMemoryWorkflowRepository()
        results = await repo.list_workflow_instances_by_user(user_id=self.common_user_id,
                                                             status=WorkflowStatus.completed)

        assert len(results) == 1
        assert results[0].id == self.instance_2_user_common_def2_completed_today.id
        assert results[0].status == WorkflowStatus.completed

    @pytest.mark.asyncio
    async def test_list_instances_with_all_filters_including_definition_id(self):
        target_instance_all_filters = WorkflowInstance(
            id="inst_mem_target", user_id=self.common_user_id, workflow_definition_id=self.def_id_1,
            name="Mem Target WF", status=WorkflowStatus.active, created_at=datetime(2023, 1, 15, 12, 0, 0).date()
        )
        _workflow_instances_db[target_instance_all_filters.id] = target_instance_all_filters.model_copy(deep=True)
        _workflow_instances_db[
            self.instance_1_user_common_def1_active_today.id] = self.instance_1_user_common_def1_active_today.model_copy(
            deep=True)
        _workflow_instances_db[
            self.instance_2_user_common_def2_completed_today.id] = self.instance_2_user_common_def2_completed_today.model_copy(
            deep=True)

        repo = InMemoryWorkflowRepository()
        filter_date = DateObject(2023, 1, 15)

        results = await repo.list_workflow_instances_by_user(
            user_id=self.common_user_id,
            created_at_date=filter_date,
            status=WorkflowStatus.active,
            definition_id=self.def_id_1
        )

        assert len(results) == 1
        assert results[0].id == target_instance_all_filters.id
        assert results[0].user_id == self.common_user_id
        assert results[0].created_at == filter_date
        assert results[0].status == WorkflowStatus.active
        assert results[0].workflow_definition_id == self.def_id_1

    @pytest.mark.asyncio
    async def test_list_instances_with_non_existent_definition_id(self):
        _workflow_instances_db[
            self.instance_1_user_common_def1_active_today.id] = self.instance_1_user_common_def1_active_today.model_copy(
            deep=True)

        repo = InMemoryWorkflowRepository()
        results = await repo.list_workflow_instances_by_user(user_id=self.common_user_id,
                                                             definition_id="def_mem_non_existent")

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_list_instances_returns_empty_for_user_with_no_instances(self):
        _workflow_instances_db[
            self.instance_4_user_other_def1_active_today.id] = self.instance_4_user_other_def1_active_today.model_copy(
            deep=True)

        repo = InMemoryWorkflowRepository()
        # common_user_id has no instances seeded for this specific test
        results = await repo.list_workflow_instances_by_user(user_id=self.common_user_id)

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_list_instances_sorting_by_created_at_desc(self):
        # instance_5_user_common_def1_active_very_recent (now)
        # instance_1_user_common_def1_active_today (now - 2 hours)
        # instance_3_user_common_def1_active_specific_past (Jan 1, 2023)

        # Ensure created_at times are what we expect for sorting
        # (Re-create with fresh utcnow if test execution is slow)
        inst1 = self.instance_1_user_common_def1_active_today.model_copy(deep=True)
        inst1.created_at = (datetime.utcnow() - timedelta(days=1)).date()  # Made explicitly one day older
        inst3 = self.instance_3_user_common_def1_active_specific_past.model_copy(
            deep=True)  # Already specific past (e.g. 2023-01-01)
        inst5 = self.instance_5_user_common_def1_active_very_recent.model_copy(deep=True)
        inst5.created_at = datetime.utcnow().date()  # Today, should be newest if test runs on a later date than inst3

        _workflow_instances_db[inst1.id] = inst1
        _workflow_instances_db[inst3.id] = inst3
        _workflow_instances_db[inst5.id] = inst5

        repo = InMemoryWorkflowRepository()
        # Getting all for common_user_id, default status filter (None in repo) might include all if not specified
        # The InMemory repo's list_workflow_instances_by_user filters by user_id first, then others.
        # If status is None, it's not filtered by status.
        results = await repo.list_workflow_instances_by_user(user_id=self.common_user_id, status=WorkflowStatus.active)

        assert len(results) == 3
        assert results[0].id == inst5.id
        assert results[1].id == inst1.id
        assert results[2].id == inst3.id


@pytest.mark.asyncio
async def test_list_workflow_definitions(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)
    # WorkflowDefinitionORM already imported
    defn1_orm = WorkflowDefinitionORM(  # Renamed to avoid confusion with Pydantic model
        id="test_def_1",
        name="Test Workflow 1",
        description="First test workflow"
        # task_names removed
    )
    defn2_orm = WorkflowDefinitionORM(  # Renamed
        id="test_def_2",
        name="Test Workflow 2",
        description="Second test workflow"
        # task_names removed
    )
    db_session.add(defn1_orm)
    db_session.add(defn2_orm)
    db_session.commit()

    # Act
    # This test will be replaced by test_list_workflow_definitions_includes_task_definitions
    # For now, let's comment out the problematic assertions or adapt if simple
    result = await repo.list_workflow_definitions()

    # Assert
    assert len(result) == 2
    assert result[0].id == "test_def_1"
    assert result[1].id == "test_def_2"
    # task_names assertions removed, will be covered by new test
    # assert result[0].task_definitions == [] # Default if not created
    # assert result[1].task_definitions == []


@pytest.mark.asyncio
async def test_get_workflow_definition_by_id(db_session):  # This will be replaced/augmented
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)
    # WorkflowDefinitionORM already imported
    defn_orm = WorkflowDefinitionORM(  # Renamed
        id="test_def_1",
        name="Test Workflow",
        description="A test workflow definition"
        # task_names removed
    )
    db_session.add(defn_orm)
    db_session.commit()

    # Act
    result = await repo.get_workflow_definition_by_id("test_def_1")

    # Assert
    assert result is not None
    assert result.id == "test_def_1"
    assert result.name == "Test Workflow"
    assert result.description == "A test workflow definition"
    # task_names assertion removed, will be covered by new test
    # assert result.task_definitions == [] # Default if not created


@pytest.mark.asyncio
async def test_get_workflow_definition_by_id_includes_task_definitions(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)
    # WorkflowDefinitionORM, TaskDefinitionORM already imported

    defn_orm = WorkflowDefinitionORM(id="test_def_tasks", name="Def With Tasks")
    db_session.add(defn_orm)
    db_session.commit()  # Commit to get ID

    td_orm_1 = TaskDefinitionORM(workflow_definition_id=defn_orm.id, name="Task Alpha", order=0)
    td_orm_2 = TaskDefinitionORM(workflow_definition_id=defn_orm.id, name="Task Beta", order=1)
    db_session.add_all([td_orm_1, td_orm_2])
    db_session.commit()

    # Act
    result = await repo.get_workflow_definition_by_id(defn_orm.id)  # Pydantic model

    # Assert
    assert result is not None
    assert result.id == defn_orm.id
    assert len(result.task_definitions) == 2
    assert result.task_definitions[0].name == "Task Alpha"
    assert result.task_definitions[0].order == 0
    assert result.task_definitions[1].name == "Task Beta"
    assert result.task_definitions[1].order == 1


@pytest.mark.asyncio
async def test_list_workflow_definitions_includes_task_definitions(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)
    # WorkflowDefinitionORM, TaskDefinitionORM already imported

    # Definition 1
    defn1_orm = WorkflowDefinitionORM(id="list_def_1", name="List Def 1")
    db_session.add(defn1_orm)
    db_session.commit()
    td1_1 = TaskDefinitionORM(workflow_definition_id=defn1_orm.id, name="L1T1", order=0)
    td1_2 = TaskDefinitionORM(workflow_definition_id=defn1_orm.id, name="L1T2", order=1)
    db_session.add_all([td1_1, td1_2])

    # Definition 2
    defn2_orm = WorkflowDefinitionORM(id="list_def_2", name="List Def 2")
    db_session.add(defn2_orm)
    db_session.commit()
    td2_1 = TaskDefinitionORM(workflow_definition_id=defn2_orm.id, name="L2T1", order=0)
    db_session.add_all([td2_1])

    db_session.commit()

    # Act
    results = await repo.list_workflow_definitions()  # List of Pydantic models

    # Assert
    assert len(results) == 2

    res1 = next((r for r in results if r.id == defn1_orm.id), None)
    assert res1 is not None
    assert len(res1.task_definitions) == 2
    assert res1.task_definitions[0].name == "L1T1"
    assert res1.task_definitions[0].order == 0
    assert res1.task_definitions[1].name == "L1T2"
    assert res1.task_definitions[1].order == 1

    res2 = next((r for r in results if r.id == defn2_orm.id), None)
    assert res2 is not None
    assert len(res2.task_definitions) == 1
    assert res2.task_definitions[0].name == "L2T1"
    assert res2.task_definitions[0].order == 0


@pytest.mark.asyncio
async def test_get_workflow_definition_by_id_not_found(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)

    # Act
    result = await repo.get_workflow_definition_by_id("non_existent_id")

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_get_tasks_sorted_pending_first_then_order(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)
    from db_models.workflow import WorkflowInstance as WorkflowInstanceORM
    from db_models.task import TaskInstance as TaskInstanceORM
    from db_models.enums import TaskStatus, WorkflowStatus
    from datetime import datetime

    # Create WorkflowInstance
    workflow_instance_id = "wf_sort_test_001"
    workflow_instance_orm = WorkflowInstanceORM(
        id=workflow_instance_id,
        name="Sort Test Workflow Instance",
        user_id="test_user_sort",
        status=WorkflowStatus.active,
        created_at=datetime.utcnow(),  # Use datetime.utcnow() for timestamp
        workflow_definition_id="def_test_sort_tasks"  # Not strictly needed to exist for this test
    )
    db_session.add(workflow_instance_orm)

    # Create TaskInstances
    task_data_list = [
        {
            "id": "task_c1", "name": "Completed Task, Order 1", "order": 1, "status": TaskStatus.completed,
            "workflow_instance_id": workflow_instance_id
        },
        {
            "id": "task_p2", "name": "Pending Task, Order 2", "order": 2, "status": TaskStatus.pending,
            "workflow_instance_id": workflow_instance_id
        },
        {
            "id": "task_c3", "name": "Completed Task, Order 3", "order": 3, "status": TaskStatus.completed,
            "workflow_instance_id": workflow_instance_id
        },
        {
            "id": "task_p4", "name": "Pending Task, Order 4", "order": 4, "status": TaskStatus.pending,
            "workflow_instance_id": workflow_instance_id
        }
    ]

    for task_data in task_data_list:
        task_orm = TaskInstanceORM(**task_data)
        db_session.add(task_orm)

    db_session.commit()

    # Act
    result_tasks = await repo.get_tasks_for_workflow_instance(workflow_instance_id)

    # Assert
    assert len(result_tasks) == 4
    # Expected order:
    # 1. Pending Task, Order 2 (task_p2)
    # 2. Pending Task, Order 4 (task_p4)
    # 3. Completed Task, Order 1 (task_c1)
    # 4. Completed Task, Order 3 (task_c3)

    assert result_tasks[0].name == "Pending Task, Order 2"
    assert result_tasks[0].id == "task_p2"

    assert result_tasks[1].name == "Pending Task, Order 4"
    assert result_tasks[1].id == "task_p4"

    assert result_tasks[2].name == "Completed Task, Order 1"
    assert result_tasks[2].id == "task_c1"

    assert result_tasks[3].name == "Completed Task, Order 3"
    assert result_tasks[3].id == "task_c3"


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
            created_at=datetime(2023, 1, 1, 12, 0, 0).date(),  # Use .date()
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
        # In the updated version, definition_id is None by default, so no extra filter for it.
        assert mock_query_chain.filter.call_count == 1  # Only user_id filter initially

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
        test_definition_id = "def_all"  # New
        await repo.list_workflow_instances_by_user(user_id="user123", created_at_date=test_date, status=test_status,
                                                   definition_id=test_definition_id)

        # Assertions
        # filter calls: user_id, then created_at, then status, then definition_id
        assert mock_query_chain.filter.call_count == 4  # Updated
        user_id_filter_call = mock_query_chain.filter.call_args_list[0]
        created_at_filter_call = mock_query_chain.filter.call_args_list[1]
        status_filter_call = mock_query_chain.filter.call_args_list[2]
        definition_id_filter_call = mock_query_chain.filter.call_args_list[3]  # New

        assert str(user_id_filter_call[0][0]) == str(WorkflowInstanceORM.user_id == "user123")
        assert str(created_at_filter_call[0][0]) == str(WorkflowInstanceORM.created_at == test_date)
        assert str(status_filter_call[0][0]) == str(WorkflowInstanceORM.status == test_status)
        assert str(definition_id_filter_call[0][0]) == str(
            WorkflowInstanceORM.workflow_definition_id == test_definition_id)  # New
        mock_query_chain.order_by.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_with_definition_id_filter(self):
        mock_db_session = MagicMock()
        mock_query_chain = MagicMock()
        mock_db_session.query.return_value = mock_query_chain
        mock_query_chain.filter.return_value = mock_query_chain
        mock_query_chain.order_by.return_value = mock_query_chain
        mock_query_chain.all.return_value = []

        repo = PostgreSQLWorkflowRepository(db_session=mock_db_session)
        test_definition_id = "def_abc"
        await repo.list_workflow_instances_by_user(user_id="user123", definition_id=test_definition_id)

        # Assertions
        # filter calls: user_id filter, then definition_id filter
        assert mock_query_chain.filter.call_count == 2
        user_id_filter_call = mock_query_chain.filter.call_args_list[0]
        definition_id_filter_call = mock_query_chain.filter.call_args_list[1]

        assert str(user_id_filter_call[0][0]) == str(WorkflowInstanceORM.user_id == "user123")
        assert str(definition_id_filter_call[0][0]) == str(
            WorkflowInstanceORM.workflow_definition_id == test_definition_id)
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
            status=WorkflowStatus.active, created_at=datetime(2023, 1, 2, 12, 0, 0).date(),  # Use .date()
            workflow_definition_id="def2"
        )
        mock_query_chain.all.return_value = [mock_orm_instance]

        repo = PostgreSQLWorkflowRepository(db_session=mock_db_session)
        test_date = DateObject(2023, 7, 1)
        test_status = WorkflowStatus.active  # Changed from .pending to a valid status
        test_definition_id = "def_iso"

        results = await repo.list_workflow_instances_by_user(
            user_id="isolated_user",
            created_at_date=test_date,
            status=test_status,
            definition_id=test_definition_id
        )

        mock_db_session.query.assert_called_once_with(WorkflowInstanceORM)

        # Ensure the very first filter applied is for the user_id
        assert mock_query_chain.filter.call_count == 4  # user_id, created_at, status, definition_id
        first_filter_call_arg = mock_query_chain.filter.call_args_list[0][0][0]
        assert str(first_filter_call_arg) == str(WorkflowInstanceORM.user_id == "isolated_user")

        # Check other filters are also applied
        second_filter_call_arg = mock_query_chain.filter.call_args_list[1][0][0]
        assert str(second_filter_call_arg) == str(WorkflowInstanceORM.created_at == test_date)

        third_filter_call_arg = mock_query_chain.filter.call_args_list[2][0][0]
        assert str(third_filter_call_arg) == str(WorkflowInstanceORM.status == test_status)

        fourth_filter_call_arg = mock_query_chain.filter.call_args_list[3][0][0]
        assert str(fourth_filter_call_arg) == str(WorkflowInstanceORM.workflow_definition_id == test_definition_id)

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
    definition_data = WorkflowDefinition(  # Pydantic model
        id="test_def_1",
        name="Test Workflow",
        description="A test workflow",
        task_definitions=[  # Changed from task_names
            TaskDefinitionBase(name="Task 1", order=0),
            TaskDefinitionBase(name="Task 2", order=1)
        ]
    )

    # Act
    created_definition = await repo.create_workflow_definition(definition_data)

    # Assert
    assert created_definition is not None
    assert created_definition.id == "test_def_1"
    assert created_definition.name == "Test Workflow"
    assert created_definition.description == "A test workflow"
    assert len(created_definition.task_definitions) == 2
    assert created_definition.task_definitions[0].name == "Task 1"
    assert created_definition.task_definitions[0].order == 0
    assert created_definition.task_definitions[1].name == "Task 2"
    assert created_definition.task_definitions[1].order == 1

    # Verify in database
    # WorkflowDefinitionORM already imported
    db_defn_orm = db_session.query(WorkflowDefinitionORM).filter(WorkflowDefinitionORM.id == "test_def_1").first()
    assert db_defn_orm is not None
    assert db_defn_orm.name == "Test Workflow"
    # Query TaskDefinitionORM objects
    task_defs_orm = db_session.query(TaskDefinitionORM).filter(
        TaskDefinitionORM.workflow_definition_id == db_defn_orm.id).order_by(TaskDefinitionORM.order).all()
    assert len(task_defs_orm) == 2
    assert task_defs_orm[0].name == "Task 1"
    assert task_defs_orm[0].order == 0
    assert task_defs_orm[1].name == "Task 2"
    assert task_defs_orm[1].order == 1


@pytest.mark.asyncio
async def test_update_workflow_definition(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)
    # WorkflowDefinitionORM, TaskDefinitionORM already imported

    # Initial WorkflowDefinitionORM
    initial_defn_orm = WorkflowDefinitionORM(
        id="test_def_1",
        name="Original Workflow",
        description="Original description"
    )
    db_session.add(initial_defn_orm)
    db_session.commit()  # Commit to get ID

    # Initial TaskDefinitionORM objects
    initial_task_def1_orm = TaskDefinitionORM(workflow_definition_id=initial_defn_orm.id, name="Original Task 1",
                                              order=0)
    initial_task_def2_orm = TaskDefinitionORM(workflow_definition_id=initial_defn_orm.id, name="Original Task 2",
                                              order=1)
    db_session.add_all([initial_task_def1_orm, initial_task_def2_orm])
    db_session.commit()

    updated_task_definitions_data = [  # List[TaskDefinitionBase]
        TaskDefinitionBase(name="Updated Task A", order=0),
        TaskDefinitionBase(name="Updated Task B", order=1)
    ]

    # Act
    result = await repo.update_workflow_definition(  # Pydantic model result
        definition_id="test_def_1",
        name="Updated Workflow",
        description="Updated description",
        task_definitions_data=updated_task_definitions_data
    )

    # Assert Pydantic model (result)
    assert result is not None
    assert result.id == "test_def_1"
    assert result.name == "Updated Workflow"
    assert result.description == "Updated description"
    assert len(result.task_definitions) == 2
    assert result.task_definitions[0].name == "Updated Task A"
    assert result.task_definitions[0].order == 0
    assert result.task_definitions[1].name == "Updated Task B"
    assert result.task_definitions[1].order == 1

    # Verify in database
    db_session.refresh(initial_defn_orm)  # Refresh the instance
    assert initial_defn_orm.name == "Updated Workflow"

    # Query new TaskDefinitionORM objects
    task_defs_orm = db_session.query(TaskDefinitionORM).filter(
        TaskDefinitionORM.workflow_definition_id == initial_defn_orm.id).order_by(TaskDefinitionORM.order).all()
    assert len(task_defs_orm) == 2
    assert task_defs_orm[0].name == "Updated Task A"
    assert task_defs_orm[0].order == 0
    assert task_defs_orm[1].name == "Updated Task B"
    assert task_defs_orm[1].order == 1

    # Ensure old tasks with "Original Task" names are gone (by checking current names)
    original_task_names_in_db = [td.name for td in task_defs_orm if "Original Task" in td.name]
    assert not original_task_names_in_db


@pytest.mark.asyncio
async def test_update_workflow_definition_not_found(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)

    # Act
    result = await repo.update_workflow_definition(
        definition_id="non_existent_id",
        name="Updated Workflow",
        description="Updated description",
        # This method now expects List[TaskDefinitionBase]
        task_definitions_data=[TaskDefinitionBase(name="Updated Task 1", order=0)]
    )

    # Assert
    assert result is None


@pytest.mark.asyncio
async def test_delete_workflow_definition(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)
    # WorkflowDefinitionORM already imported
    defn_orm = WorkflowDefinitionORM(  # Renamed
        id="test_def_1",
        name="Test Workflow",
        description="A test workflow"
        # task_names removed
    )
    db_session.add(defn_orm)
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
    # WorkflowDefinitionORM, WorkflowInstanceORM already imported
    defn_orm = WorkflowDefinitionORM(  # Renamed
        id="test_def_1",
        name="Test Workflow",
        description="A test workflow"
        # task_names removed
    )
    db_session.add(defn_orm)
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
    # WorkflowDefinitionORM, WorkflowInstanceORM already imported
    definition_orm = WorkflowDefinitionORM(  # Renamed
        id="test_def_1",
        name="Test Workflow",
        description="A test workflow definition"
        # task_names removed
    )
    db_session.add(definition_orm)
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
    # WorkflowDefinitionORM already imported
    definition_orm = WorkflowDefinitionORM(  # Renamed
        id="test_def_1",
        name="Test Workflow",
        description="A test workflow"
        # task_names removed
    )
    db_session.add(definition_orm)
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
    from db_models.workflow import WorkflowInstance as WorkflowInstanceORM
    db_instance = db_session.query(WorkflowInstanceORM).filter(WorkflowInstanceORM.id == "test_wf_1").first()
    assert db_instance is not None
    assert db_instance.user_id == "test_user"
    assert db_instance.status == WorkflowStatus.active


@pytest.mark.asyncio
async def test_update_workflow_instance(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)
    # WorkflowDefinitionORM, WorkflowInstanceORM already imported
    definition_orm = WorkflowDefinitionORM(  # Renamed
        id="test_def_1",
        name="Test Workflow",
        description="A test workflow definition"
        # task_names removed
    )
    db_session.add(definition_orm)
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
    # WorkflowDefinitionORM, WorkflowInstanceORM already imported
    def1_orm = WorkflowDefinitionORM(  # Renamed
        id="test_def_1",
        name="Test Workflow 1",
        description="First test workflow"
        # task_names removed
    )
    def2_orm = WorkflowDefinitionORM(  # Renamed
        id="test_def_2",
        name="Test Workflow 2",
        description="Second test workflow"
        # task_names removed
    )
    def3_orm = WorkflowDefinitionORM(  # Renamed
        id="test_def_3",
        name="Test Workflow 3",
        description="Third test workflow"
        # task_names removed
    )
    db_session.add(def1_orm)
    db_session.add(def2_orm)
    db_session.add(def3_orm)
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
    # Test without definition_id filter first (existing behavior)
    result_all_for_user = await repo.list_workflow_instances_by_user("test_user")

    # Assert
    assert len(result_all_for_user) == 2
    assert result_all_for_user[0].id == "test_wf_2"  # Ordered by created_at desc
    assert result_all_for_user[1].id == "test_wf_1"
    assert all(instance.user_id == "test_user" for instance in result_all_for_user)

    # Act: Test with definition_id filter
    result_filtered_by_def1 = await repo.list_workflow_instances_by_user("test_user", definition_id="test_def_1")

    # Assert: Only instance1 should be returned
    assert len(result_filtered_by_def1) == 1
    assert result_filtered_by_def1[0].id == "test_wf_1"
    assert result_filtered_by_def1[0].workflow_definition_id == "test_def_1"

    # Act: Test with a definition_id that has no instances for this user
    result_filtered_by_def3 = await repo.list_workflow_instances_by_user("test_user", definition_id="test_def_3")
    # Assert: Should be empty as instance3 belongs to "different_user"
    assert len(result_filtered_by_def3) == 0

    # Act: Test with a definition_id that exists but has no instances for ANY user (if we created such a def)
    # For this test, let's assume test_def_4 is a valid definition ID but no instances use it.
    # We need to create such a definition for this to be a valid test against the DB.
    def4_orm = WorkflowDefinitionORM(id="test_def_4", name="Unused Def")  # task_names removed, Renamed
    db_session.add(def4_orm)
    db_session.commit()
    result_filtered_by_unused_def = await repo.list_workflow_instances_by_user("test_user", definition_id="test_def_4")
    assert len(result_filtered_by_unused_def) == 0


@pytest.mark.asyncio
async def test_create_task_instance(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)
    # WorkflowDefinitionORM, WorkflowInstanceORM already imported
    definition_orm = WorkflowDefinitionORM(  # Renamed
        id="test_def_1",
        name="Test Workflow",
        description="A test workflow"
        # task_names removed
    )
    db_session.add(definition_orm)
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
    from db_models.task import TaskInstance as TaskInstanceORM
    db_task = db_session.query(TaskInstanceORM).filter(TaskInstanceORM.id == "test_task_1").first()
    assert db_task is not None
    assert db_task.name == "Test Task"
    assert db_task.status == TaskStatus.pending


@pytest.mark.asyncio
async def test_get_tasks_for_workflow_instance(db_session):
    # Arrange
    repo = PostgreSQLWorkflowRepository(db_session)
    from db_models.task import TaskInstance as TaskInstanceORM  # Import TaskInstanceORM
    # WorkflowDefinitionORM, WorkflowInstanceORM, TaskInstanceORM already imported
    definition_orm = WorkflowDefinitionORM(  # Renamed
        id="test_def_1",
        name="Test Workflow",
        description="A test workflow"
        # task_names removed
    )
    db_session.add(definition_orm)
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
    # WorkflowDefinitionORM, WorkflowInstanceORM already imported
    definition_orm = WorkflowDefinitionORM(  # Renamed
        id="test_def_1",
        name="Test Workflow",
        description="A test workflow"
        # task_names removed
    )
    db_session.add(definition_orm)
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
    from db_models.task import TaskInstance as TaskInstanceORM  # Import TaskInstanceORM
    # WorkflowDefinitionORM, WorkflowInstanceORM, TaskInstanceORM already imported
    definition_orm = WorkflowDefinitionORM(  # Renamed
        id="test_def_1",
        name="Test Workflow",
        description="A test workflow"
        # task_names removed
    )
    db_session.add(definition_orm)
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
    from db_models.task import TaskInstance as TaskInstanceORM  # Import TaskInstanceORM
    # WorkflowDefinitionORM, WorkflowInstanceORM, TaskInstanceORM already imported
    definition_orm = WorkflowDefinitionORM(  # Renamed
        id="test_def_1",
        name="Test Workflow",
        description="A test workflow"
        # task_names removed
    )
    db_session.add(definition_orm)
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
