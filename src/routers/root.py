from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Request, Depends, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse

import cj_models
import models
from cj_models import CollectionJson
from core.html_renderer import HtmlRendererInterface
from core.security import AuthenticatedUser, get_current_user
from dependencies import get_html_renderer, get_workflow_service, get_collection_json_representor
from services import WorkflowService

router = APIRouter()


@router.get("/health", status_code=status.HTTP_200_OK)
async def healthcheck():
    """API endpoint for health check."""
    return {"status": "ok"}


@router.get(
    "/",
    tags=["home"],
    openapi_extra={
        "pageTransitions": [
            "home",
            "get_workflow_definitions",
        ],
    },
    response_class=HTMLResponse
)
async def home(
        request: Request,
        current_user: AuthenticatedUser | None = Depends(get_current_user),
        renderer: HtmlRendererInterface = Depends(get_html_renderer),
        collection_json_representor: cj_models.CollectionJsonRepresentor = Depends(get_collection_json_representor),
):
    """Serves the homepage."""
    if isinstance(current_user, RedirectResponse):
        return current_user

    cj = collection_json_representor.to_collection_json(request, [])
    return await renderer.render(
        "cj_template.html",
        request,
        {
            "current_user": current_user,
            "collection": cj.collection,
            "template": cj.template,
        }
    )


