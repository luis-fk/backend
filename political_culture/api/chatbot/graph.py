# %%
import logging

from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

from political_culture.api.chatbot import nodes
from political_culture.api.chatbot.schemas import SquadState


def build_graph() -> CompiledStateGraph:
    logging.info("Building LLM graph")

    graph_builder = StateGraph(SquadState)

    graph_builder.set_entry_point("router")

    graph_builder.add_node("router", nodes.router)
    graph_builder.add_node("general_chat", nodes.general_chat)
    graph_builder.add_node("text_info_extraction", nodes.text_info_extraction)
    graph_builder.add_node("word_analysis", nodes.word_analysis)
    graph_builder.add_node("text_analysis", nodes.text_analysis)
    graph_builder.add_node("ideology_analysis", nodes.text_ideology_analysis)
    graph_builder.add_node("wrap_up", nodes.wrap_up)

    graph_builder.add_conditional_edges(
        "router",
        nodes.route_picker,
        {
            "chat": "general_chat",
            "analysis": "text_info_extraction",
        },
    )

    graph_builder.add_edge("text_info_extraction", "word_analysis")
    graph_builder.add_edge("word_analysis", "text_analysis")
    graph_builder.add_edge("text_analysis", "ideology_analysis")
    graph_builder.add_edge("ideology_analysis", "wrap_up")

    graph_builder.add_edge("general_chat", "wrap_up")

    graph_builder.set_finish_point("wrap_up")

    logging.info("LLM graph built")

    return graph_builder.compile()
