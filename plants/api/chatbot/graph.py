import logging

from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

from plants.api.chatbot.nodes import (
    call_agent,
    route_picker,
    router,
    tools_agent,
    update_memory,
    wrap_up,
)
from plants.api.chatbot.schemas import SquadState


def build_graph() -> CompiledStateGraph:
    logging.info("Building LLM graph")

    workflow = StateGraph(SquadState)

    workflow.set_entry_point("router")

    workflow.add_node("agent", call_agent)
    workflow.add_node("router", router)
    workflow.add_node("tools_agent", tools_agent)
    workflow.add_node("update_memory", update_memory)
    workflow.add_node("wrap_up", wrap_up)

    workflow.add_conditional_edges(
        "router",
        route_picker,
        {
            "continue": "agent",
            "tools_agent": "tools_agent",
            "update_memory": "update_memory",
        },
    )

    workflow.add_edge("update_memory", "wrap_up")
    workflow.add_edge("agent", "update_memory")
    workflow.add_edge("tools_agent", "update_memory")

    workflow.set_finish_point("wrap_up")

    logging.info("LLM graph built")

    return workflow.compile()
