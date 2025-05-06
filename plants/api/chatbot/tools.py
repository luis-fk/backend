from typing import Any

from langchain_core.tools import tool
from langchain_community.tools.tavily_search import TavilySearchResults


@tool
def web_search(web_search_input: str) -> Any:
    """Returns web search related questions."""
    search = TavilySearchResults(max_results=3)
    return search.invoke(input=web_search_input)
