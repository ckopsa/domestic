import re
from fastapi import APIRouter, Depends, HTTPException, Request, status, Header, Form
from fastapi.responses import RedirectResponse
from typing import List, Dict, Any, Optional, Type

from models import (
    WorkflowDefinition as PDWorkflowDefinition,
    WorkflowDefinitionCreate,
    WorkflowDefinitionUpdate,
    TaskDefinitionBase
)
from services import WorkflowService
from dependencies import get_workflow_service, get_html_renderer, get_cj_builder # Added get_cj_builder
from cj_hooks import (
    create_cj_item_response,
    create_cj_collection_response,
    create_cj_form_template_response,
    create_cj_error_response,
    CollectionJSONBuilder,
)
from cj_models import Link # For additional links if needed
from core.html_renderer import HtmlRendererInterface
from core.cj_utils import render_cj_response # Import centralized helper

router = APIRouter(
    prefix="/workflow-definitions", # This prefix is combined with /cj from main.py
    tags=["cj-workflow-definitions"],
)

CJ_BASE_URL = "/cj" # Base for CJ context (hrefs in CJ responses)
RESOURCE_NAME = "workflow-definitions" # Resource name for CJ builder

# Standardized render_cj_response helper
async def render_cj_response(
    request: Request,
    data: dict, # This is CollectionJson.model_dump() or an error dict
    template_name: str,
    html_renderer: HtmlRendererInterface,
    accept: Optional[str] = Header(None),
    status_code: int = status.HTTP_200_OK,
):
    if accept and "text/html" in accept.lower() and not "application/json" in accept.lower():
        # Handle HTML redirection for 201 CREATED or 200 OK on PUT
        if status_code == status.HTTP_201_CREATED or (status_code == status.HTTP_200_OK and request.method == "PUT"):
            if data.get("collection") and data["collection"].get("items") and len(data["collection"]["items"]) > 0:
                item_url = data["collection"]["items"][0].get("href")
                if item_url:
                    # Ensure URL is absolute or correctly relative for RedirectResponse
                    # TestClient might need full URLs, live server might be fine with relative
                    if not item_url.startswith("http") and hasattr(request.base_url, "_url"):
                        item_url = str(request.base_url.replace(path=item_url))

                    return RedirectResponse(url=item_url, status_code=status.HTTP_303_SEE_OTHER)

        # For errors, the `data` might be an error C+J structure
        # The template should be able to handle this (e.g. if data.collection.error exists)
        return html_renderer.render_template( # Changed from render to render_template
            f"cj/{template_name}", # Assuming templates are in cj/ subdirectory
            {"request": request, "data": data}, # Pass the raw dict for template
            status_code=status_code
        )
    else: # Default to JSON
        # If it's an error C+J for JSON, it's already structured correctly.
        # FastAPI will use the status_code from the endpoint decorator or overridden in the response object.
        if "collection" in data and "error" in data["collection"] and data["collection"]["error"] is not None:
             # For JSON error responses not raised via HTTPException, ensure status code matches
             error_status_code = data["collection"]["error"].get("code", status_code)
             # This is tricky as FastAPI sets status from decorator.
             # Best to raise HTTPException for JSON errors unless specific C+J error format is always returned.
             # For now, we assume direct return is fine and FastAPI handles status code.
             # A more robust way for JSON errors is to raise HTTPException(status_code, detail=cj_error_dict)
             return data # Potentially with a manually set response status if not using HTTPException for errors

        return data


