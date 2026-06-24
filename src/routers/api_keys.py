from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException, status, Form

from cj_models import CollectionJson, Collection, Item, ItemData, Template, TemplateData, Link
from core.security import get_current_active_user, AuthenticatedUser
from dependencies import get_api_key_repository
from repository import APIKeyRepository

router = APIRouter(prefix="/api/keys", tags=["API Keys"])


@router.post("/", response_model=CollectionJson)
async def create_api_key(
    key_name: str = Form(...),
    current_user: AuthenticatedUser = Depends(get_current_active_user),
    api_key_repo: APIKeyRepository = Depends(get_api_key_repository)
):
    """Create a new API key for the current user and return updated Collection+JSON."""
    key = await api_key_repo.create_api_key(current_user.user_id, key_name)

    # Get updated keys list including the new one
    keys = await api_key_repo.list_api_keys(current_user.user_id)

    items = []
    for k in keys:
        item_data = [
            ItemData(name="id", value=k["id"], prompt="Key ID", render_hint="hidden"),
            ItemData(name="name", value=k["name"], prompt="Key Name"),
            ItemData(name="created_at", value=k["created_at"], prompt="Created At"),
        ]
        delete_link = Link(
            rel="delete",
            href=f"/api/keys/{k['id']}",
            prompt="Revoke this key",
            method="DELETE"
        )
        items.append(Item(
            href=f"/api/keys/{k['id']}",
            rel="item",
            data=item_data,
            links=[delete_link]
        ))

    # Add a special item for the newly created key with the plain key
    new_key_data = [
        ItemData(name="api_key", value=key, prompt="Generated API Key (store securely)", render_hint="textarea"),
        ItemData(name="name", value=key_name, prompt="Key Name"),
    ]
    items.insert(0, Item(  # Insert at top
        href="/api/keys",
        rel="created",
        data=new_key_data
    ))

    template_data = [
        TemplateData(name="key_name", prompt="API Key Name", type="string", required=True, render_hint="text")
    ]
    template = Template(name="create-api-key", data=template_data, href="/api/keys", method="POST", prompt="Create new API key")

    collection = Collection(
        version="1.0",
        href="/api/keys",
        title="API Keys - Key Created Successfully",
        items=items,
        links=[],
        queries=[]
    )

    return CollectionJson(collection=collection, template=[template])


@router.get("/", response_model=CollectionJson)
async def list_api_keys(
    current_user: AuthenticatedUser = Depends(get_current_active_user),
    api_key_repo: APIKeyRepository = Depends(get_api_key_repository)
):
    """List all active API keys for the current user in Collection+JSON format."""
    keys = await api_key_repo.list_api_keys(current_user.user_id)

    items = []
    for key in keys:
        item_data = [
            ItemData(name="id", value=key["id"], prompt="Key ID", render_hint="hidden"),
            ItemData(name="name", value=key["name"], prompt="Key Name"),
            ItemData(name="created_at", value=key["created_at"], prompt="Created At"),
        ]
        delete_link = Link(
            rel="delete",
            href=f"/api/keys/{key['id']}",
            prompt="Revoke this key",
            method="DELETE"
        )
        items.append(Item(
            href=f"/api/keys/{key['id']}",
            rel="item",
            data=item_data,
            links=[delete_link]
        ))

    template_data = [
        TemplateData(name="key_name", prompt="API Key Name", type="string", required=True, render_hint="text")
    ]
    template = Template(name="create-api-key", data=template_data, href="/api/keys", method="POST", prompt="Create new API key")

    collection = Collection(
        version="1.0",
        href="/api/keys",
        title="API Keys",
        items=items,
        links=[],
        queries=[]
    )

    return CollectionJson(collection=collection, template=[template])


@router.delete("/{key_id}", response_model=CollectionJson)
async def revoke_api_key(
    key_id: int,
    current_user: AuthenticatedUser = Depends(get_current_active_user),
    api_key_repo: APIKeyRepository = Depends(get_api_key_repository)
):
    """Revoke an API key by ID and return updated Collection+JSON."""
    success = await api_key_repo.revoke_api_key(current_user.user_id, key_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found or not owned by user")

    # Get updated keys list after revocation
    keys = await api_key_repo.list_api_keys(current_user.user_id)

    items = []
    for k in keys:
        item_data = [
            ItemData(name="id", value=k["id"], prompt="Key ID", render_hint="hidden"),
            ItemData(name="name", value=k["name"], prompt="Key Name"),
            ItemData(name="created_at", value=k["created_at"], prompt="Created At"),
        ]
        delete_link = Link(
            rel="delete",
            href=f"/api/keys/{k['id']}",
            prompt="Revoke this key",
            method="DELETE"
        )
        items.append(Item(
            href=f"/api/keys/{k['id']}",
            rel="item",
            data=item_data,
            links=[delete_link]
        ))

    template_data = [
        TemplateData(name="key_name", prompt="API Key Name", type="string", required=True, render_hint="text")
    ]
    template = Template(name="create-api-key", data=template_data, href="/api/keys", method="POST", prompt="Create new API key")

    collection = Collection(
        version="1.0",
        href="/api/keys",
        title="API Keys - Key Revoked Successfully",
        items=items,
        links=[],
        queries=[]
    )

    return CollectionJson(collection=collection, template=[template])
