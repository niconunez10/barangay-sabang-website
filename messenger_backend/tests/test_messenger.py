import asyncio
import hashlib
import hmac
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from messenger_backend import main


class EmptyNER:
    def __call__(self, _text: str) -> SimpleNamespace:
        return SimpleNamespace(ents=[])


class MessengerUtilityTests(unittest.TestCase):
    def test_bubbles_respect_messenger_limit(self) -> None:
        text = "word " * 900

        bubbles = main._split_bubbles(text)

        self.assertGreater(len(bubbles), 1)
        self.assertTrue(all(0 < len(bubble) <= main.MAX_BUBBLE_LENGTH for bubble in bubbles))
        self.assertEqual(" ".join(bubbles), text.strip())

    def test_search_domains_reject_lookalikes(self) -> None:
        self.assertTrue(main._trusted_url("https://pagasa.dost.gov.ph/advisory"))
        self.assertFalse(main._trusted_url("https://pagasa.dost.gov.ph.attacker.example/advisory"))
        self.assertFalse(main._trusted_url("http://pagasa.dost.gov.ph/advisory"))

    def test_publication_time_requires_an_explicit_timezone(self) -> None:
        self.assertIsNone(main._timestamp("2026-11-18"))
        self.assertIsNone(main._timestamp("2026-11-18T10:30:00"))
        self.assertIsNotNone(main._timestamp("2026-11-18T10:30:00+08:00"))

    def test_webhook_signature_uses_hmac_sha256(self) -> None:
        body = b'{"object":"page"}'
        secret = "test-secret"
        signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

        with patch.object(main.settings, "facebook_app_secret", secret):
            self.assertTrue(main._messenger_signature_valid(body, f"sha256={signature}"))
            self.assertFalse(main._messenger_signature_valid(body, "sha256=invalid"))

    def test_health_and_webhook_signature_gate(self) -> None:
        with TestClient(main.app) as client:
            self.assertEqual(client.get("/health/live").status_code, 200)
            self.assertIn("status", client.get("/health/ready").json())
            response = client.post("/webhook", json={"object": "page"})
            self.assertEqual(response.status_code, 403)

    def test_emergency_returns_card_without_answer_generation(self) -> None:
        request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
            ner=EmptyNER(), background_tasks=set()
        )))
        intent = main.IntentResult(
            track="EMERGENCY", search_query="ongoing fire", language="English"
        )
        alert = AsyncMock()
        generate = AsyncMock(side_effect=AssertionError("generation must be bypassed"))

        async def run() -> tuple[str, bool]:
            with patch.object(main, "_classify", AsyncMock(return_value=intent)), \
                    patch.object(main, "_alert_duty_desk", alert), \
                    patch.object(main, "_generate", generate):
                result = await main.answer_message(request, "There is a fire", "psid")
                await asyncio.sleep(0)
                return result

        reply, emergency = asyncio.run(run())

        self.assertTrue(emergency)
        self.assertIn("911", reply)
        generate.assert_not_awaited()
        alert.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
