# repository.py
from abc import ABC, abstractmethod
from typing import List, Optional, Dict
from datetime import date as DateObject

from app.models import WorkflowDefinition, WorkflowInstance, TaskInstance

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
    async def update_workflow_instance(self, instance_id: str, instance_update: WorkflowInstance) -> Optional[
        WorkflowInstance]:
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

    @abstractmethod
    async def list_workflow_instances_by_user(self, user_id: str) -> List[WorkflowInstance]:
        pass

    @abstractmethod
    async def create_workflow_definition(self, definition_data: WorkflowDefinition) -> WorkflowDefinition:
        pass

    @abstractmethod
    async def update_workflow_definition(self, definition_id: str, name: str, description: Optional[str], task_names: List[str]) -> Optional[WorkflowDefinition]:
        pass

    @abstractmethod
    async def delete_workflow_definition(self, definition_id: str) -> bool:
        pass


class PostgreSQLWorkflowRepository(WorkflowRepository):
    def __init__(self, db_session):
        self.db_session = db_session

    async def get_workflow_instance_by_id(self, instance_id: str) -> Optional[WorkflowInstance]:
        from app.db_models.workflow import WorkflowInstance as WorkflowInstanceORM
        instance = self.db_session.query(WorkflowInstanceORM).filter(WorkflowInstanceORM.id == instance_id).first()
        return WorkflowInstance.model_validate(instance) if instance else None

    async def list_workflow_definitions(self) -> List[WorkflowDefinition]:
        from app.db_models.workflow import WorkflowDefinition as WorkflowDefinitionORM
        definitions = self.db_session.query(WorkflowDefinitionORM).all()
        return [WorkflowDefinition.model_validate(defn) for defn in definitions]

    async def get_workflow_definition_by_id(self, definition_id: str) -> Optional[WorkflowDefinition]:
        from app.db_models.workflow import WorkflowDefinition as WorkflowDefinitionORM
        defn = self.db_session.query(WorkflowDefinitionORM).filter(WorkflowDefinitionORM.id == definition_id).first()
        return WorkflowDefinition.model_validate(defn) if defn else None

    async def create_workflow_instance(self, instance_data: WorkflowInstance) -> WorkflowInstance:
        from app.db_models.workflow import WorkflowInstance as WorkflowInstanceORM
        instance = WorkflowInstanceORM(**instance_data.model_dump())
        self.db_session.add(instance)
        self.db_session.commit()
        self.db_session.refresh(instance)
        return WorkflowInstance.model_validate(instance)

    async def update_workflow_instance(self, instance_id: str, instance_update: WorkflowInstance) -> Optional[WorkflowInstance]:
        from app.db_models.workflow import WorkflowInstance as WorkflowInstanceORM
        instance = self.db_session.query(WorkflowInstanceORM).filter(WorkflowInstanceORM.id == instance_id).first()
        if instance:
            for key, value in instance_update.model_dump().items():
                setattr(instance, key, value)
            self.db_session.commit()
            return instance_update
        return None

    async def create_task_instance(self, task_data: TaskInstance) -> TaskInstance:
        from app.db_models.task import TaskInstance as TaskInstanceORM
        task = TaskInstanceORM(**task_data.model_dump())
        self.db_session.add(task)
        self.db_session.commit()
        self.db_session.refresh(task)
        return TaskInstance.model_validate(task)

    async def get_task_instance_by_id(self, task_id: str) -> Optional[TaskInstance]:
        from app.db_models.task import TaskInstance as TaskInstanceORM
        task = self.db_session.query(TaskInstanceORM).filter(TaskInstanceORM.id == task_id).first()
        return TaskInstance.model_validate(task) if task else None

    async def update_task_instance(self, task_id: str, task_update: TaskInstance) -> Optional[TaskInstance]:
        from app.db_models.task import TaskInstance as TaskInstanceORM
        task = self.db_session.query(TaskInstanceORM).filter(TaskInstanceORM.id == task_id).first()
        if task:
            for key, value in task_update.model_dump().items():
                setattr(task, key, value)
            self.db_session.commit()
            return task_update
        return None

    async def get_tasks_for_workflow_instance(self, instance_id: str) -> List[TaskInstance]:
        from app.db_models.task import TaskInstance as TaskInstanceORM
        tasks = self.db_session.query(TaskInstanceORM).filter(TaskInstanceORM.workflow_instance_id == instance_id).order_by(TaskInstanceORM.order).all()
        return [TaskInstance.model_validate(task) for task in tasks]

    async def list_workflow_instances_by_user(self, user_id: str) -> List[WorkflowInstance]:
        from app.db_models.workflow import WorkflowInstance as WorkflowInstanceORM
        instances = self.db_session.query(WorkflowInstanceORM).filter(WorkflowInstanceORM.user_id == user_id).order_by(WorkflowInstanceORM.created_at.desc()).all()
        return [WorkflowInstance.model_validate(instance) for instance in instances]

    async def create_workflow_definition(self, definition_data: WorkflowDefinition) -> WorkflowDefinition:
        from app.db_models.workflow import WorkflowDefinition as WorkflowDefinitionORM
        definition = WorkflowDefinitionORM(**definition_data.model_dump())
        self.db_session.add(definition)
        self.db_session.commit()
        self.db_session.refresh(definition)
        return WorkflowDefinition.model_validate(definition)

    async def update_workflow_definition(self, definition_id: str, name: str, description: Optional[str], task_names: List[str]) -> Optional[WorkflowDefinition]:
        from app.db_models.workflow import WorkflowDefinition as WorkflowDefinitionORM
        db_definition = self.db_session.query(WorkflowDefinitionORM).filter(WorkflowDefinitionORM.id == definition_id).first()
        if db_definition:
            db_definition.name = name
            db_definition.description = description
            db_definition.task_names = task_names if task_names else []
            self.db_session.commit()
            self.db_session.refresh(db_definition)
            return WorkflowDefinition.model_validate(db_definition)
        return None

    async def delete_workflow_definition(self, definition_id: str) -> bool:
        from app.db_models.workflow import WorkflowDefinition as WorkflowDefinitionORM
        from app.db_models.workflow import WorkflowInstance as WorkflowInstanceORM
        db_definition = self.db_session.query(WorkflowDefinitionORM).filter(WorkflowDefinitionORM.id == definition_id).first()
        if db_definition:
            linked_instances_count = self.db_session.query(WorkflowInstanceORM).filter(WorkflowInstanceORM.workflow_definition_id == definition_id).count()
            if linked_instances_count > 0:
                return False  # Indicate deletion failed due to existing instances
            self.db_session.delete(db_definition)
            self.db_session.commit()
            return True
        return False


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

    async def update_workflow_instance(self, instance_id: str, instance_update: WorkflowInstance) -> Optional[
        WorkflowInstance]:
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

    async def list_workflow_instances_by_user(self, user_id: str) -> List[WorkflowInstance]:
        instances = [
            instance.model_copy(deep=True) for instance in _workflow_instances_db.values()
            if instance.user_id == user_id
        ]
        return sorted(instances, key=lambda i: i.created_at, reverse=True)

    async def create_workflow_definition(self, definition_data: WorkflowDefinition) -> WorkflowDefinition:
        new_definition = definition_data.model_copy(deep=True)
        _workflow_definitions_db[new_definition.id] = new_definition
        return new_definition.model_copy(deep=True)

    async def update_workflow_definition(self, definition_id: str, name: str, description: Optional[str], task_names: List[str]) -> Optional[WorkflowDefinition]:
        if definition_id in _workflow_definitions_db:
            updated_definition = WorkflowDefinition(
                id=definition_id,
                name=name,
                description=description,
                task_names=task_names
            )
            _workflow_definitions_db[definition_id] = updated_definition
            return updated_definition.model_copy(deep=True)
        return None

    async def delete_workflow_definition(self, definition_id: str) -> bool:
        if definition_id in _workflow_definitions_db:
            linked_instances = any(instance.workflow_definition_id == definition_id for instance in _workflow_instances_db.values())
            if linked_instances:
                return False  # Indicate deletion failed due to existing instances
            del _workflow_definitions_db[definition_id]
            return True
        return False
