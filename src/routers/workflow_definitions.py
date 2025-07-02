from __future__ import annotations

from typing import Annotated, List

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from src import cj_models # Corrected
from src import models # Corrected
from src.cj_models import CollectionJson # Corrected
from src.core.html_renderer import HtmlRendererInterface # Corrected
# Use the same import path as the test for get_current_user
from src.core.security import AuthenticatedUser, get_current_user
from src.dependencies import get_html_renderer, get_workflow_service # Corrected
from src.services import WorkflowService # Corrected
from src.transitions import TransitionManager # Corrected

router = APIRouter(
    prefix="/workflow-definitions",
    tags=["Workflow Definitions"],
)


def get_transition_registry(request: Request) -> TransitionManager:
    return TransitionManager(request)


@router.get(
    "/",
    response_model=CollectionJson,
    summary="Workflow Definitions",
    operation_id="get_workflow_definitions",
)
async def get_workflow_definitions(
        request: Request,
        current_user: AuthenticatedUser | None = Depends(get_current_user),
        service: WorkflowService = Depends(get_workflow_service),
        renderer: HtmlRendererInterface = Depends(get_html_renderer),
        transition_manager: TransitionManager = Depends(get_transition_registry),
):
    """Returns a Collection+JSON representation of workflow definitions."""
    if isinstance(current_user, RedirectResponse):
        return current_user
    workflow_definitions: list[models.WorkflowDefinition] = await service.list_workflow_definitions()

    page_transitions = [
        transition_manager.get_transition("home", {}),
        transition_manager.get_transition("get_workflow_instances", {}),
        transition_manager.get_transition("get_workflow_definitions", {}),
        transition_manager.get_transition("simple_create_workflow_definition", {}),
    ]

    item_transitions = [
        transition_manager.get_transition("view_workflow_definition", {"definition_id": "{definition_id}"}),
        transition_manager.get_transition("create_workflow_instance_from_definition", {"definition_id": "{definition_id}"}),
    ]

    items = []
    for item in workflow_definitions:
        item_model = item.to_cj_data(href=str(request.url_for("view_workflow_definition", definition_id=item.id)))
        item_model.links.extend([t.to_link() for t in item_transitions if t])
        items.append(item_model)

    collection = cj_models.Collection(
        href=str(request.url),
        title="Workflow Definitions",
        links=[t.to_link() for t in page_transitions if t],
        items=items,
        queries=[t.to_query() for t in page_transitions if t],
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
    "/{definition_id}/createInstance",
    summary="Create Workflow Instance",
    operation_id="create_workflow_instance_from_definition",
)
async def create_workflow_instance_from_definition(
        request: Request,
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
    operation_id="view_workflow_definition",
)
async def view_workflow_definition(
        request: Request,
        definition_id: str,
        current_user: AuthenticatedUser | None = Depends(get_current_user),
        service: WorkflowService = Depends(get_workflow_service),
        renderer: HtmlRendererInterface = Depends(get_html_renderer),
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
        transition_manager.get_transition("home", {}),
        transition_manager.get_transition("get_workflow_instances", {}),
        transition_manager.get_transition("get_workflow_definitions", {}),
        transition_manager.get_transition("view_workflow_definition", {"definition_id": definition_id}),
        transition_manager.get_transition("create_workflow_instance_from_definition", {"definition_id": definition_id}),
        transition_manager.get_transition("simple_create_workflow_definition", {}),
    ]

    items = []
    for item in workflow_definition + workflow_definition[0].task_definitions:
        item_model = item.to_cj_data(href=str(request.url_for("view_workflow_definition", definition_id=definition_id)))
        items.append(item_model)

    collection = cj_models.Collection(
        href=str(request.url),
        title="View Workflow Definition",
        links=[t.to_link() for t in page_transitions if t],
        items=items,
        queries=[t.to_query() for t in page_transitions if t],
    )

    first_workflow_definition: models.WorkflowDefinition = workflow_definition[0]
    template = transition_manager.get_transition("simple_create_workflow_definition", {}).to_template(first_workflow_definition.dict())

    return await renderer.render(
        "cj_template.html",
        request,
        {
            "current_user": current_user,
            "collection": collection,
            "template": template,
        }
    )

# Moved simple_create_workflow_definition before /{definition_id} to ensure correct routing
@router.post(
    "/-simpleForm",  # Added leading slash
    response_model=CollectionJson,
    summary="Create Workflow Definition",
    operation_id="simple_create_workflow_definition",
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

    # Check if a definition with the same name already exists
    existing_definitions = await service.list_workflow_definitions(name=definition.name)

    if not existing_definitions:
        created_definition = await service.create_new_definition(
            name=definition.name,
            description=definition.description,
            task_definitions=task_definitions,
        )
    else:
        # If definition with name exists, update it.
        # The original code used definition.id which would be a new random ID from the form.
        # We should use the ID of the *existing* definition found by name.
        existing_definition_id = existing_definitions[0].id
        created_definition = await service.update_definition(
            definition_id=existing_definition_id, # Use ID of existing definition
            name=definition.name,
            description=definition.description,
            task_definitions=task_definitions,
        )
    return RedirectResponse(
        url=str(request.url_for("view_workflow_definition", definition_id=created_definition.id)),
        status_code=303
    )

@router.post(
    "/{definition_id}",
    response_model=CollectionJson,
    summary="Create Workflow Definition Form",
    operation_id="create_workflow_definition_form",
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
    operation_id="cj_create_workflow_definition",
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


# This block is the duplicated one and should be removed.
# The correctly placed simple_create_workflow_definition is earlier in the file.
