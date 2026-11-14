# Each prompt's placeholders and its template. The prompts live in the settings row
# (the admin), which starts from seed/settings.json.

from langchain_core.prompts import ChatPromptTemplate

# The {placeholders} the service fills in each prompt; the admin refuses any other.
SELECTION_FIELDS = (
    "min_minutes",
    "max_minutes",
    "target_minutes",
    "min_stories",
    "max_stories",
    "window_start",
    "window_end",
)
SCRIPT_FIELDS = (
    "podcast_name",
    "host_a",
    "host_b",
    "send_time",
    "greeting",
    "today",
    "window_start",
    "window_end",
    "min_words",
    "max_words",
)
EXPAND_FIELDS = ("words", "min_words", "max_words", "script")


def selection_template(prompt: str) -> ChatPromptTemplate:
    """The saved prompt is the system message. The headlines go in as a variable, so
    their braces are never read as placeholders."""
    return ChatPromptTemplate.from_messages(
        [("system", prompt), ("human", "{headlines}")]
    )


def script_template(prompt: str) -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([("system", prompt), ("human", "{briefs}")])


def lengthening_template(script_prompt: str, expand_prompt: str) -> ChatPromptTemplate:
    """The script's messages, with the expand prompt after the briefs."""
    return ChatPromptTemplate.from_messages(
        [("system", script_prompt), ("human", "{briefs}\n\n" + expand_prompt)]
    )
