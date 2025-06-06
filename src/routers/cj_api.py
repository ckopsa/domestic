from fastapi import APIRouter, Depends, HTTPException, Request, status
from typing import List, Optional

from core.security import get_current_active_user, AuthenticatedUser
from dependencies import get_workflow_service
from models import (
    WorkflowDefinition,
    CJWorkflowDefinition,
    WorkflowInstance,
    CJWorkflowInstance,
    TaskInstance,
    CJTaskInstance,
)
from cj_models import CollectionJson, Link, Collection # Query, QueryData might be needed for root
from services import WorkflowService

router = APIRouter(
    prefix="/api/cj",
    tags=["CollectionJSON API"],
)


@router.get("/", response_model=CollectionJson, summary="CJ API Root")
async def get_cj_api_root(request: Request):
    """
    Provides a Collection+JSON response detailing the available top-level resources
    within the CJ API.
    """
    base_url_str = str(request.base_url)

    api_root_links = [
        Link(
            rel="workflow-definitions",
            href=f"{base_url_str.rstrip('/')}{router.prefix}/workflow-definitions/",
            prompt="Workflow Definitions",
            method="GET"
        ),
        Link(
            rel="workflow-instances",
            href=f"{base_url_str.rstrip('/')}{router.prefix}/workflow-instances/", # Assuming this will exist
            prompt="Workflow Instances",
            method="GET"
        ),
        Link(
            rel="task-instances",
            href=f"{base_url_str.rstrip('/')}{router.prefix}/task-instances/", # Assuming this will exist
            prompt="Task Instances",
            method="GET"
        ),
        # Potentially add other top-level resources here as they are created
    ]

    collection_data = {
        "version": "1.0",
        "href": f"{base_url_str.rstrip('/')}{router.prefix}/",
        "title": "Collection+JSON API Root",
        "links": api_root_links,
        # No items or queries at the root level for now
    }

    # We need to import Collection from cj_models to construct this properly
    # from src.cj_models import Collection # Already imported at the top
    return CollectionJson(collection=Collection(**collection_data))


# --- Workflow Instance Endpoints ---

@router.get("/workflow-instances/", response_model=CollectionJson, summary="List Workflow Instances in CJ format")
async def list_workflow_instances_cj(
    request: Request,
    service: WorkflowService = Depends(get_workflow_service),
    user_id: Optional[str] = None,
    status: Optional[str] = None  # Assuming status is a string, e.g. "active", "completed"
):
    """
    Retrieves a list of all workflow instances in Collection+JSON format.
    Supports filtering by user_id and status.
    """
    # Assuming a service method list_workflow_instances exists or instance_repo can filter
    # For now, let's assume instance_repo.get_all_workflow_instances can take optional filters
    # or a more specific service method is called.
    # This is a simplification; a real implementation might need a dedicated service method.
    if hasattr(service.instance_repo, 'get_filtered_workflow_instances'):
        db_instances: List[WorkflowInstance] = await service.instance_repo.get_filtered_workflow_instances(user_id=user_id, status=status)
    else:
        # Fallback or placeholder if no direct filtering method on repo
        db_instances: List[WorkflowInstance] = await service.instance_repo.get_all_workflow_instances()
        if user_id:
            db_instances = [inst for inst in db_instances if inst.user_id == user_id]
        if status:
            db_instances = [inst for inst in db_instances if inst.status.value == status]


    cj_instances_list: List[CJWorkflowInstance] = [
        CJWorkflowInstance.model_validate(instance) for instance in db_instances
    ]

    return CJWorkflowInstance.to_cj_representation(
        instances=cj_instances_list,
        context={'base_url': str(request.base_url)}
    )


# --- Task Instance Endpoints ---

