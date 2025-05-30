# main.py
import os
import sys
from typing import List

# Add the project root to sys.path to ensure 'app' module can be found
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from fastapi import FastAPI, Form, status, Depends, Request, HTTPException
from app.core.security import AuthenticatedUser, get_current_user, get_current_active_user

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
                    li(a(f'Logged in as: {current_user.username}', href='#', cls='action-button disabled',
                         style='pointer-events: none;'))
                    li(a('Logout', href='/logout', cls='action-button'))
                else:
                    li(a('Login to View/Create Workflows', href='/login', cls='action-button'))
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
                            a('Edit', href=f'/edit-workflow-definition/{defn.id}', cls='action-button', style="background-color: #f6ad55; margin-left: 10px;")
                            with form(action=f'/confirm-delete-workflow-definition/{defn.id}', method="get", style="display:inline; margin-left: 10px;"):
                                button('Delete', type='submit', cls='action-button cancel')
            a('← Back to Home', href='/', cls='back-link', style="margin-top:20px;")
            a('Create New Checklist Template', href='/create-workflow-definition', cls='action-button', style="margin-top:20px;")
    return doc.render()


@app.post("/workflow-instances")
async def create_workflow_instance_handler(
        request: Request,
        definition_id: str = Form(...),
        service: WorkflowService = Depends(get_workflow_service),
        current_user: AuthenticatedUser = Depends(get_current_active_user)
):
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
        current_user: AuthenticatedUser = Depends(get_current_active_user)
):
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
        current_user: AuthenticatedUser = Depends(get_current_active_user)
):
    task = await service.complete_task(task_id, current_user.user_id)
    if not task:
        return create_message_page("Error", "Task Update Failed", "Could not complete task or access denied.",
                                   [("← Back", "/")],
                                   status_code=400)
    return RedirectResponse(url=f"/workflow-instances/{task.workflow_instance_id}",
                            status_code=status.HTTP_303_SEE_OTHER)


@app.get("/login", response_class=RedirectResponse)
async def redirect_to_keycloak_login(request: Request, redirect: str = None):
    """Redirect to Keycloak login page, storing the original URL for post-login redirect."""
    from app.config import KEYCLOAK_SERVER_URL, KEYCLOAK_REALM, KEYCLOAK_API_CLIENT_ID
    original_url = redirect if redirect else str(request.headers.get('referer', '/'))
    login_url = (
        f"{KEYCLOAK_SERVER_URL}realms/{KEYCLOAK_REALM}/protocol/openid-connect/auth"
        f"?client_id={KEYCLOAK_API_CLIENT_ID}&response_type=code&redirect_uri=http://localhost:8000/callback"
        f"&state={original_url}"
    )
    return RedirectResponse(url=login_url)


@app.get("/callback", response_class=RedirectResponse)
async def handle_keycloak_callback(code: str, state: str = None):
    """Handle the callback from Keycloak with the authorization code."""
    from app.config import KEYCLOAK_SERVER_URL, KEYCLOAK_REALM, KEYCLOAK_API_CLIENT_ID, KEYCLOAK_API_CLIENT_SECRET
    import requests

    token_url = f"{KEYCLOAK_SERVER_URL}realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"
    payload = {
        "grant_type": "authorization_code",
        "client_id": KEYCLOAK_API_CLIENT_ID,
        "client_secret": KEYCLOAK_API_CLIENT_SECRET,
        "code": code,
        "redirect_uri": "http://localhost:8000/callback"
    }

    response = requests.post(token_url, data=payload)
    if response.status_code != 200:
        raise HTTPException(status_code=400,
                            detail=f"Failed to exchange authorization code for token. Keycloak response: {response.text}")

    token_data = response.json()
    access_token = token_data.get("access_token")

    if not access_token:
        raise HTTPException(status_code=400, detail="No access token received from Keycloak")

    # Create a redirect response and set the token as a secure cookie
    redirect_url = state if state else "/"
    redirect_response = RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
    redirect_response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,  # Prevents JavaScript access to the cookie
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",  # Helps prevent CSRF
        max_age=token_data.get("expires_in", 3600)  # Set cookie expiration to match token expiration
    )

    return redirect_response


# Note: The actual token endpoint will be handled by Keycloak
# This is just a placeholder for Swagger UI compatibility
@app.post("/token")
async def token_placeholder():
    """Placeholder for token endpoint - actual authentication handled by Keycloak."""
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Authentication handled by Keycloak. Use /login endpoint or configure client to use Keycloak directly."
    )

