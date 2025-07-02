from __future__ import annotations

from fastapi import APIRouter, Request, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse

import cj_models
from core.representor import Representor
from core.security import AuthenticatedUser, get_current_user
from dependencies import get_transition_registry, get_representor
from transitions import TransitionManager

router = APIRouter()


@router.get("/health", status_code=status.HTTP_200_OK)
async def healthcheck():
    """API endpoint for health check."""
    return {"status": "ok"}


@router.get(
    "/",
    tags=["collection"],
    response_class=HTMLResponse,
    operation_id="home",
    responses={
        200: {
            "content": {
                "application/vnd.collection+json": {},
                "text/html": {}
            },
        }
    },
)
async def home(
        request: Request,
        current_user: AuthenticatedUser | None = Depends(get_current_user),
        transition_manager: TransitionManager = Depends(get_transition_registry),
        representor: Representor = Depends(get_representor),
):
    """Serves the homepage."""
    if isinstance(current_user, RedirectResponse):
        return current_user

    page_transitions = [
        transition_manager.get_transition("home", {}),
        transition_manager.get_transition("get_workflow_definitions", {}),
        transition_manager.get_transition("get_workflow_instances", {}),
    ]

    collection = cj_models.Collection(
        href=str(request.url),
        title="Home",
        links=[t.to_link() for t in page_transitions if t],
    )

    return await representor.represent(
        cj_models.CollectionJson(
            collection=collection,
            template=[],
            error=None,
        ))
