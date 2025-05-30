from typing import Annotated
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

def fake_decode_token(token: str) -> AuthenticatedUser:
    """Fake token decoding for demonstration purposes."""
    return AuthenticatedUser(
        user_id=token,
        username=token + "_decoded",
        email=f"{token}@example.com",
        full_name=f"{token.capitalize()} User"
    )

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> AuthenticatedUser:
    """Extract user information from the token. This is a placeholder for real validation."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception
    user = fake_decode_token(token)
    return user