async def _parse_form_data_to_pydantic(form_data: Dict[str, Any], model: Type[PDWorkflowDefinitionCreate] | Type[PDWorkflowDefinitionUpdate]) -> PDWorkflowDefinitionCreate | PDWorkflowDefinitionUpdate:
    """
    Basic parser for flat form data and task_definitions.
    Assumes task_definitions are like:
    task_definitions[0][name]="Task1", task_definitions[0][order]=1
    task_definitions[1][name]="Task2", task_definitions[1][order]=2
    """
    data = {}
    task_defs_dict: Dict[int, Dict[str, Any]] = {}

    for key, value in form_data.items():
        if value == "" and model.model_fields[key].is_required() is False: # Handle optional empty strings
             data[key] = None
             continue

        match_tasks = re.match(r"task_definitions\[(\d+)\]\[(\w+)\]", key)
        if match_tasks:
            index = int(match_tasks.group(1))
            field_name = match_tasks.group(2)
            if index not in task_defs_dict:
                task_defs_dict[index] = {}

            # Try to convert to int if field is 'order' or 'due_datetime_offset_minutes'
            if field_name in ["order", "due_datetime_offset_minutes"]:
                try:
                    task_defs_dict[index][field_name] = int(value) if value else None
                except ValueError:
                    # Handle error or assign raw value if conversion fails
                    task_defs_dict[index][field_name] = value
            else:
                task_defs_dict[index][field_name] = value
        else:
            # Handle due_datetime - convert from string if present
            if key == "due_datetime" and value:
                try:
                    data[key] = datetime.fromisoformat(value)
                except ValueError:
                    data[key] = None # Or raise validation error
            elif key in model.model_fields: # Ensure key is part of the model
                 data[key] = value


    if task_defs_dict:
        data["task_definitions"] = [TaskDefinitionBase(**task_defs_dict[i]) for i in sorted(task_defs_dict.keys())]
    else:
        # Ensure task_definitions is at least an empty list if model expects it
        if "task_definitions" in model.model_fields:
            data["task_definitions"] = []

    return model(**data)


@router.get("/", summary="List all workflow definitions")
async def list_workflow_definitions(
    request: Request,
    service: WorkflowService = Depends(get_workflow_service),
    accept: Optional[str] = Header(None),
    renderer: HtmlRendererInterface = Depends(get_html_renderer),
    cj_builder: CollectionJSONBuilder = Depends(get_cj_builder)
):
    db_definitions = await service.list_workflow_definitions_pydantic() # Assuming this returns List[PDWorkflowDefinition]

    cj_collection_dict = create_cj_collection_response(
        instances=db_definitions,
        model_class=PDWorkflowDefinition, # For the template part of the collection
        resource_name=RESOURCE_NAME,
        base_api_url=CJ_BASE_URL,
        builder=cj_builder
    ).model_dump(exclude_none=True)

    return await render_cj_response(request, cj_collection_dict, "items.html", renderer, accept)


@router.get("/form", summary="Get a form for creating workflow definitions")
async def get_workflow_definition_create_form( # Renamed for clarity
    request: Request,
    accept: Optional[str] = Header(None),
    renderer: HtmlRendererInterface = Depends(get_html_renderer),
    cj_builder: CollectionJSONBuilder = Depends(get_cj_builder)
):
    # For create form, use WorkflowDefinitionCreate as the model_class for template fields
    cj_form_dict = create_cj_form_template_response(
        model_class=WorkflowDefinitionCreate, # Use the Create model for the form
        resource_name=RESOURCE_NAME,
        base_api_url=CJ_BASE_URL,
        builder=cj_builder,
        form_purpose="create"
    ).model_dump(exclude_none=True)
    return await render_cj_response(request, cj_form_dict, "form.html", renderer, accept)


