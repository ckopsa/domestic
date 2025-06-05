from typing import Tuple

from fastapi import Depends

from core.html_renderer import HtmlRendererInterface, Jinja2HtmlRenderer
from database import get_db
from repository import WorkflowDefinitionRepository, WorkflowInstanceRepository, TaskInstanceRepository, \
    PostgreSQLWorkflowRepository
from services import WorkflowService
from templating import get_templates

# Collection+JSON specific imports
from cj_hooks import CollectionJSONBuilder, PydanticToItemDataArray, PydanticToTemplateDataArray

# Define a base URL for Collection+JSON responses, e.g. the prefix where CJ API is mounted
CJ_BASE_URL = "/cj"


# Dependency for HTML Renderer
def get_html_renderer() -> HtmlRendererInterface:
    return Jinja2HtmlRenderer(get_templates())

# Dependency for CollectionJSONBuilder
def get_cj_builder() -> CollectionJSONBuilder:
    """
    Provides an instance of the CollectionJSONBuilder, configured for the application.
    """
    return CollectionJSONBuilder(
        base_api_url=CJ_BASE_URL,
        item_data_strategy=PydanticToItemDataArray(),
        template_data_strategy=PydanticToTemplateDataArray()
    )

# --- Dependencies ---
def get_workflow_repository(db=Depends(get_db)) -> Tuple[
    WorkflowDefinitionRepository, WorkflowInstanceRepository, TaskInstanceRepository]:
    """Provides instances of the repository interfaces."""
    repo = PostgreSQLWorkflowRepository(db)
    return repo, repo, repo


def get_workflow_service(
        repos: Tuple[WorkflowDefinitionRepository, WorkflowInstanceRepository, TaskInstanceRepository] = Depends(
            get_workflow_repository)
) -> WorkflowService:
    """Provides an instance of the WorkflowService, injecting the repositories."""
    definition_repo, instance_repo, task_repo = repos
    return WorkflowService(definition_repo=definition_repo, instance_repo=instance_repo, task_repo=task_repo)
