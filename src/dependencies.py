from typing import Tuple

from fastapi import Depends

from src import cj_models # Corrected import
from src.core.html_renderer import HtmlRendererInterface, Jinja2HtmlRenderer # Assuming src. prefix is correct/needed
# Consistent import with how tests will refer to it, assuming project root is in PYTHONPATH
from src.database import get_db
from src.repository import WorkflowDefinitionRepository, WorkflowInstanceRepository, TaskInstanceRepository, \
    PostgreSQLWorkflowRepository # Assuming src. prefix is correct/needed
from src.services import WorkflowService # Assuming src. prefix is correct/needed
from src.templating import get_templates # Assuming src. prefix is correct/needed
from src.transitions import TransitionManager # Assuming src. prefix is correct/needed


# Dependency for HTML Renderer
def get_html_renderer() -> HtmlRendererInterface:
    return Jinja2HtmlRenderer(get_templates())


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


def get_transition_registry() -> TransitionManager:
    return TransitionManager()



