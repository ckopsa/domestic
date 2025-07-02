from __future__ import annotations

from typing import Annotated, List

from fastapi import APIRouter, Request, Depends, Form
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
    prefix="/workflow-definitions",
    tags=["Workflow Definitions"],
)


@router.get(
    "/",
    response_model=CollectionJson,
    summary="Workflow Definitions",
)
async def get_workflow_definitions(
        request: Request,
        current_user: AuthenticatedUser | None = Depends(get_current_user),
        service: WorkflowService = Depends(get_workflow_service),
        representor: Representor = Depends(get_representor),
        transition_manager: TransitionManager = Depends(get_transition_registry),
):
    """Returns a Collection+JSON representation of workflow definitions."""
    if isinstance(current_user, RedirectResponse):
        return current_user
    workflow_definitions: list[models.WorkflowDefinition] = await service.list_workflow_definitions()

    items = []
    for item in workflow_definitions:
        item_model = item.to_cj_data(
            href=str(request.url_for("view_workflow_definition", definition_id=item.id)),
            links=[t.to_link() for t in [
                transition_manager.get_transition("view_workflow_definition", {"definition_id": "{definition_id}"}),
                transition_manager.get_transition("create_workflow_instance_from_definition",
                                                  {"definition_id": "{definition_id}"}),
            ]]
        )
        items.append(item_model)

    collection = cj_models.Collection(
        href=str(request.url),
        title="Workflow Definitions",
        links=[t.to_link() for t in [
            transition_manager.get_transition("home", {}),
            transition_manager.get_transition("get_workflow_instances", {}),
            transition_manager.get_transition("get_workflow_definitions", {}),
        ]],
        items=items,
        queries=[],
    )

    template = [
        transition_manager.get_transition("simple_create_workflow_definition", {}).to_template(
            defaults={
                "name": "New Workflow Definition",
                "description": "",
                "task_definitions": "1. Task Name\n2. Another Task Name",
            }
        )
    ]

    return await representor.represent(
        cj_models.CollectionJson(
            collection=collection,
            template=template,
            error=None,
        ))


@router.post(
    "/{definition_id}/createInstance",
    summary="Create Workflow Instance",
)
async def create_workflow_instance_from_definition(
        definition_id: str,
        current_user: AuthenticatedUser | None = Depends(get_current_user),
        service: WorkflowService = Depends(get_workflow_service),
):
    if isinstance(current_user, RedirectResponse):
        return current_user

    definition = await service.list_workflow_definitions(definition_id=definition_id)
    if not definition:
        return HTMLResponse(status_code=404, content="Workflow Definition not found")
    definition = definition[0]
    new_instance = await service.create_workflow_instance(
        models.WorkflowInstance(
            workflow_definition_id=definition_id,
            user_id=current_user.user_id,
            name=definition.name,
            due_datetime=definition.due_datetime,
        )
    )

    return RedirectResponse(
        url=f"/workflow-instances/{new_instance.id}",  # Placeholder URL
        status_code=303
    )


@router.get(
    "/{definition_id}",
    response_model=CollectionJson,
    summary="View Workflow Definition",
)
async def view_workflow_definition(
        request: Request,
        definition_id: str,
        current_user: AuthenticatedUser | None = Depends(get_current_user),
        service: WorkflowService = Depends(get_workflow_service),
        representor: Representor = Depends(get_representor),
        transition_manager: TransitionManager = Depends(get_transition_registry),
):
    """Returns a Collection+JSON representation of a specific workflow definition."""
    if isinstance(current_user, RedirectResponse):
        return current_user

    workflow_definition: List[models.WorkflowDefinition] = await service.list_workflow_definitions(
        definition_id=definition_id
    )
    if not workflow_definition:
        return HTMLResponse(status_code=404, content="Workflow Definition not found")

    page_transitions = [
        transition_manager.get_transition("view_workflow_definition", {"definition_id": definition_id}),
        transition_manager.get_transition("simple_create_workflow_definition", {}),
    ]

    items = []
    for item in workflow_definition + workflow_definition[0].task_definitions:
        item_model = item.to_cj_data(href=str(request.url_for("view_workflow_definition", definition_id=definition_id)))
        items.append(item_model)

    collection = cj_models.Collection(
        href=str(request.url),
        title="View Workflow Definition",
        links=[t.to_link() for t in page_transitions if [
            transition_manager.get_transition("home", {}),
            transition_manager.get_transition("get_workflow_instances", {}),
            transition_manager.get_transition("get_workflow_definitions", {}),
        ]],
        items=items,
        queries=[],
    )

    first_workflow_definition: models.WorkflowDefinition = workflow_definition[0]
    templates = [
        transition_manager.get_transition(
            "create_workflow_instance_from_definition",
            {"definition_id": definition_id}).to_template(),
        transition_manager.get_transition(
            "simple_create_workflow_definition", {}
        ).to_template({
            "id": first_workflow_definition.id,
            "name": first_workflow_definition.name,
            "description": first_workflow_definition.description,
            "task_definitions": "\n".join(
                task.name for task in first_workflow_definition.task_definitions
            ),
        }),
    ]
    return await representor.represent(
        cj_models.CollectionJson(
            collection=collection,
            template=templates,
            error=None,
        ))


