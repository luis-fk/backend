from news_podcast.api.core.audio import (
    LOUDNESS_FILTER,
    audio_filters,
)


def test_audio_filters_speed_up_before_normalizing_loudness() -> None:
    assert audio_filters(1.5) == f"atempo=1.5,{LOUDNESS_FILTER}"
    assert audio_filters(1.25) == f"atempo=1.25,{LOUDNESS_FILTER}"
