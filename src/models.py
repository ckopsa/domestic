import uuid
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field

from cj_hooks import CJHooks
from cj_models import Link
from db_models.enums import WorkflowStatus, TaskStatus


class TaskDefinitionBase(BaseModel):
    name: str
    order: int
    due_datetime_offset_minutes: Optional[int] = 0  # New field


class WorkflowDefinition(BaseModel, CJHooks):
    id: str = Field(default_factory=lambda: "def_" + str(uuid.uuid4())[:8])
    name: str
    description: Optional[str] = ""
    task_definitions: List[TaskDefinitionBase] = Field(default_factory=list)
    due_datetime: Optional[datetime] = None  # New field

    def item_links(self, base_api_url: str, resource_name: str) -> List[Link]:
        links = super().item_links(base_api_url, resource_name)  # Call mixin's default if desired
        if self.task_definitions:
            links.append(Link(
                rel="task-definitions",
                href=f"{base_api_url}/{resource_name}/{self.id}/task-definitions",
                prompt="View Task Definitions"
            ))
        links.append(Link(
            rel="start-instance",
            href=f"{base_api_url}/workflow-instances",
            prompt="Start a new instance",
            method="POST"
        ))
        return links

    class Config:
        from_attributes = True


class TaskInstance(BaseModel, CJHooks):
    id: str = Field(default_factory=lambda: "task_" + str(uuid.uuid4())[:8])
    workflow_instance_id: str
    name: str
    order: int
    status: TaskStatus = TaskStatus.pending
    due_datetime: Optional[datetime] = None  # New field

    class Config:
        from_attributes = True


class WorkflowInstance(BaseModel, CJHooks):
    id: str = Field(default_factory=lambda: "wf_" + str(uuid.uuid4())[:8])
    workflow_definition_id: str
    name: str
    user_id: str
    status: WorkflowStatus = WorkflowStatus.active
    created_at: datetime = Field(default_factory=datetime.utcnow)
    share_token: Optional[str] = None
    due_datetime: Optional[datetime] = None  # New field

    class Config:
        from_attributes = True
