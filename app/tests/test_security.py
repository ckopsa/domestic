import pytest
import sys
import os
from unittest.mock import patch, MagicMock
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient
from jose import jwt, JWTError
import time

# Add the project root to sys.path to ensure 'app' module can be found
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from app.core.security import get_current_user, get_keycloak_public_keys, AuthenticatedUser, get_current_active_user
from app.config import KEYCLOAK_SERVER_URL, KEYCLOAK_REALM, KEYCLOAK_API_CLIENT_ID
from app.main import app

# Test client
client = TestClient(app)

# Mock data for testing
MOCK_TOKEN_VALID = jwt.encode(
    {
        "sub": "test_user_id",
        "preferred_username": "test_user",
        "email": "test@example.com",
        "iss": f"{KEYCLOAK_SERVER_URL}realms/{KEYCLOAK_REALM}",
        "aud": "account",
        "exp": int(time.time()) + 3600
    },
    "secret",  # This would be replaced with a proper key in real scenarios
    algorithm="HS256",  # Using HS256 for simplicity in test
    headers={"kid": "mock_kid"}
)

MOCK_TOKEN_EXPIRED = jwt.encode(
    {
        "sub": "test_user_id",
        "preferred_username": "test_user",
        "email": "test@example.com",
        "iss": f"{KEYCLOAK_SERVER_URL}realms/{KEYCLOAK_REALM}",
        "aud": "account",
        "exp": int(time.time()) - 3600
    },
    "secret",
    algorithm="HS256",
    headers={"kid": "mock_kid"}
)

MOCK_TOKEN_WRONG_ISSUER = jwt.encode(
    {
        "sub": "test_user_id",
        "preferred_username": "test_user",
        "email": "test@example.com",
        "iss": "wrong_issuer",
        "aud": "account"
    },
    "secret",
    algorithm="HS256",
    headers={"kid": "mock_kid"}
)

MOCK_TOKEN_WRONG_AUDIENCE = jwt.encode(
    {
        "sub": "test_user_id",
        "preferred_username": "test_user",
        "email": "test@example.com",
        "iss": f"{KEYCLOAK_SERVER_URL}realms/{KEYCLOAK_REALM}",
        "aud": "wrong_audience"
    },
    "secret",
    algorithm="HS256",
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
                # Using valid base64url encoded values for modulus and exponent with correct padding
                "n": "n4EPtA7CPjjqS6Lsro5xCvbVWkJdyJ6aBk7c8v5v5o-G8a5e5I-2fA1o2B0sV9fP1eLmx5Wv4v8i1z-3o3v4u5v6w7x8y9z-0A1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q7R8S9T0U1V2W3X4Y5Z6a7b8c9d0e1f2g3h4i5j6k7l8m9n0o1p2q3r4s5t6u7v8w9x0y1z2A3B4C5D6E7F8G9H0I1J2K3L4M5N6O7P8Q9R0S1T2U3V4W5X6Y7Z8a9b0c1d2e3f4g5h6i7j8k9l0m1n2o3p4q5r6s7t8u9v0w1x2y3z4AA",
                "e": "AQAB"
            }
        ]
    }

# Mock jwt.decode to return predefined payloads based on token
def mock_jwt_decode(token, key, algorithms, audience, issuer):
    if token == MOCK_TOKEN_VALID:
        return {
            "sub": "test_user_id",
            "preferred_username": "test_user",
            "email": "test@example.com",
            "iss": f"{KEYCLOAK_SERVER_URL}realms/{KEYCLOAK_REALM}",
            "aud": "account",
            "exp": int(time.time()) + 3600
        }
    elif token == MOCK_TOKEN_EXPIRED:
        return {
            "sub": "test_user_id",
            "preferred_username": "test_user",
            "email": "test@example.com",
            "iss": f"{KEYCLOAK_SERVER_URL}realms/{KEYCLOAK_REALM}",
            "aud": "account",
            "exp": int(time.time()) - 3600
        }
    elif token == MOCK_TOKEN_WRONG_ISSUER:
        return {
            "sub": "test_user_id",
            "preferred_username": "test_user",
            "email": "test@example.com",
            "iss": "wrong_issuer",
            "aud": "account"
        }
    elif token == MOCK_TOKEN_WRONG_AUDIENCE:
        return {
            "sub": "test_user_id",
            "preferred_username": "test_user",
            "email": "test@example.com",
            "iss": f"{KEYCLOAK_SERVER_URL}realms/{KEYCLOAK_REALM}",
            "aud": "wrong_audience"
        }
    raise JWTError("Invalid token")

