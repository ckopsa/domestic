from fastapi import APIRouter, Request, Depends
from fastapi import status
from fastapi.responses import RedirectResponse

from core.html_renderer import HtmlRendererInterface
from core.security import AuthenticatedUser, get_current_active_user
from dependencies import get_workflow_service, get_html_renderer
from services import WorkflowService
from utils import create_message_page

router = APIRouter(prefix="/task-instances", tags=["tasks"])


@router.post("/{task_id}/complete", response_class=RedirectResponse)
async def complete_task_handler(
        request: Request,
        task_id: str,
        service: WorkflowService = Depends(get_workflow_service),
        current_user: AuthenticatedUser = Depends(get_current_active_user),
        renderer: HtmlRendererInterface = Depends(get_html_renderer)
):
    if isinstance(current_user, RedirectResponse):
        return current_user
    task = await service.complete_task(task_id, current_user.user_id)
    if not task:
        return await create_message_page(
            request, "Error", "Task Update Failed", "Could not complete task or access denied.",
            [("← Back", "/")], status_code=400, renderer=renderer
        )
    return RedirectResponse(url=f"/workflow-instances/{task.workflow_instance_id}",
                            status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{task_id}/undo-complete", response_class=RedirectResponse)
async def undo_complete_task_handler(
        request: Request,
        task_id: str,
        service: WorkflowService = Depends(get_workflow_service),
        current_user: AuthenticatedUser = Depends(get_current_active_user),
        renderer: HtmlRendererInterface = Depends(get_html_renderer)
):
    if isinstance(current_user, RedirectResponse):
        return current_user
    task = await service.undo_complete_task(task_id, current_user.user_id)
    if not task:
        return await create_message_page(
            request, "Error", "Task Update Failed", "Could not revert task status or access denied.",
            [("← Back", "/")], status_code=400, renderer=renderer
        )
    return RedirectResponse(url=f"/workflow-instances/{task.workflow_instance_id}",
                            status_code=status.HTTP_303_SEE_OTHER)
