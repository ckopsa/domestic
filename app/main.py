# main.py
import os
import sys
from typing import List

# Add the project root to sys.path to ensure 'app' module can be found
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from fastapi import FastAPI, Form, status, Depends, Request, HTTPException
from app.core.security import AuthenticatedUser, get_current_user

from dominate import document
from dominate.tags import *
from fastapi.responses import HTMLResponse, RedirectResponse

from app.repository import WorkflowRepository, PostgreSQLWorkflowRepository
from app.services import WorkflowService
from app.style import my_style
from app.database import get_db

app = FastAPI()


# --- Dependencies ---
def get_workflow_repository(db=Depends(get_db)) -> WorkflowRepository:
    """Provides an instance of the WorkflowRepository."""
    return PostgreSQLWorkflowRepository(db)


def get_workflow_service(repo: WorkflowRepository = Depends(get_workflow_repository)) -> WorkflowService:
    """Provides an instance of the WorkflowService, injecting the repository."""
    return WorkflowService(repository=repo)


# --- Utility for HTML message/error pages ---
def create_message_page(
        title: str,
        heading: str,
        message: str,
        links: List[tuple[str, str]],
        status_code: int = 200
) -> HTMLResponse:
    """Helper function to generate simple HTML message pages."""
    doc = document(title=title)
    with doc.head:
        style(my_style)
    with doc.body:
        with div(cls='container'):
            heading_style = "color: #48bb78;"
            if "error" in title.lower() or "fail" in title.lower():
                heading_style = "color: #ef4444;"
            elif "warn" in title.lower():
                heading_style = "color: #f6ad55;"

            h1(heading, style=heading_style)
            p(message)
            for link_text, link_href in links:
                a(link_text, href=link_href, cls='back-link',
                  style="margin-right:15px; display:inline-block; margin-top:10px;")
    return HTMLResponse(content=doc.render(), status_code=status_code)


# --- Routes ---

@app.get("/", response_class=HTMLResponse)
async def read_root(
        request: Request,
        current_user: AuthenticatedUser | None = Depends(get_current_user),
):
    """Serves the homepage."""
    doc = document(title='Simple Checklist MVP')
    with doc.head:
        style(my_style)
    with doc.body:
        with div(cls='container'):
            h1('Simple Checklist MVP')
            p('Manage your simple checklist workflows.')
            h2('Workflows:')
            with ul():
                li(a('Available Workflow Definitions', href='/workflow-definitions', cls='action-button'))
                if current_user:
                    li(a('My Workflows', href='/my-workflows', cls='action-button'))
                else:
                    li(a('Login to View/Create Workflows', href='/docs#/default/login_token_post', cls='action-button'))
    return doc.render()


@app.get("/workflow-definitions", response_class=HTMLResponse)
async def list_workflow_definitions_page(request: Request, service: WorkflowService = Depends(get_workflow_service)):
    definitions = await service.list_workflow_definitions()
    doc = document(title='Available Workflow Definitions')
    with doc.head:
        style(my_style)
    with doc.body:
        with div(cls='container'):
            h1('Available Workflow Definitions')
            if not definitions:
                p("No workflow definitions available.")
            else:
                with ul():
                    for defn in definitions:
                        with li(cls='wip-list-item'):
                            h2(defn.name)
                            p(defn.description or "No description.")
                            p(strong("Tasks: "), ", ".join(defn.task_names) or "None")
                            with form(action="/workflow-instances", method="post", style="margin-top:10px;"):
                                input_(type="hidden", name="definition_id", value=defn.id)
                                button(f"Start '{defn.name}'", type="submit", cls="action-button create-wip-link")
            a('← Back to Home', href='/', cls='back-link', style="margin-top:20px;")
    return doc.render()


