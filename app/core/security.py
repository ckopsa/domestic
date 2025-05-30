from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2AuthorizationCodeBearer
from jose import JWTError, jwt
import requests
from typing import Dict, Any
from pydantic import BaseModel
from app.config import KEYCLOAK_SERVER_URL, KEYCLOAK_REALM, KEYCLOAK_API_CLIENT_ID

# OAuth2 scheme for Bearer token
oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=f"{KEYCLOAK_SERVER_URL}realms/{KEYCLOAK_REALM}/protocol/openid-connect/auth",
    tokenUrl=f"{KEYCLOAK_SERVER_URL}realms/{KEYCLOAK_REALM}/protocol/openid-connect/token",
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
        jwks_url = f"{KEYCLOAK_SERVER_URL}realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"
        response = requests.get(jwks_url)
        response.raise_for_status()
        _jwks_cache.update(response.json())
    return _jwks_cache

async def get_current_user(token: str = Depends(oauth2_scheme)) -> AuthenticatedUser:
    """Validate JWT token and extract user information."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
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
    except JWTError:
        raise credentials_exception
