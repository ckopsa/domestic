import asyncio
import unittest
import uuid
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from sqlalchemy import text

from core.security import AuthenticatedUser
from db_models.enums import TaskStatus, WorkflowStatus
from main import app
from services import WorkflowService


class WorkflowsIntegrationTestCase(IsolatedAsyncioTestCase):
    client: TestClient
    workflow_service: WorkflowService
    mock_authenticated_user: AuthenticatedUser

    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        from repository import PostgreSQLWorkflowRepository
        from database import SessionLocal
        from core.security import get_current_user

        cls.db_session = SessionLocal()
        cls.workflow_repository = PostgreSQLWorkflowRepository(cls.db_session)
        cls.workflow_service = WorkflowService(
            definition_repo=cls.workflow_repository,
            instance_repo=cls.workflow_repository,
            task_repo=cls.workflow_repository
        )
        cls.mock_authenticated_user = AuthenticatedUser(
            user_id="test_user_id",
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            disabled=False
        )
        app.dependency_overrides[get_current_user] = lambda: cls.mock_authenticated_user
        asyncio.run(cls.asyncSetUpClass())

    @classmethod
    async def asyncSetUpClass(cls):
        # Clean up database before tests
        await cls.cleanup_database()

    @classmethod
    async def cleanup_database(cls):
        cls.db_session.execute(text("DELETE FROM task_instances"))
        cls.db_session.execute(text("DELETE FROM workflow_instances"))
        cls.db_session.execute(text("DELETE FROM task_definitions"))
        cls.db_session.execute(text("DELETE FROM workflow_definitions"))
        cls.db_session.commit()

    @classmethod
    async def asyncTearDownClass(cls):
        cls.db_session.close()
        app.dependency_overrides = {}

    async def asyncTearDown(self) -> None:
        await self.cleanup_database()

    @patch('core.security.get_current_user')
    async def test_e2e_workflow_definition_creation_and_view(self, mock_get_current_user: MagicMock):
        mock_get_current_user.return_value = self.mock_authenticated_user

        # 1. Test simple_create_workflow_definition (POST /workflow-definitions/-simpleForm)
        definition_name = f"My Test Workflow {uuid.uuid4()}"
        definition_description = "A workflow for testing purposes."
        task_definitions_str = "Task 1\nTask 2\nTask 3"

        response = self.client.post(
            "/workflow-definitions-simpleForm",
            data={
                "name": definition_name,
                "description": definition_description,
                "task_definitions": task_definitions_str
            },
            follow_redirects=False
        )
        self.assertEqual(303, response.status_code, response.text)
        redirect_url = response.headers["location"]
        from urllib.parse import urlparse
        parsed_url = urlparse(redirect_url)
        self.assertTrue(parsed_url.path.startswith("/workflow-definitions/def_"))

        definition_id = redirect_url.split("/")[-1]

        # 2. Test get_workflow_definitions (GET /workflow-definitions/)
        response = self.client.get("/workflow-definitions/")
        self.assertEqual(200, response.status_code, response.text)
        self.assertIn(definition_name, response.text)

        # 3. Test view_workflow_definition (GET /workflow-definitions/{definition_id})
        response = self.client.get(f"/workflow-definitions/{definition_id}")
        self.assertEqual(200, response.status_code, response.text)
        self.assertIn(definition_name, response.text)
        self.assertIn("Task 1", response.text)
        self.assertIn("Task 2", response.text)
        self.assertIn("Task 3", response.text)

    @patch('core.security.get_current_user')
    async def test_e2e_workflow_instance_creation_and_management(self, mock_get_current_user: MagicMock):
        mock_get_current_user.return_value = self.mock_authenticated_user

        # Create a workflow definition first
        definition_name = f"Instance Test Workflow {uuid.uuid4()}"
        task_definitions_str = "Instance Task 1\nInstance Task 2"
        response = self.client.post(
            "/workflow-definitions-simpleForm",
            data={
                "name": definition_name,
                "description": "Description for instance test",
                "task_definitions": task_definitions_str
            },
            follow_redirects=False
        )
        self.assertEqual(303, response.status_code, response.text)
        definition_id = response.headers["location"].split("/")[-1]

        # 1. Test create_workflow_instance_from_definition (POST /workflow-definitions/{definition_id}/createInstance)
        response = self.client.post(
            f"/workflow-definitions/{definition_id}/createInstance",
            follow_redirects=False
        )
        self.assertEqual(303, response.status_code, response.text)
        instance_redirect_url = response.headers["location"]
        self.assertTrue(instance_redirect_url.startswith("/workflow-instances/wf_"))
        instance_id = instance_redirect_url.split("/")[-1]

        # 2. Test get_workflow_instances (GET /workflow-instances/)
        response = self.client.get("/workflow-instances/")
        self.assertEqual(200, response.status_code, response.text)
        self.assertIn(definition_name, response.text)

        # 3. Test view_workflow_instance (GET /workflow-instances/{instance_id})
        response = self.client.get(f"/workflow-instances/{instance_id}")
        self.assertEqual(200, response.status_code, response.text)
        self.assertIn(definition_name, response.text)
        self.assertIn("Instance Task 1", response.text)
        self.assertIn("Instance Task 2", response.text)
        self.assertIn(TaskStatus.pending.value, response.text)

        # Get task IDs from the rendered HTML (this is a bit brittle, but works for E2E)
        # A more robust approach would be to query the database directly or parse the Collection+JSON
        # For now, let's assume we can extract them from the HTML for simplicity in E2E.
        # In a real scenario, you might have an API endpoint to list tasks for an instance.
        # For this example, I'll simulate getting task IDs by querying the service directly after creation.
        workflow_instance_with_tasks = await self.workflow_service.get_workflow_instance_with_tasks(
            instance_id=instance_id, user_id=self.mock_authenticated_user.user_id
        )
        task_1_id = None
        task_2_id = None
        for task in workflow_instance_with_tasks.tasks:
            if task.name == "Instance Task 1":
                task_1_id = task.id
            elif task.name == "Instance Task 2":
                task_2_id = task.id
        self.assertIsNotNone(task_1_id)
        self.assertIsNotNone(task_2_id)

        # 4. Test complete_task_instance (POST /workflow-instances-task/{task_id}/complete)
        response = self.client.post(
            f"/workflow-instances-task/{task_1_id}/complete",
            follow_redirects=False
        )
        self.assertEqual(303, response.status_code, response.text)
        from urllib.parse import urlparse
        parsed_location = urlparse(response.headers["location"])
        self.assertEqual(parsed_location.path, f"/workflow-instances/{instance_id}")

        # Verify task status is completed
        response = self.client.get(f"/workflow-instances/{instance_id}")
        self.assertEqual(200, response.status_code, response.text)
        self.assertIn(TaskStatus.completed.value, response.text)

        # 5. Test reopen_task_instance (POST /workflow-instances-task/{task_id}/reopen)
        response = self.client.post(
            f"/workflow-instances-task/{task_1_id}/reopen",
            follow_redirects=False
        )
        self.assertEqual(303, response.status_code, response.text)
        from urllib.parse import urlparse
        parsed_location = urlparse(response.headers["location"])
        self.assertEqual(parsed_location.path, f"/workflow-instances/{instance_id}")

        # Verify task status is pending again
        response = self.client.get(f"/workflow-instances/{instance_id}")
        self.assertEqual(200, response.status_code, response.text)
        self.assertIn(TaskStatus.pending.value, response.text)

        # 6. Test archive_workflow_instance (POST /workflow-instances/{instance_id}/archive)
        response = self.client.post(
            f"/workflow-instances/{instance_id}/archive",
            follow_redirects=False
        )
        self.assertEqual(303, response.status_code, response.text)
        from urllib.parse import urlparse
        parsed_location = urlparse(response.headers["location"])
        self.assertEqual(parsed_location.path, f"/workflow-instances/{instance_id}")

        # Verify workflow instance status is archived
        response = self.client.get(f"/workflow-instances/{instance_id}")
        self.assertEqual(200, response.status_code, response.text)
        self.assertIn(WorkflowStatus.archived.value.capitalize(), response.text)


if __name__ == "__main__":
    unittest.main()
