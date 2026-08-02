import re


STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "of",
    "on",
    "that",
    "the",
    "to",
    "was",
    "were",
    "with",
}

NEGATIVE_WORDS = {
    "cannot",
    "didn't",
    "doesn't",
    "false",
    "never",
    "no",
    "not",
    "without",
}


def tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9']+", text.lower())
    return {word for word in words if word not in STOP_WORDS}


def calculate_relevance(
    claim_text: str,
    evidence_text: str,
) -> tuple[float, list[str]]:
    claim_words = tokenize(claim_text)
    evidence_words = tokenize(evidence_text)

    if not claim_words:
        return 0.0, []

    matched_words = sorted(claim_words.intersection(evidence_words))
    score = len(matched_words) / len(claim_words)

    return round(score, 3), matched_words


def contains_negation(text: str) -> bool:
    words = set(re.findall(r"[a-z0-9']+", text.lower()))
    return bool(words.intersection(NEGATIVE_WORDS))


def extract_numbers(text: str) -> set[str]:
    return set(re.findall(r"\b\d+(?:\.\d+)?\b", text))