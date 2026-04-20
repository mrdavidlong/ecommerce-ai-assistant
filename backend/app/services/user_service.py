from uuid import UUID

from sqlalchemy.orm import Session

from app.models.user import User


def get_all_users(db: Session) -> list[User]:
    return db.query(User).all()


def get_user_by_id(db: Session, user_id: UUID) -> User | None:
    return db.query(User).filter(User.id == user_id).first()
