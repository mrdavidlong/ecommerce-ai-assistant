from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.user import UserRead
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=list[UserRead])
def list_users(db: Session = Depends(get_db)):
    return user_service.get_all_users(db)


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: UUID, db: Session = Depends(get_db)):
    user = user_service.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user
