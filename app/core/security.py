from typing import Annotated, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class AuthenticatedUser(BaseModel):
    user_id: str
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None

class UserInDB(AuthenticatedUser):
    hashed_password: str

# Fake user database
fake_users_db = {
    "johndoe": {
        "user_id": "johndoe_id",
        "username": "johndoe",
        "full_name": "John Doe",
        "email": "johndoe@example.com",
        "hashed_password": "fakehashedsecret",
        "disabled": False,
    },
    "alice": {
        "user_id": "alice_id",
        "username": "alice",
        "full_name": "Alice Wonderson",
        "email": "alice@example.com",
        "hashed_password": "fakehashedsecret2",
        "disabled": True,
    },
}

def get_user(username: str) -> Optional[UserInDB]:
    """Get user from the fake database."""
    if username in fake_users_db:
        user_dict = fake_users_db[username]
        return UserInDB(**user_dict)
    return None

def fake_hash_password(password: str) -> str:
    """Fake password hashing for demonstration purposes."""
    return "fakehashed" + password

def fake_decode_token(token: str) -> Optional[AuthenticatedUser]:
    """Fake token decoding for demonstration purposes."""
    return get_user(token)

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> AuthenticatedUser:
    """Extract user information from the token. This is a placeholder for real validation."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    user = fake_decode_token(token)
    if not user:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: Annotated[AuthenticatedUser, Depends(get_current_user)]) -> AuthenticatedUser:
    """Check if the current user is active."""
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