@router.post(
    "/{definition_id}",
    response_model=CollectionJson,
    summary="Create Workflow Definition Form",
)
async def create_workflow_definition(
        request: Request,
        definition_id: str,
        workflow_definition_task: Annotated[models.TaskDefinitionBase, Form()],
        service: WorkflowService = Depends(get_workflow_service),
        current_user: AuthenticatedUser | None = Depends(get_current_user),
):
    """Returns a form to create a new workflow definition in Collection+JSON format."""
    if isinstance(current_user, RedirectResponse):
        return current_user

    workflow_definition = await service.list_workflow_definitions(definition_id=definition_id)
    if not workflow_definition:
        return HTMLResponse(status_code=404, content="Workflow Definition not found")

    workflow_definition = workflow_definition[0]  # Assuming single definition returned
    # Create a task for the new workflow definition
    await service.update_definition(
        definition_id=workflow_definition.id,
        name=workflow_definition.name,
        description=workflow_definition.description,
        task_definitions=workflow_definition.task_definitions + [workflow_definition_task]
    )

    return RedirectResponse(
        url=str(request.url_for("view_workflow_definition", definition_id=workflow_definition.id)),
        status_code=303
    )


@router.post(
    "/",
    response_model=CollectionJson,
    summary="Create Workflow Definition",
)
async def cj_create_workflow_definition(
        request: Request,
        definition: Annotated[models.WorkflowDefinitionCreateRequest, Form()],
        current_user: AuthenticatedUser | None = Depends(get_current_user),
        service: WorkflowService = Depends(get_workflow_service),
):
    """Creates a new workflow definition and returns it in Collection+JSON format."""
    if isinstance(current_user, RedirectResponse):
        return current_user

    created_definition = await service.create_new_definition(
        name=definition.name,
        description=definition.description,
        task_definitions=[]
    )

    return RedirectResponse(
        url=str(request.url_for("view_workflow_definition", definition_id=created_definition.id)),
        status_code=303
    )


@router.post(
    "-simpleForm",
    response_model=CollectionJson,
    summary="Create Workflow Definition",
)
async def simple_create_workflow_definition(
        request: Request,
        definition: Annotated[models.SimpleWorkflowDefinitionCreateRequest, Form()],
        current_user: AuthenticatedUser | None = Depends(get_current_user),
        service: WorkflowService = Depends(get_workflow_service),
):
    """Creates a new workflow definition and returns it in Collection+JSON format."""
    if isinstance(current_user, RedirectResponse):
        return current_user

    task_definitions = []
    for order, task_name in enumerate(definition.task_definitions.splitlines(), start=1):
        if task_name.strip():
            print(order)
            task_definitions.append(
                models.TaskDefinitionBase(name=task_name.strip(), order=order, due_datetime_offset_minutes=0))

    if not await service.list_workflow_definitions(name=definition.name):
        created_definition = await service.create_new_definition(
            name=definition.name,
            description=definition.description,
            task_definitions=task_definitions,
        )
    else:
        created_definition = await service.update_definition(
            definition_id=definition.id,
            name=definition.name,
            description=definition.description,
            task_definitions=task_definitions,
        )
    return RedirectResponse(
        url=str(request.url_for("view_workflow_definition", definition_id=created_definition.id)),
        status_code=303
    )
