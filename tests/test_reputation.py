from app.services.reputation import (
    get_registry,
    lookup_reputation,
    reset_registry,
    set_reputation,
)


def setup_function():
    reset_registry()


def test_default_nasa_reputation():
    assert lookup_reputation("NASA") >= 0.9


def test_unknown_fallback():
    score = lookup_reputation("TotallyUnknownSourceXYZ")
    assert 0.0 <= score <= 1.0


def test_set_and_get_reputation():
    set_reputation("My Lab", 0.77)
    assert lookup_reputation("my lab") == 0.77
    registry = get_registry()
    assert "my lab" in registry


def test_substring_match():
    assert lookup_reputation("NASA.gov Portal") >= 0.9
