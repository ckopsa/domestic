# services.py
import uuid
from datetime import date as DateObject, datetime, timedelta # Ensure datetime and timedelta
from typing import List, Optional, Dict, Any

from models import WorkflowDefinition, WorkflowInstance, TaskInstance, TaskStatus, WorkflowStatus, TaskDefinitionBase
from repository import WorkflowDefinitionRepository, WorkflowInstanceRepository, TaskInstanceRepository


class WorkflowService:
    def __init__(self, definition_repo: WorkflowDefinitionRepository, instance_repo: WorkflowInstanceRepository,
                 task_repo: TaskInstanceRepository):
        self.definition_repo = definition_repo
        self.instance_repo = instance_repo
        self.task_repo = task_repo

    async def get_workflow_instance_with_tasks(self, instance_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        instance = await self.instance_repo.get_workflow_instance_by_id(instance_id)
        if not instance or instance.user_id != user_id:
            return None
        tasks = await self.task_repo.get_tasks_for_workflow_instance(instance_id)
        return {"instance": instance, "tasks": tasks}

    async def create_workflow_instance(self, definition_id: str, user_id: str, override_due_datetime: Optional[datetime] = None) -> Optional[WorkflowInstance]: # Updated signature
        definition = await self.definition_repo.get_workflow_definition_by_id(definition_id) # This is a Pydantic model
        if not definition:
            return None

        instance_due_datetime: Optional[datetime] = None
        if override_due_datetime:
            instance_due_datetime = override_due_datetime
        elif definition.due_datetime: # Accessing due_datetime from the Pydantic model
            instance_due_datetime = definition.due_datetime

        instance = WorkflowInstance(
            workflow_definition_id=definition.id,
            name=definition.name,
            user_id=user_id,
            due_datetime=instance_due_datetime # New assignment
            # created_at will be set by default_factory in Pydantic model
            # id will be set by default_factory in Pydantic model
        )

        created_instance = await self.instance_repo.create_workflow_instance(instance) # repo expects Pydantic
        if not created_instance: # Should not happen if create_workflow_instance raises on failure
            return None

        for task_def in definition.task_definitions: # Iterate over TaskDefinitionBase from Pydantic WorkflowDefinition
            task_due_datetime: Optional[datetime] = None
            if created_instance.due_datetime:
                if task_def.due_datetime_offset_minutes is not None:
                    offset_minutes = task_def.due_datetime_offset_minutes
                    offset = timedelta(minutes=offset_minutes)
                    task_due_datetime = created_instance.due_datetime + offset
                else:
                    # If task_def.due_datetime_offset_minutes is None, but the instance has a due_datetime,
                    # the task inherits the instance's due_datetime.
                    task_due_datetime = created_instance.due_datetime
            # If created_instance.due_datetime is None, task_due_datetime remains None regardless of task_def offset.

            task = TaskInstance(
                workflow_instance_id=created_instance.id, # Use ID from the created instance
                name=task_def.name,
                order=task_def.order,
                due_datetime=task_due_datetime # New assignment
                # id will be set by default_factory in Pydantic model
                # status will be set by default_factory
            )
            await self.task_repo.create_task_instance(task) # repo expects Pydantic

        return created_instance # Return the Pydantic model of the created instance

    async def list_workflow_definitions(self, name: Optional[str] = None, definition_id: Optional[str] = None) -> List[WorkflowDefinition]:
        return await self.definition_repo.list_workflow_definitions(name=name, definition_id=definition_id)

    async def complete_task(self, task_id: str, user_id: str) -> Optional[TaskInstance]:
        task = await self.task_repo.get_task_instance_by_id(task_id)
        if not task or task.status == "completed":
            return None

        # Check if the workflow instance belongs to the user
        workflow_instance = await self.instance_repo.get_workflow_instance_by_id(task.workflow_instance_id)
        if not workflow_instance or workflow_instance.user_id != user_id:
            return None

        task.status = "completed"
        updated_task = await self.task_repo.update_task_instance(task_id, task)

        if updated_task:
            workflow_details = await self.get_workflow_instance_with_tasks(task.workflow_instance_id, user_id)
            if workflow_details and workflow_details["instance"]:
                all_tasks_completed = all(t.status == "completed" for t in workflow_details["tasks"])
                if all_tasks_completed:
                    workflow_instance = workflow_details["instance"]
                    workflow_instance.status = "completed"
                    await self.instance_repo.update_workflow_instance(workflow_instance.id, workflow_instance)
        return updated_task

    async def list_instances_for_user(self, user_id: str, created_at_date: Optional[DateObject] = None,
                                      status: Optional[WorkflowStatus] = None, definition_id: Optional[str] = None) -> List[WorkflowInstance]:
        return await self.instance_repo.list_workflow_instances_by_user(user_id, created_at_date=created_at_date,
                                                                        status=status, definition_id=definition_id)

    async def create_new_definition(self, name: str, description: Optional[str],
                                    task_definitions: List[TaskDefinitionBase]) -> WorkflowDefinition:
        if not name.strip():
            raise ValueError("Definition name cannot be empty.")
        if not task_definitions:
            raise ValueError("A definition must have at least one task.")

        # task_definitions is already List[TaskDefinitionBase]
        definition = WorkflowDefinition(
            name=name,
            description=description,
            task_definitions=task_definitions
        )
        return await self.definition_repo.create_workflow_definition(definition)

    async def update_definition(self, definition_id: str, name: str, description: Optional[str],
                                task_definitions: List[TaskDefinitionBase]) -> Optional[WorkflowDefinition]:
        if not name.strip():
            raise ValueError("Definition name cannot be empty.")
        if not task_definitions:
            raise ValueError("A definition must have at least one task.")

        # task_definitions is already List[TaskDefinitionBase]
        # The repository method expects List[TaskDefinitionBase]
        return await self.definition_repo.update_workflow_definition(definition_id, name, description, task_definitions)

    async def delete_definition(self, definition_id: str) -> None:
        from repository import DefinitionNotFoundError, DefinitionInUseError
        try:
            await self.definition_repo.delete_workflow_definition(definition_id)
        except DefinitionNotFoundError as e:
            raise ValueError(str(e)) from e
        except DefinitionInUseError as e:
            raise ValueError(str(e)) from e

    async def undo_complete_task(self, task_id: str, user_id: str) -> Optional[TaskInstance]:
        task = await self.task_repo.get_task_instance_by_id(task_id)
        if not task or task.status != TaskStatus.completed:
            return None

        workflow_instance = await self.instance_repo.get_workflow_instance_by_id(task.workflow_instance_id)
        if not workflow_instance or workflow_instance.user_id != user_id:
            return None

        task.status = TaskStatus.pending
        updated_task = await self.task_repo.update_task_instance(task_id, task)

        if updated_task and workflow_instance.status == WorkflowStatus.completed:
            workflow_instance.status = WorkflowStatus.active
            await self.instance_repo.update_workflow_instance(workflow_instance.id, workflow_instance)

        return updated_task

    async def archive_workflow_instance(self, instance_id: str, user_id: str) -> Optional[WorkflowInstance]:
        instance = await self.instance_repo.get_workflow_instance_by_id(instance_id)

        if not instance:
            return None  # Or raise InstanceNotFoundError

        if instance.user_id != user_id:
            # Consider raising an authorization error or just returning None
            return None

        if instance.status == WorkflowStatus.completed:
            # Cannot archive a completed instance, return None or raise error
            # For now, returning None as per subtask description ("return None")
            return None

        if instance.status == WorkflowStatus.archived:
            # Already archived, return the instance as is
            return instance

        instance.status = WorkflowStatus.archived
        updated_instance = await self.instance_repo.update_workflow_instance(instance.id, instance)
        return updated_instance

    async def unarchive_workflow_instance(self, instance_id: str, user_id: str) -> Optional[WorkflowInstance]:
        instance = await self.instance_repo.get_workflow_instance_by_id(instance_id)

        if not instance:
            return None  # Instance not found

        if instance.user_id != user_id:
            return None  # User does not own this instance

        if instance.status != WorkflowStatus.archived:
            # Can only unarchive instances that are currently archived
            return None

        instance.status = WorkflowStatus.active  # Set status to active
        updated_instance = await self.instance_repo.update_workflow_instance(instance.id, instance)
        return updated_instance

    async def generate_shareable_link(self, instance_id: str, user_id: str) -> Optional[WorkflowInstance]:
        instance = await self.instance_repo.get_workflow_instance_by_id(instance_id)

        if not instance or instance.user_id != user_id:
            return None

        if instance.share_token:
            return instance

        new_token = uuid.uuid4().hex
        instance.share_token = new_token
        
        # The Pydantic model 'instance' is updated here.
        # We need to pass the updated Pydantic model to the repository.
        updated_instance_pydantic = instance 
        
        await self.instance_repo.update_workflow_instance(instance_id, updated_instance_pydantic)
        
        # update_workflow_instance is expected to return the updated DB model object,
        # which should then be converted back to Pydantic if needed by the caller,
        # but here we are returning the Pydantic model we already have and just updated.
        # This assumes update_workflow_instance doesn't change it further or return a different object.
        return updated_instance_pydantic

    async def get_workflow_instance_by_share_token(self, share_token: str) -> Optional[Dict[str, Any]]:
        # This assumes instance_repo.get_workflow_instance_by_share_token returns a Pydantic model
        instance = await self.instance_repo.get_workflow_instance_by_share_token(share_token)

        if not instance:
            return None

        # This assumes task_repo.get_tasks_for_workflow_instance returns a list of Pydantic models
        tasks = await self.task_repo.get_tasks_for_workflow_instance(instance.id)
        
        return {"instance": instance, "tasks": tasks}