@app.get("/create-workflow-definition", response_class=HTMLResponse)
async def create_workflow_definition_page(request: Request, current_user: AuthenticatedUser = Depends(get_current_active_user)):
    """Serves a page for creating a new workflow definition."""
    doc = document(title='Create New Checklist Template')
    with doc.head:
        style(my_style)
    with doc.body:
        with div(cls='container'):
            h1('Create New Checklist Template')
            with form(action="/create-workflow-definition", method="post"):
                with div():
                    label('Definition Name:', for_="name")
                    input_(type="text", name="name", id="name", required=True)
                with div():
                    label('Description:', for_="description")
                    textarea(name="description", id="description", rows=3)
                with div():
                    label('Task Names (one per line):', for_="task_names_str")
                    textarea(name="task_names_str", id="task_names_str", rows=5, placeholder="Enter one task name per line", required=True)
                button('Create Template', type="submit", cls="action-button submit")
            a('← Back to Available Definitions', href='/workflow-definitions', cls='back-link', style="margin-top:20px; display:inline-block;")
            a('← Back to Home', href='/', cls='back-link', style="margin-top:20px; display:inline-block; margin-left:15px;")
    return doc.render()

@app.post("/create-workflow-definition", response_class=RedirectResponse)
async def create_workflow_definition_handler(
    request: Request,
    name: str = Form(...),
    description: str = Form(default=""),
    task_names_str: str = Form(...),
    service: WorkflowService = Depends(get_workflow_service),
    current_user: AuthenticatedUser = Depends(get_current_active_user)
):
    """Handles the submission of a new workflow definition."""
    try:
        task_names = [task.strip() for task in task_names_str.split('\n') if task.strip()]
        await service.create_new_definition(name=name, description=description, task_names=task_names)
        return RedirectResponse(url="/workflow-definitions", status_code=status.HTTP_303_SEE_OTHER)
    except ValueError as e:
        return create_message_page(
            "Creation Failed", 
            "Error", 
            str(e),
            [("← Back to Create Template", "/create-workflow-definition"), ("← Back to Definitions", "/workflow-definitions")],
            status_code=400
        )

@app.get("/edit-workflow-definition/{definition_id}", response_class=HTMLResponse)
async def edit_workflow_definition_page(
    request: Request, 
    definition_id: str, 
    service: WorkflowService = Depends(get_workflow_service),
    current_user: AuthenticatedUser = Depends(get_current_active_user)
):
    """Serves a page for editing an existing workflow definition."""
    definition = await service.repository.get_workflow_definition_by_id(definition_id)
    if not definition:
        return create_message_page(
            "Not Found", 
            "Error 404", 
            f"Workflow Definition with ID '{definition_id}' not found.",
            [("← Back to Definitions", "/workflow-definitions")],
            status_code=404
        )
    
    doc = document(title=f'Edit Checklist Template: {definition.name}')
    with doc.head:
        style(my_style)
    with doc.body:
        with div(cls='container'):
            h1(f'Edit Checklist Template: {definition.name}')
            with form(action=f"/edit-workflow-definition/{definition_id}", method="post"):
                with div():
                    label('Definition Name:', for_="name")
                    input_(type="text", name="name", id="name", value=definition.name, required=True)
                with div():
                    label('Description:', for_="description")
                    textarea(name="description", id="description", rows=3, text=definition.description or "")
                with div():
                    label('Task Names (one per line):', for_="task_names_str")
                    textarea(name="task_names_str", id="task_names_str", rows=5, placeholder="Enter one task name per line", required=True, text="\n".join(definition.task_names))
                button('Save Changes', type="submit", cls="action-button submit")
            a('← Back to Available Definitions', href='/workflow-definitions', cls='back-link', style="margin-top:20px; display:inline-block;")
            a('← Back to Home', href='/', cls='back-link', style="margin-top:20px; display:inline-block; margin-left:15px;")
    return doc.render()

@app.post("/edit-workflow-definition/{definition_id}", response_class=RedirectResponse)
async def edit_workflow_definition_handler(
    request: Request,
    definition_id: str,
    name: str = Form(...),
    description: str = Form(default=""),
    task_names_str: str = Form(...),
    service: WorkflowService = Depends(get_workflow_service),
    current_user: AuthenticatedUser = Depends(get_current_active_user)
):
    """Handles the submission of updates to an existing workflow definition."""
    try:
        task_names = [task.strip() for task in task_names_str.split('\n') if task.strip()]
        updated_definition = await service.update_definition(definition_id=definition_id, name=name, description=description, task_names=task_names)
        if not updated_definition:
            return create_message_page(
                "Update Failed", 
                "Error 404", 
                f"Workflow Definition with ID '{definition_id}' not found.",
                [("← Back to Definitions", "/workflow-definitions")],
                status_code=404
            )
        return RedirectResponse(url="/workflow-definitions", status_code=status.HTTP_303_SEE_OTHER)
    except ValueError as e:
        return create_message_page(
            "Update Failed", 
            "Error", 
            str(e),
            [("← Back to Edit Template", f"/edit-workflow-definition/{definition_id}"), ("← Back to Definitions", "/workflow-definitions")],
            status_code=400
        )

