from datetime import date
from typing import Optional

from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.html_renderer import HtmlRendererInterface
from app.core.security import AuthenticatedUser, get_current_active_user
from app.db_models.enums import WorkflowStatus
from app.dependencies import get_workflow_service, get_html_renderer
from app.services import WorkflowService

router = APIRouter(tags=["user_workflows"])


@router.get("/my-workflows", response_class=HTMLResponse)
async def list_user_workflows(
        request: Request,
        created_at: Optional[str] = Query(None, description="Filter by creation date (YYYY-MM-DD)"),
        status: Optional[str] = Query(None, description="Filter by workflow status (string value like 'active')"),
        service: WorkflowService = Depends(get_workflow_service),
        current_user: AuthenticatedUser = Depends(get_current_active_user),
        renderer: HtmlRendererInterface = Depends(get_html_renderer)
):
    """Serves a page listing all workflow instances for the current user, with optional filters."""
    if isinstance(current_user, RedirectResponse):
        return current_user

    # Date handling (remains unchanged from previous correction)
    created_at_for_service: date
    if created_at and created_at.strip():
        try:
            created_at_for_service = date.fromisoformat(created_at)
        except ValueError:
            # Invalid date format, default to today's date
            created_at_for_service = date.today()
    else:  # No date query param or it's empty, default to today's date
        created_at_for_service = date.today()

    selected_created_at_str = created_at_for_service.isoformat()

    # New status handling logic
    status_for_service: Optional[WorkflowStatus] = None
    selected_status_for_template: str = ""

    if status is None or status == "":
        # No status filter needed, status_for_service remains None
        # selected_status_for_template remains ""
        pass
    else:
        try:
            status_for_service = WorkflowStatus(status)
            selected_status_for_template = status_for_service.value
        except ValueError:
            # Invalid status string from query, default to active for filtering
            # and reflect 'active' as selected in template.
            status_for_service = WorkflowStatus.active
            selected_status_for_template = WorkflowStatus.active.value
            # Alternatively, could raise HTTPException(400, "Invalid status value")
            # or pass None to service (no filter) and "" to template.
            # Current subtask: default to active if invalid non-empty string.

    instances = await service.list_instances_for_user(
        user_id=current_user.user_id,
        created_at_date=created_at_for_service,  # Pass the determined date object
        status=status_for_service  # Pass the refined status for service (can be None)
    )

    # For the template, if 'created_at' (the string query param) was provided, use it.
    # If not, selected_created_at_str is date.today().isoformat().
    # For status, selected_status_for_template is now correctly set.
    return await renderer.render(
        "my_workflows.html",
        request,
        {
            "instances": instances,
            "selected_created_at": selected_created_at_str,
            "selected_status": selected_status_for_template,  # Use the newly determined value
            "workflow_statuses": [s.value for s in WorkflowStatus]  # For dropdown
        }
    )
