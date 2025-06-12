# repository.py
from abc import ABC, abstractmethod
from datetime import date as DateObject
from typing import List, Optional, Dict

from sqlalchemy import case

from db_models.enums import WorkflowStatus, TaskStatus
from db_models.task import TaskInstance as TaskInstanceORM
from db_models.task_definition import TaskDefinition as TaskDefinitionORM
from db_models.workflow import WorkflowDefinition as WorkflowDefinitionORM, WorkflowInstance as WorkflowInstanceORM
from models import WorkflowDefinition, WorkflowInstance, TaskInstance, TaskDefinitionBase

# In-memory stores
_workflow_definitions_db: Dict[str, WorkflowDefinition] = {}
_workflow_instances_db: Dict[str, WorkflowInstance] = {}
_task_instances_db: Dict[str, TaskInstance] = {}


class WorkflowDefinitionRepository(ABC):
    @abstractmethod
    async def list_workflow_definitions(self, name: Optional[str] = None, definition_id: Optional[str] = None) -> List[WorkflowDefinition]:
        pass

    @abstractmethod
    async def get_filtered_workflow_instances(self, user_id: Optional[str] = None, status: Optional[WorkflowStatus] = None) -> List[WorkflowInstance]:
        pass

    @abstractmethod
    async def get_workflow_definition_by_id(self, definition_id: str) -> Optional[WorkflowDefinition]:
        pass

    @abstractmethod
    async def create_workflow_definition(self, definition_data: WorkflowDefinition) -> WorkflowDefinition:
        pass

    @abstractmethod
    async def update_workflow_definition(self, definition_id: str, name: str, description: Optional[str],
                                         task_definitions_data: List[TaskDefinitionBase]) -> Optional[WorkflowDefinition]:
        pass

    @abstractmethod
    async def delete_workflow_definition(self, definition_id: str) -> None:
        pass


class WorkflowInstanceRepository(ABC):
    @abstractmethod
    async def get_workflow_instance_by_id(self, instance_id: str) -> Optional[WorkflowInstance]:
        pass

    @abstractmethod
    async def create_workflow_instance(self, instance_data: WorkflowInstance) -> WorkflowInstance:
        pass

    @abstractmethod
    async def update_workflow_instance(self, instance_id: str, instance_update: WorkflowInstance) -> Optional[
        WorkflowInstance]:
        pass

    @abstractmethod
    async def list_workflow_instances_by_user(self, user_id: str, created_at_date: Optional[DateObject] = None, status: Optional[WorkflowStatus] = None, definition_id: Optional[str] = None) -> List[WorkflowInstance]:
        pass

    @abstractmethod
    async def get_workflow_instance_by_share_token(self, share_token: str) -> Optional[WorkflowInstance]:
        pass


class TaskInstanceRepository(ABC):
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


# Custom exceptions for repository operations
class DefinitionNotFoundError(Exception):
    """Raised when a workflow definition is not found."""
    pass


class DefinitionInUseError(ValueError):
    """Raised when a workflow definition cannot be deleted because it's in use."""
    pass


class InstanceNotFoundError(Exception):
    """Raised when a workflow instance is not found."""
    pass


class TaskNotFoundError(Exception):
    """Raised when a task instance is not found."""
    pass


