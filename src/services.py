# services.py
import uuid
from datetime import date as DateObject, datetime, timedelta # Ensure datetime and timedelta
from typing import List, Optional, Dict, Any

# Ensure WorkflowInstance is imported if not already (it is in the original code)
from models import WorkflowDefinition, WorkflowInstance, TaskInstance, TaskStatus, WorkflowStatus, TaskDefinitionBase
from repository import WorkflowDefinitionRepository, WorkflowInstanceRepository, TaskInstanceRepository
# Removed direct DB model imports like DbWorkflow, DbTask, DbWorkflowDefinition
# Removed sqlalchemy.orm and sqlalchemy.future imports


class WorkflowService:
    def __init__(self, definition_repo: WorkflowDefinitionRepository, instance_repo: WorkflowInstanceRepository,
                 task_repo: TaskInstanceRepository):
        self.definition_repo = definition_repo
        self.instance_repo = instance_repo
        self.task_repo = task_repo

    # Renamed the existing create_workflow_instance to avoid conflict for now.
    # This will be resolved by the new create_workflow_instance method signature.
    async def create_workflow_instance_from_data(self, instance_data: WorkflowInstance) -> Optional[WorkflowInstance]:
        definition = await self.definition_repo.get_workflow_definition_by_id(instance_data.workflow_definition_id)
        if not definition:
            return None

        new_instance_pydantic = WorkflowInstance(
            workflow_definition_id=definition.id,
            name=instance_data.name or definition.name,
            user_id=instance_data.user_id,
            status=instance_data.status or WorkflowStatus.pending,
            due_datetime=instance_data.due_datetime or definition.due_datetime
        )

        created_instance = await self.instance_repo.create_workflow_instance(new_instance_pydantic)
        if not created_instance:
            return None

        for task_def in definition.task_definitions:
            task_due_datetime: Optional[datetime] = None
            if created_instance.due_datetime and task_def.due_datetime_offset_minutes is not None:
                offset = timedelta(minutes=task_def.due_datetime_offset_minutes)
                task_due_datetime = created_instance.due_datetime + offset
            elif created_instance.due_datetime and task_def.due_datetime_offset_minutes is None:
                 task_due_datetime = created_instance.due_datetime

            task = TaskInstance(
                workflow_instance_id=created_instance.id,
                name=task_def.name,
                order=task_def.order,
                due_datetime=task_due_datetime
            )
            await self.task_repo.create_task_instance(task)
        return created_instance

    async def create_workflow_instance(self, definition_id: str, user_id: str) -> WorkflowInstance: # Added user_id based on typical needs
        # Fetch the workflow definition using the repository
        db_definition = await self.definition_repo.get_workflow_definition_by_id(definition_id)

        if not db_definition:
            # Consider raising an HTTPException or a custom exception
            # For now, aligning with the provided snippet's Exception
            raise Exception(f"Workflow Definition with id {definition_id} not found")

        # Create the workflow instance using Pydantic model
        # Assuming WorkflowInstance has a default_factory for id and sensible defaults
        workflow_instance_data = WorkflowInstance(
            id=str(uuid.uuid4()), # Or let the model/DB handle it if configured
            workflow_definition_id=db_definition.id,
            name=db_definition.name,  # Or a generated instance name
            description=db_definition.description,
            status=WorkflowStatus.pending,  # Or some initial status
            user_id=user_id, # user_id is crucial
            # due_datetime can be inherited or calculated if needed
            # created_at and updated_at are likely handled by the base model or DB
        )

        # Save the new workflow instance using the repository
        # The repository method is expected to handle the conversion to a DB model and saving it.
        created_instance = await self.instance_repo.create_workflow_instance(workflow_instance_data)
        if not created_instance:
            raise Exception("Failed to create workflow instance")


        # Create tasks for the instance based on task definitions
        created_tasks = []
        for task_def in db_definition.task_definitions:
            task_due_datetime: Optional[datetime] = None
            if created_instance.due_datetime and task_def.due_datetime_offset_minutes is not None:
                offset = timedelta(minutes=task_def.due_datetime_offset_minutes)
                task_due_datetime = created_instance.due_datetime + offset
            elif created_instance.due_datetime and task_def.due_datetime_offset_minutes is None:
                 task_due_datetime = created_instance.due_datetime


            task_data = TaskInstance(
                id=str(uuid.uuid4()), # Or let the model/DB handle it
                workflow_instance_id=created_instance.id,
                # task_definition_id=task_def.id, # If your TaskInstance model needs this
                name=task_def.name,
                description=task_def.description,
                status=TaskStatus.pending,  # Initial status for tasks
                order=task_def.order,
                due_datetime=task_due_datetime,
                due_datetime_offset_minutes=task_def.due_datetime_offset_minutes,
                # created_at and updated_at
            )
            created_task = await self.task_repo.create_task_instance(task_data)
            if created_task:
                created_tasks.append(created_task)
            else:
                # Handle error in task creation if necessary
                pass

        # The created_instance from instance_repo should be the Pydantic model.
        # If it needs to be augmented with tasks, ensure the model supports it.
        # For now, returning the instance as created. If tasks need to be part of the returned object,
        # the WorkflowInstance model should have a tasks field, and we'd populate it here or refresh.
        # However, the existing create_workflow_instance_from_data returns the instance without explicitly loading tasks into it.
        # Let's assume the instance object as returned by instance_repo.create_workflow_instance is sufficient.
        # If the instance model is expected to have tasks, we might need a refresh/reload.

        # To align with get_workflow_instance, we should return the instance with its tasks.
        # We can fetch them after creation.
        refreshed_instance_dict = await self.get_workflow_instance_with_tasks(created_instance.id, user_id)
        if refreshed_instance_dict and refreshed_instance_dict["instance"]:
             # Assuming get_workflow_instance_with_tasks returns a dict with 'instance' and 'tasks'
             # and that 'instance' is the Pydantic model with tasks possibly loaded or accessible.
             # For the return type to be WorkflowInstance, we need to ensure this.
             # A simple way is to fetch the instance again, which should include tasks if models are set up with relationships.
            final_instance = await self.get_workflow_instance(created_instance.id, user_id) # call the new get_workflow_instance
            if final_instance:
                return final_instance
            else: # Should not happen if creation was successful
                raise Exception("Failed to retrieve created instance with tasks")

        return created_instance # Fallback, though the above block should ideally return


    async def get_workflow_instance(self, instance_id: str, user_id: str) -> WorkflowInstance | None: # Added user_id
        # Fetch the workflow instance using the repository
        instance = await self.instance_repo.get_workflow_instance_by_id(instance_id)

        if not instance or instance.user_id != user_id: # Check ownership
            return None

        # Fetch associated tasks
        tasks = await self.task_repo.get_tasks_for_workflow_instance(instance_id)

        # Assuming WorkflowInstance Pydantic model has a 'tasks' field (e.g., List[TaskInstance])
        # And that the instance object returned by the repo can have this field populated.
        # Pydantic models with ORM mode usually handle relationships if defined correctly.
        # If 'tasks' is not automatically populated, we might need to set it manually.
        # For example: instance.tasks = tasks (if instance is a Pydantic model and tasks is a list of TaskInstance models)
        # Let's assume the repository and Pydantic models are set up to handle this.
        # If `instance_repo.get_workflow_instance_by_id` returns a model that already includes tasks
        # (e.g., through SQLAlchemy relationship loading configured in the repository),
        # then `tasks` might already be part of `instance`.
        # If not, we need to combine them.
        # The existing get_workflow_instance_with_tasks returns a dict.
        # This method should return a WorkflowInstance model.

        # Let's ensure the tasks are part of the returned WorkflowInstance object.
        # A common pattern is for the Pydantic model to have a field for related objects.
        # If WorkflowInstance has `tasks: List[TaskInstance] = []`, we can assign it.
        instance.tasks = tasks # Assuming instance is a Pydantic model and tasks is List[TaskInstance]

        return instance

    async def get_workflow_instance_with_tasks(self, instance_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        instance = await self.instance_repo.get_workflow_instance_by_id(instance_id)
        if not instance or instance.user_id != user_id:
            return None
        tasks = await self.task_repo.get_tasks_for_workflow_instance(instance_id)
        # This is where the dict is constructed. The new get_workflow_instance should return the model itself.
        return {"instance": instance, "tasks": tasks}


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
        # if not task_definitions:
        #     raise ValueError("A definition must have at least one task.")

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
