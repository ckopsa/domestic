from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse

from app.services import WorkflowService
from app.dependencies import get_workflow_service, get_html_renderer
from app.core.html_renderer import HtmlRendererInterface
# Ensure app.utils.create_message_page is available or define a similar utility if needed
from app.utils import create_message_page 

router = APIRouter(prefix="/share", tags=["share"])

@router.get("/workflow/{share_token}", response_class=HTMLResponse, name="view_shared_workflow_instance")
async def view_shared_workflow_instance(
    request: Request,
    share_token: str,
    service: WorkflowService = Depends(get_workflow_service),
    renderer: HtmlRendererInterface = Depends(get_html_renderer)
):
    details = await service.get_workflow_instance_by_share_token(share_token)

    if not details or not details.get("instance"):
        # Use create_message_page or a simple HTTPException for error display
        # For example, using create_message_page:
        return await create_message_page(
            request, 
            "Not Found", 
            "Error 404 - Not Found", 
            "The shared workflow link is invalid or the workflow was not found.", 
            [("← Home", "/")], # Provide a link to a safe page
            status_code=404, 
            renderer=renderer
        )
        # Alternatively, a simpler HTTPException:
        # raise HTTPException(status_code=404, detail="Shared workflow not found or link is invalid.")

    instance = details["instance"]
    tasks = details["tasks"]
    
    # Assuming 'workflow_instance.html' is the correct template name
    return await renderer.render(
        "workflow_instance.html", # The existing template
        request,
        {"instance": instance, "tasks": tasks, "is_shared_view": True} # Pass an extra flag
    )
