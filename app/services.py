# services.py
from typing import List, Optional, Dict, Any

from app.models import WorkflowDefinition, WorkflowInstance, TaskInstance
from app.repository import WorkflowRepository


class WorkflowService:
    def __init__(self, repository: WorkflowRepository):
        self.repository = repository

    async def get_workflow_instance_with_tasks(self, instance_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        instance = await self.repository.get_workflow_instance_by_id(instance_id)
        if not instance or instance.user_id != user_id:
            return None
        tasks = await self.repository.get_tasks_for_workflow_instance(instance_id)
        return {"instance": instance, "tasks": tasks}

    async def create_workflow_instance(self, definition_id: str, user_id: str) -> Optional[WorkflowInstance]:
        definition = await self.repository.get_workflow_definition_by_id(definition_id)
        if not definition:
            return None

        instance = WorkflowInstance(
            workflow_definition_id=definition.id,
            name=definition.name,
            user_id=user_id
        )
        created_instance = await self.repository.create_workflow_instance(instance)

        for i, task_name in enumerate(definition.task_names):
            task = TaskInstance(
                workflow_instance_id=created_instance.id,
                name=task_name,
                order=i
            )
            await self.repository.create_task_instance(task)
        return created_instance

    async def list_workflow_definitions(self) -> List[WorkflowDefinition]:
        return await self.repository.list_workflow_definitions()

    async def complete_task(self, task_id: str, user_id: str) -> Optional[TaskInstance]:
        task = await self.repository.get_task_instance_by_id(task_id)
        if not task or task.status == "completed":
            return None

        # Check if the workflow instance belongs to the user
        workflow_instance = await self.repository.get_workflow_instance_by_id(task.workflow_instance_id)
        if not workflow_instance or workflow_instance.user_id != user_id:
            return None

        task.status = "completed"
        updated_task = await self.repository.update_task_instance(task_id, task)

        if updated_task:
            workflow_details = await self.get_workflow_instance_with_tasks(task.workflow_instance_id, user_id)
            if workflow_details and workflow_details["instance"]:
                all_tasks_completed = all(t.status == "completed" for t in workflow_details["tasks"])
                if all_tasks_completed:
                    workflow_instance = workflow_details["instance"]
                    workflow_instance.status = "completed"
                    await self.repository.update_workflow_instance(workflow_instance.id, workflow_instance)
        return updated_task

    async def list_instances_for_user(self, user_id: str) -> List[WorkflowInstance]:
        return await self.repository.list_workflow_instances_by_user(user_id)

    async def create_new_definition(self, name: str, description: Optional[str], task_names: List[str]) -> WorkflowDefinition:
        if not name.strip():
            raise ValueError("Definition name cannot be empty.")
        if not task_names:
            raise ValueError("A definition must have at least one task name.")
        
        definition = WorkflowDefinition(
            name=name,
            description=description,
            task_names=task_names
        )
        return await self.repository.create_workflow_definition(definition)
