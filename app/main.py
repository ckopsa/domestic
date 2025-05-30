# main.py
import os
import sys

# Add the project root to sys.path to ensure 'app' module can be found
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from fastapi import FastAPI, Depends
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from app.repository import WorkflowDefinitionRepository, WorkflowInstanceRepository, TaskInstanceRepository, PostgreSQLWorkflowRepository
from app.services import WorkflowService
from app.database import get_db
from app.core.html_renderer import HtmlRendererInterface, Jinja2HtmlRenderer
from app.routers import root, workflow_definitions, workflow_instances, tasks, auth, user_workflows

app = FastAPI()

# Set up Jinja2 templates
templates = Jinja2Templates(directory="app/templates")

# Mount static files
app.mount("/static", StaticFiles(directory="app/templates"), name="static")

# Dependency for HTML Renderer
def get_html_renderer() -> HtmlRendererInterface:
    return Jinja2HtmlRenderer(templates)

# --- Dependencies ---
def get_workflow_repository(db=Depends(get_db)) -> tuple[WorkflowDefinitionRepository, WorkflowInstanceRepository, TaskInstanceRepository]:
    """Provides instances of the repository interfaces."""
    repo = PostgreSQLWorkflowRepository(db)
    return repo, repo, repo

def get_workflow_service(
    repos: tuple[WorkflowDefinitionRepository, WorkflowInstanceRepository, TaskInstanceRepository] = Depends(get_workflow_repository)
) -> WorkflowService:
    """Provides an instance of the WorkflowService, injecting the repositories."""
    definition_repo, instance_repo, task_repo = repos
    return WorkflowService(definition_repo=definition_repo, instance_repo=instance_repo, task_repo=task_repo)

# Include routers
app.include_router(root.router)
app.include_router(workflow_definitions.router)
app.include_router(workflow_instances.router)
app.include_router(tasks.router)
app.include_router(auth.router)
app.include_router(user_workflows.router)
