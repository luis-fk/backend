import logging

from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

from plants.api.chatbot.nodes import (
    call_agent,
    route_picker,
    router,
    tool_response,
    tools_agent,
    update_memory,
    wrap_up,
)
from plants.api.chatbot.schemas import SquadState
from plants.api.chatbot.tools import web_search


def build_graph() -> CompiledStateGraph[SquadState]:
    logging.info("Building LLM graph")

    workflow = StateGraph(SquadState)

    workflow.set_entry_point("router")

    workflow.add_node("agent", call_agent)
    workflow.add_node("router", router)
    workflow.add_node("tools_agent", tools_agent)
    workflow.add_node("tool_executor", ToolNode([web_search]))
    workflow.add_node("tool_response", tool_response)
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
    workflow.add_edge("tools_agent", "tool_executor")
    workflow.add_edge("tool_executor", "tool_response")
    workflow.add_edge("tool_response", "update_memory")

    workflow.set_finish_point("wrap_up")

    logging.info("LLM graph built")

    return workflow.compile()
