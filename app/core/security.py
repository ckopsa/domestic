from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2AuthorizationCodeBearer
from jose import JWTError, jwt
import requests
from typing import Dict, Any, Optional
from pydantic import BaseModel
from app.config import KEYCLOAK_SERVER_URL, KEYCLOAK_REALM, KEYCLOAK_API_CLIENT_ID

# OAuth2 scheme for Bearer token
oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=f"{KEYCLOAK_SERVER_URL}realms/{KEYCLOAK_REALM}/protocol/openid-connect/auth",
    tokenUrl=f"{KEYCLOAK_SERVER_URL}realms/{KEYCLOAK_REALM}/protocol/openid-connect/token",
    auto_error=False
)

class AuthenticatedUser(BaseModel):
    user_id: str
    username: str
    email: str = ""

# Cache for Keycloak public keys
_jwks_cache: Dict[str, Any] = {}

def get_keycloak_public_keys() -> Dict[str, Any]:
    """Fetch and cache Keycloak public keys from JWKS endpoint."""
    if not _jwks_cache:
        try:
            jwks_url = f"{KEYCLOAK_SERVER_URL}realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"
            response = requests.get(jwks_url, timeout=5)
            response.raise_for_status()
            _jwks_cache.update(response.json())
        except requests.exceptions.RequestException as e:
            # Log the error in a real application
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to fetch Keycloak public keys",
            ) from e
    return _jwks_cache

from fastapi import Request

async def get_current_user(request: Request, token: Optional[str] = Depends(oauth2_scheme)) -> AuthenticatedUser:
    """Validate JWT token or mock cookie and extract user information. Prioritizes mock cookie, then JWT Bearer token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # For MVP, first check for mock cookie before attempting JWT validation
        cookie_token = request.cookies.get("auth_token", "")
        if cookie_token and cookie_token.startswith("mock_token_"):
            user_id = cookie_token.replace("mock_token_", "")
            return AuthenticatedUser(user_id=user_id, username=user_id, email=f"{user_id}@example.com")
        
        # If no valid cookie, try Bearer token (if token was provided by Depends(oauth2_scheme))
        if token:
            jwks = get_keycloak_public_keys()
            # Find the correct key for the token's 'kid'
            kid = jwt.get_unverified_header(token).get('kid')
            key = next((k for k in jwks.get('keys', []) if k['kid'] == kid), None)
            if not key:
                raise credentials_exception
            
            # Decode and validate the token
            payload = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=KEYCLOAK_API_CLIENT_ID,
                issuer=f"{KEYCLOAK_SERVER_URL}realms/{KEYCLOAK_REALM}"
            )
            
            user_id: str = payload.get("sub")
            username: str = payload.get("preferred_username", "")
            email: str = payload.get("email", "")
            
            if user_id is None:
                raise credentials_exception
                
            return AuthenticatedUser(user_id=user_id, username=username, email=email)
        
        # If neither cookie nor token authenticated the user
        raise credentials_exception
    except JWTError:
        # If JWT validation fails, we've already checked the cookie, so fail
        raise credentials_exception
