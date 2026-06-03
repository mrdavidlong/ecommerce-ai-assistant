import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

load_dotenv()

from app.db.base import Base  # noqa: E402
from app.db.seed import seed_database  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.models import order, order_item, product, user  # noqa: F401, E402
from app.routers.chat_v1 import router as chat_v1_router  # noqa: E402
from app.routers.chat_v2 import router as chat_v2_router  # noqa: E402
from app.routers.orders import router as orders_router  # noqa: E402
from app.routers.products import router as products_router  # noqa: E402
from app.routers.users import router as users_router  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        # Demo-only SQLite migration shim for existing local app.db files.
        # create_all() will not add columns to existing tables.
        cols = {c[1] for c in conn.execute(text("PRAGMA table_info(order_items)")).fetchall()}
        if "refunded" not in cols:
            conn.execute(
                text("ALTER TABLE order_items ADD COLUMN refunded BOOLEAN NOT NULL DEFAULT 0")
            )
            conn.commit()
        cols = {c[1] for c in conn.execute(text("PRAGMA table_info(order_items)")).fetchall()}
        if "refunded_quantity" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE order_items ADD COLUMN "
                    "refunded_quantity INTEGER NOT NULL DEFAULT 0"
                )
            )
            conn.commit()
    db = SessionLocal()
    try:
        seed_database(db)
        if os.getenv("OPENAI_API_KEY"):
            from app.agent.shared.rag import embed_products
            from app.models.product import Product as ProductModel

            # ChromaDB is in-memory in this demo, so rebuild the product index on startup.
            products = db.query(ProductModel).all()
            embed_products(products)
        else:
            print("[RAG] OPENAI_API_KEY not set — skipping product embedding")
    except Exception as e:
        db.rollback()
        print(f"Startup error: {e}")
    finally:
        db.close()
    yield


app = FastAPI(title="Ecommerce AI Assistant API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users_router)
app.include_router(products_router)
app.include_router(orders_router)
app.include_router(chat_v1_router, prefix="/v1")
app.include_router(chat_v2_router, prefix="/v2")