@pytest.mark.asyncio
async def test_get_current_user_valid_token(monkeypatch):
    # Arrange
    monkeypatch.setattr("app.core.security.get_keycloak_public_keys", mock_get_keycloak_public_keys)
    monkeypatch.setattr("jose.jwt.decode", mock_jwt_decode)
    
    # Act
    user = await get_current_user(MagicMock(cookies={"access_token": MOCK_TOKEN_VALID}))
    
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
        await get_current_user(MagicMock(cookies={"access_token": MOCK_TOKEN_INVALID}))
    assert exc_info.value.status_code == 401

@pytest.mark.asyncio
async def test_get_current_user_expired_token(monkeypatch):
    # Arrange
    monkeypatch.setattr("app.core.security.get_keycloak_public_keys", mock_get_keycloak_public_keys)
    monkeypatch.setattr("jose.jwt.decode", mock_jwt_decode)
    
    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(MagicMock(cookies={"access_token": MOCK_TOKEN_EXPIRED}))
    assert exc_info.value.status_code == 401

@pytest.mark.asyncio
async def test_get_current_user_wrong_issuer(monkeypatch):
    # Arrange
    monkeypatch.setattr("app.core.security.get_keycloak_public_keys", mock_get_keycloak_public_keys)
    monkeypatch.setattr("jose.jwt.decode", mock_jwt_decode)
    
    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(MagicMock(cookies={"access_token": MOCK_TOKEN_WRONG_ISSUER}))
    assert exc_info.value.status_code == 401

@pytest.mark.asyncio
async def test_get_current_user_wrong_audience(monkeypatch):
    # Arrange
    monkeypatch.setattr("app.core.security.get_keycloak_public_keys", mock_get_keycloak_public_keys)
    monkeypatch.setattr("jose.jwt.decode", mock_jwt_decode)
    
    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(MagicMock(cookies={"access_token": MOCK_TOKEN_WRONG_AUDIENCE}))
    assert exc_info.value.status_code == 401

@pytest.mark.asyncio
async def test_get_current_user_no_token(monkeypatch):
    # Arrange
    monkeypatch.setattr("app.core.security.get_keycloak_public_keys", mock_get_keycloak_public_keys)
    monkeypatch.setattr("jose.jwt.decode", mock_jwt_decode)
    
    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(MagicMock(cookies={}))
    assert exc_info.value.status_code == 401

@pytest.mark.asyncio
async def test_get_current_active_user_disabled(monkeypatch):
    # Arrange
    disabled_user = AuthenticatedUser(
        user_id="test_user_id",
        username="test_user",
        email="test@example.com",
        disabled=True
    )
    
    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await get_current_active_user(disabled_user)
    assert exc_info.value.status_code == 400
    assert "Inactive user" in str(exc_info.value.detail)

@pytest.mark.asyncio
async def test_get_current_active_user_active(monkeypatch):
    # Arrange
    active_user = AuthenticatedUser(
        user_id="test_user_id",
        username="test_user",
        email="test@example.com",
        disabled=False
    )
    
    # Act
    result = await get_current_active_user(active_user)
    
    # Assert
    assert result == active_user

# Test protected routes for authentication
def test_protected_route_without_auth():
    # Act
    response = client.get("/my-workflows")
    
    # Assert
    assert response.status_code in [401, 403]

def test_protected_route_api_without_auth():
    # Act
    response = client.get("/api/my-workflows")
    
    # Assert
    assert response.status_code in [401, 403]

# Mocking Keycloak login and callback
@pytest.mark.asyncio
async def test_login_redirect(monkeypatch):
    # Arrange
    mock_response = MagicMock()
    monkeypatch.setattr("requests.post", mock_response)
    
    # Act
    response = client.get("/login", follow_redirects=False)
    
    # Assert
    assert response.status_code == 307  # Redirect status code
    assert "realms" in response.headers.get('location', '')
    assert "openid-connect/auth" in response.headers.get('location', '')

@pytest.mark.asyncio
async def test_callback_with_valid_code(monkeypatch):
    # Arrange
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "mock_access_token",
        "expires_in": 3600
    }
    monkeypatch.setattr("requests.post", mock_response)
    
    # Act
    response = client.get("/callback", params={"code": "valid_code", "state": "/"}, follow_redirects=False)
    
    # Assert
    assert response.status_code == 303  # Redirect after successful token exchange
    assert "access_token" in response.cookies

@pytest.mark.asyncio
async def test_callback_with_invalid_code(monkeypatch):
    # Arrange
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Invalid code"
    monkeypatch.setattr("requests.post", mock_response)
    
    # Act
    response = client.get("/callback?code=invalid_code")
    
    # Assert
    assert response.status_code == 400

@pytest.mark.asyncio
async def test_logout(monkeypatch):
    # Act
    response = client.get("/logout", follow_redirects=False)
    
    # Assert
    assert response.status_code == 303  # Redirect to Keycloak logout
    assert "access_token" not in response.cookies or response.cookies.get("access_token", "") == ""
    assert "openid-connect/logout" in response.headers.get('location', '')
