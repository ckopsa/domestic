from typing import List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status

from core.security import AuthenticatedUser, get_current_active_user
from dependencies import get_workflow_service
from models import WorkflowDefinition, WorkflowInstance, TaskInstance, WorkflowInstanceCreateRequest # Added WorkflowInstanceCreateRequest
from services import WorkflowService

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/healthz", status_code=status.HTTP_200_OK)
async def healthcheck():
    """API endpoint for health check."""
    return {"status": "ok"}


@router.get("/workflow-definitions", response_model=List[WorkflowDefinition])
async def list_workflow_definitions(
        service: WorkflowService = Depends(get_workflow_service)
):
    """API endpoint to list all workflow definitions as JSON."""
    return await service.list_workflow_definitions()


@router.post("/workflow-definitions", response_model=WorkflowDefinition, status_code=status.HTTP_201_CREATED)
async def create_workflow_definition(
        definition: WorkflowDefinition,
        service: WorkflowService = Depends(get_workflow_service),
        current_user: AuthenticatedUser = Depends(get_current_active_user)
):
    """API endpoint to create a new workflow definition."""
    try:
        return await service.create_new_definition(
            name=definition.name,
            description=definition.description,
            task_definitions=definition.task_definitions # Changed from task_names
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/workflow-definitions/{definition_id}", response_model=WorkflowDefinition)
async def update_workflow_definition(
        definition_id: str,
        definition: WorkflowDefinition,
        service: WorkflowService = Depends(get_workflow_service),
        current_user: AuthenticatedUser = Depends(get_current_active_user)
):
    """API endpoint to update an existing workflow definition."""
    updated = await service.update_definition(
        definition_id=definition_id,
        name=definition.name,
        description=definition.description,
        task_definitions=definition.task_definitions # Changed from task_names
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Definition not found")
    return updated


@router.delete("/workflow-definitions/{definition_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow_definition(
        definition_id: str,
        service: WorkflowService = Depends(get_workflow_service),
        current_user: AuthenticatedUser = Depends(get_current_active_user)
):
    """API endpoint to delete a workflow definition."""
    try:
        await service.delete_definition(definition_id)
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/workflow-instances", response_model=WorkflowInstance, status_code=status.HTTP_201_CREATED)
async def create_workflow_instance(
        payload: WorkflowInstanceCreateRequest, # Changed to use the new Pydantic model
        service: WorkflowService = Depends(get_workflow_service),
        current_user: AuthenticatedUser = Depends(get_current_active_user)
):
    """API endpoint to create a workflow instance from a definition."""
    # Construct the full WorkflowInstance Pydantic model to pass to the service
    instance_data = WorkflowInstance(
        workflow_definition_id=payload.definition_id,
        user_id=current_user.user_id,
        name=payload.name # Will use Pydantic model's default if payload.name is None
        # Other fields like id, created_at, status, due_datetime will use defaults
        # from WorkflowInstance Pydantic model or be set by the service/repository.
    )
    instance = await service.create_workflow_instance(instance_data) # Call service with the model
    if not instance:
        # Consider more specific error based on why instance creation failed (e.g., def not found)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not create workflow instance. Ensure definition_id is valid.")
    return instance


@router.get("/workflow-instances/{instance_id}", response_model=Dict[str, Any])
async def get_workflow_instance(
        instance_id: str,
        service: WorkflowService = Depends(get_workflow_service),
        current_user: AuthenticatedUser = Depends(get_current_active_user)
):
    """API endpoint to get details of a workflow instance including tasks."""
    details = await service.get_workflow_instance_with_tasks(instance_id, current_user.user_id)
    if not details or not details["instance"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instance not found or access denied")
    return details


@router.post("/task-instances/{task_id}/complete", response_model=TaskInstance)
async def complete_task(
        task_id: str,
        service: WorkflowService = Depends(get_workflow_service),
        current_user: AuthenticatedUser = Depends(get_current_active_user)
):
    """API endpoint to mark a task as complete."""
    task = await service.complete_task(task_id, current_user.user_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task not found or already completed")
    return task


@router.get("/my-workflows", response_model=Dict[str, List[WorkflowInstance]])
async def list_user_workflows(
        service: WorkflowService = Depends(get_workflow_service),
        current_user: AuthenticatedUser = Depends(get_current_active_user)
):
    """API endpoint to list all workflow instances for the current user."""
    from fastapi.responses import RedirectResponse
    if isinstance(current_user, RedirectResponse):
        return current_user
    instances = await service.list_instances_for_user(current_user.user_id)
    return {"instances": instances}
