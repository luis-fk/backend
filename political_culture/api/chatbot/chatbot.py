import logging

from dotenv import load_dotenv
from langchain_core.messages import (
    HumanMessage,
)
from langgraph.graph.state import CompiledStateGraph

from political_culture.api.chatbot.graph import build_graph

load_dotenv()

logger = logging.getLogger(__name__)


class LLM:
    def __init__(self) -> None:
        self.graph: CompiledStateGraph | None = None

    def setup(self) -> None:
        logger.info("Building schema")

        self.graph = build_graph()

        logger.info("Schema built successfully")

    def process_text(self, text: str, user_id: int) -> bool:
        logger.info(f"Processing message for user {user_id}")

        if self.graph:
            self.graph.invoke(
                input={
                    "text": [HumanMessage(content=text)],
                    "user_id": user_id,
                }
            )
        else:
            return False

        logger.info(f"Message processed for user {user_id}")
        return True
