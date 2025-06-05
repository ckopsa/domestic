import uuid
from datetime import datetime
from typing import Optional, List, ClassVar

from pydantic import BaseModel, Field

from cj_models import CollectionJSONRepresentable, Link, Query, QueryData
from db_models.enums import WorkflowStatus, TaskStatus


class TaskDefinitionBase(BaseModel):
    name: str
    order: int
    due_datetime_offset_minutes: Optional[int] = 0  # New field


class CJTaskDefinition(CollectionJSONRepresentable, TaskDefinitionBase):
    id: str = Field(default_factory=lambda: "task_def_" + str(uuid.uuid4())[:8])
    cj_collection_href_template: ClassVar[str] = "/tasks/"
    cj_item_href_template: ClassVar[str] = "/tasks/{id}/"
    cj_item_rel: ClassVar[str] = "task"
    cj_collection_title: ClassVar[str] = "Task Definitions"

    cj_global_links: ClassVar[List[Link]] = [
        Link(rel="self", href="/tasks/", prompt="All Task Definitions", method="GET"),
        Link(rel="home", href="/", prompt="API Home", method="GET")
    ]
    cj_global_queries: ClassVar[List[Query]] = [
        Query(
            rel="search", href="/tasks/search", prompt="Search Task Definitions",
            name="search_tasks",
            data=[
                QueryData(name="name_contains", value="", prompt="Name contains", type="text"),
                QueryData(name="completed_status", value="", prompt="Completed Status (true/false)", type="boolean")
            ]
        )
    ]

    def get_cj_instance_item_links(self, base_url: str = "") -> List[Link]:
        links = super().get_cj_instance_item_links(base_url=base_url)  # Gets base edit/delete
        resolved_item_href = self._resolve_href(self.cj_href or "", base_url=base_url) if self.cj_href else None

        if resolved_item_href and not self.is_completed:
            links.append(Link(
                rel="mark-complete",
                href=f"{resolved_item_href}/complete",
                prompt="Mark as Complete",
                method="POST"
            ))
        elif resolved_item_href and self.is_completed:
            links.append(Link(
                rel="mark-incomplete",
                href=f"{resolved_item_href}/incomplete",
                prompt="Mark as Incomplete",
                method="POST"
            ))
        return links


class WorkflowDefinition(BaseModel):
    id: str = Field(default_factory=lambda: "def_" + str(uuid.uuid4())[:8])
    name: str
    description: Optional[str] = ""
    task_definitions: List[TaskDefinitionBase] = Field(default_factory=list)
    due_datetime: Optional[datetime] = None

    class Config:
        from_attributes = True


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
    name: str
    user_id: str
    status: WorkflowStatus = WorkflowStatus.active
    created_at: datetime = Field(default_factory=datetime.utcnow)
    share_token: Optional[str] = None
    due_datetime: Optional[datetime] = None  # New field

    class Config:
        from_attributes = True
