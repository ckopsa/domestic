import pytest
import sys
import os
from unittest.mock import patch
from fastapi import HTTPException
from jose import jwt
from app.core.security import get_current_user, get_keycloak_public_keys, AuthenticatedUser
from app.config import KEYCLOAK_SERVER_URL, KEYCLOAK_REALM, KEYCLOAK_API_CLIENT_ID

# Add the project root to sys.path to ensure 'app' module can be found
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Mock data for testing
MOCK_TOKEN_VALID = jwt.encode(
    {
        "sub": "test_user_id",
        "preferred_username": "test_user",
        "email": "test@example.com",
        "iss": f"{KEYCLOAK_SERVER_URL}realms/{KEYCLOAK_REALM}",
        "aud": KEYCLOAK_API_CLIENT_ID
    },
    "secret",  # This would be replaced with a proper key in real scenarios
    algorithm="HS256",  # Using HS256 for simplicity in test
    headers={"kid": "mock_kid"}
)

MOCK_TOKEN_INVALID = "invalid.token.string"

# Mock get_keycloak_public_keys to avoid real HTTP calls during tests
def mock_get_keycloak_public_keys():
    return {
        "keys": [
            {
                "kid": "mock_kid",
                "kty": "RSA",
                "alg": "RS256",
                "use": "sig",
                "n": "mock_modulus",
                "e": "mock_exponent"
            }
        ]
    }

# Mock jwt.decode to return a predefined payload
def mock_jwt_decode(token, key, algorithms, audience, issuer):
    if token == MOCK_TOKEN_VALID:
        return {
            "sub": "test_user_id",
            "preferred_username": "test_user",
            "email": "test@example.com",
            "iss": f"{KEYCLOAK_SERVER_URL}realms/{KEYCLOAK_REALM}",
            "aud": KEYCLOAK_API_CLIENT_ID
        }
    raise jwt.JWTError("Invalid token")

@pytest.mark.asyncio
async def test_get_current_user_valid_token(monkeypatch):
    # Arrange
    monkeypatch.setattr("app.core.security.get_keycloak_public_keys", mock_get_keycloak_public_keys)
    monkeypatch.setattr("jose.jwt.decode", mock_jwt_decode)
    
    # Act
    user = await get_current_user(MOCK_TOKEN_VALID)
    
    # Assert
    assert isinstance(user, AuthenticatedUser)
    assert user.user_id == "test_user_id"
    assert user.username == "test_user"
    assert user.email == "test@example.com"

@pytest.mark.asyncio
async def test_get_current_user_invalid_token(monkeypatch):
    # Arrange
    monkeypatch.setattr("app.core.security.get_keycloak_public_keys", mock_get_keycloak_public_keys)
    monkeypatch.setattr("jose.jwt.decode", mock_jwt_decode)
    
    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(MOCK_TOKEN_INVALID)
    assert exc_info.value.status_code == 401
