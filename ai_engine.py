"""Small, transparent text retrieval and intent models trained from local files."""

import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


ENGLISH_STOPWORDS = {
    "a", "about", "after", "again", "all", "am", "an", "and", "any", "are",
    "as", "at", "be", "because", "been", "before", "being", "but", "by",
    "can", "could", "did", "do", "does", "during", "each", "for", "from",
    "had", "has", "have", "he", "her", "here", "hers", "him", "his", "how",
    "i", "if", "in", "into", "is", "it", "its", "may", "me", "more", "most",
    "my", "no", "not", "of", "on", "or", "our", "ours", "please", "she",
    "should", "so", "than", "that", "the", "their", "them", "then", "there",
    "these", "they", "this", "those", "to", "too", "up", "us", "was", "we",
    "were", "what", "when", "where", "which", "who", "why", "will", "with",
    "would", "you", "your", "yours",
}

TAGALOG_STOPWORDS = {
    "ako", "akin", "aking", "alin", "ang", "ano", "anu", "at", "ay", "ba",
    "bakit", "dahil", "dito", "doon", "gaya", "hanggang", "ikaw", "ilal",
    "ito", "iyan", "iyon", "kami", "kanila", "kanino", "kanya", "kayo",
    "ko", "kung", "maari", "maaari", "mga", "mo", "na", "namin", "natin",
    "ng", "ni", "nila", "nito", "noon", "o", "pa", "paano", "para", "po",
    "rin", "sa", "saan", "sila", "siya", "sino", "siyang", "tayo", "tulad",
    "upang", "wala", "with", "yung",
}
def levenshtein_distance(left, right):
    """Return edit distance using O(min(len(left), len(right))) memory."""
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for row, left_char in enumerate(left, start=1):
        current = [row]
        for column, right_char in enumerate(right, start=1):
            current.append(min(
                current[-1] + 1,
                previous[column] + 1,
                previous[column - 1] + (left_char != right_char),
            ))
        previous = current
    return previous[-1]


class TextPreprocessor:
    def __init__(self, synonyms):
        self.stopwords = ENGLISH_STOPWORDS | TAGALOG_STOPWORDS
        self.synonym_replacements = []
        for canonical, variants in synonyms.items():
            self.synonym_replacements.append((canonical, canonical))
            for variant in variants:
                self.synonym_replacements.append((variant, canonical))
        self.synonym_replacements.sort(key=lambda pair: len(pair[0]), reverse=True)

    @staticmethod
    def _fold(text):
        folded = unicodedata.normalize("NFKC", str(text)).casefold()
        return re.sub(r"[^\w\s'-]", " ", folded, flags=re.UNICODE)

    def tokens(self, text):
        normalized = self._fold(text)
        for phrase, canonical in self.synonym_replacements:
            pattern = rf"(?<!\w){re.escape(phrase.casefold())}(?!\w)"
            normalized = re.sub(pattern, canonical, normalized)
        tokens = []
        for token in re.findall(r"[\w'-]+", normalized, flags=re.UNICODE):
            token = token.strip("'-_")
            if len(token) < 2 or token in self.stopwords:
                continue
            stem = self.stem(token)
            if stem and stem not in self.stopwords:
                tokens.append(stem)
        return tokens

    @staticmethod
    def stem(token):
        word = token
        for prefix in ("nag", "mag", "pag", "ipa", "nak"):
            if word.startswith(prefix) and len(word) > len(prefix) + 4:
                word = word[len(prefix):]
                break
        for suffix in ("ization", "ations", "ation", "ments", "ment", "ingly",
                       "edly", "ing", "ers", "ies", "ed", "es", "s"):
            if word.endswith(suffix) and len(word) > len(suffix) + 2:
                word = word[:-len(suffix)]
                if suffix == "ing" and len(word) > 2 and word[-1] == word[-2]:
                    word = word[:-1]
                if suffix == "ies":
                    word += "y"
                break
        for suffix in ("han", "hin"):
            if word.endswith(suffix) and len(word) > 7:
                word = word[:-len(suffix)]
                break
        return word