@router.get("/workflow-instances/{instance_id}/tasks/", response_model=CollectionJson, summary="List Task Instances for a Workflow Instance in CJ format")
async def list_task_instances_for_workflow_cj(
    instance_id: str,
    request: Request,
    service: WorkflowService = Depends(get_workflow_service)
):
    """
    Retrieves a list of all task instances for a specific workflow instance in Collection+JSON format.
    """
    # First, check if workflow instance exists to give a proper 404 for it
    wf_instance = await service.instance_repo.get_workflow_instance_by_id(instance_id)
    if not wf_instance:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Workflow Instance {instance_id} not found.")

    db_tasks: List[TaskInstance] = await service.task_repo.get_tasks_for_workflow_instance(instance_id)

    cj_tasks_list: List[CJTaskInstance] = [
        CJTaskInstance.model_validate(task) for task in db_tasks
    ]

    # The collection href should ideally be the URL from which it was requested.
    # The CJTaskInstance.to_cj_representation method uses the class's cj_collection_href_template by default.
    # We can override the title, and potentially the main collection href if the model/method supports it.
    # For now, we rely on item 'href' and 'rel' to be correct and link back.
    # A more sophisticated approach might involve passing a collection_href_override.
    return CJTaskInstance.to_cj_representation(
        instances=cj_tasks_list,
        context={'base_url': str(request.base_url)},
        collection_title_override=f"Tasks for Workflow Instance {instance_id}",
        # If to_cj_representation supported collection_href_override:
        # collection_href_override=str(request.url)
    )

@router.get("/task-instances/{task_id}", response_model=CollectionJson, summary="Get a specific Task Instance in CJ format")
async def get_task_instance_cj(
    task_id: str,
    request: Request,
    service: WorkflowService = Depends(get_workflow_service)
):
    """
    Retrieves a specific task instance by its ID in Collection+JSON format.
    """
    db_task = await service.task_repo.get_task_instance_by_id(task_id)
    if not db_task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task Instance not found")

    cj_task = CJTaskInstance.model_validate(db_task)

    return CJTaskInstance.to_cj_representation(
        instances=cj_task,
        context={'base_url': str(request.base_url)}
    )

@router.post("/task-instances/{task_id}/complete", response_model=CollectionJson, summary="Mark a Task Instance as complete and return CJ representation")
async def complete_task_instance_cj(
    task_id: str,
    request: Request,
    service: WorkflowService = Depends(get_workflow_service),
    current_user: AuthenticatedUser = Depends(get_current_active_user) # Assuming this dependency provides user_id
):
    """
    Marks a task instance as complete.
    """
    try:
        # Assuming service.complete_task returns the updated TaskInstance Pydantic model
        updated_task_instance = await service.complete_task(task_id=task_id, user_id=current_user.user_id)
    except ValueError as e: # Or a more specific custom exception from the service
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionError as e: # Example, service might raise this
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    if not updated_task_instance: # Should be handled by exceptions, but as a safeguard
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task Instance not found or could not be updated")

    cj_updated_task = CJTaskInstance.model_validate(updated_task_instance)

    return CJTaskInstance.to_cj_representation(
        instances=cj_updated_task,
        context={'base_url': str(request.base_url)}
    )

