# services.py
from typing import List, Optional, Dict, Any

from app.models import WorkflowDefinition, WorkflowInstance, TaskInstance
from app.repository import WorkflowRepository


class WorkflowService:
    def __init__(self, repository: WorkflowRepository):
        self.repository = repository

    async def get_workflow_instance_with_tasks(self, instance_id: str) -> Optional[Dict[str, Any]]:
        instance = await self.repository.get_workflow_instance_by_id(instance_id)
        if not instance:
            return None
        tasks = await self.repository.get_tasks_for_workflow_instance(instance_id)
        return {"instance": instance, "tasks": tasks}

    async def create_workflow_instance(self, definition_id: str) -> Optional[WorkflowInstance]:
        definition = await self.repository.get_workflow_definition_by_id(definition_id)
        if not definition:
            return None

        instance = WorkflowInstance(
            workflow_definition_id=definition.id,
            name=definition.name
        )
        created_instance = await self.repository.create_workflow_instance(instance)

        task_ids = []
        for i, task_name in enumerate(definition.task_names):
            task = TaskInstance(
                workflow_instance_id=created_instance.id,
                name=task_name,
                order=i
            )
            created_task = await self.repository.create_task_instance(task)
            task_ids.append(created_task.id)

        created_instance.task_ids = task_ids
        await self.repository.update_workflow_instance(created_instance.id, created_instance)
        return created_instance

    async def list_workflow_definitions(self) -> List[WorkflowDefinition]:
        return await self.repository.list_workflow_definitions()

    async def complete_task(self, task_id: str) -> Optional[TaskInstance]:
        task = await self.repository.get_task_instance_by_id(task_id)
        if not task or task.status == "completed":
            return None

        task.status = "completed"
        updated_task = await self.repository.update_task_instance(task_id, task)

        if updated_task:
            workflow_details = await self.get_workflow_instance_with_tasks(task.workflow_instance_id)
            if workflow_details and workflow_details["instance"]:
                all_tasks_completed = all(t.status == "completed" for t in workflow_details["tasks"])
                if all_tasks_completed:
                    workflow_instance = workflow_details["instance"]
                    workflow_instance.status = "completed"
                    await self.repository.update_workflow_instance(workflow_instance.id, workflow_instance)
        return updated_task
