from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from fastapi import status
from app.services import WorkflowService
from app.core.html_renderer import HtmlRendererInterface
from app.core.security import AuthenticatedUser, get_current_active_user
from app.main import get_workflow_service
from app.utils import create_message_page

router = APIRouter(prefix="/task-instances", tags=["tasks"])

@router.post("/{task_id}/complete", response_class=RedirectResponse)
async def complete_task_handler(
        request: Request,
        task_id: str,
        service: WorkflowService = Depends(get_workflow_service),
        current_user: AuthenticatedUser = Depends(get_current_active_user),
        renderer: HtmlRendererInterface = Depends(get_html_renderer)
):
    task = await service.complete_task(task_id, current_user.user_id)
    if not task:
        return await create_message_page(
            request, "Error", "Task Update Failed", "Could not complete task or access denied.",
            [("← Back", "/")], status_code=400, renderer=renderer
        )
    return RedirectResponse(url=f"/workflow-instances/{task.workflow_instance_id}",
                            status_code=status.HTTP_303_SEE_OTHER)
