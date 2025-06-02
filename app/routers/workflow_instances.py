from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import status
from app.services import WorkflowService
from app.core.html_renderer import HtmlRendererInterface
from app.core.security import AuthenticatedUser, get_current_active_user
from app.dependencies import get_workflow_service, get_html_renderer
from app.utils import create_message_page

router = APIRouter(prefix="/workflow-instances", tags=["workflow_instances"])

@router.get("/dashboard", response_class=HTMLResponse)
async def workflow_dashboard_page(
        request: Request,
        service: WorkflowService = Depends(get_workflow_service),
        current_user: AuthenticatedUser = Depends(get_current_active_user),
        renderer: HtmlRendererInterface = Depends(get_html_renderer)
):
    if isinstance(current_user, RedirectResponse):
        return current_user
    
    instances = await service.list_instances_for_user(current_user.user_id)
    
    return await renderer.render(
        "workflow_dashboard.html",
        request,
        {"instances": instances}
    )

@router.post("", response_class=RedirectResponse)
async def create_workflow_instance_handler(
        request: Request,
        definition_id: str = Form(...),
        service: WorkflowService = Depends(get_workflow_service),
        current_user: AuthenticatedUser = Depends(get_current_active_user),
        renderer: HtmlRendererInterface = Depends(get_html_renderer)
):
    if isinstance(current_user, RedirectResponse):
        return current_user
    instance = await service.create_workflow_instance(definition_id=definition_id, user_id=current_user.user_id)
    if not instance:
        return await create_message_page(
            request, "Creation Failed", "Error", "Could not create workflow instance.",
            [("← Definitions", "/workflow-definitions")], status_code=500, renderer=renderer
        )
    return RedirectResponse(url=f"/workflow-instances/{instance.id}", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/{instance_id}", response_class=HTMLResponse)
async def read_workflow_instance_page(
        request: Request,
        instance_id: str,
        service: WorkflowService = Depends(get_workflow_service),
        current_user: AuthenticatedUser = Depends(get_current_active_user),
        renderer: HtmlRendererInterface = Depends(get_html_renderer)
):
    if isinstance(current_user, RedirectResponse):
        return current_user
    details = await service.get_workflow_instance_with_tasks(instance_id, current_user.user_id)
    if not details or not details["instance"]:
        return await create_message_page(
            request, "Workflow Not Found", "Error 404",
            f"Workflow Instance with ID '{instance_id}' not found or access denied.",
            [("← Back to Definitions", "/workflow-definitions")], status_code=404, renderer=renderer
        )

    instance = details["instance"]
    tasks = details["tasks"]
    return await renderer.render(
        "workflow_instance.html",
        request,
        {"instance": instance, "tasks": tasks}
    )

@router.get("/{instance_id}/dashboard", response_class=HTMLResponse)
async def read_single_workflow_dashboard_page(
        request: Request,
        instance_id: str,
        service: WorkflowService = Depends(get_workflow_service),
        current_user: AuthenticatedUser = Depends(get_current_active_user),
        renderer: HtmlRendererInterface = Depends(get_html_renderer)
):
    if isinstance(current_user, RedirectResponse): # Handle if user is not authenticated
        return current_user

    details = await service.get_workflow_instance_with_tasks(instance_id, current_user.user_id)

    if not details or not details["instance"]:
        return await create_message_page(
            request, 
            "Workflow Dashboard Not Found", 
            "Error 404",
            f"Workflow Instance Dashboard for ID '{instance_id}' not found or access denied.",
            [("← Back to All Workflows Dashboard", "/workflow-instances/dashboard")], 
            status_code=404, 
            renderer=renderer
        )

    instance = details["instance"]
    tasks = details["tasks"]
    
    return await renderer.render(
        "single_workflow_dashboard.html",
        request,
        {"instance": instance, "tasks": tasks, "current_user": current_user}
    )
