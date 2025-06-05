from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status, Header
from fastapi.responses import RedirectResponse

from models import WorkflowInstance as PDWorkflowInstance, WorkflowInstanceCreate, WorkflowInstanceUpdate
from services import WorkflowService
from dependencies import get_workflow_service, get_html_renderer, get_cj_builder # Import centralized get_cj_builder
from cj_hooks import (
    create_cj_item_response,
    create_cj_collection_response,
    create_cj_form_template_response,
    create_cj_error_response,
    CollectionJSONBuilder # Keep for type hinting
    # PydanticToItemDataArray and PydanticToTemplateDataArray removed as they were for local builder
)
from cj_models import Link # Import Link for creating additional_links
from core.html_renderer import HtmlRendererInterface
from core.cj_utils import render_cj_response # Import centralized helper

BASE_API_URL = "/cj" # This is the prefix, so actual base for builder might be "/" or specific to version
CJ_BASE_URL = "/cj" # Explicit base for CollectionJSONBuilder context
RESOURCE_NAME = "workflow-instances" # Used by cj_hooks, not for router paths directly here

router = APIRouter() # Paths will be relative to where this router is mounted in main.py


# Local get_cj_builder function removed. Using centralized one from dependencies.py

@router.get("/", summary="List all workflow instances") # Mounted at /cj/workflow-instances
async def list_workflow_instances(
    request: Request,
    workflow_service: WorkflowService = Depends(get_workflow_service),
    html_renderer: HtmlRendererInterface = Depends(get_html_renderer),
    accept: Optional[str] = Header(None),
    cj_builder: CollectionJSONBuilder = Depends(get_cj_builder),
):
    instances_pydantic = await workflow_service.list_workflow_instances_pydantic()

    cj_collection_dict = create_cj_collection_response(
        instances=instances_pydantic,
        model_class=PDWorkflowInstance,
        resource_name=RESOURCE_NAME, # "workflow-instances"
        base_api_url=CJ_BASE_URL,
        builder=cj_builder
    ).model_dump(exclude_none=True)

    return await render_cj_response(request, cj_collection_dict, "items.html", html_renderer, accept)

@router.get("/form", summary="Get a form for creating workflow instances")
async def get_workflow_instance_create_form(
    request: Request,
    html_renderer: HtmlRendererInterface = Depends(get_html_renderer),
    accept: Optional[str] = Header(None),
    cj_builder: CollectionJSONBuilder = Depends(get_cj_builder),
):
    cj_form_dict = create_cj_form_template_response(
        model_class=WorkflowInstanceCreate,
        resource_name=RESOURCE_NAME, # "workflow-instances"
        base_api_url=CJ_BASE_URL,
        builder=cj_builder,
        form_purpose="create"
    ).model_dump(exclude_none=True)

    return await render_cj_response(request, cj_form_dict, "form.html", html_renderer, accept)


@router.get("/{instance_id}", summary="Get a specific workflow instance")
async def get_workflow_instance(
    instance_id: str,
    request: Request,
    workflow_service: WorkflowService = Depends(get_workflow_service),
    html_renderer: HtmlRendererInterface = Depends(get_html_renderer),
    accept: Optional[str] = Header(None),
    cj_builder: CollectionJSONBuilder = Depends(get_cj_builder),
):
    instance = await workflow_service.get_workflow_instance_pydantic(instance_id)
    if not instance:
        error_title = "Not Found"
        error_message = f"Workflow instance with ID '{instance_id}' not found."
        error_href = str(request.url) # Current URL for error context
        # Use centralized render_cj_response for HTML error
        if accept and "text/html" in accept.lower() and not "application/json" in accept.lower():
            error_resp_cj_dict = create_cj_error_response(
                title=error_title,
                status_code=status.HTTP_404_NOT_FOUND,
                message=error_message,
                href=error_href
            ).model_dump(exclude_none=True)
            return await render_cj_response(request, error_resp_cj_dict, "error.html", html_renderer, accept, status_code=status.HTTP_404_NOT_FOUND)
        else: # Default to JSON HTTPException for non-HTML
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_message)

    item_specific_url_base = f"{CJ_BASE_URL}/{RESOURCE_NAME}/{instance.id}"
    item_url_full_path = f"{item_specific_url_base}/"
    additional_links = [
        Link(rel="edit-form", href=f"{item_specific_url_base}/form/", prompt="Edit this instance", method="GET"),
    ]

    cj_item_dict = create_cj_item_response(
        instance=instance,
        resource_name=RESOURCE_NAME,
        base_api_url=CJ_BASE_URL,
        builder=cj_builder,
        additional_links=additional_links
    ).model_dump(exclude_none=True)
    cj_item_dict["collection"]["href"] = item_url_full_path # Ensure correct href for single item view

    return await render_cj_response(request, cj_item_dict, "item.html", html_renderer, accept)


