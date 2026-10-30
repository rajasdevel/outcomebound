"""Factual prose controls for the bounded reports; wording is otherwise free."""

from __future__ import annotations

import re


def normalize(text):
    numbers = {
        "zero": "0",
        "one": "1",
        "two": "2",
        "three": "3",
        "four": "4",
        "five": "5",
        "seven": "7",
        "ten": "10",
        "eleven": "11",
        "sixteen": "16",
        "twenty-one": "21",
    }
    text = text.lower().replace("\u2019", "'").replace("`", "")
    text = re.sub(r"\b(?:" + "|".join(numbers) + r")\b", lambda match: numbers[match[0]], text)
    return re.sub(r"\s+", " ", text)


DENIAL = (
    r"(?:not(?! only\b)|never|cannot|can't|doesn't|don't|didn't|isn't|aren't|wasn't|weren't|"
    r"won't|hasn't|haven't|hadn't|shouldn't|wouldn't|couldn't|mustn't)"
)
NEGATION = re.compile(r"\b(?:" + DENIAL + r"|no|unverified|incorrect|false)\b")
CONDITIONAL = re.compile(r"\b(?:until|unless|once|after|when|if|before)\b")
CLAUSE = re.compile(r"[;!?|]|\.(?=\s|$)|:\s+|\b(?:but|however|whereas)\b")
BOUNDARY = re.compile(
    CLAUSE.pattern + r"|\band\s+(?=(?:we|i|it|this|the|approve|do|does|must|should|never)\b)"
)


def denied(pattern):
    return r"\b" + DENIAL + r"(?:\s+(?:yet|been|be|being|have|has|had|to))*\s+(?:" + pattern + ")"


def statements(text, pattern):
    text = normalize(text)
    for match in re.finditer(pattern, text):
        boundaries = list(BOUNDARY.finditer(text, 0, match.start()))
        prefix = text[boundaries[-1].end() if boundaries else 0 : match.start()]
        # A negation explicitly named by the fact is part of its meaning, as in
        # "must not merge". Wildcards cannot silently absorb a reversed conclusion.
        negative = bool(NEGATION.search(prefix)) or any(
            not re.search(r"\b" + re.escape(word[0]) + r"\b", pattern)
            for word in NEGATION.finditer(match[0])
        )
        suffix = text[match.end() :]
        negative |= bool(re.match(r"\s+(?:is|are|was)\s+(?:not|incorrect|false)\b", suffix))
        yield not negative


def asserted(text, pattern):
    return any(
        not CONDITIONAL.search(clause) and any(statements(clause, pattern))
        for clause in CLAUSE.split(normalize(text))
    )


def require(text, facts, contradictions=()):
    for fact, pattern in facts.items():
        patterns = [pattern] if isinstance(pattern, str) else pattern
        found = [value for option in patterns for value in statements(text, option)]
        if not found or not all(found):
            raise ValueError("operator note omits or negates " + fact)
    if any(asserted(text, pattern) for pattern in contradictions):
        raise ValueError("operator note contradicts the checked facts")
