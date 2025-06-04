# models.py
import uuid
from datetime import datetime, date as DateObject # Keep DateObject for other uses if any, ensure datetime is primary
from typing import Optional, List

from pydantic import BaseModel, Field

from db_models.enums import WorkflowStatus, TaskStatus


class WorkflowDefinition(BaseModel):
    id: str = Field(default_factory=lambda: "def_" + str(uuid.uuid4())[:8])
    name: str
    description: Optional[str] = ""
    task_definitions: List['TaskDefinitionBase'] = Field(default_factory=list)
    due_datetime: Optional[datetime] = None # New field

    class Config:
        from_attributes = True

    def to_dict(self):
        return self.model_dump(mode='json')

    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)


class TaskDefinitionBase(BaseModel):
    name: str
    order: int
    due_datetime_offset_minutes: Optional[int] = 0 # New field


class TaskDefinition(TaskDefinitionBase):
    id: str
    workflow_definition_id: str

    class Config:
        from_attributes = True


class TaskInstance(BaseModel):
    id: str = Field(default_factory=lambda: "task_" + str(uuid.uuid4())[:8])
    workflow_instance_id: str
    name: str
    order: int
    status: TaskStatus = TaskStatus.pending
    due_datetime: Optional[datetime] = None # New field

    class Config:
        from_attributes = True

    def to_dict(self):
        return self.model_dump(mode='json')

    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)


class WorkflowInstance(BaseModel):
    id: str = Field(default_factory=lambda: "wf_" + str(uuid.uuid4())[:8])
    workflow_definition_id: str
    name: str
    user_id: str
    status: WorkflowStatus = WorkflowStatus.active
    created_at: datetime = Field(default_factory=datetime.utcnow)
    share_token: Optional[str] = None
    due_datetime: Optional[datetime] = None # New field

    class Config:
        from_attributes = True

    def to_dict(self):
        # Ensure datetime objects are handled correctly if they exist
        dump = self.model_dump(mode='json')
        if 'due_datetime' in dump and dump['due_datetime']:
             # Pydantic v2 model_dump handles datetime to ISO string by default
             pass
        return dump

    @classmethod
    def from_dict(cls, data: dict):
        # Updated to handle datetime for created_at
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if isinstance(data.get("due_datetime"), str): # Handle string to datetime conversion
            data["due_datetime"] = datetime.fromisoformat(data["due_datetime"])
        return cls(**data)

# Added for completeness, assuming these were part of the original file
class WorkflowInstanceCreate(BaseModel):
    workflow_definition_id: str
    name: str
    user_id: str
    # due_datetime: Optional[datetime] = None # This might be added here too if needed on creation

class WorkflowInstanceShare(BaseModel):
    workflow_instance_id: str
    user_id: str # or some other identifier for sharing context

class ShareTokenResponse(BaseModel):
    share_token: str

class WorkflowWithTasks(WorkflowInstance): # Assuming this was used somewhere
    tasks: List[TaskInstance] = Field(default_factory=list)

    class Config:
        from_attributes = True # Ensure this is here if inheriting from a model with it

    @classmethod
    def from_dict(cls, data: dict):
        # Handle nested task instantiation if necessary
        if 'tasks' in data:
            data['tasks'] = [TaskInstance.from_dict(task) for task in data['tasks']]

        # Call parent from_dict for other fields
        # This is tricky with Pydantic; direct instantiation is often better
        # For simplicity, assuming direct instantiation or that parent from_dict is compatible
        # Or, handle all fields here explicitly if needed
        # For now, let's assume the basic structure is fine and specific from_dict logic might need refinement
        # based on actual usage.

        # Simplified approach: let Pydantic handle it after type conversion
        # Updated to handle datetime for created_at
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if isinstance(data.get("due_datetime"), str):
            data["due_datetime"] = datetime.fromisoformat(data["due_datetime"])
        return cls(**data)

class WorkflowDefinitionCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    task_definitions: List[TaskDefinitionBase] = Field(default_factory=list)
    # due_datetime: Optional[datetime] = None # This might be added here too if needed on creation