@app.get("/confirm-delete-workflow-definition/{definition_id}", response_class=HTMLResponse)
async def confirm_delete_workflow_definition_page(
    request: Request, 
    definition_id: str, 
    service: WorkflowService = Depends(get_workflow_service),
    current_user: AuthenticatedUser = Depends(get_current_active_user)
):
    """Serves a confirmation page for deleting a workflow definition."""
    definition = await service.repository.get_workflow_definition_by_id(definition_id)
    if not definition:
        return create_message_page(
            "Not Found", 
            "Error 404", 
            f"Workflow Definition with ID '{definition_id}' not found.",
            [("← Back to Definitions", "/workflow-definitions")],
            status_code=404
        )
    
    doc = document(title=f'Confirm Delete: {definition.name}')
    with doc.head:
        style(my_style)
    with doc.body:
        with div(cls='container'):
            h1(f'Confirm Delete: {definition.name}')
            p(f"Are you sure you want to delete the workflow definition '{definition.name}'? This action cannot be undone.")
            with form(action=f"/delete-workflow-definition/{definition_id}", method="post"):
                button('Yes, Delete Permanently', type="submit", cls="action-button cancel")
            a('No, Cancel', href='/workflow-definitions', cls='back-link', style="margin-top:20px; display:inline-block;")
    return doc.render()

@app.post("/delete-workflow-definition/{definition_id}", response_class=RedirectResponse)
async def delete_workflow_definition_handler(
    request: Request,
    definition_id: str,
    service: WorkflowService = Depends(get_workflow_service),
    current_user: AuthenticatedUser = Depends(get_current_active_user)
):
    """Handles the deletion of a workflow definition."""
    try:
        was_deleted = await service.delete_definition(definition_id)
        if not was_deleted:
            definition = await service.repository.get_workflow_definition_by_id(definition_id)
            if definition:
                return create_message_page(
                    "Deletion Failed", 
                    "Error", 
                    "Cannot delete definition: It is currently used by one or more workflow instances.",
                    [("← Back to Definitions", "/workflow-definitions")],
                    status_code=400
                )
            return create_message_page(
                "Deletion Failed", 
                "Error 404", 
                f"Workflow Definition with ID '{definition_id}' not found.",
                [("← Back to Definitions", "/workflow-definitions")],
                status_code=404
            )
        return RedirectResponse(url="/workflow-definitions", status_code=status.HTTP_303_SEE_OTHER)
    except ValueError as e:
        return create_message_page(
            "Deletion Failed", 
            "Error", 
            str(e),
            [("← Back to Definitions", "/workflow-definitions")],
            status_code=400
        )


@app.get("/logout", response_class=RedirectResponse)
async def logout():
    """Logout user by clearing cookies and redirecting to Keycloak logout."""
    from app.config import KEYCLOAK_SERVER_URL, KEYCLOAK_REALM, KEYCLOAK_API_CLIENT_ID
    from urllib.parse import quote_plus

    post_logout_redirect_to_app = "http://localhost:8000/login"
    encoded_post_logout_redirect = quote_plus(post_logout_redirect_to_app)

    keycloak_logout_url = (
        f"{KEYCLOAK_SERVER_URL}realms/{KEYCLOAK_REALM}/protocol/openid-connect/logout"
        f"?post_logout_redirect_uri={encoded_post_logout_redirect}&client_id={KEYCLOAK_API_CLIENT_ID}"
    )

    response = RedirectResponse(url=keycloak_logout_url, status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(key="access_token")
    return response


@app.get("/my-workflows", response_class=HTMLResponse)
async def list_user_workflows(
        request: Request,
        service: WorkflowService = Depends(get_workflow_service),
        current_user: AuthenticatedUser = Depends(get_current_active_user)
):
    """Serves a page listing all workflow instances for the current user."""
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
            a('Create New Checklist Template', href='/create-workflow-definition', cls='action-button', style="margin-top:20px; display:inline-block; margin-left:15px;")
            a('Logout', href='/logout', cls='back-link', style="margin-top:20px; display:inline-block; margin-left:15px;")
    return doc.render()
