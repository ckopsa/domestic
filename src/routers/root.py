from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse

import cj_models
import models
from cj_models import CollectionJson, Collection
from core.html_renderer import HtmlRendererInterface
from core.security import AuthenticatedUser, get_current_user
from dependencies import get_html_renderer, get_workflow_service, get_transition_registry
from services import WorkflowService
from transitions import TransitionManager

router = APIRouter()

global welcome_message
welcome_message = "Ain't Nothing But A Thing"


@router.get(
    "/",
    tags=["home"],
    openapi_extra={
        "pageTransitions": ["home", "update_welcome_message", "get_workflow_definitions"],
    },
    response_class=HTMLResponse
)
async def home(
        request: Request,
        current_user: AuthenticatedUser | None = Depends(get_current_user),
        renderer: HtmlRendererInterface = Depends(get_html_renderer),
        transition_manager: TransitionManager = Depends(get_transition_registry)
):
    """Serves the homepage."""
    if isinstance(current_user, RedirectResponse):
        return current_user

    transitions = transition_manager.get_transitions( "home", request)
    links = [transition.to_link() for transition in transitions if not transition.properties]
    template: cj_models.Template = [transition.to_template() for transition in transitions if transition.href == '/' and transition.method == 'POST'][0]
    message_template_data = [template_data for template_data in template.data if template_data.name == 'message'][0]
    message_template_data.value = welcome_message
    cj = CollectionJson(
        collection=Collection(
            href=str(request.url),
            version="1.0",
            items=[],
            queries=[],
            links=links,
            title=welcome_message,
        ),
        template=template,
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


# set the welcome message via POST request using form data
@router.post("/", response_class=HTMLResponse)
async def update_welcome_message(
        request: Request,
        message: Annotated[str, Form(examples=["Hello, World!", "Welcome to the API!"])],
        current_user: AuthenticatedUser | None = Depends(get_current_user),
):
    """Updates the welcome message."""
    global welcome_message
    welcome_message = message.strip()

    if isinstance(current_user, RedirectResponse):
        return current_user
    # Redirect to the root endpoint to show the updated message
    return RedirectResponse(url=str(request.url), status_code=303)


# Collection+JSON endpoint for Workflow Definitions
@router.get(
    "/cj-workflow-definitions",
    response_model=CollectionJson,
    openapi_extra={
        "pageTransitions": ["home", "get_workflow_definitions", "list_workflow_definitions_page"],
    },
    summary="Workflow Definitions",
)
async def get_workflow_definitions(
        request: Request,
        current_user: AuthenticatedUser | None = Depends(get_current_user),
        service: WorkflowService = Depends(get_workflow_service),
        renderer: HtmlRendererInterface = Depends(get_html_renderer),
        transition_manager: TransitionManager = Depends(get_transition_registry)
):
    """Returns a Collection+JSON representation of workflow definitions."""
    if isinstance(current_user, RedirectResponse):
        return current_user

    transitions = transition_manager.get_transitions( "home", request)
    links = [transition.to_link() for transition in transitions if not transition.properties]

    # Placeholder for actual data retrieval logic
    workflow_definitions: list[models.WorkflowDefinition] = await service.list_workflow_definitions()
    cj = CollectionJson(
        collection=Collection(
            href=str(request.url),
            version="1.0",
            items=[cj_models.Item(
                href=f"/workflow-definitions/{workflow_definition.id}",
                rel="workflow-definition",
                data=[
                    cj_models.ItemData(
                        name="id",
                        value=workflow_definition.id,
                        prompt="Workflow Definition ID",
                        type="text",
                    ),
                    cj_models.ItemData(
                        name="name",
                        value=workflow_definition.name,
                        prompt="Workflow Definition Name",
                        type="text",
                    ),
                    cj_models.ItemData(
                        name="description",
                        value=workflow_definition.description,
                        prompt="Workflow Definition Description",
                        type="text",
                    ),
                ],

            ) for workflow_definition in workflow_definitions],
            queries=[],
            links=links,
            title=welcome_message,
        ),
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
