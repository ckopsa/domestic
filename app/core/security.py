from typing import Annotated, Dict, Any
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
import jwt
import requests
from app.config import KEYCLOAK_SERVER_URL, KEYCLOAK_REALM, KEYCLOAK_API_CLIENT_ID
from jwt.algorithms import RSAAlgorithm


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

class AuthenticatedUser(BaseModel):
    user_id: str
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = False

# Temporarily comment out lru_cache to rule out stale cached keys
# @lru_cache(maxsize=1) 
def get_keycloak_public_keys() -> Dict[str, Any]:
    """Fetch public keys from Keycloak server."""
    certs_url = f"{KEYCLOAK_SERVER_URL}realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"
    response = requests.get(certs_url, timeout=10)
    response.raise_for_status()
    jwks_data = response.json()
    return jwks_data

async def get_current_user(request: Request, token: Annotated[str | None, Depends(oauth2_scheme)] = None) -> AuthenticatedUser:
    """Extract user information from Keycloak JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if token is None:
        token = request.cookies.get("access_token", "")
    
    if not token:
        if request.url.path.startswith("/api"):
            raise credentials_exception # Defined earlier, raises 401
        else:
            # Redirect to login page for non-API routes
            from fastapi.responses import RedirectResponse
            original_url = str(request.url)
            login_url = f"/login?redirect={original_url}"
            return RedirectResponse(url=login_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
        
    try:
        jwks = get_keycloak_public_keys()
        keys_from_jwks = jwks.get('keys', [])
        
        if not keys_from_jwks:
            raise credentials_exception

        decoded_token_payload = None
        last_exception = None
        
        for key_data in keys_from_jwks: 
            try:
                public_key = RSAAlgorithm.from_jwk(key_data)
                expected_issuer = f"{KEYCLOAK_SERVER_URL}realms/{KEYCLOAK_REALM}"
                decoded_token_payload = jwt.decode(
                    token,
                    public_key,
                    algorithms=["RS256", "HS256"],  # Allow HS256 for testing
                    audience="account",
                    issuer=expected_issuer
                )
                break
            except jwt.ExpiredSignatureError as e:
                last_exception = e
                raise credentials_exception from e
            except jwt.InvalidTokenError as e:
                last_exception = e
                continue 
            except Exception as e: 
                last_exception = e
                continue
                
        if decoded_token_payload is None:
            if last_exception:
                raise credentials_exception from last_exception
            else:
                raise credentials_exception
            
        user_id = decoded_token_payload.get("sub", "")
        username = decoded_token_payload.get("preferred_username", "")
        email = decoded_token_payload.get("email", None)
        full_name = decoded_token_payload.get("name", None)
        
        if not user_id or not username:
            raise credentials_exception
            
        return AuthenticatedUser(
            user_id=user_id,
            username=username,
            email=email,
            full_name=full_name,
            disabled=False 
        )
    except HTTPException as e: 
        raise e
    except Exception as e: 
        raise credentials_exception from e

async def get_current_active_user(current_user: Annotated[AuthenticatedUser, Depends(get_current_user)]) -> AuthenticatedUser:
    """Check if the current user is active. Keycloak handles this before token issuance."""
    # If current_user is a RedirectResponse, return it immediately
    if not isinstance(current_user, AuthenticatedUser):
        return current_user
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
