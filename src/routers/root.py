from __future__ import annotations

from fastapi import APIRouter, Request, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse

import cj_models
from core.representor import Representor
from core.security import AuthenticatedUser, get_current_user
from dependencies import get_transition_registry, get_representor, get_api_key_repository
from repository import APIKeyRepository
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

    return await representor.represent(
        cj_models.CollectionJson(
            collection=(cj_models.Collection(
                href="/",
                title="Home",
                links=[t.to_link() for t in [
                    transition_manager.get_transition("home", {}),
                    transition_manager.get_transition("get_workflow_definitions", {}),
                    transition_manager.get_transition("get_workflow_instances", {}),
                ]],
            )),
            template=[],
            error=None,
        ))


@router.get(
    "/api-keys",
    tags=["collection"],
    response_class=HTMLResponse,
    operation_id="api_keys_page",
    responses={
        200: {
            "content": {
                "text/html": {}
            },
        }
    },
)
async def api_keys_page(
        request: Request,
        current_user: AuthenticatedUser = Depends(get_current_user),
        api_key_repo: APIKeyRepository = Depends(get_api_key_repository),
        representor: Representor = Depends(get_representor),
):
    """Serves the API keys management page as HTML."""
    if isinstance(current_user, RedirectResponse):
        return current_user

    # Build CJ collection similar to api_keys.py
    keys = await api_key_repo.list_api_keys(current_user.user_id)

    items = []
    for key in keys:
        item_data = [
            cj_models.ItemData(name="id", value=key["id"], prompt="Key ID", render_hint="hidden"),
            cj_models.ItemData(name="name", value=key["name"], prompt="Key Name"),
            cj_models.ItemData(name="created_at", value=key["created_at"], prompt="Created At"),
        ]
        delete_link = cj_models.Link(
            rel="delete",
            href=f"/api/keys/{key['id']}",
            prompt="Revoke this key",
            method="DELETE"
        )
        items.append(cj_models.Item(
            href=f"/api/keys/{key['id']}",
            rel="item",
            data=item_data,
            links=[delete_link]
        ))

    template_data = [
        cj_models.TemplateData(name="key_name", prompt="API Key Name", type="string", required=True, render_hint="text")
    ]
    template = cj_models.Template(name="create-api-key", data=template_data, href="/api/keys", method="POST", prompt="Create new API key")

    collection = cj_models.Collection(
        version="1.0",
        href="/api-keys",
        title="API Keys",
        items=items,
        links=[],
        queries=[]
    )

    cj = cj_models.CollectionJson(collection=collection, template=[template])

    return await representor.represent(cj)
