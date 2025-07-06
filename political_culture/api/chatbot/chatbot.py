import logging
import threading

from dotenv import load_dotenv
from langgraph.graph.state import CompiledStateGraph

from political_culture.api.chatbot.graph import build_graph
from political_culture.api.chatbot.utils import singleton
from political_culture.models import UserMemory
from django.db import close_old_connections
load_dotenv()

logger = logging.getLogger(__name__)


@singleton
class LLM:
    def __init__(self) -> None:
        self.graph: CompiledStateGraph | None = None

        logger.info("Building schema")

        self.graph = build_graph()

        logger.info("Schema built successfully")

    def process_text(self, text: str, user_id: int) -> None:
        threading.Thread(
            target=self._background_process,
            args=(text, user_id),
            daemon=True,
        ).start()

        logger.info(f"Received request and spawned new thread for user {user_id}")

        return

    def _background_process(self, text: str, user_id: int) -> None:
        close_old_connections()
        logger.info(f"Processing message for user {user_id}")

        user_memory = (
            UserMemory.objects.filter(user_id=user_id)
            .values_list("memory", flat=True)
            .first()
        )

        if not self.graph:
            logger.error(f"No LLM graph available for user {user_id}")
            return

        try:
            self.graph.invoke(
                input={"input": text, "memory": user_memory, "user_id": user_id},
                config={"recursion_limit": 50},
            )
            logger.info(f"Message processed for user {user_id}")

        except Exception:
            logger.exception(f"Error in background processing for user {user_id}")
