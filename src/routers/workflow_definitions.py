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
    prefix="/workflow-definitions",
    tags=["Workflow Definitions"],
)


@router.get(
    "/",
    response_model=CollectionJson,
    openapi_extra={
        "pageTransitions": [
            "home",
            "get_workflow_definitions",
            "foo_bar",
        ],
        "itemTransitions": [
            "view_workflow_definition",
        ],
    },
    summary="Workflow Definitions",
)
async def get_workflow_definitions(
        request: Request,
        current_user: AuthenticatedUser | None = Depends(get_current_user),
        service: WorkflowService = Depends(get_workflow_service),
        renderer: HtmlRendererInterface = Depends(get_html_renderer),
        collection_json_representor: cj_models.CollectionJsonRepresentor = Depends(get_collection_json_representor)
):
    """Returns a Collection+JSON representation of workflow definitions."""
    if isinstance(current_user, RedirectResponse):
        return current_user
    workflow_definitions: list[models.WorkflowDefinition] = await service.list_workflow_definitions()

    # Convert the workflow definition to Collection+JSON format
    def item_context_mapper(item: models.WorkflowDefinition) -> dict:
        return {
            "definition_id": item.id,
        }

    cj = collection_json_representor.to_collection_json(request, workflow_definitions, context={"definition_id": None},
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


@router.post(
    "/{definition_id}/createInstance",
    summary="Create Workflow Instance",
    # Ensure appropriate response model if not redirecting directly or for OpenAPI docs
)
async def create_workflow_instance_from_definition(
        request: Request,
        definition_id: str,
        current_user: AuthenticatedUser | None = Depends(get_current_user),
        service: WorkflowService = Depends(get_workflow_service),
):
    if isinstance(current_user, RedirectResponse):
        return current_user

    # This service method will be created in a later step
    new_instance = await service.create_workflow_instance(definition_id=definition_id)

    # Redirect to the view_workflow_instance route
    # Ensure the route name for view_workflow_instance is correct, it might be 'view_workflow_instance'
    # or whatever it's named in workflow_instances.py. For now, assuming 'view_workflow_instance'
    # and that it's registered with the app in main.py to be resolvable by name.
    # If workflow_instances router is mounted with a prefix, that needs to be handled.
    # For now, constructing URL path directly, assuming 'workflow_instances' is the prefix for that router.

    # The URL for redirecting should be constructed using request.url_for,
    # but we need to ensure the new router and its routes are known to the app for url_for to work.
    # As a placeholder, using a direct path. This might need refinement once main.py is updated.
    # Ideal: RedirectResponse(url=request.url_for('view_workflow_instance', instance_id=new_instance.id), status_code=303)

    return RedirectResponse(
        url=f"/workflow-instances/{new_instance.id}",  # Placeholder URL
        status_code=303
    )


@router.get(
    "/{definition_id}",
    response_model=CollectionJson,
    openapi_extra={
        "pageTransitions": [
            "home",
            "get_workflow_definitions",
            "view_workflow_definition",
            "create_workflow_definition_form",
        ],
    },
    summary="View Workflow Definition",
)
async def view_workflow_definition(
        request: Request,
        definition_id: str,
        current_user: AuthenticatedUser | None = Depends(get_current_user),
        service: WorkflowService = Depends(get_workflow_service),
        renderer: HtmlRendererInterface = Depends(get_html_renderer),
        collection_json_representor: cj_models.CollectionJsonRepresentor = Depends(get_collection_json_representor)
):
    """Returns a Collection+JSON representation of a specific workflow definition."""
    if isinstance(current_user, RedirectResponse):
        return current_user

    workflow_definition = await service.list_workflow_definitions(definition_id=definition_id)
    if not workflow_definition:
        return HTMLResponse(status_code=404, content="Workflow Definition not found")

    # Convert the workflow definition to Collection+JSON format
    cj = collection_json_representor.to_collection_json(
        request,
        workflow_definition + workflow_definition[0].task_definitions,
        context={"definition_id": definition_id}
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


@router.post(
    "/{definition_id}",
    response_model=CollectionJson,
    summary="Create Workflow Definition Form",
)
async def create_workflow_definition_form(
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
async def foo_bar(
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

    created_definition = await service.create_new_definition(
        name=definition.name,
        description=definition.description,
        task_definitions=task_definitions,
    )
    return RedirectResponse(
        url=str(request.url_for("view_workflow_definition", definition_id=created_definition.id)),
        status_code=303
    )
