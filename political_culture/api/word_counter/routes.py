import logging
from typing import Any

from rest_framework.response import Response
from rest_framework.views import APIView

from political_culture.api.chatbot.agents import call_title_and_author_extractor_agent
from political_culture.api.word_counter.serializers import TextsSerializer
from political_culture.api.word_counter.service import (
    count_words,
    word_picker,
)
from political_culture.models import Texts, TextWordCount

logger = logging.getLogger(__name__)


class WordCounterApi(APIView):
    def post(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        logger.info("Receiving text, starting word counting")

        serializer = TextsSerializer(data=request.data)

        if serializer.is_valid():
            text_db = self._add_text(serializer)

            logger.info("Getting word frequency and total word count")

            self._add_text_word_count(text_db)

            logger.info("Data created successfully")

            return Response(status=200)
        else:
            logger.error("Invalid data received from ESP32", serializer.errors)

            return Response(serializer.errors, status=400)

    def _add_text(self, serializer: TextsSerializer) -> Texts:
        text = serializer.validated_data["text"]
        user_id = serializer.validated_data["user_id"]

        text_data = call_title_and_author_extractor_agent(text)

        title = text_data.title
        author = text_data.author
        content_description = text_data.content_description

        logger.info("Adding text to the database")

        return Texts.objects.create(
            user_id=user_id,
            text=text,
            title=title,
            author=author,
            content_description=content_description,
        )

    def _add_text_word_count(self, text_db: Texts) -> None:
        word_frequencies, total_word_count = count_words(text_db.text, 1000)

        new_word_frequencies = word_picker(word_frequencies)

        dict_word_frequencies = dict(
            (word_count.word, word_count.count)
            for word_count in new_word_frequencies.words_list
        )
        
        TextWordCount.objects.create(
            text=text_db,
            total_word_count=total_word_count,
            word_frequencies=dict_word_frequencies,
        )
