from typing import Tuple

from fastapi import Depends, Request

from core.html_renderer import HtmlRendererInterface, Jinja2HtmlRenderer
from core.representor import Representor
from database import get_db
from repository import WorkflowDefinitionRepository, WorkflowInstanceRepository, TaskInstanceRepository, \
    APIKeyRepository, PostgreSQLWorkflowRepository
from services import WorkflowService
from templating import get_templates
from transitions import TransitionManager


def get_html_renderer() -> HtmlRendererInterface:
    return Jinja2HtmlRenderer(get_templates())


def get_workflow_repository(db=Depends(get_db)) -> Tuple[
    WorkflowDefinitionRepository, WorkflowInstanceRepository, TaskInstanceRepository, APIKeyRepository]:
    """Provides instances of the repository interfaces."""
    repo = PostgreSQLWorkflowRepository(db)
    return repo, repo, repo, repo


def get_workflow_service(
        repos: Tuple[WorkflowDefinitionRepository, WorkflowInstanceRepository, TaskInstanceRepository, APIKeyRepository] = Depends(
            get_workflow_repository)
) -> WorkflowService:
    """Provides an instance of the WorkflowService, injecting the repositories."""
    definition_repo, instance_repo, task_repo, _ = repos
    return WorkflowService(definition_repo=definition_repo, instance_repo=instance_repo, task_repo=task_repo)


def get_api_key_repository(db=Depends(get_db)) -> APIKeyRepository:
    """Provides an instance of the API key repository."""
    repo = PostgreSQLWorkflowRepository(db)
    return repo


def get_transition_registry(request: Request) -> TransitionManager:
    return TransitionManager(request)


def get_representor(
        request: Request,
        html_renderer: HtmlRendererInterface = Depends(get_html_renderer),
) -> Representor:
    """Provides an instance of the Representor."""
    return Representor(
        request=request,
        html_renderer=html_renderer,
    )
