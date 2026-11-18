import re
from typing import Protocol


class Entity(Protocol):
    label_: str
    start_char: int
    end_char: int


class Document(Protocol):
    ents: list[Entity]


class NER(Protocol):
    def __call__(self, text: str) -> Document: ...


_LABELED_ID = re.compile(
    r"\b(?:SSS|TIN|PhilHealth|PhilHealth\s+ID|PHIC)\b"
    r"\s*(?:ID|number|no\.?)?\s*[:#-]?\s*[\d][\d\s-]{5,17}\d?",
    re.IGNORECASE,
)
_FORMATTED_ID = re.compile(
    r"(?<!\d)(?:\d{2}-\d{7}-\d|\d{2}-\d{9}-\d|"
    r"\d{3}-\d{3}-\d{3}-\d{3}|\d{12})(?!\d)"
)
_MONTH = (
    r"January|February|March|April|May|June|July|August|September|October|November|December|"
    r"Enero|Pebrero|Marso|Abril|Mayo|Hunyo|Hulyo|Agosto|Setyembre|Oktubre|Nobyembre|Disyembre"
)
_DATE = re.compile(
    r"\b(?:"
    r"(?:0?[1-9]|[12]\d|3[01])[-/.](?:0?[1-9]|1[0-2])[-/.](?:19|20)\d{2}"
    r"|(?:19|20)\d{2}[-/.](?:0?[1-9]|1[0-2])[-/.](?:0?[1-9]|[12]\d|3[01])"
    rf"|(?:{_MONTH})\s+(?:0?[1-9]|[12]\d|3[01]),?\s+(?:19|20)\d{{2}}"
    rf"|(?:0?[1-9]|[12]\d|3[01])\s+(?:of\s+)?(?:{_MONTH})\s+(?:19|20)\d{{2}}"
    r")\b",
    re.IGNORECASE,
)
_LABELED_HOUSE_NUMBER = re.compile(
    r"\b(?:house\s*(?:no\.?|number|#)|address\s+(?:is\s+)?(?:no\.?|number|#))"
    r"\s*[:#-]?\s*(?P<number>\d{1,5}(?:[-/]\d{1,5})?)\b",
    re.IGNORECASE,
)
_HOUSE_NUMBER = re.compile(
    r"\b(?P<number>(?:No\.?\s*)?\d{1,5}(?:[-/]\d{1,5})?)"
    r"(?=\s+(?:[\w.-]+\s+){0,5}"
    r"(?:Street|St\.|Road|Rd\.|Avenue|Ave\.|Boulevard|Blvd\.|"
    r"Lane|Ln\.|Drive|Dr\.|Subdivision|Village|Phase|Block|Blk\.?|"
    r"Sitio|Purok)\b)",
    re.IGNORECASE,
)


def _mask_spans(text: str, spans: list[tuple[int, int, str]]) -> str:
    if not spans:
        return text
    spans.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    merged: list[tuple[int, int, str]] = []
    for start, end, label in spans:
        if merged and start < merged[-1][1]:
            prior_start, prior_end, prior_label = merged[-1]
            merged[-1] = (prior_start, max(prior_end, end), prior_label)
        else:
            merged.append((start, end, label))
    result = text
    for start, end, label in reversed(merged):
        result = result[:start] + f"[{label}]" + result[end:]
    return result


def redact_pii(text: str, ner: NER | None, require_ner: bool = True) -> str:
    """Redact known Philippine identifiers, complete dates, house numbers and NER names."""
    if require_ner and ner is None:
        raise RuntimeError("The configured local NER model is unavailable.")

    spans: list[tuple[int, int, str]] = []
    for pattern in (_LABELED_ID, _FORMATTED_ID, _DATE):
        spans.extend((match.start(), match.end(), "REDACTED") for match in pattern.finditer(text))
    for pattern in (_HOUSE_NUMBER, _LABELED_HOUSE_NUMBER):
        spans.extend(
            (match.start("number"), match.end("number"), "HOUSE_NUMBER")
            for match in pattern.finditer(text)
        )
    if ner is not None:
        for entity in ner(text).ents:
            if entity.label_ == "PERSON":
                spans.append((entity.start_char, entity.end_char, "PERSON"))
    return _mask_spans(text, spans)
