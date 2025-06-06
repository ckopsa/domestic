import uuid
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field

from db_models.enums import WorkflowStatus, TaskStatus


class TaskDefinitionBase(BaseModel):
    name: str
    order: int
    due_datetime_offset_minutes: Optional[int] = 0  # New field


class TaskInstance(BaseModel):
    id: str = Field(default_factory=lambda: "task_" + str(uuid.uuid4())[:8])
    workflow_instance_id: str
    name: str
    order: int
    status: TaskStatus = TaskStatus.pending
    due_datetime: Optional[datetime] = None  # New field

    class Config:
        from_attributes = True


class WorkflowInstance(BaseModel):
    id: str = Field(default_factory=lambda: "wf_" + str(uuid.uuid4())[:8])
    workflow_definition_id: str
    name: Optional[str] = None  # Made name optional
    user_id: str
    status: WorkflowStatus = WorkflowStatus.active
    created_at: datetime = Field(default_factory=datetime.utcnow)
    share_token: Optional[str] = None
    due_datetime: Optional[datetime] = None  # New field

    class Config:
        from_attributes = True


class WorkflowDefinition(BaseModel):
    id: str = Field(default_factory=lambda: "def_" + str(uuid.uuid4())[:8])
    name: str
    description: Optional[str] = ""
    task_definitions: List[TaskDefinitionBase] = Field(default_factory=list)
    due_datetime: Optional[datetime] = None

    class Config:
        from_attributes = True


class WorkflowInstanceCreateRequest(BaseModel):
    definition_id: str
    name: Optional[str] = None