@app.post("/workflow-instances")
async def create_workflow_instance_handler(
        request: Request,
        definition_id: str = Form(...),
        service: WorkflowService = Depends(get_workflow_service),
        current_user: AuthenticatedUser = Depends(get_current_user)
):
    if not current_user:
        return RedirectResponse(url="/docs#/default/login_token_post", status_code=status.HTTP_303_SEE_OTHER)
    instance = await service.create_workflow_instance(definition_id=definition_id, user_id=current_user.user_id)
    if not instance:
        return create_message_page("Creation Failed", "Error", "Could not create workflow instance.",
                                   [("← Definitions", "/workflow-definitions")], status_code=500)
    return RedirectResponse(url=f"/workflow-instances/{instance.id}", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/workflow-instances/{instance_id}", response_class=HTMLResponse)
async def read_workflow_instance_page(
        request: Request,
        instance_id: str,
        service: WorkflowService = Depends(get_workflow_service),
        current_user: AuthenticatedUser = Depends(get_current_user)
):
    if not current_user:
        return RedirectResponse(url="/docs#/default/login_token_post", status_code=status.HTTP_303_SEE_OTHER)
    details = await service.get_workflow_instance_with_tasks(instance_id, current_user.user_id)
    if not details or not details["instance"]:
        return create_message_page("Workflow Not Found", "Error 404",
                                   f"Workflow Instance with ID '{instance_id}' not found or access denied.",
                                   [("← Back to Definitions", "/workflow-definitions")], status_code=404)

    instance = details["instance"]
    tasks = details["tasks"]

    doc = document(title=f'Workflow: {instance.name}')
    with doc.head:
        style(my_style)
    with doc.body:
        with div(cls='container'):
            h1(f'Workflow: {instance.name}')
            with div(cls='workflow-details'):
                p(strong('ID:'), f' {instance.id}')
                p(strong('Status:'), f' {instance.status.upper()}')
                p(strong('Created At:'), f' {instance.created_at.isoformat()}')
                h2('Tasks:')
                if not tasks:
                    p("No tasks available for this workflow.")
                else:
                    with ul():
                        for task in tasks:
                            with li(cls='task-item', style="margin-bottom:10px;"):
                                p(strong('Task:'), f' {task.name} - {task.status.upper()}')
                                if task.status == "pending":
                                    with form(action=f"/task-instances/{task.id}/complete", method="post",
                                              style="display:inline; margin-left:10px;"):
                                        button("Mark Complete", type="submit", cls="action-button submit")
                if instance.status == "completed":
                    p("🎉 Workflow Complete!",
                      style="color: green; font-weight: bold; font-size:1.2em; margin-top:15px;")
            a('← Back to Workflow Definitions', href='/workflow-definitions', cls='back-link',
              style="margin-top:20px; display:inline-block;")
            a('← Back to Home', href='/', cls='back-link',
              style="margin-top:20px; display:inline-block; margin-left:15px;")
    return doc.render()


@app.post("/task-instances/{task_id}/complete")
async def complete_task_handler(
        request: Request,
        task_id: str,
        service: WorkflowService = Depends(get_workflow_service),
        current_user: AuthenticatedUser = Depends(get_current_user)
):
    if not current_user:
        return RedirectResponse(url="/docs#/default/login_token_post", status_code=status.HTTP_303_SEE_OTHER)
    task = await service.complete_task(task_id, current_user.user_id)
    if not task:
        return create_message_page("Error", "Task Update Failed", "Could not complete task or access denied.",
                                   [("← Back", "/")],
                                   status_code=400)
    return RedirectResponse(url=f"/workflow-instances/{task.workflow_instance_id}",
                            status_code=status.HTTP_303_SEE_OTHER)


@app.post("/token")
async def login():
    """Placeholder for token generation. In a real app, this would validate username/password."""
    # This is a placeholder. In a real app, you would validate credentials here.
    return {"access_token": "test_user", "token_type": "bearer"}


@app.get("/my-workflows", response_class=HTMLResponse)
async def list_user_workflows(
        request: Request,
        service: WorkflowService = Depends(get_workflow_service),
        current_user: AuthenticatedUser = Depends(get_current_user)
):
    """Serves a page listing all workflow instances for the current user."""
    if not current_user:
        return RedirectResponse(url="/docs#/default/login_token_post", status_code=status.HTTP_303_SEE_OTHER)

    instances = await service.list_instances_for_user(current_user.user_id)
    doc = document(title='My Workflows')
    with doc.head:
        style(my_style)
    with doc.body:
        with div(cls='container'):
            h1('My Workflows')
            if not instances:
                p("You have no workflows yet.")
            else:
                with ul():
                    for instance in instances:
                        with li(cls='wip-list-item'):
                            h2(instance.name)
                            p(strong("Status: "), instance.status.upper())
                            p(strong("Created: "), instance.created_at.isoformat())
                            a("View Details", href=f"/workflow-instances/{instance.id}", cls='action-button')
            a('← Back to Home', href='/', cls='back-link', style="margin-top:20px; display:inline-block;")
            a('← Available Definitions', href='/workflow-definitions', cls='back-link',
              style="margin-top:20px; display:inline-block; margin-left:15px;")
    return doc.render()
