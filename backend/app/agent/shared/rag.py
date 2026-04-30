import logging
import os

import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

# Lazy in-memory Chroma collection; process restart means the index is rebuilt.
_collection: chromadb.Collection | None = None


def _get_collection() -> chromadb.Collection:
    global _collection
    if _collection is None:
        client = chromadb.Client()
        embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        ef = OpenAIEmbeddingFunction(
            api_key=os.environ["OPENAI_API_KEY"],
            model_name=embedding_model,
        )
        _collection = client.get_or_create_collection(
            name="products",
            embedding_function=ef,  # type: ignore[arg-type] — ChromaDB EmbeddingFunction[Documents] vs [list[str]] mismatch
        )
    return _collection


def embed_products(products: list) -> None:
    collection = _get_collection()
    if not products:
        return
    collection.upsert(
        ids=[str(p.id) for p in products],
        documents=[f"{p.name}. {p.description}" for p in products],
        metadatas=[
            {
                "name": p.name,
                "price": p.price,
                "product_id": str(p.id),
            }
            for p in products
        ],
    )
    logging.getLogger(__name__).info("Embedded %d products into ChromaDB", len(products))


def search_products_rag(query: str, n: int = 3) -> list[dict]:
    collection = _get_collection()
    results = collection.query(query_texts=[query], n_results=n)
    if not results["ids"] or not results["ids"][0]:
        return []
    metadatas = (results["metadatas"] or [[]])[0]
    documents = (results["documents"] or [[]])[0]
    return [
        {
            "product_id": meta["product_id"],
            "name": meta["name"],
            "price": meta["price"],
            "document": doc,
        }
        for meta, doc in zip(metadatas, documents)
    ]
