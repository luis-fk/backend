# %%
import logging

from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

from political_culture.api.chatbot import nodes
from political_culture.api.chatbot.schemas import SquadState


def build_graph() -> CompiledStateGraph:
    logging.info("Building LLM graph")

    workflow = StateGraph(SquadState)

    workflow.set_entry_point("text_info_extraction")

    workflow.add_node("text_info_extraction", nodes.text_info_extraction)

    workflow.set_finish_point("text_info_extraction")

    logging.info("LLM graph built")

    return workflow.compile()
