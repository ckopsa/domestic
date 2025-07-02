from __future__ import annotations

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse

import cj_models
import models
from cj_models import CollectionJson
from core.html_renderer import HtmlRendererInterface
from core.security import AuthenticatedUser, get_current_user
from dependencies import get_html_renderer, get_workflow_service
from services import WorkflowService
from transitions import TransitionManager

router = APIRouter(
    prefix="/workflow-instances",
    tags=["Workflow Instances"],
)


def get_transition_registry(request: Request) -> TransitionManager:
    return TransitionManager(request)


@router.get(
    "/",
    response_model=CollectionJson,
    summary="Workflow Instances",
)
async def get_workflow_instances(
        request: Request,
        current_user: AuthenticatedUser | None = Depends(get_current_user),
        service: WorkflowService = Depends(get_workflow_service),
        renderer: HtmlRendererInterface = Depends(get_html_renderer),
        transition_manager: TransitionManager = Depends(get_transition_registry),
):
    """Returns a Collection+JSON representation of workflow instances."""
    if isinstance(current_user, RedirectResponse):
        return current_user

    workflow_instances: list[models.WorkflowInstance] = await service.list_instances_for_user(
        user_id=current_user.user_id)

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

    return await renderer.render(
        "cj_template.html",
        request,
        {
            "current_user": current_user,
            "collection": collection,
        }
    )


@router.get(
    "/{instance_id}",
    response_model=CollectionJson,
    summary="View Workflow Instance",
)
async def view_workflow_instance(
        request: Request,
        instance_id: str,
        current_user: AuthenticatedUser | None = Depends(get_current_user),
        service: WorkflowService = Depends(get_workflow_service),
        renderer: HtmlRendererInterface = Depends(get_html_renderer),
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

    return await renderer.render(
        "cj_template.html",
        request,
        {
            "current_user": current_user,
            "collection": collection,
        }
    )


@router.post(
    "-task/{task_id}/complete",
    response_model=CollectionJson,
    summary="Complete Task",
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