@router.get("/{definition_id}", summary="Get a specific workflow definition")
async def get_workflow_definition(
    definition_id: str,
    request: Request,
    service: WorkflowService = Depends(get_workflow_service),
    accept: Optional[str] = Header(None),
    renderer: HtmlRendererInterface = Depends(get_html_renderer),
    cj_builder: CollectionJSONBuilder = Depends(get_cj_builder)
):
    definition_pydantic = await service.get_workflow_definition_pydantic(definition_id) # Changed method name

    if not definition_pydantic:
        if accept and "text/html" in accept.lower() and not "application/json" in accept.lower():
            error_cj = create_cj_error_response(
                title="Not Found", status_code=status.HTTP_404_NOT_FOUND,
                message=f"Workflow definition with ID '{definition_id}' not found.",
                href=str(request.url)
            ).model_dump(exclude_none=True)
            return await render_cj_response(request, error_cj, "error.html", renderer, accept, status_code=status.HTTP_404_NOT_FOUND)
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Workflow definition with ID '{definition_id}' not found.")

    cj_item_dict = create_cj_item_response(
        instance=definition_pydantic,
        resource_name=RESOURCE_NAME,
        base_api_url=CJ_BASE_URL,
        builder=cj_builder,
        additional_links=[Link(rel="edit-form", href=f"{CJ_BASE_URL}/{RESOURCE_NAME}/{definition_id}/form/", prompt="Edit")]
    ).model_dump(exclude_none=True)

    return await render_cj_response(request, cj_item_dict, "item.html", renderer, accept)


@router.get("/{definition_id}/form", summary="Get a form for updating a specific workflow definition")
async def get_workflow_definition_edit_form( # Renamed for clarity
    definition_id: str,
    request: Request,
    service: WorkflowService = Depends(get_workflow_service),
    accept: Optional[str] = Header(None),
    renderer: HtmlRendererInterface = Depends(get_html_renderer),
    cj_builder: CollectionJSONBuilder = Depends(get_cj_builder)
):
    definition_pydantic = await service.get_workflow_definition_pydantic(definition_id) # Changed method name

    if not definition_pydantic:
        if accept and "text/html" in accept.lower() and not "application/json" in accept.lower():
            error_cj = create_cj_error_response(
                title="Not Found", status_code=status.HTTP_404_NOT_FOUND,
                message=f"Workflow definition with ID '{definition_id}' not found for edit form.",
                href=str(request.url)
            ).model_dump(exclude_none=True)
            return await render_cj_response(request, error_cj, "error.html", renderer, accept, status_code=status.HTTP_404_NOT_FOUND)
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Workflow definition with ID '{definition_id}' not found for edit form.")

    # For edit form, use WorkflowDefinitionUpdate as model_class for template fields
    cj_form_dict = create_cj_form_template_response(
        model_class=WorkflowDefinitionUpdate, # Use Update model for edit form fields
        resource_name=RESOURCE_NAME,
        base_api_url=CJ_BASE_URL,
        builder=cj_builder,
        item_instance=definition_pydantic, # Populate with existing data
        form_purpose="edit"
    ).model_dump(exclude_none=True)

    return await render_cj_response(request, cj_form_dict, "form.html", renderer, accept)


