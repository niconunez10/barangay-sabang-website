import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app as site
from ai_engine import LocalAIEngine
from database import LocalDatabase


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class LocalEventIndexTests(unittest.TestCase):
    def test_admin_event_requirements_are_saved_and_indexed(self):
        client = site.app.test_client()
        with client.session_transaction() as session:
            session["is_admin"] = True
            session["csrf"] = "local-test-token"

        with tempfile.TemporaryDirectory() as temp_dir:
            database = LocalDatabase(Path(temp_dir) / "barangay.db")
            engine = LocalAIEngine(PROJECT_ROOT)
            with patch.object(site, "LOCAL_DATABASE", database), \
                    patch.object(site, "LOCAL_AI_ENGINE", engine), \
                    patch.object(site, "AI_DB_FILE", Path(temp_dir) / "legacy.sqlite3"), \
                    patch.object(site, "DATA_FILE", Path(temp_dir) / "data.json"), \
                    patch.object(site, "start_event_background_check"):
                response = client.post(
                    "/api/admin/events",
                    json={
                        "title": "Community vaccination",
                        "date": "2030-01-12",
                        "time": "09:00",
                        "location": "Health Center",
                        "description": "Officially scheduled clinic.",
                        "requirements": "Bring a vaccination card.",
                    },
                    headers={"X-CSRF-Token": "local-test-token"},
                )
                event_id = response.get_json()["event"]["id"]
                self.addCleanup(self._remove_event, event_id)
                record = database.get_active_record("event", event_id)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(record["requirements"], "Bring a vaccination card.")
                self.assertEqual(engine.search("vaccination card")[0]["record_id"], event_id)

    def test_only_published_admin_posts_enter_local_index(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database = LocalDatabase(Path(temp_dir) / "barangay.db")
            database.sync_portal_records(
                [{
                    "id": 1,
                    "title": "Live notice",
                    "description": "Confirmed local notice.",
                    "status": "Published",
                }, {
                    "id": 2,
                    "title": "Archived notice",
                    "description": "Hidden notice.",
                    "status": "Archived",
                }],
                [],
                [],
                [],
            )

            records = database.list_active_records()
            engine = LocalAIEngine(PROJECT_ROOT)
            engine.rebuild_index(records)

            self.assertEqual([record["title"] for record in records], ["Live notice"])
            self.assertNotIn("Sample: Libreng Anti-Rabies Vaccination",
                             [record["title"] for record in records])
            self.assertEqual(engine.search("confirmed local notice")[0]["title"], "Live notice")

    def test_local_background_check_marks_post_unverified_and_reindexes(self):
        post = {
            "id": 987654,
            "title": "Temporary medical mission",
            "date": "January 12, 2030",
            "_sort": "2030-01-12",
            "time": "9:00 AM",
            "location": "Barangay Hall",
            "requirements": "Bring a health record.",
            "description": "Community health activity.",
            "status": "Published",
            "media": [{"name": "notice.pdf"}],
        }
        site.events.append(post)
        try:
            with patch.object(site, "save_data"):
                site.run_event_background_check(post["id"], "events")

            self.assertEqual(post["verification_status"], "local_only")
            self.assertIn("not an independent", post["verified_reference"])
            self.assertIn("medical", post["auto_keywords"])
            self.assertEqual(post["source_urls"], [])
            self.assertTrue(post["last_checked_at"])
        finally:
            site.events.remove(post)

    def test_event_requirements_are_synchronized_for_retrieval(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database = LocalDatabase(Path(temp_dir) / "barangay.db")
            database.sync_portal_records(
                [],
                [{
                    "id": 3,
                    "title": "Vaccination day",
                    "date": "January 12, 2030",
                    "_sort": "2030-01-12",
                    "time": "9:00 AM",
                    "location": "Health Center",
                    "requirements": "Bring a vaccination card.",
                    "description": "",
                    "status": "Published",
                }],
                [],
                [],
            )

            record = database.get_active_record("event", 3)

            self.assertEqual(record["requirements"], "Bring a vaccination card.")
            self.assertEqual(record["event_date"], "2030-01-12")

    @staticmethod
    def _remove_event(event_id):
        item = site.find_item("events", event_id)
        if item:
            site.events.remove(item)


if __name__ == "__main__":
    unittest.main()
