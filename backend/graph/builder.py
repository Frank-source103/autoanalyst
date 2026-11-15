"""Graph construction and compilation using LangGraph 0.2+ and AsyncSqliteSaver."""

from typing import Optional
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph

from backend.app.core.config import settings
from backend.graph.edges import route_after_evaluate, route_after_generate_code
from backend.graph.nodes import (
    evaluate_node,
    execute_node,
    generate_code_node,
    human_checkpoint_node,
    plan_node,
    profile_node,
    self_correct_node,
    synthesize_report_node,
)
from backend.graph.state import AgentState


def calculate_recursion_limit(
    max_steps: int = settings.MAX_PLAN_STEPS,
    max_retries: int = settings.MAX_RETRIES_PER_STEP,
    nodes_per_attempt: int = 4,
    overhead: int = 25,
) -> int:
    """Dynamically derive safe recursion limit: max_steps * (1 + max_retries) * nodes_per_attempt + overhead."""
    return (max_steps * (1 + max_retries) * nodes_per_attempt) + overhead


def build_graph(checkpointer: Optional[AsyncSqliteSaver] = None):
    """Construct and compile the AutoAnalyst StateGraph."""
    workflow = StateGraph(AgentState)

    # Register all nodes
    workflow.add_node("plan", plan_node)
    workflow.add_node("profile", profile_node)
    workflow.add_node("generate_code", generate_code_node)
    workflow.add_node("human_checkpoint", human_checkpoint_node)
    workflow.add_node("execute", execute_node)
    workflow.add_node("evaluate", evaluate_node)
    workflow.add_node("self_correct", self_correct_node)
    workflow.add_node("synthesize_report", synthesize_report_node)

    # Add edges
    workflow.add_edge(START, "plan")
    workflow.add_edge("plan", "profile")
    workflow.add_edge("profile", "generate_code")

    workflow.add_conditional_edges(
        "generate_code",
        route_after_generate_code,
        {
            "human_checkpoint": "human_checkpoint",
            "synthesize_report": "synthesize_report",
        },
    )

    workflow.add_edge("human_checkpoint", "execute")
    workflow.add_edge("execute", "evaluate")

    workflow.add_conditional_edges(
        "evaluate",
        route_after_evaluate,
        {
            "generate_code": "generate_code",
            "self_correct": "self_correct",
            "synthesize_report": "synthesize_report",
        },
    )

    workflow.add_edge("self_correct", "human_checkpoint")
    workflow.add_edge("synthesize_report", END)

    return workflow.compile(checkpointer=checkpointer)
