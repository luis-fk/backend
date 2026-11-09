import pytest

from cfflch.api.admission_status.utils import normalize_text


@pytest.mark.parametrize(
    ("text", "normalized"),
    [
        ("Fulano de Tal", "fulano de tal"),
        ("  BELTRANA CONCEIÇÃO\n", "beltrana conceicao"),
        ("Sicrano Araújo Müller", "sicrano araujo muller"),
    ],
)
def test_names_are_compared_without_case_accents_or_outer_spaces(
    text: str, normalized: str
) -> None:
    assert normalize_text(text) == normalized
