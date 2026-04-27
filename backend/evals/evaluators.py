"""
Custom evaluators for the ecommerce assistant eval suite.

- routing_accuracy: Did the supervisor send to the right specialist?
- tool_accuracy:    Did the specialist call the right tool first?

LangSmith built-in evaluators (faithfulness, helpfulness) are wired in run_eval.py.
"""

from langsmith.schemas import Example, Run


def routing_accuracy(run: Run, example: Example) -> dict:
    """Score 1 if agent_name matches expected_agent, 0 otherwise."""
    agent_used = (run.outputs or {}).get("agent_name", "")
    expected = (example.outputs or {}).get("expected_agent", "")
    return {"key": "routing_accuracy", "score": int(agent_used == expected)}


def tool_accuracy(run: Run, example: Example) -> dict:
    """Score 1 if the first non-supervisor step used the expected tool."""
    expected_tool = (example.outputs or {}).get("expected_tool")
    steps = (run.outputs or {}).get("steps", [])

    if expected_tool is None:
        # General queries — no tool call expected; penalise if a specialist tool was called
        specialist_steps = [s for s in steps if s.get("tool") != "supervisor"]
        return {"key": "tool_accuracy", "score": int(len(specialist_steps) == 0)}

    specialist_steps = [s for s in steps if s.get("tool") != "supervisor"]
    if not specialist_steps:
        return {"key": "tool_accuracy", "score": 0}

    first_tool = specialist_steps[0].get("tool", "")
    return {"key": "tool_accuracy", "score": int(first_tool == expected_tool)}