@router.post("/task-instances/{task_id}/undo-complete", response_model=CollectionJson, summary="Undo Task Instance completion and return CJ representation")
async def undo_complete_task_instance_cj(
    task_id: str,
    request: Request,
    service: WorkflowService = Depends(get_workflow_service),
    current_user: AuthenticatedUser = Depends(get_current_active_user)
):
    """
    Marks a task instance as not complete (undoes completion).
    """
    try:
        # Assuming service.undo_complete_task returns the updated TaskInstance Pydantic model
        updated_task_instance = await service.undo_complete_task(task_id=task_id, user_id=current_user.user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    if not updated_task_instance:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task Instance not found or could not be updated")

    cj_updated_task = CJTaskInstance.model_validate(updated_task_instance)

    return CJTaskInstance.to_cj_representation(
        instances=cj_updated_task,
        context={'base_url': str(request.base_url)}
    )

@router.post("/workflow-instances/", response_model=CollectionJson, status_code=status.HTTP_201_CREATED, summary="Create Workflow Instance and return CJ representation")
async def create_workflow_instance_cj(
    request: Request,
    instance_data: WorkflowInstance, # Input model, contains workflow_definition_id, user_id, due_datetime
    service: WorkflowService = Depends(get_workflow_service)
):
    """
    Creates a new workflow instance and returns its representation in Collection+JSON format.
    """
    # instance_data is already a WorkflowInstance Pydantic model from the request body
    created_db_instance = await service.create_workflow_instance(instance_data)

    if not created_db_instance:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not create workflow instance, possibly due to invalid definition ID.")

    created_cj_instance = CJWorkflowInstance.model_validate(created_db_instance)

    return CJWorkflowInstance.to_cj_representation(
        instances=created_cj_instance,
        context={'base_url': str(request.base_url)}
    )

@router.get("/workflow-instances/{instance_id}", response_model=CollectionJson, summary="Get a specific Workflow Instance in CJ format")
async def get_workflow_instance_cj(
    instance_id: str,
    request: Request,
    service: WorkflowService = Depends(get_workflow_service)
):
    """
    Retrieves a specific workflow instance by its ID in Collection+JSON format.
    """
    db_instance = await service.instance_repo.get_workflow_instance_by_id(instance_id)
    if not db_instance:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow Instance not found")

    cj_instance = CJWorkflowInstance.model_validate(db_instance)

    return CJWorkflowInstance.to_cj_representation(
        instances=cj_instance,
        context={'base_url': str(request.base_url)}
    )


@router.get("/workflow-definitions/", response_model=CollectionJson, summary="List Workflow Definitions in CJ format")
async def list_workflow_definitions_cj(request: Request, service: WorkflowService = Depends(get_workflow_service)):
    """
    Retrieves a list of all workflow definitions in Collection+JSON format.
    """
    db_definitions: List[WorkflowDefinition] = await service.list_workflow_definitions()

    cj_definitions_list: List[CJWorkflowDefinition] = [
        CJWorkflowDefinition.model_validate(definition.model_dump()) for definition in db_definitions
    ]

    return CJWorkflowDefinition.to_cj_representation(
        instances=cj_definitions_list,
        context={'base_url': str(request.base_url)}
    )


@router.post("/workflow-definitions/", response_model=CollectionJson, status_code=status.HTTP_201_CREATED, summary="Create Workflow Definition and return CJ representation")
async def create_workflow_definition_cj(request: Request, definition_data: WorkflowDefinition, service: WorkflowService = Depends(get_workflow_service)):
    """
    Creates a new workflow definition and returns its representation in Collection+JSON format.
    The input `definition_data` should be a valid WorkflowDefinition model.
    """
    # The service method `create_new_definition` expects individual arguments,
    # not the whole WorkflowDefinition object directly, based on the subtask description.
    # It also implies that `task_definitions` within `definition_data` are `TaskDefinitionBase`
    created_db_definition = await service.create_new_definition(
        name=definition_data.name,
        description=definition_data.description,
        task_definitions=definition_data.task_definitions, # Assuming these are TaskDefinitionBase
    )

    # Convert the Pydantic model returned by the service to CJWorkflowDefinition
    # The service returns a WorkflowDefinition Pydantic model, so model_validate is appropriate
    created_cj_definition = CJWorkflowDefinition.model_validate(created_db_definition.model_dump())

    return CJWorkflowDefinition.to_cj_representation(
        instances=created_cj_definition, # Pass a single instance
        context={'base_url': str(request.base_url)}
    )


@router.get("/workflow-definitions/{definition_id}", response_model=CollectionJson, summary="Get a specific Workflow Definition in CJ format")
async def get_workflow_definition_cj(definition_id: str, request: Request, service: WorkflowService = Depends(get_workflow_service)):
    """
    Retrieves a specific workflow definition by its ID in Collection+JSON format.
    """
    # Assuming get_workflow_definition_by_id returns a Pydantic model (WorkflowDefinition)
    # as services or repos might be set up to do so, or an ORM model if from_attributes=True is used.
    db_definition = await service.definition_repo.get_workflow_definition_by_id(definition_id)
    if not db_definition:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow Definition not found")

    # Ensure it's a Pydantic WorkflowDefinition model first.
    # If db_definition is already a Pydantic model, model_validate is idempotent.
    # If it's an ORM model, model_validate will convert it (assuming Config.from_attributes = True).
    pydantic_definition = WorkflowDefinition.model_validate(db_definition)

    # Then convert to CJWorkflowDefinition
    cj_definition = CJWorkflowDefinition.model_validate(pydantic_definition.model_dump())

    return CJWorkflowDefinition.to_cj_representation(
        instances=cj_definition, # Pass a single instance
        context={'base_url': str(request.base_url)}
    )
