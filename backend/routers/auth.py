import re

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from datetime import datetime

from bson import ObjectId
from database import get_db
from core.security import hash_password, verify_password, create_access_token
from models.user import UserCreate, UserLogin, UserOut, TokenResponse, UserInDB, ProfileUpdate, PasswordChange
from .deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

# Names: letters/digits/underscore only, and must contain at least 3 letters.
NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")


def _validate_name(name: str) -> str:
    cleaned = (name or "").strip()
    if not NAME_RE.fullmatch(cleaned):
        raise HTTPException(
            status_code=400,
            detail="Name may only contain letters, numbers, and underscore (_).",
        )
    letter_count = sum(1 for ch in cleaned if ch.isalpha())
    if letter_count < 3:
        raise HTTPException(
            status_code=400,
            detail="Name must contain at least 3 letters.",
        )
    return cleaned


@router.post("/register", response_model=TokenResponse)
async def register(user_in: UserCreate, db=Depends(get_db)):
    """
    Register a new user (Teacher or Student).
    """
    try:
        # Check if user already exists
        if db is None:
            raise HTTPException(status_code=500, detail="Database not initialized")

        # Public register is for students/teachers only — admin accounts
        # must be created by another admin (or via the bootstrap env vars).
        if user_in.role == "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin accounts can only be created by another admin.",
            )

        # Name format check shared with admin/create user.
        user_in.name = _validate_name(user_in.name)

        existing_user = await db["users"].find_one({"email": user_in.email})
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        # Hash password and prepare user data
        hashed_pwd = hash_password(user_in.password)
        
        # Pydantic v2 use model_dump, fallback to dict()
        user_dict = user_in.model_dump() if hasattr(user_in, "model_dump") else user_in.dict()
        user_dict.pop("password")
        
        user_record = UserInDB(
            **user_dict,
            hashed_password=hashed_pwd,
            created_at=datetime.utcnow(),
            is_active=True
        )

        # Insert into MongoDB
        # Pydantic v2 use model_dump, fallback to dict()
        record_dict = user_record.model_dump() if hasattr(user_record, "model_dump") else user_record.dict()
        result = await db["users"].insert_one(record_dict)
        
        # Generate token
        access_token = create_access_token(data={"sub": user_in.email})
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "role": user_in.role,
            "name": user_in.name
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR IN REGISTER: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db=Depends(get_db)):
    """
    Login with username (email) and password to get a JWT token.
    Using OAuth2PasswordRequestForm for standard compatibility with Swagger docs.
    """
    user_data = await db["users"].find_one({"email": form_data.username})
    
    if not user_data or not verify_password(form_data.password, user_data["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user_data.get("is_active", True) is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been disabled. Contact an administrator.",
        )

    access_token = create_access_token(data={"sub": user_data["email"]})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user_data["role"],
        "name": user_data["name"]
    }


@router.get("/me", response_model=UserOut)
async def get_me(current_user=Depends(get_current_user)):
    """
    Get current logged-in user information.
    """
    return current_user


@router.patch("/profile", response_model=UserOut)
async def update_profile(
    profile_in: ProfileUpdate,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """Update the current user's profile details."""
    updates = {}
    if profile_in.name is not None:
        updates["name"] = profile_in.name.strip()
    if profile_in.bio is not None:
        updates["bio"] = profile_in.bio.strip()
    if profile_in.phone is not None:
        updates["phone"] = profile_in.phone.strip()
    if profile_in.institution is not None:
        updates["institution"] = profile_in.institution.strip()

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    await db["users"].update_one(
        {"_id": ObjectId(current_user["id"])},
        {"$set": updates},
    )

    updated = await db["users"].find_one({"_id": ObjectId(current_user["id"])})
    updated["id"] = str(updated["_id"])
    return updated


@router.post("/change-password")
async def change_password(
    payload: PasswordChange,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """Change the current user's password."""
    if not verify_password(payload.current_password, current_user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    new_hash = hash_password(payload.new_password)
    await db["users"].update_one(
        {"_id": ObjectId(current_user["id"])},
        {"$set": {"hashed_password": new_hash}},
    )
    return {"detail": "Password updated successfully"}


@router.delete("/account")
async def delete_account(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """Permanently delete the current user's account and associated data."""
    user_id = current_user["id"]

    # Clean up user's data based on role (admins own classes/assignments like teachers)
    if current_user["role"] in ("teacher", "admin"):
        # Get teacher's assignments
        assignments = await db["assignments"].find({"teacher_id": user_id}).to_list(length=None)
        assignment_ids = [str(a["_id"]) for a in assignments]
        # Delete submissions under those assignments
        if assignment_ids:
            await db["submissions"].delete_many({"assignment_id": {"$in": assignment_ids}})
        await db["assignments"].delete_many({"teacher_id": user_id})
        await db["classes"].delete_many({"teacher_id": user_id})
    else:
        await db["submissions"].delete_many({"student_id": user_id})
        await db["enrollments"].delete_many({"student_id": user_id})

    # Delete the user
    await db["users"].delete_one({"_id": ObjectId(user_id)})
    return {"detail": "Account deleted successfully"}
