from fastapi import APIRouter, Request, Form, Depends
from fastapi import status
from fastapi.responses import HTMLResponse, RedirectResponse

from core.html_renderer import HtmlRendererInterface
from core.security import AuthenticatedUser, get_current_active_user
from dependencies import get_workflow_service, get_html_renderer
from models import WorkflowStatus  # Added import
from services import WorkflowService
from utils import create_message_page

router = APIRouter(prefix="/workflow-instances", tags=["workflow_instances"])


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


@router.post("/{instance_id}/archive", response_class=HTMLResponse)
async def archive_workflow_instance_handler(
        request: Request,
        instance_id: str,
        service: WorkflowService = Depends(get_workflow_service),
        current_user: AuthenticatedUser = Depends(get_current_active_user),
        renderer: HtmlRendererInterface = Depends(get_html_renderer)
):
    if isinstance(current_user, RedirectResponse):  # Handles unauthenticated users
        return current_user

    # Attempt to archive the instance
    # The service method already checks for user_id match and if instance is COMPLETED.
    # It returns None if archiving is not possible or instance not found.
    archived_instance_result = await service.archive_workflow_instance(instance_id, current_user.user_id)

    if archived_instance_result:
        # If successful and instance is now archived, redirect
        # We assume archive_workflow_instance returns the updated instance which should have ARCHIVED status
        return RedirectResponse(url=f"/workflow-instances/{instance_id}", status_code=status.HTTP_303_SEE_OTHER)
    else:
        # Archiving failed, determine why for a more specific error message.
        # Re-fetch the instance details. Note: service.archive_workflow_instance might have returned None
        # because the instance was not found OR because it was completed OR because it didn't belong to user.
        instance_details = await service.get_workflow_instance_with_tasks(instance_id, current_user.user_id)

        if not instance_details or not instance_details["instance"]:
            # This implies instance_id is invalid or user does not own it.
            # The service.archive_workflow_instance would have returned None.
            return await create_message_page(
                request, "Not Found", "Error 404",
                f"Workflow Instance with ID '{instance_id}' not found or you do not have permission to view it.",
                [("← Back to Definitions", "/workflow-definitions")],
                status_code=404, renderer=renderer
            )

        instance_obj = instance_details["instance"]

        # If instance exists and belongs to user, but archiving failed, it's likely because it's completed.
        if instance_obj.status == WorkflowStatus.completed:
            return await create_message_page(
                request, "Archiving Failed", "Error 400 - Bad Request",
                "Cannot archive a workflow instance that is already completed.",
                [(f"← Back to Instance", f"/workflow-instances/{instance_id}")],
                status_code=status.HTTP_400_BAD_REQUEST, renderer=renderer
            )

        # If it's already archived (should have been returned by archive_workflow_instance directly, but as a fallback)
        if instance_obj.status == WorkflowStatus.archived:
            return RedirectResponse(url=f"/workflow-instances/{instance_id}", status_code=status.HTTP_303_SEE_OTHER)

        # Default error if none of the above specific conditions were met
        # This could be due to some other unexpected state or error in the service layer.
        return await create_message_page(
            request, "Archiving Failed", "Error 500 - Server Error",
            "Could not archive the workflow instance due to an unexpected error.",
            [(f"← Back to Instance", f"/workflow-instances/{instance_id}")],
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, renderer=renderer
        )


@router.post("/{instance_id}/share", response_class=RedirectResponse)
async def generate_share_link_handler(
    request: Request,
    instance_id: str,
    service: WorkflowService = Depends(get_workflow_service),
    current_user: AuthenticatedUser = Depends(get_current_active_user)
    # renderer: HtmlRendererInterface = Depends(get_html_renderer) # Not using for now
):
    if isinstance(current_user, RedirectResponse): # Handles unauthenticated users
        return current_user

    # The service method will handle logic like checking ownership 
    # and if a token already exists (though it currently regenerates if called again,
    # which is fine for this handler's purpose of ensuring a link is active).
    # It returns the updated instance or None if instance not found / not owned.
    updated_instance = await service.generate_shareable_link(instance_id, current_user.user_id)

    # if not updated_instance:
        # If generate_shareable_link returns None (e.g. instance not found, or user doesn't own it)
        # For now, simply redirecting back. The instance page will either show the new link
        # or not, based on whether updated_instance.share_token got set.
        # A more sophisticated approach might involve flash messages or an error page.
        # return RedirectResponse(url=f"/workflow-instances/{instance_id}", status_code=status.HTTP_303_SEE_OTHER)
        # The above commented block is one way, but the service.generate_shareable_link as per previous
        # subtask returns None if instance not found or user_id doesn't match.
        # If it returns None, we still redirect. The UI will simply not show a share_token.

    # Always redirect back to the instance page.
    # The page will then re-query the instance and display the share link if available.
    return RedirectResponse(url=f"/workflow-instances/{instance_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{instance_id}/unarchive", response_class=HTMLResponse)
async def unarchive_workflow_instance_handler(
        request: Request,
        instance_id: str,
        service: WorkflowService = Depends(get_workflow_service),
        current_user: AuthenticatedUser = Depends(get_current_active_user),
        renderer: HtmlRendererInterface = Depends(get_html_renderer)
):
    if isinstance(current_user, RedirectResponse):  # Handles unauthenticated users
        return current_user

    unarchived_instance_result = await service.unarchive_workflow_instance(instance_id, current_user.user_id)

    if unarchived_instance_result:
        # If successful and instance is now active, redirect
        return RedirectResponse(url=f"/workflow-instances/{instance_id}", status_code=status.HTTP_303_SEE_OTHER)
    else:
        # Unarchiving failed, determine why for a more specific error message.
        # Re-fetch the instance details to provide accurate error feedback.
        instance_details = await service.get_workflow_instance_with_tasks(instance_id, current_user.user_id)

        if not instance_details or not instance_details["instance"]:
            # Instance not found or user does not have permission.
            return await create_message_page(
                request, "Not Found", "Error 404",
                f"Workflow Instance with ID '{instance_id}' not found or you do not have permission to view it.",
                [("← Back to Definitions", "/workflow-definitions")],
                status_code=status.HTTP_404_NOT_FOUND, renderer=renderer
            )

        instance_obj = instance_details["instance"]

        # If instance exists and belongs to user, but unarchiving failed, it's likely because it's not archived.
        if instance_obj.status != WorkflowStatus.archived:
            return await create_message_page(
                request, "Unarchiving Failed", "Error 400 - Bad Request",
                "Cannot unarchive a workflow instance that is not currently archived.",
                [(f"← Back to Instance", f"/workflow-instances/{instance_id}")],
                status_code=status.HTTP_400_BAD_REQUEST, renderer=renderer
            )

        # Default error if none of the above specific conditions were met (e.g., unexpected service layer issue)
        return await create_message_page(
            request, "Unarchiving Failed", "Error 500 - Server Error",
            "Could not unarchive the workflow instance due to an unexpected error.",
            [(f"← Back to Instance", f"/workflow-instances/{instance_id}")],
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, renderer=renderer
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
