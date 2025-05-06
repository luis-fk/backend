import logging
from typing import cast

from dotenv import load_dotenv
from langgraph.graph.state import CompiledStateGraph

from political_culture.api.chatbot.graph import build_graph
from political_culture.api.chatbot.utils import singleton
from political_culture.models import UserMemory

load_dotenv()

logger = logging.getLogger(__name__)


@singleton
class LLM:
    def __init__(self) -> None:
        self.graph: CompiledStateGraph | None = None

        logger.info("Building schema")

        self.graph = build_graph()

        logger.info("Schema built successfully")

    def process_text(self, text: str, user_id: int) -> str:
        logger.info(f"Processing message for user {user_id}")

        user_memory = (
            UserMemory.objects.filter(user_id=user_id)
            .values_list("memory", flat=True)
            .first()
        )

        if self.graph:
            result = self.graph.invoke(
                input={
                    "input": text,
                    "memory": user_memory,
                    "user_id": user_id,
                }
            )

            logger.info(f"Message processed for user {user_id}")

            return cast(str, result["response"])
        else:
            return "An error occurred while processing the message."
