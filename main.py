# main.py
import uuid
from datetime import datetime, date as DateObject
from typing import Optional, List

from dominate import document
from dominate.tags import *
from fastapi import FastAPI, HTTPException, Form, status, Depends
from fastapi.responses import HTMLResponse, RedirectResponse

from models import WorkflowDefinition, WorkflowInstance, TaskInstance
from repository import InMemoryWorkflowRepository, WorkflowRepository
from services import WorkflowService
from style import my_style

app = FastAPI()

# --- Dependencies ---
def get_workflow_repository() -> WorkflowRepository:
    """Provides an instance of the WorkflowRepository."""
    return InMemoryWorkflowRepository()

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
                a(link_text, href=link_href, cls='back-link', style="margin-right:15px; display:inline-block; margin-top:10px;")
    return HTMLResponse(content=doc.render(), status_code=status_code)

# --- Routes ---

@app.get("/", response_class=HTMLResponse)
async def read_root():
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
    return doc.render()

@app.get("/workflow-definitions", response_class=HTMLResponse)
async def list_workflow_definitions_page(service: WorkflowService = Depends(get_workflow_service)):
    definitions = await service.list_workflow_definitions()
    doc = document(title='Available Workflow Definitions')
    with doc.head: style(my_style)
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
    definition_id: str = Form(...),
    service: WorkflowService = Depends(get_workflow_service)
):
    instance = await service.create_workflow_instance(definition_id=definition_id)
    if not instance:
        return create_message_page("Creation Failed", "Error", "Could not create workflow instance.", [("← Definitions", "/workflow-definitions")], status_code=500)
    return RedirectResponse(url=f"/workflow-instances/{instance.id}", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/workflow-instances/{instance_id}", response_class=HTMLResponse)
async def read_workflow_instance_page(instance_id: str, service: WorkflowService = Depends(get_workflow_service)):
    details = await service.get_workflow_instance_with_tasks(instance_id)
    if not details or not details["instance"]:
        return create_message_page("Workflow Not Found", "Error 404", f"Workflow Instance with ID '{instance_id}' not found.", [("← Back to Definitions", "/workflow-definitions")], status_code=404)

    instance = details["instance"]
    tasks = details["tasks"]

    doc = document(title=f'Workflow: {instance.name}')
    with doc.head: style(my_style)
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
                                    with form(action=f"/task-instances/{task.id}/complete", method="post", style="display:inline; margin-left:10px;"):
                                        button("Mark Complete", type="submit", cls="action-button submit")
                if instance.status == "completed":
                    p("🎉 Workflow Complete!", style="color: green; font-weight: bold; font-size:1.2em; margin-top:15px;")
            a('← Back to Workflow Definitions', href='/workflow-definitions', cls='back-link', style="margin-top:20px; display:inline-block;")
            a('← Back to Home', href='/', cls='back-link', style="margin-top:20px; display:inline-block; margin-left:15px;")
    return doc.render()

@app.post("/task-instances/{task_id}/complete")
async def complete_task_handler(
    task_id: str,
    service: WorkflowService = Depends(get_workflow_service)
):
    task = await service.complete_task(task_id)
    if not task:
        return create_message_page("Error", "Task Update Failed", "Could not complete task.", [("← Back", "/")], status_code=400)
    return RedirectResponse(url=f"/workflow-instances/{task.workflow_instance_id}", status_code=status.HTTP_303_SEE_OTHER)
