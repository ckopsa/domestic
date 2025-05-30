from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class AuthenticatedUser(BaseModel):
    user_id: str
    username: str
    email: str = ""

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> AuthenticatedUser:
    """Extract user information from the token. This is a placeholder for real validation."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    # For simplicity, we're not validating the token against a real user database
    # Just returning a mock user based on the token content
    if not token:
        raise credentials_exception
    return AuthenticatedUser(user_id=token, username=token, email=f"{token}@example.com")
