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
    "/",
    response_model=CollectionJson,
    openapi_extra={
        "pageTransitions": [
            "home",
            "get_workflow_instances",
        ],
        "itemTransitions": [
            "view_workflow_instance",
        ],
    },
    summary="Workflow Instances",
)
async def get_workflow_instances(
        request: Request,
        current_user: AuthenticatedUser | None = Depends(get_current_user),
        service: WorkflowService = Depends(get_workflow_service),
        renderer: HtmlRendererInterface = Depends(get_html_renderer),
        collection_json_representor: cj_models.CollectionJsonRepresentor = Depends(get_collection_json_representor)
):
    """Returns a Collection+JSON representation of workflow instances."""
    if isinstance(current_user, RedirectResponse):
        return current_user

    workflow_instances: list[models.WorkflowInstance] = await service.list_instances_for_user(
        user_id=current_user.user_id)

    # Convert the workflow instance to Collection+JSON format
    def item_context_mapper(item: models.WorkflowInstance) -> dict:
        return {
            "instance_id": item.id,
        }

    cj = collection_json_representor.to_collection_json(request, workflow_instances, context={"instance_id": None},
                                                        item_context_mapper=item_context_mapper)
    return await renderer.render(
        "cj_template.html",
        request,
        {
            "current_user": current_user,
            "collection": cj.collection,
            "template": cj.template,
        }
    )


@router.get(
    "/{instance_id}",
    response_model=CollectionJson,
    openapi_extra={
        "pageTransitions": [
            "home",
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

    workflow_instance = await service.get_workflow_instance_with_tasks(instance_id=instance_id, user_id=current_user.user_id)
    if not workflow_instance:
        return HTMLResponse(status_code=404, content="Workflow Instance not found")

    cj = collection_json_representor.to_collection_json(
        request,
        [workflow_instance] + workflow_instance.tasks,
        context={"instance_id": instance_id}
    )
    return await renderer.render(
        "cj_template.html", 
        request,
        {
            "current_user": current_user,
            "collection": cj.collection,
            "template": cj.template,
        }
    )
