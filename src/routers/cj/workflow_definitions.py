from fastapi import APIRouter, Depends, HTTPException, Request, status, Header
from typing import List, Dict, Any, Optional # Added Optional

from models import WorkflowDefinition as PDWorkflowDefinition # Renamed to avoid clash
from services import WorkflowService
from dependencies import get_workflow_service, get_html_renderer # Added get_html_renderer
from cj_hooks import (
    create_cj_item_response,
    create_cj_collection_response,
    create_cj_form_template_response,
    create_cj_error_response,
    CollectionJSONBuilder, # Added CollectionJSONBuilder
)
from cj_models import CollectionJson # For type hinting, already in cj_hooks but good for clarity
from core.html_renderer import HtmlRendererInterface # Added HtmlRendererInterface

# Assuming cj_models.py defines Link, Item, Template etc.
# from cj_models import Link, Template, Item

router = APIRouter(
    prefix="/workflow-definitions",
    tags=["cj-workflow-definitions"],
    # dependencies=[Depends(get_current_active_user)], # Add auth later
)

BASE_API_URL = "/cj" # Prefix for all CJ routes, as defined in main.py
RESOURCE_NAME = "workflow-definitions"

# Helper for content negotiation
async def render_cj_response(
    request: Request,
    cj_response_func, # A callable that returns a CollectionJson object
    html_template_name: str,
    renderer: HtmlRendererInterface,
    accept: Optional[str] = Header(None)
):
    if accept and "text/html" in accept.lower() and not "application/json" in accept.lower(): # Prioritize HTML if explicitly asked and JSON not preferred
        # Generate the CollectionJson object by calling the provided function
        cj_data = await cj_response_func() # Corrected indentation
        # Ensure request is passed to the template context if templates use it (e.g. for url_for)
        return await renderer.render( # Changed render_template to render
            template_name=f"cj/{html_template_name}",
            request=request,
            context={"collection": cj_data.collection} # Pass the .collection part
        )
    else: # Default to JSON
        return await cj_response_func() # Added await


@router.get("/", summary="List all workflow definitions as Collection+JSON or HTML")
async def list_workflow_definitions(
    request: Request,
    service: WorkflowService = Depends(get_workflow_service),
    accept: Optional[str] = Header(None),
    renderer: HtmlRendererInterface = Depends(get_html_renderer),
    # Add query parameter dependencies for filtering later:
    # limit: int = 100, offset: int = 0, name_filter: Optional[str] = None
):
    builder = CollectionJSONBuilder(base_api_url=f"{BASE_API_URL}")

    async def get_cj_data(): # Made async to allow await inside
        # definitions_db = await service.list_workflow_definitions(limit=limit, offset=offset, name_filter=name_filter)
        # TEMP: Using mock-like data until service methods are fully confirmed for Pydantic models
        # definitions_pd = [
        #     PDWorkflowDefinition(**{
        #         "id": "wf-def-1", "name": "Test Def 1", "description": "Desc 1",
        #         "task_definitions": [{"name": "td1", "order": 1}]
        #     }),
        #     PDWorkflowDefinition(**{
        #         "id": "wf-def-2", "name": "Test Def 2", "description": "Desc 2",
        #         "task_definitions": [{"name": "td2", "order": 1}]
        #     })
        # ] # Replace with actual service call: await service.list_workflow_definitions_pydantic()

        # For now, let's assume service returns Pydantic models directly
        db_definitions = await service.list_workflow_definitions() # This returns DB models / Pydantic models in mock

        # We need to convert DB models to Pydantic models if service doesn't do it
        # If mock service returns Pydantic, this list comprehension will still work.
        pydantic_definitions = [PDWorkflowDefinition.model_validate(db_def) for db_def in db_definitions]

        return create_cj_collection_response(
            instances=pydantic_definitions,
            model_class=PDWorkflowDefinition,
            resource_name=RESOURCE_NAME,
            base_api_url=BASE_API_URL,
            builder=builder
        )

    return await render_cj_response(request, get_cj_data, "items.html", renderer, accept)


@router.get("/form", summary="Get a form for creating workflow definitions as Collection+JSON or HTML")
async def get_workflow_definition_form(
    request: Request,
    accept: Optional[str] = Header(None),
    renderer: HtmlRendererInterface = Depends(get_html_renderer)
):
    builder = CollectionJSONBuilder(base_api_url=f"{BASE_API_URL}")
    async def get_cj_data(): # No await needed here as no async calls inside - actually it IS for consistency
        return create_cj_form_template_response(
            model_class=PDWorkflowDefinition,
            resource_name=RESOURCE_NAME,
            base_api_url=BASE_API_URL,
            builder=builder,
            form_purpose="create"
        )
    return await render_cj_response(request, get_cj_data, "form.html", renderer, accept)


