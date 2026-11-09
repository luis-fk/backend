import logging
import threading
from typing import Any, cast

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import close_old_connections
from langgraph.graph.state import CompiledStateGraph

from political_culture.api.chatbot.graph import build_graph
from political_culture.api.chatbot.schemas import SquadState
from political_culture.api.chatbot.utils import singleton, wrap_up_get_response
from political_culture.models import UserMemory

logger = logging.getLogger(__name__)


@singleton
class LLM:
    def __init__(self) -> None:
        self.graph: CompiledStateGraph[SquadState, None, Any, Any] | None = None

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

        try:
            message = self._answer(text, user_id)
        except Exception:
            logger.exception(f"Error in background processing for user {user_id}")
            # The page waits for a message on the socket after each question.
            message = {"failed": True}

        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f"chat_{user_id}", {"type": "chat.message", "message": message}
            )

    def _answer(self, text: str, user_id: int) -> dict[str, Any]:
        if not self.graph:
            raise RuntimeError("No LLM graph available")

        user_memory = (
            UserMemory.objects.filter(user_id=user_id)
            .values_list("memory", flat=True)
            .first()
        )
        self.graph.invoke(
            input=cast(
                SquadState,
                {"input": text, "memory": user_memory, "user_id": user_id},
            ),
            config={"recursion_limit": 50},
        )
        logger.info(f"Message processed for user {user_id}")
        return wrap_up_get_response(user_id)
