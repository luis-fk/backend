import logging
from typing import Any, cast

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
)
from langgraph.graph.state import CompiledStateGraph

from plants.api.chatbot.graph import build_graph
from plants.api.chatbot.schemas import SquadState
from plants.api.messages.serializers import ChatHistorySerializer
from plants.models import ChatHistory, UserMemory

logger = logging.getLogger(__name__)


class LLM:
    def __init__(self) -> None:
        self.graph: CompiledStateGraph[SquadState, None, Any, Any] | None = None
        self.chat_history: list[BaseMessage] | None = None

    def setup(self) -> None:
        logger.info("Building schema")

        self.graph = build_graph()

        logger.info("Schema built successfully")

    def process_message(
        self, message: str, user_id: int
    ) -> ChatHistorySerializer | None:
        logger.info(f"Processing message for user {user_id}")

        user_memory = (
            UserMemory.objects.filter(user_id=user_id)
            .values_list("memory", flat=True)
            .first()
        )

        newest_first = ChatHistory.objects.filter(user_id=user_id).order_by("-id")
        human_messages = list(newest_first.filter(role="human")[:5])[::-1]
        ai_messages = list(newest_first.filter(role="ai")[:5])[::-1]

        chat_history: list[BaseMessage] = []

        for human, ai in zip(human_messages, ai_messages):
            chat_history.append(HumanMessage(content=human.message))
            chat_history.append(AIMessage(content=ai.message))

        if self.graph:
            self.graph.invoke(
                input=cast(
                    SquadState,
                    {
                        "messages": chat_history + [HumanMessage(content=message)],
                        "memory": user_memory,
                        "user_id": user_id,
                        "tool_rounds": 0,
                    },
                )
            )
        else:
            return None

        llm_response = ChatHistory.objects.filter(user_id=user_id, role="ai").last()

        serialized_response = ChatHistorySerializer(llm_response)

        logger.info(f"Sending LLM response for user {user_id}")

        return serialized_response
