from typing import Annotated, Any

from django.db import connections
from langchain_core.tools import BaseTool, tool
from langchain_tavily import TavilySearch
from langgraph.prebuilt import InjectedState

from plants.api.sensors.summary import plant_summary, plants_overview


@tool
def web_search(web_search_input: str) -> Any:
    """Returns web search related questions."""
    search = TavilySearch(max_results=3, search_depth="advanced")
    return search.invoke(input=web_search_input)


# The person comes from the graph's state (InjectedState), never from the model,
# so it can't read another person's plants. The ToolNode runs each tool in a
# worker thread, whose database connections Django doesn't close: the tools do.


@tool
def list_my_plants(
    user_id: Annotated[int, InjectedState("user_id")],
) -> dict[str, Any]:
    """Lists the person's plants that have a soil sensor: each plant's nickname, its
    number of readings, its first and last reading times (São Paulo time) and the
    usual minutes between readings. An empty list means they have none."""
    # An object, not a bare list: an empty list would reach OpenAI as an empty
    # tool message, which it refuses.
    try:
        return {"plants": plants_overview(user_id)}
    finally:
        connections.close_all()


@tool
def get_plant_readings(
    plant: str,
    user_id: Annotated[int, InjectedState("user_id")],
    hours: int = 24,
) -> dict[str, Any]:
    """Reads one of the person's plants, by its nickname, over the last hours (1 to
    720, 24 by default). For soil moisture (percent and the sensor's raw value), air
    humidity (%) and temperature (°C) it gives the last value, the lowest and the
    highest with their times, the average and the change over the period, plus the
    readings themselves or their hourly or daily averages. Times are São Paulo time.
    Temperature and air humidity are the weather where the person lives, not
    measured at the plant, and can be missing."""
    try:
        return plant_summary(user_id, plant, hours)
    finally:
        connections.close_all()


TOOLS: list[BaseTool] = [web_search, list_my_plants, get_plant_readings]
