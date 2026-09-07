from app.services.semantic import semantic_similarity


def test_identical_texts_high_similarity():
    text = "Earth has one natural satellite called the Moon"
    assert semantic_similarity(text, text) >= 0.9


def test_unrelated_texts_low_similarity():
    score = semantic_similarity(
        "Earth has one natural satellite",
        "Python is a popular programming language for data science",
    )
    assert score < 0.3


def test_empty_similarity():
    assert semantic_similarity("", "hello world") == 0.0
