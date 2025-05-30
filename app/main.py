# main.py
import os
import sys
from typing import List

# Add the project root to sys.path to ensure 'app' module can be found
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from fastapi import FastAPI, Form, status, Depends, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from app.core.security import AuthenticatedUser, get_current_user, get_current_active_user
from app.repository import WorkflowDefinitionRepository, WorkflowInstanceRepository, TaskInstanceRepository, PostgreSQLWorkflowRepository
from app.services import WorkflowService
from app.database import get_db

app = FastAPI()

# Set up Jinja2 templates
templates = Jinja2Templates(directory="app/templates")

# Mount static files
app.mount("/static", StaticFiles(directory="app/templates"), name="static")

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


# --- Utility for HTML message/error pages ---
def create_message_page(
        request: Request,
        title: str,
        heading: str,
        message: str,
        links: List[tuple[str, str]],
        status_code: int = 200
) -> HTMLResponse:
    """Helper function to render simple HTML message pages using Jinja2 templates."""
    heading_style = "color: #48bb78;"
    if "error" in title.lower() or "fail" in title.lower():
        heading_style = "color: #ef4444;"
    elif "warn" in title.lower():
        heading_style = "color: #f6ad55;"
    
    return templates.TemplateResponse(
        "message.html",
        {
            "request": request,
            "title": title,
            "heading": heading,
            "message": message,
            "links": links,
            "heading_style": heading_style
        },
        status_code=status_code
    )


# --- Routes ---

@app.get("/", response_class=HTMLResponse)
async def read_root(
        request: Request,
        current_user: AuthenticatedUser | None = Depends(get_current_user),
):
    """Serves the homepage."""
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "current_user": current_user
        }
    )


@app.get("/workflow-definitions", response_class=HTMLResponse)
async def list_workflow_definitions_page(request: Request, service: WorkflowService = Depends(get_workflow_service)):
    definitions = await service.list_workflow_definitions()
    return templates.TemplateResponse(
        "workflow_definitions.html",
        {
            "request": request,
            "definitions": definitions
        }
    )


@app.post("/workflow-instances")
async def create_workflow_instance_handler(
        request: Request,
        definition_id: str = Form(...),
        service: WorkflowService = Depends(get_workflow_service),
        current_user: AuthenticatedUser = Depends(get_current_active_user)
):
    instance = await service.create_workflow_instance(definition_id=definition_id, user_id=current_user.user_id)
    if not instance:
        return create_message_page(request, "Creation Failed", "Error", "Could not create workflow instance.",
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
        return create_message_page(request, "Workflow Not Found", "Error 404",
                                   f"Workflow Instance with ID '{instance_id}' not found or access denied.",
                                   [("← Back to Definitions", "/workflow-definitions")], status_code=404)

    instance = details["instance"]
    tasks = details["tasks"]
    return templates.TemplateResponse(
        "workflow_instance.html",
        {
            "request": request,
            "instance": instance,
            "tasks": tasks
        }
    )


@app.post("/task-instances/{task_id}/complete")
async def complete_task_handler(
        request: Request,
        task_id: str,
        service: WorkflowService = Depends(get_workflow_service),
        current_user: AuthenticatedUser = Depends(get_current_active_user)
):
    task = await service.complete_task(task_id, current_user.user_id)
    if not task:
        return create_message_page(request, "Error", "Task Update Failed", "Could not complete task or access denied.",
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
    return templates.TemplateResponse(
        "create_workflow_definition.html",
        {
            "request": request
        }
    )

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
            request,
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
    definition = await service.definition_repo.get_workflow_definition_by_id(definition_id)
    if not definition:
        return create_message_page(
            request,
            "Not Found", 
            "Error 404", 
            f"Workflow Definition with ID '{definition_id}' not found.",
            [("← Back to Definitions", "/workflow-definitions")],
            status_code=404
        )
    
    return templates.TemplateResponse(
        "edit_workflow_definition.html",
        {
            "request": request,
            "definition": definition
        }
    )

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
                request,
                "Update Failed", 
                "Error 404", 
                f"Workflow Definition with ID '{definition_id}' not found.",
                [("← Back to Definitions", "/workflow-definitions")],
                status_code=404
            )
        return RedirectResponse(url="/workflow-definitions", status_code=status.HTTP_303_SEE_OTHER)
    except ValueError as e:
        return create_message_page(
            request,
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
    definition = await service.definition_repo.get_workflow_definition_by_id(definition_id)
    if not definition:
        return create_message_page(
            request,
            "Not Found", 
            "Error 404", 
            f"Workflow Definition with ID '{definition_id}' not found.",
            [("← Back to Definitions", "/workflow-definitions")],
            status_code=404
        )
    
    return templates.TemplateResponse(
        "confirm_delete_workflow_definition.html",
        {
            "request": request,
            "definition": definition
        }
    )

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
            definition = await service.definition_repo.get_workflow_definition_by_id(definition_id)
            if definition:
                return create_message_page(
                    request,
                    "Deletion Failed", 
                    "Error", 
                    "Cannot delete definition: It is currently used by one or more workflow instances.",
                    [("← Back to Definitions", "/workflow-definitions")],
                    status_code=400
                )
            return create_message_page(
                request,
                "Deletion Failed", 
                "Error 404", 
                f"Workflow Definition with ID '{definition_id}' not found.",
                [("← Back to Definitions", "/workflow-definitions")],
                status_code=404
            )
        return RedirectResponse(url="/workflow-definitions", status_code=status.HTTP_303_SEE_OTHER)
    except ValueError as e:
        return create_message_page(
            request,
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
    return templates.TemplateResponse(
        "my_workflows.html",
        {
            "request": request,
            "instances": instances
        }
    )
