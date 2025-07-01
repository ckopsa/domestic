from __future__ import annotations

from fastapi import APIRouter, Request, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse

import cj_models
from core.html_renderer import HtmlRendererInterface
from core.security import AuthenticatedUser, get_current_user
from dependencies import get_html_renderer
from transitions import TransitionManager

router = APIRouter()


def get_transition_registry(request: Request) -> TransitionManager:
    return TransitionManager(request)


@router.get("/health", status_code=status.HTTP_200_OK)
async def healthcheck():
    """API endpoint for health check."""
    return {"status": "ok"}


@router.get(
    "/",
    tags=["home"],
    response_class=HTMLResponse,
    operation_id="home"
)
async def home(
        request: Request,
        current_user: AuthenticatedUser | None = Depends(get_current_user),
        renderer: HtmlRendererInterface = Depends(get_html_renderer),
        transition_manager: TransitionManager = Depends(get_transition_registry),
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

    return await renderer.render(
        "cj_template.html",
        request,
        {
            "current_user": current_user,
            "collection": collection,
        }
    )


