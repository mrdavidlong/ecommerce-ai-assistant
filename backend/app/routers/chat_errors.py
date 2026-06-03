import logging

from fastapi import HTTPException

logger = logging.getLogger(__name__)


def agent_error_response(exc: Exception) -> HTTPException:
    """Convert agent failures into API errors without hiding common LLM issues."""
    message = str(exc)
    normalized = message.lower()

    logger.exception("Chat agent failed")

    if "insufficient_quota" in normalized or "exceeded your current quota" in normalized:
        return HTTPException(
            status_code=503,
            detail=(
                "LLM provider quota exceeded: OpenAI returned insufficient_quota. "
                "Check the OpenAI project credits, billing limits, and OPENAI_API_KEY project."
            ),
        )

    if "rate limit" in normalized or "rate_limit" in normalized:
        return HTTPException(
            status_code=429,
            detail=(
                "LLM provider rate limit reached. Please retry shortly or check the "
                "OpenAI project rate limits."
            ),
        )

    return HTTPException(status_code=500, detail=f"Agent error: {message}")
