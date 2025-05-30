from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from app.services import WorkflowService
from app.dependencies import get_workflow_service, get_html_renderer
from app.core.html_renderer import HtmlRendererInterface
from app.core.security import AuthenticatedUser, get_current_active_user

router = APIRouter(tags=["user_workflows"])

@router.get("/my-workflows", response_class=HTMLResponse)
async def list_user_workflows(
        request: Request,
        service: WorkflowService = Depends(get_workflow_service),
        current_user: AuthenticatedUser = Depends(get_current_active_user),
        renderer: HtmlRendererInterface = Depends(get_html_renderer)
):
    """Serves a page listing all workflow instances for the current user."""
    instances = await service.list_instances_for_user(current_user.user_id)
    return await renderer.render("my_workflows.html", request, {"instances": instances})
