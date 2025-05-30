# models.py
import uuid
from datetime import date as DateObject
from typing import Optional, Literal, List

from pydantic import BaseModel, Field

WorkflowStatus = Literal["active", "completed"]
TaskStatus = Literal["pending", "completed"]


class WorkflowDefinition(BaseModel):
    id: str = Field(default_factory=lambda: "def_" + str(uuid.uuid4())[:8])
    name: str
    description: Optional[str] = ""
    task_names: List[str] = Field(default_factory=list)  # Simple list of task names for MVP

    def to_dict(self):
        return self.model_dump(mode='json')

    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)


class TaskInstance(BaseModel):
    id: str = Field(default_factory=lambda: "task_" + str(uuid.uuid4())[:8])
    workflow_instance_id: str
    name: str
    order: int
    status: TaskStatus = "pending"

    def to_dict(self):
        return self.model_dump(mode='json')

    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)


class WorkflowInstance(BaseModel):
    id: str = Field(default_factory=lambda: "wf_" + str(uuid.uuid4())[:8])
    workflow_definition_id: str
    name: str  # Copied from definition for easy display
    status: WorkflowStatus = "active"
    created_at: DateObject = Field(default_factory=DateObject.today)
    task_ids: List[str] = Field(default_factory=list)  # List of TaskInstance IDs

    def to_dict(self):
        return self.model_dump(mode='json')

    @classmethod
    def from_dict(cls, data: dict):
        if isinstance(data.get("created_at"), str):
            data["created_at"] = DateObject.fromisoformat(data["created_at"])
        return cls(**data)
