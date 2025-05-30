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
    print("Fetching public keys from Keycloak JWKS endpoint...")
    certs_url = f"{KEYCLOAK_SERVER_URL}realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"
    response = requests.get(certs_url, timeout=10)
    response.raise_for_status()
    jwks_data = response.json()
    print(f"Fetched {len(jwks_data.get('keys', []))} keys from JWKS.")
    return jwks_data

async def get_current_user(request: Request, token: Annotated[str, Depends(oauth2_scheme)]) -> AuthenticatedUser:
    """Extract user information from Keycloak JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not token:
        token = request.cookies.get("access_token", "")
    
    if not token:
        raise credentials_exception
        
    # --- Start Debug Logging ---
    try:
        unverified_header = jwt.get_unverified_header(token)
        token_kid = unverified_header.get('kid')
        print(f"DEBUG: Token KID from header: {token_kid}")
        # Decoding without verification for debug purposes ONLY
        unverified_payload = jwt.decode(token, options={"verify_signature": False, "verify_aud": False, "verify_iss": False})
        print(f"DEBUG: Token Issuer (unverified): {unverified_payload.get('iss')}")
        print(f"DEBUG: Token Audience (unverified): {unverified_payload.get('aud')}")
    except Exception as e:
        print(f"DEBUG: Error decoding unverified token header/payload: {e}")

    expected_issuer = f"{KEYCLOAK_SERVER_URL}realms/{KEYCLOAK_REALM}"
    print(f"DEBUG: Expected Issuer: {expected_issuer}")
    print(f"DEBUG: Expected Audience: {KEYCLOAK_API_CLIENT_ID}")
    # --- End Debug Logging ---

    try:
        jwks = get_keycloak_public_keys()
        keys_from_jwks = jwks.get('keys', []) # Renamed to avoid confusion with 'key' loop variable
        
        if not keys_from_jwks:
            print("DEBUG: No keys found in JWKS response.")
            raise credentials_exception # Or a more specific error

        print(f"DEBUG: Number of keys in JWKS being tried: {len(keys_from_jwks)}")
        for idx, key_data in enumerate(keys_from_jwks):
            print(f"DEBUG: Trying key index {idx}, KID from JWKS: {key_data.get('kid')}")
        # --- End Debug Logging for keys ---

        decoded_token_payload = None
        last_exception = None
        
        for key_data in keys_from_jwks: 
            try:
                public_key = RSAAlgorithm.from_jwk(key_data)
                
                decoded_token_payload = jwt.decode(
                    token,
                    public_key,
                    algorithms=["RS256"],
                    audience='account',
                    issuer=expected_issuer # Use the variable for consistency
                )
                print(f"DEBUG: Token successfully decoded with KID: {key_data.get('kid')}")
                break
            except jwt.ExpiredSignatureError as e:
                print(f"Token decoding failed: Expired signature. {e}")
                last_exception = e
                raise credentials_exception from e
            except jwt.InvalidTokenError as e: # InvalidSignatureError is a subclass of InvalidTokenError
                last_exception = e
                print(f"Invalid token with key KID {key_data.get('kid', 'N/A')}: {e}. Trying next key.")
                continue 
            except Exception as e: 
                last_exception = e
                print(f"Unexpected error decoding token with key KID {key_data.get('kid', 'N/A')}: {e}. Trying next key.")
                continue
                
        if decoded_token_payload is None:
            if last_exception:
                print(f"DEBUG: All keys failed. Last error: {last_exception}")
                raise credentials_exception from last_exception
            else: 
                print("DEBUG: Decoded token payload is None, but no exception was caught or no keys in JWKS.")
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
        print(f"General exception during token processing: {e}")
        raise credentials_exception from e

async def get_current_active_user(current_user: Annotated[AuthenticatedUser, Depends(get_current_user)]) -> AuthenticatedUser:
    """Check if the current user is active. Keycloak handles this before token issuance."""
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
