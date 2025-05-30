# repository.py
import uuid
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from models import WorkflowDefinition, WorkflowInstance, TaskInstance

# In-memory stores
_workflow_definitions_db: Dict[str, WorkflowDefinition] = {}
_workflow_instances_db: Dict[str, WorkflowInstance] = {}
_task_instances_db: Dict[str, TaskInstance] = {}

class WorkflowRepository(ABC):
    @abstractmethod
    async def get_workflow_instance_by_id(self, instance_id: str) -> Optional[WorkflowInstance]:
        pass

    @abstractmethod
    async def list_workflow_definitions(self) -> List[WorkflowDefinition]:
        pass

    @abstractmethod
    async def get_workflow_definition_by_id(self, definition_id: str) -> Optional[WorkflowDefinition]:
        pass

    @abstractmethod
    async def create_workflow_instance(self, instance_data: WorkflowInstance) -> WorkflowInstance:
        pass

    @abstractmethod
    async def update_workflow_instance(self, instance_id: str, instance_update: WorkflowInstance) -> Optional[WorkflowInstance]:
        pass

    @abstractmethod
    async def create_task_instance(self, task_data: TaskInstance) -> TaskInstance:
        pass

    @abstractmethod
    async def get_task_instance_by_id(self, task_id: str) -> Optional[TaskInstance]:
        pass

    @abstractmethod
    async def update_task_instance(self, task_id: str, task_update: TaskInstance) -> Optional[TaskInstance]:
        pass

    @abstractmethod
    async def get_tasks_for_workflow_instance(self, instance_id: str) -> List[TaskInstance]:
        pass

class InMemoryWorkflowRepository(WorkflowRepository):
    def __init__(self):
        self._seed_definitions()

    def _seed_definitions(self):
        if not _workflow_definitions_db:  # Seed only if empty
            def1 = WorkflowDefinition(
                id="def_morning_quick_start",
                name="Morning Quick Start",
                description="A simple routine to kick off the day.",
                task_names=["Make Bed", "Brush Teeth", "Get Dressed"]
            )
            _workflow_definitions_db[def1.id] = def1
            def2 = WorkflowDefinition(
                id="def_evening_wind_down",
                name="Evening Wind Down",
                description="Prepare for a good night's sleep.",
                task_names=["Tidy Up Living Room (5 mins)", "Prepare Outfit for Tomorrow", "Read a Book (15 mins)"]
            )
            _workflow_definitions_db[def2.id] = def2

    async def get_workflow_instance_by_id(self, instance_id: str) -> Optional[WorkflowInstance]:
        instance = _workflow_instances_db.get(instance_id)
        return instance.model_copy(deep=True) if instance else None

    async def list_workflow_definitions(self) -> List[WorkflowDefinition]:
        return [defn.model_copy(deep=True) for defn in _workflow_definitions_db.values()]

    async def get_workflow_definition_by_id(self, definition_id: str) -> Optional[WorkflowDefinition]:
        defn = _workflow_definitions_db.get(definition_id)
        return defn.model_copy(deep=True) if defn else None

    async def create_workflow_instance(self, instance_data: WorkflowInstance) -> WorkflowInstance:
        new_instance = instance_data.model_copy(deep=True)
        _workflow_instances_db[new_instance.id] = new_instance
        return new_instance.model_copy(deep=True)

    async def update_workflow_instance(self, instance_id: str, instance_update: WorkflowInstance) -> Optional[WorkflowInstance]:
        if instance_id in _workflow_instances_db:
            _workflow_instances_db[instance_id] = instance_update.model_copy(deep=True)
            return _workflow_instances_db[instance_id].model_copy(deep=True)
        return None

    async def create_task_instance(self, task_data: TaskInstance) -> TaskInstance:
        new_task = task_data.model_copy(deep=True)
        _task_instances_db[new_task.id] = new_task
        return new_task.model_copy(deep=True)

    async def get_task_instance_by_id(self, task_id: str) -> Optional[TaskInstance]:
        task = _task_instances_db.get(task_id)
        return task.model_copy(deep=True) if task else None

    async def update_task_instance(self, task_id: str, task_update: TaskInstance) -> Optional[TaskInstance]:
        if task_id in _task_instances_db:
            _task_instances_db[task_id] = task_update.model_copy(deep=True)
            return _task_instances_db[task_id].model_copy(deep=True)
        return None

    async def get_tasks_for_workflow_instance(self, instance_id: str) -> List[TaskInstance]:
        tasks = [
            task.model_copy(deep=True) for task in _task_instances_db.values()
            if task.workflow_instance_id == instance_id
        ]
        return sorted(tasks, key=lambda t: t.order)
