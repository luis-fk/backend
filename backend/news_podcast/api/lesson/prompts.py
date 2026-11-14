"""Each lesson prompt's placeholders. The prompts live in the lesson settings row (the
admin), which starts from the seed. Single values are placeholders; lists go in the
human message."""

CHOICE_FIELDS = ("today",)
PICK_FIELDS = ("today", "topic", "area", "max_pages")
SCRIPT_FIELDS = (
    "host_a",
    "host_b",
    "today",
    "topic",
    "area",
    "min_words",
    "max_words",
    "news_sent",
)
REVIEW_FIELDS = ("today", "topic")