class NaiveBayesIntentClassifier:
    def __init__(self, intents, preprocessor):
        self.preprocessor = preprocessor
        self.examples = {}
        self.document_counts = Counter()
        self.word_counts = defaultdict(Counter)
        self.total_words = Counter()
        self.vocabulary = set()
        self.responses = {}
        self._train(intents)

    def _train(self, intents):
        for intent in intents.get("intents", []):
            tag = intent["tag"]
            patterns = intent.get("patterns", [])
            self.examples[tag] = len(patterns)
            self.responses[tag] = intent.get("responses", {})
            for pattern in patterns:
                tokens = self.preprocessor.tokens(pattern)
                self.document_counts[tag] += 1
                self.word_counts[tag].update(tokens)
                self.total_words[tag] += len(tokens)
                self.vocabulary.update(tokens)

    def classify(self, text):
        tokens = self.preprocessor.tokens(text)
        if not tokens or not self.document_counts:
            return None
        total_documents = sum(self.document_counts.values())
        vocabulary_size = max(1, len(self.vocabulary))
        scores = {}
        for tag, document_count in self.document_counts.items():
            score = math.log(document_count / total_documents)
            denominator = self.total_words[tag] + vocabulary_size
            for token in tokens:
                score += math.log(
                    (self.word_counts[tag][token] + 1) / denominator
                )
            scores[tag] = score
        maximum = max(scores.values())
        exponentials = {tag: math.exp(value - maximum) for tag, value in scores.items()}
        normalizer = sum(exponentials.values())
        tag = max(scores, key=scores.get)
        return {
            "tag": tag,
            "confidence": exponentials[tag] / normalizer,
            "responses": self.responses.get(tag, {}),
        }


class LocalAIEngine:
    def __init__(self, base_dir=None):
        self.base_dir = Path(base_dir or Path(__file__).resolve().parent)
        self.synonyms = self._load_json("synonyms.json")
        self.intent_data = self._load_json("intents.json")
        self.preprocessor = TextPreprocessor(self.synonyms)
        self.intent_classifier = NaiveBayesIntentClassifier(
            self.intent_data, self.preprocessor
        )
        self.records = []
        self.document_vectors = []
        self.idf = {}
        self.vocabulary = set()

    def _load_json(self, filename):
        path = self.base_dir / filename
        try:
            with path.open(encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Could not load local AI data file {path.name}.") from exc
        if not isinstance(data, dict):
            raise ValueError(f"{path.name} must contain a JSON object.")
        return data

    def classify_intent(self, text):
        return self.intent_classifier.classify(text)

    def _correct_query_tokens(self, tokens):
        corrected = []
        vocabulary = self.vocabulary
        for token in tokens:
            if token in vocabulary or len(token) < 5:
                corrected.append(token)
                continue
            maximum_distance = 1 if len(token) < 9 else 2
            candidates = [
                candidate for candidate in vocabulary
                if abs(len(candidate) - len(token)) <= maximum_distance
            ]
            closest = min(
                candidates,
                key=lambda candidate: levenshtein_distance(token, candidate),
                default=None,
            )
            if closest and levenshtein_distance(token, closest) <= maximum_distance:
                corrected.append(closest)
            else:
                corrected.append(token)
        return corrected

    def _record_tokens(self, record):
        counts = Counter()
        weighted_fields = (
            ("title", 3.0),
            ("keywords", 3.0),
            ("location", 2.0),
            ("category", 1.0),
            ("date_posted", 1.0),
            ("event_date", 1.0),
            ("event_time", 1.0),
            ("requirements", 1.0),
            ("details", 1.0),
        )
        for field, weight in weighted_fields:
            value = record.get(field, "")
            text = " ".join(value) if isinstance(value, list) else str(value)
            for token, count in Counter(self.preprocessor.tokens(text)).items():
                counts[token] += count * weight
        return counts

    def rebuild_index(self, records):
        self.records = list(records)
        document_counts = [
            self._record_tokens(record)
            for record in self.records
        ]
        document_frequency = Counter()
        for counts in document_counts:
            document_frequency.update(counts.keys())
        document_count = len(document_counts)
        self.vocabulary = set(document_frequency)
        self.vocabulary.update(
            self.preprocessor.tokens(
                " ".join(
                    pattern
                    for intent in self.intent_data.get("intents", [])
                    for pattern in intent.get("patterns", [])
                )
            )
        )
        self.idf = {
            term: math.log((1 + document_count) / (1 + frequency)) + 1
            for term, frequency in document_frequency.items()
        }
        self.document_vectors = [
            self._normalized_vector(counts)
            for counts in document_counts
        ]

    def _normalized_vector(self, counts):
        weighted = {
            term: count * self.idf.get(term, 0.0)
            for term, count in counts.items()
            if self.idf.get(term, 0.0) > 0
        }
        norm = math.sqrt(sum(weight * weight for weight in weighted.values()))
        return {
            term: weight / norm
            for term, weight in weighted.items()
        } if norm else {}

    def search(self, query, limit=5):
        tokens = self._correct_query_tokens(self.preprocessor.tokens(query))
        query_vector = self._normalized_vector(Counter(tokens))
        if not query_vector:
            return []
        results = []
        for record, vector in zip(self.records, self.document_vectors):
            score = sum(
                weight * vector.get(term, 0.0)
                for term, weight in query_vector.items()
            )
            if score > 0:
                results.append({**record, "similarity": score})
        return sorted(
            results, key=lambda record: record["similarity"], reverse=True
        )[:limit]