@router.get("/{definition_id}", summary="Get a specific workflow definition as Collection+JSON or HTML")
async def get_workflow_definition(
    definition_id: str,
    request: Request,
    service: WorkflowService = Depends(get_workflow_service),
    accept: Optional[str] = Header(None),
    renderer: HtmlRendererInterface = Depends(get_html_renderer)
):
    builder = CollectionJSONBuilder(base_api_url=f"{BASE_API_URL}")

    # Mock service returns Pydantic model directly for get_workflow_definition_by_id
    definition_pydantic = await service.get_workflow_definition_by_id(definition_id)

    async def get_cj_data(): # No await needed here as no async calls inside - actually it IS for consistency
        if not definition_pydantic:
            return create_cj_error_response(
                title="Not Found",
                status_code=status.HTTP_404_NOT_FOUND,
                message=f"Workflow definition with ID '{definition_id}' not found.",
                href=f"{BASE_API_URL}/{RESOURCE_NAME}/{definition_id}"
            )
        return create_cj_item_response(
            instance=definition_pydantic,
            resource_name=RESOURCE_NAME,
            base_api_url=BASE_API_URL,
            builder=builder
        )

    # If not found and client wants JSON (or doesn't specify, defaulting to JSON), raise HTTPException
    if not definition_pydantic and not (accept and "text/html" in accept.lower() and not "application/json" in accept.lower()):
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Workflow definition with ID '{definition_id}' not found.")

    # For HTML, let the template handle the "not found" display via the error in CollectionJSON
    # or if found, it will render the item.
    return await render_cj_response(request, get_cj_data, "item.html", renderer, accept)


@router.get("/{definition_id}/form", summary="Get a form for updating a specific workflow definition as Collection+JSON or HTML")
async def get_specific_workflow_definition_form(
    definition_id: str,
    request: Request,
    service: WorkflowService = Depends(get_workflow_service),
    accept: Optional[str] = Header(None),
    renderer: HtmlRendererInterface = Depends(get_html_renderer)
):
    builder = CollectionJSONBuilder(base_api_url=f"{BASE_API_URL}")
    definition_pydantic = await service.get_workflow_definition_by_id(definition_id)


    async def get_cj_data(): # No await needed here - actually it IS for consistency
        if not definition_pydantic:
            return create_cj_error_response(
                title="Not Found",
                status_code=status.HTTP_404_NOT_FOUND,
                message=f"Workflow definition with ID '{definition_id}' not found, cannot generate edit form.",
                href=f"{BASE_API_URL}/{RESOURCE_NAME}/{definition_id}/form"
            )
        return create_cj_form_template_response(
            model_class=PDWorkflowDefinition,
            resource_name=RESOURCE_NAME,
            base_api_url=BASE_API_URL,
            builder=builder,
            item_instance=definition_pydantic,
            form_purpose="edit"
        )

    if not definition_pydantic and not (accept and "text/html" in accept.lower() and not "application/json" in accept.lower()):
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Workflow definition with ID '{definition_id}' not found.")

    return await render_cj_response(request, get_cj_data, "form.html", renderer, accept)


# PUT /workflow-definitions/form - Placeholder
@router.put("/form", summary="Create or update a workflow definition from form data (idempotent)")
async def put_workflow_definition_form(
    request: Request,
    # item: PDWorkflowDefinition, # Or a Pydantic model for form data
    # service: WorkflowService = Depends(get_workflow_service),
):
    return {"message": "PUT /workflow-definitions/form endpoint for Collection+JSON - Not yet implemented"}

# PUT /workflow-definitions/{id}/form - Placeholder
@router.put("/{definition_id}/form", summary="Create or update a specific workflow definition from form data (idempotent)")
async def put_specific_workflow_definition_form(
    definition_id: str,
    request: Request,
    # item: PDWorkflowDefinition, # Or a Pydantic model for form data
    # service: WorkflowService = Depends(get_workflow_service),
):
    return {"message": f"PUT /workflow-definitions/{definition_id}/form endpoint for Collection+JSON - Not yet implemented"}
