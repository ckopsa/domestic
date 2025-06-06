import uuid
from datetime import datetime
from typing import Optional, List, ClassVar, Dict, Any # Added Dict and Any

from pydantic import BaseModel, Field

from cj_models import CollectionJSONRepresentable, Link, Query, QueryData
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
    name: Optional[str] = None # Made name optional
    user_id: str
    status: WorkflowStatus = WorkflowStatus.active
    created_at: datetime = Field(default_factory=datetime.utcnow)
    share_token: Optional[str] = None
    due_datetime: Optional[datetime] = None  # New field

    class Config:
        from_attributes = True

class CJTaskDefinition(CollectionJSONRepresentable, TaskDefinitionBase):
    id: str = Field(default_factory=lambda: "task_def_" + str(uuid.uuid4())[:8])
    cj_collection_href_template: ClassVar[str] = "/api/cj/task-definitions/"
    cj_item_href_template: ClassVar[str] = "/api/cj/task-definitions/{id}" # Removed trailing slash
    cj_item_rel: ClassVar[str] = "task-definition" # More specific rel
    cj_collection_title: ClassVar[str] = "Task Definitions"

    cj_global_links: ClassVar[List[Link]] = [
        Link(rel="self", href="/api/cj/task-definitions/", prompt="All Task Definitions", method="GET"),
        Link(rel="home", href="/api/cj/", prompt="CJ API Home", method="GET") # home points to CJ root
    ]
    cj_global_queries: ClassVar[List[Query]] = [
        Query(
            rel="search", href="/api/cj/task-definitions/search", prompt="Search Task Definitions",
            name="search_task_definitions", # Consistent naming
            data=[
                QueryData(name="name_contains", value="", prompt="Name contains", type="text"),
                # Removed completed_status as it's not applicable to definitions
            ]
        )
    ]

    # Signature already updated in previous step, just ensuring super() call is correct.
    def get_cj_instance_item_links(self, context: Optional[Dict[str, Any]] = None) -> List[Link]:
        # base_url = self.__class__._get_base_url_from_context(context) # Not needed if super handles context
        links = super().get_cj_instance_item_links(context=context)
        return links


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
    # Add other fields if the API is meant to accept them at creation,
    # e.g., due_datetime: Optional[datetime] = None
    # For now, only definition_id and optional name. User will be from auth.


class CJWorkflowDefinition(WorkflowDefinition, CollectionJSONRepresentable):
    cj_collection_href_template: ClassVar[str] = "/api/cj/workflow-definitions/"
    cj_item_href_template: ClassVar[str] = "/api/cj/workflow-definitions/{id}" # Removed trailing slash
    cj_item_rel: ClassVar[str] = "workflow-definition"
    cj_collection_title: ClassVar[str] = "Workflow Definitions"

    cj_global_links: ClassVar[List[Link]] = [
        Link(rel="self", href="/api/cj/workflow-definitions/", method="GET"),
        Link(rel="create", href="/api/cj/workflow-definitions/", method="POST"),
        Link(rel="home", href="/api/cj/", method="GET"),
    ]
    cj_global_queries: ClassVar[List[Query]] = [
        Query(
            rel="search",
            href="/api/cj/workflow-definitions/search",
            prompt="Search Workflow Definitions",
            name="search_workflow_definitions",
            data=[
                QueryData(name="name_contains", value="", prompt="Name contains", type="text"),
            ],
        )
    ]

    # task_definitions are inherited and will be serialized as part of ItemData


class CJWorkflowInstance(WorkflowInstance, CollectionJSONRepresentable):
    cj_collection_href_template: ClassVar[str] = "/api/cj/workflow-instances/"
    cj_item_href_template: ClassVar[str] = "/api/cj/workflow-instances/{id}" # Removed trailing slash
    cj_item_rel: ClassVar[str] = "workflow-instance"
    cj_collection_title: ClassVar[str] = "Workflow Instances"

    cj_global_links: ClassVar[List[Link]] = [
        Link(rel="self", href="/api/cj/workflow-instances/", method="GET"),
        Link(rel="create", href="/api/cj/workflow-instances/", method="POST"),
        Link(rel="home", href="/api/cj/", method="GET"),
    ]
    cj_global_queries: ClassVar[List[Query]] = [
        Query(
            rel="search",
            href="/api/cj/workflow-instances/search",
            prompt="Search Workflow Instances",
            name="search_workflow_instances",
            data=[
                QueryData(name="user_id", value="", prompt="User ID", type="text"),
                QueryData(name="status", value="", prompt="Status", type="text"), # Assuming status is string representable
            ],
        )
    ]

    # Signature already updated, ensure calls to _resolve_href and super() are correct
    def get_cj_instance_item_links(self, context: Optional[Dict[str, Any]] = None) -> List[Link]:
        links = super().get_cj_instance_item_links(context=context)
        links.append(
            Link(
                rel="workflow-definition",
                href=self.__class__._resolve_href(
                    context=context,
                    template_str=CJWorkflowDefinition.cj_item_href_template.format(id=self.workflow_definition_id)
                ),
                prompt="Parent Workflow Definition",
                method="GET",
            )
        )
        # Construct the instance's own href path first for the tasks link
        instance_item_path = self.cj_item_href_template.format(id=self.id)
        links.append(
            Link(
                rel="tasks",
                href=self.__class__._resolve_href(
                    context=context,
                    template_str=f"{instance_item_path}/tasks/"
                ),
                prompt="Task Instances for this Workflow",
                method="GET",
            )
        )
        return links


class CJTaskInstance(TaskInstance, CollectionJSONRepresentable):
    cj_collection_href_template: ClassVar[str] = "/api/cj/task-instances/"
    cj_item_href_template: ClassVar[str] = "/api/cj/task-instances/{id}" # Removed trailing slash
    cj_item_rel: ClassVar[str] = "task-instance"
    cj_collection_title: ClassVar[str] = "Task Instances"

    cj_global_links: ClassVar[List[Link]] = [
        Link(rel="self", href="/api/cj/task-instances/", method="GET"),
        Link(rel="home", href="/api/cj/", method="GET"),
    ]
    cj_global_queries: ClassVar[List[Query]] = [
        Query(
            rel="search",
            href="/api/cj/task-instances/search",
            prompt="Search Task Instances",
            name="search_task_instances",
            data=[
                QueryData(name="status", value="", prompt="Status", type="text"), # Assuming status is string representable
            ],
        )
    ]

    # Signature already updated, ensure calls to _resolve_href and super() are correct
    def get_cj_instance_item_links(self, context: Optional[Dict[str, Any]] = None) -> List[Link]:
        links = super().get_cj_instance_item_links(context=context)
        links.append(
            Link(
                rel="workflow-instance",
                href=self.__class__._resolve_href(
                    context=context,
                    template_str=CJWorkflowInstance.cj_item_href_template.format(id=self.workflow_instance_id)
                ),
                prompt="Parent Workflow Instance",
                method="GET",
            )
        )

        resolved_item_href = self.__class__._resolve_href(context=context, template_str=(self.cj_href or "")) if self.cj_href else None

        if resolved_item_href:
            if self.status == TaskStatus.pending or self.status == TaskStatus.in_progress:
                links.append(
                    Link(
                        rel="complete",
                        href=f"{resolved_item_href}/complete",
                        prompt="Complete Task",
                        method="POST",
                    )
                )
            if self.status == TaskStatus.completed:
                links.append(
                    Link(
                        rel="undo-complete",
                        href=f"{resolved_item_href}/undo-complete",
                        prompt="Undo Task Completion",
                        method="POST",
                    )
                )
        return links


