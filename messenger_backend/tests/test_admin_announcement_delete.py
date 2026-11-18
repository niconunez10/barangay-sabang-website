import unittest
from unittest.mock import patch

import app as site


class AdminAnnouncementDeleteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = site.app.test_client()
        with self.client.session_transaction() as session:
            session["is_admin"] = True
            session["csrf"] = "test-csrf-token"

    def test_published_announcement_can_be_deleted(self) -> None:
        item = {
            "id": 900000001,
            "title": "Temporary test announcement",
            "status": "Published",
            "media": [],
        }
        site.announcements.append(item)
        try:
            with patch.object(site, "save_data") as save_data:
                response = self.client.delete(
                    f"/api/admin/announcements/{item['id']}",
                    headers={"X-CSRF-Token": "test-csrf-token"},
                )

            self.assertEqual(response.status_code, 200)
            self.assertNotIn(item, site.announcements)
            self.assertEqual(response.get_json()["message"], "Announcement deleted permanently.")
            save_data.assert_called_once()
        finally:
            if item in site.announcements:
                site.announcements.remove(item)

    def test_published_event_still_requires_archiving_before_delete(self) -> None:
        item = {
            "id": 900000002,
            "title": "Temporary test event",
            "status": "Published",
            "media": [],
        }
        site.events.append(item)
        try:
            with patch.object(site, "save_data"):
                response = self.client.delete(
                    f"/api/admin/events/{item['id']}",
                    headers={"X-CSRF-Token": "test-csrf-token"},
                )

            self.assertEqual(response.status_code, 400)
            self.assertIn(item, site.events)
        finally:
            site.events.remove(item)


if __name__ == "__main__":
    unittest.main()