@router.put("/form", status_code=status.HTTP_201_CREATED, summary="Create a new workflow definition")
async def create_workflow_definition_from_form(
    request: Request,
    service: WorkflowService = Depends(get_workflow_service),
    accept: Optional[str] = Header(None),
    renderer: HtmlRendererInterface = Depends(get_html_renderer),
    cj_builder: CollectionJSONBuilder = Depends(get_cj_builder),
    # FastAPI will try to bind JSON to this if Content-Type is application/json
    # For form data, we'll parse it manually from request.form()
    # To make one parameter work for both, it's complex. We'll check content-type.
    # payload: Optional[WorkflowDefinitionCreate] = None # This would be for JSON
):
    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type:
        form_data_raw = await request.form()
        try:
            definition_data = await _parse_form_data_to_pydantic(form_data_raw, WorkflowDefinitionCreate)
        except Exception as e: # Broad exception for parsing errors
            # Handle Pydantic validation error or other parsing issues
            if accept and "text/html" in accept.lower():
                error_cj = create_cj_error_response(title="Validation Error", status_code=status.HTTP_400_BAD_REQUEST, message=str(e), href=str(request.url)).model_dump(exclude_none=True)
                return await render_cj_response(request, error_cj, "form.html", renderer, accept, status_code=status.HTTP_400_BAD_REQUEST) # Re-render form with error
            else:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Form parsing error: {str(e)}")
    elif "application/json" in content_type:
        json_payload = await request.json()
        try:
            definition_data = WorkflowDefinitionCreate(**json_payload)
        except Exception as e: # Pydantic validation error
             if accept and "text/html" in accept.lower(): # Should not happen with JSON typically
                error_cj = create_cj_error_response(title="Validation Error", status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, message=str(e), href=str(request.url)).model_dump(exclude_none=True)
                return await render_cj_response(request, error_cj, "form.html", renderer, accept, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
             else:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    else:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported content type. Use application/json or application/x-www-form-urlencoded.")

    created_definition = await service.create_workflow_definition(definition_data) # Changed method name

    cj_item_dict = create_cj_item_response(
        instance=created_definition,
        resource_name=RESOURCE_NAME,
        base_api_url=CJ_BASE_URL,
        builder=cj_builder,
        additional_links=[Link(rel="edit-form", href=f"{CJ_BASE_URL}/{RESOURCE_NAME}/{created_definition.id}/form/", prompt="Edit")]
    ).model_dump(exclude_none=True)

    return await render_cj_response(request, cj_item_dict, "item.html", renderer, accept, status_code=status.HTTP_201_CREATED)


@router.put("/{definition_id}/form", summary="Update an existing workflow definition")
async def update_workflow_definition_from_form(
    definition_id: str,
    request: Request,
    service: WorkflowService = Depends(get_workflow_service),
    accept: Optional[str] = Header(None),
    renderer: HtmlRendererInterface = Depends(get_html_renderer),
    cj_builder: CollectionJSONBuilder = Depends(get_cj_builder),
):
    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type:
        form_data_raw = await request.form()
        try:
            definition_update_data = await _parse_form_data_to_pydantic(form_data_raw, WorkflowDefinitionUpdate)
        except Exception as e:
            if accept and "text/html" in accept.lower():
                error_cj = create_cj_error_response(title="Validation Error", status_code=status.HTTP_400_BAD_REQUEST, message=str(e), href=str(request.url)).model_dump(exclude_none=True)
                # For HTML, ideally re-render the edit form with existing data + error
                # This requires fetching definition_pydantic again if not passed or available
                # For simplicity, just showing an error page or a generic form error might be acceptable for now.
                return await render_cj_response(request, error_cj, "error.html", renderer, accept, status_code=status.HTTP_400_BAD_REQUEST)
            else:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Form parsing error: {str(e)}")

    elif "application/json" in content_type:
        json_payload = await request.json()
        try:
            definition_update_data = WorkflowDefinitionUpdate(**json_payload)
        except Exception as e: # Pydantic validation error
             if accept and "text/html" in accept.lower():
                error_cj = create_cj_error_response(title="Validation Error", status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, message=str(e), href=str(request.url)).model_dump(exclude_none=True)
                return await render_cj_response(request, error_cj, "error.html", renderer, accept, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
             else:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    else:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported content type")

    updated_definition = await service.update_workflow_definition(definition_id, definition_update_data) # Changed method name

    if not updated_definition:
        if accept and "text/html" in accept.lower() and not "application/json" in accept.lower():
            error_cj = create_cj_error_response(
                title="Not Found", status_code=status.HTTP_404_NOT_FOUND,
                message=f"Workflow definition with ID '{definition_id}' not found, cannot update.",
                href=str(request.url) # Or link to the collection list
            ).model_dump(exclude_none=True)
            return await render_cj_response(request, error_cj, "error.html", renderer, accept, status_code=status.HTTP_404_NOT_FOUND)
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Workflow definition with ID '{definition_id}' not found, cannot update.")

    cj_item_dict = create_cj_item_response(
        instance=updated_definition,
        resource_name=RESOURCE_NAME,
        base_api_url=CJ_BASE_URL,
        builder=cj_builder,
        additional_links=[Link(rel="edit-form", href=f"{CJ_BASE_URL}/{RESOURCE_NAME}/{updated_definition.id}/form/", prompt="Edit")]
    ).model_dump(exclude_none=True)

    return await render_cj_response(request, cj_item_dict, "item.html", renderer, accept, status_code=status.HTTP_200_OK)
