from uuid import UUID

from sqlalchemy.orm import Session

from app.models.product import Product


def get_all_products(db: Session) -> list[Product]:
    return db.query(Product).all()


def get_product_by_id(db: Session, product_id: UUID) -> Product | None:
    return db.query(Product).filter(Product.id == product_id).first()
