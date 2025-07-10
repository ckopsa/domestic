from __future__ import annotations

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse

import cj_models
import models
from cj_models import CollectionJson
from core.representor import Representor
from core.security import AuthenticatedUser, get_current_user
from dependencies import get_workflow_service, get_transition_registry, get_representor
from services import WorkflowService
from transitions import TransitionManager

router = APIRouter(
    prefix="/workflow-instances",
    tags=["workflow-instances"],
    responses={
        200: {
            "content": {
                "application/vnd.collection+json": {},
                "text/html": {}
            },
        }
    },
)


@router.get(
    "/",
    response_model=CollectionJson,
    summary="Workflow Instances",
    tags=["collection"]
)
async def get_workflow_instances(
        request: Request,
        current_user: AuthenticatedUser | None = Depends(get_current_user),
        service: WorkflowService = Depends(get_workflow_service),
        representor: Representor = Depends(get_representor),
        transition_manager: TransitionManager = Depends(get_transition_registry),
):
    """Returns a Collection+JSON representation of workflow instances."""
    if isinstance(current_user, RedirectResponse):
        return current_user

    family_id_param = request.query_params.get('family_id')
    workflow_instances: list[models.WorkflowInstance]

    if family_id_param:
        # TODO: Add authorization check: is current_user part of this family_id_param?
        # This is crucial for security. For now, proceeding as per initial prompt's scope.
        workflow_instances = await service.list_instances_for_family(family_id_param)
    elif current_user and hasattr(current_user, 'user_id'): # Check current_user and user_id existence
        workflow_instances = await service.list_instances_for_user(user_id=current_user.user_id)
    else:
        # Not authenticated and no family_id provided.
        # Return empty list or an appropriate error response.
        # For Collection+JSON, an empty list of items is acceptable.
        workflow_instances = []

    items = []
    for item in workflow_instances:
        links = []
        if item.status == models.WorkflowStatus.archived:
            links.append(
                transition_manager.get_transition("view_workflow_instance", {"instance_id": item.id}).to_link())
        else:
            links.append(
                transition_manager.get_transition("view_workflow_instance", {"instance_id": item.id}).to_link())
            links.append(
                transition_manager.get_transition("archive_workflow_instance", {"instance_id": item.id}).to_link())
        item_model = item.to_cj_data(
            href=str(request.url_for("view_workflow_instance", instance_id=item.id)),
            links=links,
        )
        items.append(item_model)

    collection = cj_models.Collection(
        href=str(request.url),
        title="Workflow Instances",
        links=[t.to_link() for t in [
            transition_manager.get_transition("home", {}),
            transition_manager.get_transition("get_workflow_instances", {}),
            transition_manager.get_transition("get_workflow_definitions", {}),
        ]],
        items=items,
    )

    return await representor.represent(
        cj_models.CollectionJson(
            collection=collection,
            template=[],
            error=None,
        ))


@router.get(
    "/{instance_id}",
    response_model=CollectionJson,
    summary="View Workflow Instance",
    tags=["item"],
)
async def view_workflow_instance(
        request: Request,
        instance_id: str,
        current_user: AuthenticatedUser | None = Depends(get_current_user),
        service: WorkflowService = Depends(get_workflow_service),
        representor: Representor = Depends(get_representor),
        transition_manager: TransitionManager = Depends(get_transition_registry),
):
    """Returns a Collection+JSON representation of a specific workflow instance."""
    if isinstance(current_user, RedirectResponse):
        return current_user

    workflow_instance = await service.get_workflow_instance_with_tasks(instance_id=instance_id,
                                                                       user_id=current_user.user_id)
    if not workflow_instance:
        return HTMLResponse(status_code=404, content="Workflow Instance not found")

    page_transitions = [
        transition_manager.get_transition("home", {}),
        transition_manager.get_transition("get_workflow_instances", {}),
        transition_manager.get_transition("get_workflow_definitions", {}),
        transition_manager.get_transition("view_workflow_definition",
                                          {"definition_id": workflow_instance.workflow_definition_id}),
    ]

    item_transitions = [
    ]

    tasks = workflow_instance.tasks
    # sort by completed last and then order
    tasks.sort(key=lambda x: x.order if x.status != models.TaskStatus.completed else x.order + 100)

    items = []
    for item in [models.SimpleTaskInstance.from_task_instance(task) for task in tasks]:
        links = []
        if item.status == models.TaskStatus.completed:
            links.append(transition_manager.get_transition("reopen_task_instance", {"task_id": item.id}).to_link())
        else:
            links.append(transition_manager.get_transition("complete_task_instance", {"task_id": item.id}).to_link())
        items.append(item.to_cj_data(
            href=str(request.url_for("view_workflow_instance", instance_id=instance_id)),
            links=links,
        ))

    collection = cj_models.Collection(
        href=str(request.url),
        title=f"{workflow_instance.name} - {workflow_instance.status.title()}",
        links=[t.to_link() for t in page_transitions if t],
        items=items,
    )

    return await representor.represent(
        cj_models.CollectionJson(
            collection=collection,
            template=[],
            error=None,
        ))


@router.post(
    "-task/{task_id}/complete",
    response_model=CollectionJson,
    summary="Complete Task",
    tags=["edit"],
)
async def complete_task_instance(
        request: Request,
        task_id: str,
        current_user: AuthenticatedUser | None = Depends(get_current_user),
        service: WorkflowService = Depends(get_workflow_service),
):
    if isinstance(current_user, RedirectResponse):
        return current_user

    task_instance = await service.complete_task(
        task_id=task_id,
        user_id=current_user.user_id
    )

    return RedirectResponse(
        url=str(request.url_for("view_workflow_instance", instance_id=task_instance.workflow_instance_id)),
        status_code=303
    )


@router.post(
    "-task/{task_id}/reopen",
    response_model=CollectionJson,
    summary="Reopen Task",
    tags=["edit"],
)
async def reopen_task_instance(
        request: Request,
        task_id: str,
        current_user: AuthenticatedUser | None = Depends(get_current_user),
        service: WorkflowService = Depends(get_workflow_service),
):
    if isinstance(current_user, RedirectResponse):
        return current_user

    task_instance = await service.undo_complete_task(
        task_id=task_id,
        user_id=current_user.user_id
    )

    return RedirectResponse(
        url=str(request.url_for("view_workflow_instance", instance_id=task_instance.workflow_instance_id)),
        status_code=303
    )


@router.post(
    "/{instance_id}/archive",
    response_model=CollectionJson,
    summary="Archive Workflow Instance",
    tags=["edit"],
)
async def archive_workflow_instance(
        request: Request,
        instance_id: str,
        current_user: AuthenticatedUser | None = Depends(get_current_user),
        service: WorkflowService = Depends(get_workflow_service),
):
    if isinstance(current_user, RedirectResponse):
        return current_user

    workflow_instance = await service.archive_workflow_instance(
        instance_id=instance_id,
        user_id=current_user.user_id
    )

    return RedirectResponse(
        url=str(request.url_for("view_workflow_instance", instance_id=workflow_instance.id)),
        status_code=303
    )