@router.get("/{instance_id}/form", summary="Get a form for editing a specific workflow instance")
async def get_workflow_instance_edit_form(
    instance_id: str,
    request: Request,
    workflow_service: WorkflowService = Depends(get_workflow_service),
    html_renderer: HtmlRendererInterface = Depends(get_html_renderer),
    accept: Optional[str] = Header(None),
    cj_builder: CollectionJSONBuilder = Depends(get_cj_builder),
):
    instance = await workflow_service.get_workflow_instance_pydantic(instance_id)
    if not instance:
        error_title = "Not Found"
        error_message = f"Workflow instance with ID '{instance_id}' not found, cannot generate edit form."
        error_href = str(request.url)
        if accept and "text/html" in accept.lower() and not "application/json" in accept.lower():
            error_resp_cj_dict = create_cj_error_response(
                title=error_title,
                status_code=status.HTTP_404_NOT_FOUND,
                message=error_message,
                href=error_href
            ).model_dump(exclude_none=True)
            return await render_cj_response(request, error_resp_cj_dict, "error.html", html_renderer, accept, status_code=status.HTTP_404_NOT_FOUND)
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_message)

    cj_form_dict = create_cj_form_template_response(
        model_class=WorkflowInstanceUpdate,
        resource_name=RESOURCE_NAME,
        base_api_url=CJ_BASE_URL,
        builder=cj_builder,
        item_instance=instance,
        form_purpose="edit"
    ).model_dump(exclude_none=True)

    return await render_cj_response(request, cj_form_dict, "form.html", html_renderer, accept)


@router.put("/form", summary="Create a new workflow instance", status_code=status.HTTP_201_CREATED)
async def create_workflow_instance(
    request: Request,
    workflow_instance_data: WorkflowInstanceCreate, # FastAPI handles JSON binding
    workflow_service: WorkflowService = Depends(get_workflow_service),
    html_renderer: HtmlRendererInterface = Depends(get_html_renderer),
    accept: Optional[str] = Header(None),
    cj_builder: CollectionJSONBuilder = Depends(get_cj_builder),
):
    created_instance = await workflow_service.create_workflow_instance(workflow_instance_data)

    item_specific_url_base = f"{CJ_BASE_URL}/{RESOURCE_NAME}/{created_instance.id}"
    item_url_full_path = f"{item_specific_url_base}/"
    additional_links = [
        Link(rel="edit-form", href=f"{item_specific_url_base}/form/", prompt="Edit this instance", method="GET"),
    ]

    cj_item_dict = create_cj_item_response(
        instance=created_instance,
        resource_name=RESOURCE_NAME,
        base_api_url=CJ_BASE_URL,
        builder=cj_builder,
        additional_links=additional_links
    ).model_dump(exclude_none=True)
    cj_item_dict["collection"]["href"] = item_url_full_path

    return await render_cj_response(request, cj_item_dict, "item.html", html_renderer, accept, status_code=status.HTTP_201_CREATED)


@router.put("/{instance_id}/form", summary="Update an existing workflow instance")
async def update_workflow_instance(
    instance_id: str,
    request: Request,
    workflow_instance_update_data: WorkflowInstanceUpdate, # FastAPI handles JSON binding
    workflow_service: WorkflowService = Depends(get_workflow_service),
    html_renderer: HtmlRendererInterface = Depends(get_html_renderer),
    accept: Optional[str] = Header(None),
    cj_builder: CollectionJSONBuilder = Depends(get_cj_builder),
):
    updated_instance = await workflow_service.update_workflow_instance(instance_id, workflow_instance_update_data)

    if not updated_instance:
        error_title = "Not Found"
        error_message = f"Workflow instance with ID '{instance_id}' not found, cannot update."
        error_href = str(request.url)
        if accept and "text/html" in accept.lower() and not "application/json" in accept.lower():
            error_resp_cj_dict = create_cj_error_response(
                title=error_title,
                status_code=status.HTTP_404_NOT_FOUND,
                message=error_message,
                href=error_href
            ).model_dump(exclude_none=True)
            return await render_cj_response(request, error_resp_cj_dict, "error.html", html_renderer, accept, status_code=status.HTTP_404_NOT_FOUND)
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_message)

    item_specific_url_base = f"{CJ_BASE_URL}/{RESOURCE_NAME}/{updated_instance.id}"
    item_url_full_path = f"{item_specific_url_base}/"
    additional_links = [
        Link(rel="edit-form", href=f"{item_specific_url_base}/form/", prompt="Edit this instance", method="GET"),
    ]

    cj_item_dict = create_cj_item_response(
        instance=updated_instance,
        resource_name=RESOURCE_NAME,
        base_api_url=CJ_BASE_URL,
        builder=cj_builder,
        additional_links=additional_links
    ).model_dump(exclude_none=True)
    cj_item_dict["collection"]["href"] = item_url_full_path

    return await render_cj_response(request, cj_item_dict, "item.html", html_renderer, accept, status_code=status.HTTP_200_OK)
