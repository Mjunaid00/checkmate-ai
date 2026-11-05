from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from database import get_db
from core.security import decode_token
from models.user import UserOut

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme), db = Depends(get_db)):
    """
    Dependency to extract and validate the JWT token.
    Returns the authenticated user document.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # Fetch user from DB
    user_data = await db["users"].find_one({"email": email})
    if user_data is None:
        raise credentials_exception
    # A deactivated account keeps a valid token until it expires: refuse it here too.
    if user_data.get("is_active") is False:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account has been deactivated")

    # Map _id to id for UserOut compatibility
    user_data["id"] = str(user_data["_id"])
    return user_data


# Roles with teacher privileges. An admin can do everything a teacher can (acting as the
# teacher of the classes/assignments it creates) on top of the admin-only endpoints.
# Student-only endpoints (submit, enrol, take quizzes) stay student-only.
TEACHER_ROLES = ("teacher", "admin")


def is_teacher_like(user) -> bool:
    return (user or {}).get("role") in TEACHER_ROLES


async def get_current_teacher(current_user: dict = Depends(get_current_user)):
    """
    Dependency to ensure the current authenticated user has teacher privileges
    (role 'teacher' or 'admin').
    """
    if current_user.get("role") not in TEACHER_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Teacher role required",
        )
    return current_user

async def get_current_student(current_user: dict = Depends(get_current_user)):
    """
    Dependency to ensure the current authenticated user has the 'student' role.
    """
    if current_user.get("role") != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Student role required",
        )
    return current_user


async def get_current_admin(current_user: dict = Depends(get_current_user)):
    """
    Dependency to ensure the current authenticated user has the 'admin' role.
    """
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Admin role required",
        )
    return current_user
