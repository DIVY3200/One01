from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from typing import Optional
import uuid

from db.database import get_db
from db.models import User, UserPreferences
from utils.auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter()

class UserRegister(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str

class PreferencesUpdate(BaseModel):
    nickname: str
    ai_teacher_name: str
    ai_gender: str
    teaching_style: str

@router.post("/register", response_model=Token)
async def register(user_data: UserRegister, db: AsyncSession = Depends(get_db)):
    # Check if user exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="An account with this email already exists.")
    
    # Create user
    new_user = User(
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        full_name=user_data.full_name
    )
    db.add(new_user)
    await db.flush()
    
    # Create default preferences
    prefs = UserPreferences(user_id=new_user.id)
    db.add(prefs)
    
    await db.commit()
    
    # Return token
    access_token = create_access_token(data={"sub": str(new_user.id)})
    return {"access_token": access_token, "token_type": "bearer"}

from fastapi.security import OAuth2PasswordRequestForm
@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account found with this email.",
        )
    
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password. Please try again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/preferences")
async def save_preferences(
    prefs_data: PreferencesUpdate, 
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(UserPreferences).where(UserPreferences.user_id == current_user.id))
    prefs = result.scalar_one_or_none()
    
    if not prefs:
        prefs = UserPreferences(user_id=current_user.id)
        db.add(prefs)
    
    prefs.nickname = prefs_data.nickname
    prefs.ai_teacher_name = prefs_data.ai_teacher_name
    prefs.ai_gender = prefs_data.ai_gender
    prefs.teaching_style = prefs_data.teaching_style
    
    current_user.onboarding_completed = True
    
    await db.commit()
    return {"message": "Preferences saved"}

@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "full_name": current_user.full_name,
        "onboarding_completed": current_user.onboarding_completed,
        "preferences": {
            "nickname": current_user.preferences.nickname if current_user.preferences else "buddy",
            "ai_teacher_name": current_user.preferences.ai_teacher_name if current_user.preferences else "Lead",
            "ai_gender": current_user.preferences.ai_gender if current_user.preferences else "neutral",
            "teaching_style": current_user.preferences.teaching_style if current_user.preferences else "mentor",
        } if current_user.preferences else None
    }
