from django.urls import path

from political_culture.api.word_counter.routes import WordCounterApi

word_counter_urls = [
    path(
        "api/political-culture/word-counter",
        WordCounterApi.as_view(),
        name="word_counter",
    ),
]
