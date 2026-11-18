import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app as site
from ai_engine import LocalAIEngine, levenshtein_distance
from chatbot import LocalChatbot
from database import LocalDatabase


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class WebsiteAiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = LocalDatabase(Path(self.temp_dir.name) / "barangay.db")
        self.engine = LocalAIEngine(PROJECT_ROOT)
        self.bot = LocalChatbot(self.database, self.engine)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_synonyms_and_typo_matching_normalize_resident_queries(self):
        tokens = self.engine.preprocessor.tokens("clerance vaccine")
        self.assertIn("clearance", tokens)
        self.assertIn("bakuna", tokens)
        self.assertEqual(levenshtein_distance("clearance", "clerance"), 1)

    def test_retrieval_uses_tf_idf_and_typo_correction(self):
        service = {
            "id": 1,
            "name": "Barangay Clearance",
            "tag": "Documents",
            "description": "Clearance certificate service.",
            "details": "Ask the barangay service desk for current instructions.",
            "requirements": "",
        }
        self.database.sync_portal_records([], [], [service], [])
        self.engine.rebuild_index(self.database.list_active_records())

        results = self.engine.search("clerance")

        self.assertEqual(results[0]["title"], "Barangay Clearance")
        self.assertGreaterEqual(results[0]["similarity"], 0.35)
        reply = self.bot.respond("clerance", "resident-1")
        self.assertIn("Barangay Clearance", reply["reply"])

    def test_low_similarity_uses_no_guess_fallback(self):
        self.database.sync_portal_records(
            [], [], [],
            [{
                "id": 9,
                "topic": "E-library access",
                "keywords": ["library", "learning"],
                "answer": "Ask staff about current access instructions.",
                "media": [],
                "status": "Published",
            }],
        )
        self.engine.rebuild_index(self.database.list_active_records())

        reply = self.bot.respond("Where can I buy a spaceship?", "resident-2")

        self.assertIn("don't have enough information", reply["reply"])
        self.assertTrue(reply["suggestions"])

    def test_long_responses_are_split_into_safe_bubbles(self):
        response = self.bot._response("Official record. " * 300)

        self.assertGreater(len(response["bubbles"]), 1)
        self.assertTrue(all(len(bubble) <= 1800 for bubble in response["bubbles"]))

    def test_local_intents_handle_greetings_and_announcement_requests(self):
        greeting = self.bot.respond("hi", "resident-3")
        self.assertIn("Good day", greeting["reply"])
        thanks = self.bot.respond("salamat po", "resident-3")
        self.assertIn("Walang anuman", thanks["reply"])
        self.assertEqual(
            self.engine.classify_intent("Mga Bagong Anunsyo")["tag"],
            "latest_announcements",
        )

    def test_emergency_uses_immediate_local_safety_reply(self):
        response = self.bot.respond("Sunog po!", "resident-emergency")
        self.assertIn("911", response["reply"])
        self.assertIn("Tanod", response["reply"])

    def test_dialogue_context_answers_followup_from_same_event(self):
        self.database.sync_portal_records(
            [],
            [{
                "id": 7,
                "title": "Community Medical Mission",
                "date": "January 12, 2030",
                "_sort": "2030-01-12",
                "time": "9:00 AM",
                "location": "Barangay Hall",
                "requirements": "Bring your health record.",
                "description": "Free checkup.",
                "status": "Published",
            }],
            [],
            [],
        )
        self.engine.rebuild_index(self.database.list_active_records())

        first = self.bot.respond("Kailan ang medical mission?", "resident-4")
        second = self.bot.respond("Saan po ito?", "resident-4")
        third = self.bot.respond("Anong kailangan dalhin?", "resident-4")

        self.assertIn("January 12, 2030", first["reply"])
        self.assertIn("Barangay Hall", second["reply"])
        self.assertIn("Bring your health record", third["reply"])

    def test_chat_endpoint_uses_injected_local_chatbot_without_provider_keys(self):
        guide = {
            "id": 77,
            "topic": "Special printing instructions",
            "keywords": ["specialprinter"],
            "answer": "Ask the service desk for the approved printing instructions.",
            "media": [],
            "status": "Published",
        }
        self.database.sync_portal_records([], [], [], [guide])
        self.engine.rebuild_index(self.database.list_active_records())
        client = site.app.test_client()
        with patch.object(site, "LOCAL_CHATBOT", self.bot):
            response = client.post(
                "/api/chat", json={"message": "specialprinter"}
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(guide["answer"], response.get_json()["reply"])
        self.assertEqual(response.get_json()["sources"], [])


if __name__ == "__main__":
    unittest.main()
