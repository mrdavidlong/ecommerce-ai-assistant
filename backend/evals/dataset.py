"""
Push the eval dataset to LangSmith (idempotent — safe to run multiple times).

Usage:
    cd backend && uv run python -m evals.dataset
"""

from dotenv import load_dotenv

load_dotenv()

from langsmith import Client  # noqa: E402

DATASET_NAME = "ecommerce-assistant-eval"

EXAMPLES = [
    # Product Search (7)
    {"input": "find a webcam", "expected_tool": "search_products", "expected_agent": "product"},
    {
        "input": "what laptops do you have?",
        "expected_tool": "search_products",
        "expected_agent": "product",
    },
    {
        "input": "I need something for video calls",
        "expected_tool": "search_products",
        "expected_agent": "product",
    },
    {
        "input": "show me Bluetooth trackers",
        "expected_tool": "search_products",
        "expected_agent": "product",
    },
    {
        "input": "what keyboards are available?",
        "expected_tool": "search_products",
        "expected_agent": "product",
    },
    {
        "input": "do you have any USB hubs?",
        "expected_tool": "search_products",
        "expected_agent": "product",
    },
    {
        "input": "I'm looking for desk accessories",
        "expected_tool": "search_products",
        "expected_agent": "product",
    },
    # Product Compare (2)
    {
        "input": "compare Apple AirTag and Tile Mate",
        "expected_tool": "compare_products",
        "expected_agent": "product",
    },
    {
        "input": "AirTag vs Tile Mate — what's the difference?",
        "expected_tool": "compare_products",
        "expected_agent": "product",
    },
    # Account / Balance (4)
    {
        "input": "what's my balance?",
        "expected_tool": "get_user_balance",
        "expected_agent": "account",
    },
    {
        "input": "how much money do I have?",
        "expected_tool": "get_user_balance",
        "expected_agent": "account",
    },
    {
        "input": "show me my order history",
        "expected_tool": "get_order_history",
        "expected_agent": "account",
    },
    {
        "input": "what did I buy last time?",
        "expected_tool": "get_order_history",
        "expected_agent": "account",
    },
    # Budget Shopping (2)
    {
        "input": "what can I afford?",
        "expected_tool": "get_affordable_products",
        "expected_agent": "product",
    },
    {
        "input": "show me products within my budget",
        "expected_tool": "get_affordable_products",
        "expected_agent": "product",
    },
    # Refunds (2) — agent calls get_order_history first to see items, then process_item_refund
    {
        "input": "I want to refund an item from my last order",
        "expected_tool": "get_order_history",
        "expected_agent": "account",
    },
    {
        "input": "can I get a refund on something I bought?",
        "expected_tool": "get_order_history",
        "expected_agent": "account",
    },
    # Cart Management (1)
    {
        "input": "remove the mouse from my cart",
        "expected_tool": "remove_from_cart",
        "expected_agent": "cart",
    },
    # General / Chitchat (3)
    {"input": "hello", "expected_tool": None, "expected_agent": "general"},
    {"input": "what are your store hours?", "expected_tool": None, "expected_agent": "general"},
    {"input": "thank you!", "expected_tool": None, "expected_agent": "general"},
]


def push_dataset() -> str:
    client = Client()

    existing = [d for d in client.list_datasets() if d.name == DATASET_NAME]
    if existing:
        client.delete_dataset(dataset_id=existing[0].id)
        print(f"Deleted existing dataset: {DATASET_NAME}")

    dataset = client.create_dataset(
        DATASET_NAME,
        description="21-query routing + tool accuracy eval for ecommerce AI assistant",
    )
    client.create_examples(
        inputs=[{"message": ex["input"]} for ex in EXAMPLES],
        outputs=[
            {"expected_tool": ex["expected_tool"], "expected_agent": ex["expected_agent"]}
            for ex in EXAMPLES
        ],
        dataset_id=dataset.id,
    )
    print(f"Created dataset '{DATASET_NAME}' with {len(EXAMPLES)} examples.")
    return str(dataset.id)


if __name__ == "__main__":
    push_dataset()
