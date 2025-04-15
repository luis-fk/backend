from langgraph.graph import MessagesState


class SquadState(MessagesState):
    text: str
    user_id: int
