from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import status
from app.services import WorkflowService
from app.core.html_renderer import HtmlRendererInterface
from app.core.security import AuthenticatedUser, get_current_active_user
from app.main import get_workflow_service
from app.utils import create_message_page

router = APIRouter(prefix="/workflow-definitions", tags=["workflow_definitions"])

@router.get("/", response_class=HTMLResponse)
async def list_workflow_definitions_page(
        request: Request,
        service: WorkflowService = Depends(get_workflow_service),
        renderer: HtmlRendererInterface = Depends(get_html_renderer)
):
    definitions = await service.list_workflow_definitions()
    return await renderer.render(
        "workflow_definitions.html",
        request,
        {"definitions": definitions}
    )

@router.get("/create", response_class=HTMLResponse)
async def create_workflow_definition_page(
        request: Request,
        current_user: AuthenticatedUser = Depends(get_current_active_user),
        renderer: HtmlRendererInterface = Depends(get_html_renderer)
):
    """Serves a page for creating a new workflow definition."""
    return await renderer.render("create_workflow_definition.html", request, {})

@router.post("/create", response_class=RedirectResponse)
async def create_workflow_definition_handler(
    request: Request,
    name: str = Form(...),
    description: str = Form(default=""),
    task_names_str: str = Form(...),
    service: WorkflowService = Depends(get_workflow_service),
    current_user: AuthenticatedUser = Depends(get_current_active_user),
    renderer: HtmlRendererInterface = Depends(get_html_renderer)
):
    """Handles the submission of a new workflow definition."""
    try:
        task_names = [task.strip() for task in task_names_str.split('\n') if task.strip()]
        await service.create_new_definition(name=name, description=description, task_names=task_names)
        return RedirectResponse(url="/workflow-definitions", status_code=status.HTTP_303_SEE_OTHER)
    except ValueError as e:
        return await create_message_page(
            request,
            "Creation Failed", 
            "Error", 
            str(e),
            [("← Back to Create Template", "/workflow-definitions/create"), ("← Back to Definitions", "/workflow-definitions")],
            status_code=400,
            renderer=renderer
        )

@router.get("/edit/{definition_id}", response_class=HTMLResponse)
async def edit_workflow_definition_page(
    request: Request, 
    definition_id: str, 
    service: WorkflowService = Depends(get_workflow_service),
    current_user: AuthenticatedUser = Depends(get_current_active_user),
    renderer: HtmlRendererInterface = Depends(get_html_renderer)
):
    """Serves a page for editing an existing workflow definition."""
    definition = await service.definition_repo.get_workflow_definition_by_id(definition_id)
    if not definition:
        return await create_message_page(
            request,
            "Not Found", 
            "Error 404", 
            f"Workflow Definition with ID '{definition_id}' not found.",
            [("← Back to Definitions", "/workflow-definitions")],
            status_code=404,
            renderer=renderer
        )
    
    return await renderer.render("edit_workflow_definition.html", request, {"definition": definition})

@router.post("/edit/{definition_id}", response_class=RedirectResponse)
async def edit_workflow_definition_handler(
    request: Request,
    definition_id: str,
    name: str = Form(...),
    description: str = Form(default=""),
    task_names_str: str = Form(...),
    service: WorkflowService = Depends(get_workflow_service),
    current_user: AuthenticatedUser = Depends(get_current_active_user),
    renderer: HtmlRendererInterface = Depends(get_html_renderer)
):
    """Handles the submission of updates to an existing workflow definition."""
    try:
        task_names = [task.strip() for task in task_names_str.split('\n') if task.strip()]
        updated_definition = await service.update_definition(definition_id=definition_id, name=name, description=description, task_names=task_names)
        if not updated_definition:
            return await create_message_page(
                request,
                "Update Failed", 
                "Error 404", 
                f"Workflow Definition with ID '{definition_id}' not found.",
                [("← Back to Definitions", "/workflow-definitions")],
                status_code=404,
                renderer=renderer
            )
        return RedirectResponse(url="/workflow-definitions", status_code=status.HTTP_303_SEE_OTHER)
    except ValueError as e:
        return await create_message_page(
            request,
            "Update Failed", 
            "Error", 
            str(e),
            [("← Back to Edit Template", f"/workflow-definitions/edit/{definition_id}"), ("← Back to Definitions", "/workflow-definitions")],
            status_code=400,
            renderer=renderer
        )

@router.get("/confirm-delete/{definition_id}", response_class=HTMLResponse)
async def confirm_delete_workflow_definition_page(
    request: Request, 
    definition_id: str, 
    service: WorkflowService = Depends(get_workflow_service),
    current_user: AuthenticatedUser = Depends(get_current_active_user),
    renderer: HtmlRendererInterface = Depends(get_html_renderer)
):
    """Serves a confirmation page for deleting a workflow definition."""
    definition = await service.definition_repo.get_workflow_definition_by_id(definition_id)
    if not definition:
        return await create_message_page(
            request,
            "Not Found", 
            "Error 404", 
            f"Workflow Definition with ID '{definition_id}' not found.",
            [("← Back to Definitions", "/workflow-definitions")],
            status_code=404,
            renderer=renderer
        )
    
    return await renderer.render("confirm_delete_workflow_definition.html", request, {"definition": definition})

@router.post("/delete/{definition_id}", response_class=RedirectResponse)
async def delete_workflow_definition_handler(
    request: Request,
    definition_id: str,
    service: WorkflowService = Depends(get_workflow_service),
    current_user: AuthenticatedUser = Depends(get_current_active_user),
    renderer: HtmlRendererInterface = Depends(get_html_renderer)
):
    """Handles the deletion of a workflow definition."""
    try:
        await service.delete_definition(definition_id)
        return RedirectResponse(url="/workflow-definitions", status_code=status.HTTP_303_SEE_OTHER)
    except ValueError as e:
        error_message = str(e)
        status_code = 400
        if "not found" in error_message.lower():
            status_code = 404
        return await create_message_page(
            request,
            "Deletion Failed", 
            "Error" + ( " 404" if status_code == 404 else "" ),
            error_message,
            [("← Back to Definitions", "/workflow-definitions")],
            status_code=status_code,
            renderer=renderer
        )
