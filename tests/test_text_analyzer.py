from app.services.text_analyzer import (
    calculate_relevance,
    contains_negation,
    extract_numbers,
    tokenize,
)


def test_tokenize_removes_common_words():
    words = tokenize("The Earth has one natural satellite")

    assert "the" not in words
    assert "has" not in words
    assert "earth" in words
    assert "satellite" in words


def test_calculate_relevance():
    score, keywords = calculate_relevance(
        "Earth has one natural satellite",
        "NASA confirms Earth has one natural satellite called the Moon",
    )

    assert score == 1.0
    assert "earth" in keywords
    assert "satellite" in keywords


def test_contains_negation():
    assert contains_negation("Earth does not have two moons") is True
    assert contains_negation("Earth has one moon") is False


def test_extract_numbers():
    numbers = extract_numbers("The scores were 42 and 98.5")

    assert numbers == {"42", "98.5"}