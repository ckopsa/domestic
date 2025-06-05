from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status, Header, Query
from fastapi.responses import RedirectResponse

from models import TaskInstance as PDTaskInstance, TaskInstanceUpdate
# from models import TaskInstanceCreate # Not used for now

from services import WorkflowService
from dependencies import get_workflow_service, get_html_renderer, get_cj_builder
from cj_hooks import (
    create_cj_item_response,
    create_cj_collection_response,
    create_cj_form_template_response,
    create_cj_error_response,
    CollectionJSONBuilder
)
from cj_models import Link
from core.html_renderer import HtmlRendererInterface
from core.cj_utils import render_cj_response # Import centralized helper

CJ_BASE_URL = "/cj"
RESOURCE_NAME = "task-instances" # Used by cj_hooks, not for router paths directly here

router = APIRouter() # Paths will be relative to where this router is mounted in main.py


@router.get("/", summary="List all task instances, optionally filtered by workflow_instance_id")
async def list_task_instances(
    request: Request,
    workflow_instance_id: Optional[str] = Query(None, description="Filter by Workflow Instance ID"),
    workflow_service: WorkflowService = Depends(get_workflow_service),
    html_renderer: HtmlRendererInterface = Depends(get_html_renderer),
    accept: Optional[str] = Header(None),
    cj_builder: CollectionJSONBuilder = Depends(get_cj_builder),
):
    task_instances_pydantic = await workflow_service.list_task_instances_pydantic(workflow_instance_id=workflow_instance_id)

    # Construct self link with query parameters if they exist
    self_collection_href = f"{CJ_BASE_URL}/{RESOURCE_NAME}/"
    if workflow_instance_id:
        self_collection_href += f"?workflow_instance_id={workflow_instance_id}"

    cj_collection_dict = create_cj_collection_response(
        instances=task_instances_pydantic,
        model_class=PDTaskInstance,
        resource_name=RESOURCE_NAME, # "task-instances"
        base_api_url=CJ_BASE_URL,
        builder=cj_builder,
        collection_links=[Link(rel="self", href=self_collection_href, prompt="Self")] # Override default self
    ).model_dump(exclude_none=True)

    return await render_cj_response(request, cj_collection_dict, "items.html", html_renderer, accept)

@router.get("/form", summary="Get a generic form representing Task Instance fields (for editing context)")
async def get_task_instance_generic_form(
    request: Request,
    html_renderer: HtmlRendererInterface = Depends(get_html_renderer),
    accept: Optional[str] = Header(None),
    cj_builder: CollectionJSONBuilder = Depends(get_cj_builder),
):
    cj_form_dict = create_cj_form_template_response(
        model_class=TaskInstanceUpdate,
        resource_name=RESOURCE_NAME, # "task-instances"
        base_api_url=CJ_BASE_URL,
        builder=cj_builder,
        form_purpose="edit_structure"
    ).model_dump(exclude_none=True)

    return await render_cj_response(request, cj_form_dict, "form.html", html_renderer, accept)


@router.get("/{task_id}", summary="Get a specific task instance")
async def get_task_instance(
    task_id: str,
    request: Request,
    workflow_service: WorkflowService = Depends(get_workflow_service),
    html_renderer: HtmlRendererInterface = Depends(get_html_renderer),
    accept: Optional[str] = Header(None),
    cj_builder: CollectionJSONBuilder = Depends(get_cj_builder),
):
    instance = await workflow_service.get_task_instance_pydantic(task_id)
    if not instance:
        error_title = "Not Found"
        error_message = f"Task instance with ID '{task_id}' not found."
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

    item_specific_url_base = f"{CJ_BASE_URL}/{RESOURCE_NAME}/{instance.id}"
    item_url_full_path = f"{item_specific_url_base}/"

    additional_links = [
        Link(rel="edit-form", href=f"{item_specific_url_base}/form/", prompt="Edit this task instance", method="GET"),
    ]
    if instance.workflow_instance_id:
        parent_wf_inst_url = f"{CJ_BASE_URL}/workflow-instances/{instance.workflow_instance_id}/"
        additional_links.append(Link(rel="collection", href=parent_wf_inst_url, prompt="Parent Workflow Instance"))

    cj_item_dict = create_cj_item_response(
        instance=instance,
        resource_name=RESOURCE_NAME,
        base_api_url=CJ_BASE_URL,
        builder=cj_builder,
        additional_links=additional_links
    ).model_dump(exclude_none=True)
    cj_item_dict["collection"]["href"] = item_url_full_path # Ensure correct href for single item view

    return await render_cj_response(request, cj_item_dict, "item.html", html_renderer, accept)


@router.get("/{task_id}/form", summary="Get a form for editing a specific task instance")
async def get_task_instance_edit_form(
    task_id: str,
    request: Request,
    workflow_service: WorkflowService = Depends(get_workflow_service),
    html_renderer: HtmlRendererInterface = Depends(get_html_renderer),
    accept: Optional[str] = Header(None),
    cj_builder: CollectionJSONBuilder = Depends(get_cj_builder),
):
    instance = await workflow_service.get_task_instance_pydantic(task_id)
    if not instance:
        error_title = "Not Found"
        error_message = f"Task instance with ID '{task_id}' not found, cannot generate edit form."
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
        model_class=TaskInstanceUpdate,
        resource_name=RESOURCE_NAME,
        base_api_url=CJ_BASE_URL,
        builder=cj_builder,
        item_instance=instance,
        form_purpose="edit"
    ).model_dump(exclude_none=True)

    return await render_cj_response(request, cj_form_dict, "form.html", html_renderer, accept)


@router.put("/{task_id}/form", summary="Update an existing task instance")
async def update_task_instance_from_form(
    task_id: str,
    request: Request,
    task_instance_update_data: TaskInstanceUpdate, # FastAPI handles JSON binding
    workflow_service: WorkflowService = Depends(get_workflow_service),
    html_renderer: HtmlRendererInterface = Depends(get_html_renderer),
    accept: Optional[str] = Header(None),
    cj_builder: CollectionJSONBuilder = Depends(get_cj_builder),
):
    updated_instance = await workflow_service.update_task_instance(task_id, task_instance_update_data)

    if not updated_instance:
        error_title = "Not Found"
        error_message = f"Task instance with ID '{task_id}' not found, cannot update."
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
        Link(rel="edit-form", href=f"{item_specific_url_base}/form/", prompt="Edit this task instance", method="GET"),
    ]
    if updated_instance.workflow_instance_id:
        parent_wf_inst_url = f"{CJ_BASE_URL}/workflow-instances/{updated_instance.workflow_instance_id}/"
        additional_links.append(Link(rel="collection", href=parent_wf_inst_url, prompt="Parent Workflow Instance"))

    cj_item_dict = create_cj_item_response(
        instance=updated_instance,
        resource_name=RESOURCE_NAME,
        base_api_url=CJ_BASE_URL,
        builder=cj_builder,
        additional_links=additional_links
    ).model_dump(exclude_none=True)
    cj_item_dict["collection"]["href"] = item_url_full_path # Ensure correct href for updated item response

    return await render_cj_response(request, cj_item_dict, "item.html", html_renderer, accept, status_code=status.HTTP_200_OK)
