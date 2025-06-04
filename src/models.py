# models.py
import uuid
from datetime import date as DateObject
from typing import Optional, List

from pydantic import BaseModel, Field

from db_models.enums import WorkflowStatus, TaskStatus


class WorkflowDefinition(BaseModel):
    id: str = Field(default_factory=lambda: "def_" + str(uuid.uuid4())[:8])
    name: str
    description: Optional[str] = ""
    task_definitions: List['TaskDefinitionBase'] = Field(default_factory=list)

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


class TaskDefinition(TaskDefinitionBase):
    id: str
    workflow_definition_id: str # Potentially optional or not included if it's clear from context

    class Config:
        from_attributes = True


class TaskInstance(BaseModel):
    id: str = Field(default_factory=lambda: "task_" + str(uuid.uuid4())[:8])
    workflow_instance_id: str
    name: str
    order: int
    status: TaskStatus = TaskStatus.pending

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
    name: str  # Copied from definition for easy display
    user_id: str
    status: WorkflowStatus = WorkflowStatus.active
    created_at: DateObject = Field(default_factory=DateObject.today)
    share_token: Optional[str] = None

    class Config:
        from_attributes = True

    def to_dict(self):
        return self.model_dump(mode='json')

    @classmethod
    def from_dict(cls, data: dict):
        if isinstance(data.get("created_at"), str):
            data["created_at"] = DateObject.fromisoformat(data["created_at"])
        return cls(**data)