class PostgreSQLWorkflowRepository(WorkflowDefinitionRepository, WorkflowInstanceRepository, TaskInstanceRepository):
    def __init__(self, db_session):
        self.db_session = db_session

    async def get_workflow_instance_by_id(self, instance_id: str) -> Optional[WorkflowInstance]:
        instance = self.db_session.query(WorkflowInstanceORM).filter(WorkflowInstanceORM.id == instance_id).first()
        return WorkflowInstance.model_validate(instance, from_attributes=True) if instance else None

    async def get_filtered_workflow_instances(self, user_id: Optional[str] = None, status: Optional[WorkflowStatus] = None) -> List[WorkflowInstance]:
        query = self.db_session.query(WorkflowInstanceORM)
        if user_id:
            query = query.filter(WorkflowInstanceORM.user_id == user_id)
        if status:
            query = query.filter(WorkflowInstanceORM.status == status)
        instances = query.order_by(WorkflowInstanceORM.created_at.desc()).all()
        return [WorkflowInstance.model_validate(instance, from_attributes=True) for instance in instances]

    async def list_workflow_definitions(self, name: Optional[str] = None, definition_id: Optional[str] = None) -> List[WorkflowDefinition]:
        query = self.db_session.query(WorkflowDefinitionORM)
        if definition_id:
            query = query.filter(WorkflowDefinitionORM.id == definition_id)
        elif name:
            query = query.filter(WorkflowDefinitionORM.name.ilike(f"%{name}%"))
        definitions = query.all()
        return [WorkflowDefinition.model_validate(defn, from_attributes=True) for defn in definitions]

    async def get_workflow_definition_by_id(self, definition_id: str) -> Optional[WorkflowDefinition]:
        defn = self.db_session.query(WorkflowDefinitionORM).filter(WorkflowDefinitionORM.id == definition_id).first()
        return WorkflowDefinition.model_validate(defn, from_attributes=True) if defn else None

    async def create_workflow_instance(self, instance_data: WorkflowInstance) -> WorkflowInstance:
        instance_orm_data = instance_data.model_dump() # Use default mode='python'
        instance = WorkflowInstanceORM(**instance_orm_data)
        self.db_session.add(instance)
        self.db_session.commit()
        self.db_session.refresh(instance)
        return WorkflowInstance.model_validate(instance, from_attributes=True)

    async def update_workflow_instance(self, instance_id: str, instance_update: WorkflowInstance) -> Optional[WorkflowInstance]:
        instance = self.db_session.query(WorkflowInstanceORM).filter(WorkflowInstanceORM.id == instance_id).first()
        if instance:
            update_data = instance_update.model_dump(exclude=set("tasks")) # Use default mode='python'
            for key, value in update_data.items():
                    setattr(instance, key, value)
            self.db_session.commit()
            self.db_session.refresh(instance) # Refresh to get any DB-level changes
            return WorkflowInstance.model_validate(instance, from_attributes=True)
        return None

    async def create_task_instance(self, task_data: TaskInstance) -> TaskInstance:
        task_orm_data = task_data.model_dump() # Use default mode='python'
        task = TaskInstanceORM(**task_orm_data)
        self.db_session.add(task)
        self.db_session.commit()
        self.db_session.refresh(task)
        return TaskInstance.model_validate(task, from_attributes=True)

    async def get_task_instance_by_id(self, task_id: str) -> Optional[TaskInstance]:
        task = self.db_session.query(TaskInstanceORM).filter(TaskInstanceORM.id == task_id).first()
        return TaskInstance.model_validate(task, from_attributes=True) if task else None

    async def update_task_instance(self, task_id: str, task_update: TaskInstance) -> Optional[TaskInstance]:
        task = self.db_session.query(TaskInstanceORM).filter(TaskInstanceORM.id == task_id).first()
        if task:
            update_data = task_update.model_dump() # Use default mode='python'
            for key, value in update_data.items():
                setattr(task, key, value)
            self.db_session.commit()
            self.db_session.refresh(task) # Refresh to get any DB-level changes
            return TaskInstance.model_validate(task, from_attributes=True)
        return None

    async def get_tasks_for_workflow_instance(self, instance_id: str) -> List[TaskInstance]:
        status_order = case(
            (TaskInstanceORM.status == TaskStatus.pending, 0),
            (TaskInstanceORM.status == TaskStatus.completed, 1),
            else_=2
        )
        tasks = self.db_session.query(TaskInstanceORM).filter(
            TaskInstanceORM.workflow_instance_id == instance_id
        ).order_by(status_order, TaskInstanceORM.order).all()
        return [TaskInstance.model_validate(task, from_attributes=True) for task in tasks]

    async def list_workflow_instances_by_user(self, user_id: str, created_at_date: Optional[DateObject] = None,
                                              status: Optional[WorkflowStatus] = None, definition_id: Optional[str] = None) -> List[WorkflowInstance]:
        query = self.db_session.query(WorkflowInstanceORM).filter(WorkflowInstanceORM.user_id == user_id)
        if created_at_date:
            query = query.filter(WorkflowInstanceORM.created_at == created_at_date)
        if status:
            query = query.filter(WorkflowInstanceORM.status == status)
        if definition_id:
            query = query.filter(WorkflowInstanceORM.workflow_definition_id == definition_id)
        instances = query.order_by(WorkflowInstanceORM.created_at.desc()).all()
        return [WorkflowInstance.model_validate(instance, from_attributes=True) for instance in instances]

    async def get_workflow_instance_by_share_token(self, share_token: str) -> Optional[WorkflowInstance]:
        instance_orm = self.db_session.query(WorkflowInstanceORM).filter(WorkflowInstanceORM.share_token == share_token).first()
        if instance_orm:
            return WorkflowInstance.model_validate(instance_orm, from_attributes=True)
        return None

    async def create_workflow_definition(self, definition_data: WorkflowDefinition) -> WorkflowDefinition:
        task_definitions_data = definition_data.task_definitions
        orm_data = definition_data.model_dump(exclude={'task_definitions'}) # mode='python' by default

        definition_orm = WorkflowDefinitionORM(**orm_data)
        self.db_session.add(definition_orm)
        self.db_session.commit()
        self.db_session.refresh(definition_orm)

        for task_def_data in task_definitions_data:
            task_def_orm = TaskDefinitionORM(
                workflow_definition_id=definition_orm.id,
                name=task_def_data.name,
                order=task_def_data.order,
                due_datetime_offset_minutes=task_def_data.due_datetime_offset_minutes
            )
            self.db_session.add(task_def_orm)

        self.db_session.commit()
        self.db_session.refresh(definition_orm)
        return WorkflowDefinition.model_validate(definition_orm, from_attributes=True)

    async def update_workflow_definition(self, definition_id: str, name: str, description: Optional[str],
                                         task_definitions_data: List[TaskDefinitionBase]) -> Optional[WorkflowDefinition]:
        db_definition = self.db_session.query(WorkflowDefinitionORM).filter(
            WorkflowDefinitionORM.id == definition_id).first()
        if db_definition:
            db_definition.name = name
            db_definition.description = description

            self.db_session.query(TaskDefinitionORM).filter(
                TaskDefinitionORM.workflow_definition_id == definition_id
            ).delete(synchronize_session=False) # Added synchronize_session=False

            for task_def_data in task_definitions_data:
                task_def_orm = TaskDefinitionORM(
                    workflow_definition_id=db_definition.id,
                    name=task_def_data.name,
                    order=task_def_data.order,
                    due_datetime_offset_minutes=task_def_data.due_datetime_offset_minutes
                )
                self.db_session.add(task_def_orm)

            self.db_session.commit()
            self.db_session.refresh(db_definition)
            return WorkflowDefinition.model_validate(db_definition, from_attributes=True)
        return None

    async def delete_workflow_definition(self, definition_id: str) -> None:
        db_definition = self.db_session.query(WorkflowDefinitionORM).filter(
            WorkflowDefinitionORM.id == definition_id).first()
        if not db_definition:
            raise DefinitionNotFoundError(f"Workflow Definition with ID '{definition_id}' not found.")

        linked_instances_count = self.db_session.query(WorkflowInstanceORM).filter(
            WorkflowInstanceORM.workflow_definition_id == definition_id).count()
        if linked_instances_count > 0:
            raise DefinitionInUseError(
                f"Cannot delete definition: It is currently used by {linked_instances_count} workflow instance(s).")

        self.db_session.query(TaskDefinitionORM).filter(
            TaskDefinitionORM.workflow_definition_id == definition_id
        ).delete(synchronize_session=False)

        self.db_session.delete(db_definition)
        self.db_session.commit()

    async def get_workflow_instance_by_share_token(self, share_token: str) -> Optional[WorkflowInstance]:
        instance_orm = self.db_session.query(WorkflowInstanceORM).filter(WorkflowInstanceORM.share_token == share_token).first()
        if instance_orm:
            return WorkflowInstance.model_validate(instance_orm, from_attributes=True)
        return None


