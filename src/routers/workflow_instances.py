from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse

import cj_models
import models
from cj_models import CollectionJson
from core.html_renderer import HtmlRendererInterface
from core.security import AuthenticatedUser, get_current_user
from dependencies import get_html_renderer, get_workflow_service, get_collection_json_representor
from services import WorkflowService

router = APIRouter(
    prefix="/workflow-instances",
    tags=["Workflow Instances"],
)


@router.get(
    "/{instance_id}",
    response_model=CollectionJson,
    openapi_extra={
        "pageTransitions": [
            "home",
            "get_workflow_instances", # This might need to be adjusted based on actual page flow
        ],
    },
    summary="View Workflow Instance",
)
async def view_workflow_instance(
        request: Request,
        instance_id: str,
        current_user: AuthenticatedUser | None = Depends(get_current_user),
        service: WorkflowService = Depends(get_workflow_service),
        renderer: HtmlRendererInterface = Depends(get_html_renderer),
        collection_json_representor: cj_models.CollectionJsonRepresentor = Depends(get_collection_json_representor)
):
    """Returns a Collection+JSON representation of a specific workflow instance."""
    if isinstance(current_user, RedirectResponse):
        return current_user

    workflow_instance = await service.get_workflow_instance(instance_id=instance_id) # This service method will be created in a later step
    if not workflow_instance:
        return HTMLResponse(status_code=404, content="Workflow Instance not found")

    # Convert the workflow instance to Collection+JSON format
    # This will likely need adjustment based on the structure of WorkflowInstance and its related data
    cj = collection_json_representor.to_collection_json(
        request,
        [workflow_instance],  # Assuming get_workflow_instance returns a single object, wrap in a list
        context={"instance_id": instance_id}
    )
    return await renderer.render(
        "cj_template.html", # Assuming a generic template, might need a specific one
        request,
        {
            "current_user": current_user,
            "collection": cj.collection,
            "template": cj.template,
        }
    )
