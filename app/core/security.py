from typing import Annotated, Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
import jwt
import requests
from functools import lru_cache
from app.config import KEYCLOAK_SERVER_URL, KEYCLOAK_REALM, KEYCLOAK_API_CLIENT_ID

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

class AuthenticatedUser(BaseModel):
    user_id: str
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = False

@lru_cache(maxsize=1)
def get_keycloak_public_keys() -> Dict[str, Any]:
    """Fetch public keys from Keycloak server."""
    certs_url = f"{KEYCLOAK_SERVER_URL}realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"
    response = requests.get(certs_url, timeout=10)
    response.raise_for_status()
    return response.json()

async def get_current_user(request: Request, token: Annotated[str, Depends(oauth2_scheme)]) -> AuthenticatedUser:
    """Extract user information from Keycloak JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # If token is not in header, try to get it from cookie
    if not token:
        token = request.cookies.get("access_token", "")
    
    if not token:
        raise credentials_exception
        
    try:
        # Get public keys from Keycloak
        jwks = get_keycloak_public_keys()
        keys = jwks.get('keys', [])
        
        # Try to decode with each key (usually there's just one, but handling multiple for robustness)
        decoded_token = None
        for key in keys:
            try:
                decoded_token = jwt.decode(
                    token,
                    key,
                    algorithms=["RS256"],
                    audience=KEYCLOAK_API_CLIENT_ID,
                    issuer=f"{KEYCLOAK_SERVER_URL}realms/{KEYCLOAK_REALM}"
                )
                break
            except jwt.InvalidTokenError:
                continue
                
        if decoded_token is None:
            raise credentials_exception
            
        # Extract user information from token
        user_id = decoded_token.get("sub", "")
        username = decoded_token.get("preferred_username", "")
        email = decoded_token.get("email", None)
        full_name = decoded_token.get("name", None)
        
        if not user_id or not username:
            raise credentials_exception
            
        return AuthenticatedUser(
            user_id=user_id,
            username=username,
            email=email,
            full_name=full_name,
            disabled=False  # Keycloak handles disabled status before token issuance
        )
        
    except Exception as e:
        raise credentials_exception from e

async def get_current_active_user(current_user: Annotated[AuthenticatedUser, Depends(get_current_user)]) -> AuthenticatedUser:
    """Check if the current user is active. Keycloak handles this before token issuance."""
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