class InMemoryWorkflowRepository(WorkflowDefinitionRepository, WorkflowInstanceRepository, TaskInstanceRepository):
    def __init__(self):
        self._seed_definitions()

    def _seed_definitions(self):
        if not _workflow_definitions_db:
            def1 = WorkflowDefinition(
                id="def_morning_quick_start", name="Morning Quick Start", description="A simple routine to kick off the day.",
                task_definitions=[ TaskDefinitionBase(name="Make Bed", order=0), TaskDefinitionBase(name="Brush Teeth", order=1), TaskDefinitionBase(name="Get Dressed", order=2)]
            )
            _workflow_definitions_db[def1.id] = def1
            def2 = WorkflowDefinition(
                id="def_evening_wind_down", name="Evening Wind Down", description="Prepare for a good night's sleep.",
                task_definitions=[ TaskDefinitionBase(name="Tidy Up Living Room (5 mins)", order=0), TaskDefinitionBase(name="Prepare Outfit for Tomorrow", order=1), TaskDefinitionBase(name="Read a Book (15 mins)", order=2)]
            )
            _workflow_definitions_db[def2.id] = def2

    async def get_workflow_instance_by_id(self, instance_id: str) -> Optional[WorkflowInstance]:
        instance = _workflow_instances_db.get(instance_id)
        return instance.model_copy(deep=True) if instance else None

    async def list_workflow_definitions(self, name: Optional[str] = None, definition_id: Optional[str] = None) -> List[WorkflowDefinition]:
        definitions = [defn.model_copy(deep=True) for defn in _workflow_definitions_db.values()]
        if definition_id:
            definitions = [defn for defn in definitions if defn.id == definition_id]
        elif name:
            definitions = [defn for defn in definitions if name.lower() in defn.name.lower()]
        return definitions

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
        tasks = [task.model_copy(deep=True) for task in _task_instances_db.values() if task.workflow_instance_id == instance_id]
        return sorted(tasks, key=lambda t: (0 if t.status == TaskStatus.pending else 1, t.order))

    async def list_workflow_instances_by_user(self, user_id: str, created_at_date: Optional[DateObject] = None,
                                              status: Optional[WorkflowStatus] = None, definition_id: Optional[str] = None) -> List[WorkflowInstance]:
        instances = [instance.model_copy(deep=True) for instance in _workflow_instances_db.values() if instance.user_id == user_id]
        if definition_id:
            instances = [instance for instance in instances if instance.workflow_definition_id == definition_id]
        if created_at_date:
            # instance.created_at is a datetime object (from model), created_at_date is a DateObject (date)
            instances = [instance for instance in instances if instance.created_at.date() == created_at_date]
        if status:
            instances = [instance for instance in instances if instance.status == status]
        return sorted(instances, key=lambda i: i.created_at, reverse=True)

    async def get_workflow_instance_by_share_token(self, share_token: str) -> Optional[WorkflowInstance]:
        for instance in _workflow_instances_db.values():
            if instance.share_token == share_token:
                return instance.model_copy(deep=True)
        return None

    async def get_filtered_workflow_instances(self, user_id: Optional[str] = None, status: Optional[WorkflowStatus] = None) -> List[WorkflowInstance]:
        instances = [instance.model_copy(deep=True) for instance in _workflow_instances_db.values()]
        if user_id:
            instances = [inst for inst in instances if inst.user_id == user_id]
        if status:
            instances = [inst for inst in instances if inst.status == status]
        return sorted(instances, key=lambda i: i.created_at, reverse=True)

    async def create_workflow_definition(self, definition_data: WorkflowDefinition) -> WorkflowDefinition:
        new_definition = definition_data.model_copy(deep=True)
        _workflow_definitions_db[new_definition.id] = new_definition
        return new_definition.model_copy(deep=True)

    async def update_workflow_definition(self, definition_id: str, name: str, description: Optional[str],
                                         task_definitions_data: List[TaskDefinitionBase]) -> Optional[WorkflowDefinition]:
        if definition_id in _workflow_definitions_db:
            updated_definition = WorkflowDefinition(
                id=definition_id, name=name, description=description,
                task_definitions=task_definitions_data
            )
            _workflow_definitions_db[definition_id] = updated_definition
            return updated_definition.model_copy(deep=True)
        return None

    async def delete_workflow_definition(self, definition_id: str) -> None:
        if definition_id not in _workflow_definitions_db:
            raise DefinitionNotFoundError(f"Workflow Definition with ID '{definition_id}' not found.")
        linked_instances = any(instance.workflow_definition_id == definition_id for instance in _workflow_instances_db.values())
        if linked_instances:
            raise DefinitionInUseError("Cannot delete definition: It is currently used by one or more workflow instances.")
        del _workflow_definitions_db[definition_id]
