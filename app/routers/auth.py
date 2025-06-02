import os
from urllib.parse import quote_plus

import requests
from fastapi import APIRouter, Request, HTTPException
from fastapi import status
from fastapi.responses import RedirectResponse

from app.config import KEYCLOAK_SERVER_URL, KEYCLOAK_REALM, KEYCLOAK_API_CLIENT_ID, KEYCLOAK_API_CLIENT_SECRET, \
    KEYCLOAK_REDIRECT_URI

router = APIRouter(tags=["auth"])


@router.get("/login", response_class=RedirectResponse)
async def redirect_to_keycloak_login(request: Request, redirect: str = None):
    """Redirect to Keycloak login page, storing the original URL for post-login redirect."""
    original_url = redirect if redirect else str(request.headers.get('referer', '/'))
    login_url = (
        f"{KEYCLOAK_SERVER_URL}realms/{KEYCLOAK_REALM}/protocol/openid-connect/auth"
        f"?client_id={KEYCLOAK_API_CLIENT_ID}&response_type=code&redirect_uri={KEYCLOAK_REDIRECT_URI}"
        f"&state={original_url}"
    )
    return RedirectResponse(url=login_url)


@router.get("/callback", response_class=RedirectResponse)
async def handle_keycloak_callback(code: str, state: str = None):
    """Handle the callback from Keycloak with the authorization code."""
    token_url = f"{KEYCLOAK_SERVER_URL}realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"
    payload = {
        "grant_type": "authorization_code",
        "client_id": KEYCLOAK_API_CLIENT_ID,
        "client_secret": KEYCLOAK_API_CLIENT_SECRET,
        "code": code,
        "redirect_uri": KEYCLOAK_REDIRECT_URI
    }

    response = requests.post(token_url, data=payload)
    if response.status_code != 200:
        raise HTTPException(status_code=400,
                            detail=f"Failed to exchange authorization code for token. Keycloak response: {response.text}")

    token_data = response.json()
    access_token = token_data.get("access_token")

    if not access_token:
        raise HTTPException(status_code=400, detail="No access token received from Keycloak")

    # Create a redirect response and set the token as a secure cookie
    redirect_url = state if state else "/"
    redirect_response = RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
    redirect_response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,  # Prevents JavaScript access to the cookie
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",  # Helps prevent CSRF
        max_age=token_data.get("expires_in", 3600)  # Set cookie expiration to match token expiration
    )

    return redirect_response


@router.post("/token")
async def token_placeholder():
    """Placeholder for token endpoint - actual authentication handled by Keycloak."""
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Authentication handled by Keycloak. Use /login endpoint or configure client to use Keycloak directly."
    )


@router.get("/logout", response_class=RedirectResponse)
async def logout():
    """Logout user by clearing cookies and redirecting to Keycloak logout."""
    post_logout_redirect_to_app = os.getenv("KEYCLOAK_POST_LOGOUT_REDIRECT_URI",
                                            f"{KEYCLOAK_REDIRECT_URI.split('/callback')[0]}/login")
    encoded_post_logout_redirect = quote_plus(post_logout_redirect_to_app)

    keycloak_logout_url = (
        f"{KEYCLOAK_SERVER_URL}realms/{KEYCLOAK_REALM}/protocol/openid-connect/logout"
        f"?post_logout_redirect_uri={encoded_post_logout_redirect}&client_id={KEYCLOAK_API_CLIENT_ID}"
    )

    response = RedirectResponse(url=keycloak_logout_url, status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(key="access_token")
    return response
