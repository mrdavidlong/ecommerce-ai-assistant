from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.product import ProductRead
from app.services.product_service import get_all_products, get_product_by_id

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/", response_model=list[ProductRead])
def list_products(db: Session = Depends(get_db)):
    return get_all_products(db)


@router.get("/{product_id}", response_model=ProductRead)
def get_product(product_id: UUID, db: Session = Depends(get_db)):
    product = get_product_by_id(db, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product
