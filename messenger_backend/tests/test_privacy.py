import unittest
from types import SimpleNamespace

from messenger_backend.privacy import redact_pii


class FakeNER:
    def __call__(self, text: str) -> SimpleNamespace:
        start = text.index("Ana Dela Cruz")
        entity = SimpleNamespace(
            label_="PERSON",
            start_char=start,
            end_char=start + len("Ana Dela Cruz"),
        )
        return SimpleNamespace(ents=[entity])


class PrivacyRedactionTests(unittest.TestCase):
    def test_masks_labeled_ids_birthdates_and_exact_house_number(self) -> None:
        text = (
            "SSS: 12-3456789-0, TIN 123-456-789-000, "
            "PhilHealth 123456789012. Born 1990-04-15, May 3, 1991, "
            "and 15 Hunyo 1992. Address: 24 Mabini Street, house no. 19."
        )

        result = redact_pii(text, ner=None, require_ner=False)

        for sensitive_value in (
            "12-3456789-0", "123-456-789-000", "123456789012",
            "1990-04-15", "May 3, 1991", "15 Hunyo 1992", "24", "19",
        ):
            self.assertNotIn(sensitive_value, result)
        self.assertIn("[HOUSE_NUMBER] Mabini Street", result)

    def test_masks_person_entities_from_local_ner(self) -> None:
        result = redact_pii("Please help Ana Dela Cruz.", FakeNER())

        self.assertEqual(result, "Please help [PERSON].")

    def test_fails_closed_when_ner_is_required_but_unavailable(self) -> None:
        with self.assertRaises(RuntimeError):
            redact_pii("Need a barangay clearance.", ner=None)


if __name__ == "__main__":
    unittest.main()
