import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase, override_settings
from django.urls import reverse

from time_preferences.forms import TimePreferenceForm
from time_preferences.models import TimePreference


class TimePreferenceViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="planner",
            email="planner@example.com",
            password="pass1234",
        )
        self.url = reverse("time_preferences:itinerary")

    def test_get_returns_form_context(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        self.assertIsInstance(response.context["form"], TimePreferenceForm)

    @override_settings(CREATE_JSON_OUTPUT=True)
    def test_post_creates_preference_and_json_file(self):
        self.client.force_login(self.user)
        export_dir = Path(settings.BASE_DIR) / "time_preferences" / "json"
        existing_files = set(export_dir.glob("*.json")) if export_dir.exists() else set()

        payload = {
            "wake_up_time": "07:30",
            "sleep_time": "22:15",
            "enable_meals": "on",
            "breakfast_time": "08:00",
            "lunch_time": "12:30",
            "dinner_time": "18:45",
            "break_frequency": TimePreference.BREAK_FREQUENCY_CHOICES[0][0],
            "break_duration": TimePreference.BREAK_DURATION_CHOICES[1][0],
            "schedule_strictness": TimePreference.SCHEDULE_STRICTNESS_CHOICES[1][0],
            "preferred_start_time": "09:00",
            "preferred_end_time": "19:00",
        }

        response = self.client.post(self.url, payload, follow=True)
        self.assertRedirects(response, self.url)

        self.assertEqual(TimePreference.objects.count(), 1)
        preference = TimePreference.objects.get()
        self.assertEqual(preference.break_frequency, payload["break_frequency"])
        self.assertEqual(preference.enable_meals, True)

        new_files = set(export_dir.glob("*.json")) - existing_files
        self.assertTrue(new_files)
        for path in new_files:
            data = json.loads(path.read_text())
            self.assertEqual(data["preference_id"], preference.id)
            self.assertEqual(data["wake_up_time"], "07:30:00")
            path.unlink(missing_ok=True)

    def test_post_accounts_for_blank_optional_fields(self):
        self.client.force_login(self.user)
        payload = {
            "enable_meals": "False",
            "wake_up_time": "",
            "sleep_time": "",
            "breakfast_time": "",
            "lunch_time": "",
            "dinner_time": "",
            "break_frequency": "",
            "break_duration": "",
            "schedule_strictness": "",
            "preferred_start_time": "",
            "preferred_end_time": "",
        }

        response = self.client.post(self.url, payload, follow=True)
        self.assertRedirects(response, self.url)

        preference = TimePreference.objects.get()
        self.assertFalse(preference.enable_meals)
        self.assertIsNone(preference.breakfast_time)
        self.assertIsNone(preference.lunch_time)
        self.assertIsNone(preference.dinner_time)

    def test_post_with_invalid_time_range_shows_error(self):
        self.client.force_login(self.user)
        payload = {
            "enable_meals": "on",
            "wake_up_time": "07:00",
            "sleep_time": "22:00",
            "breakfast_time": "08:00",
            "lunch_time": "12:00",
            "dinner_time": "18:00",
            "break_frequency": "",
            "break_duration": "",
            "schedule_strictness": "",
            "preferred_start_time": "18:00",
            "preferred_end_time": "16:00",
        }

        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertIn("End time must be after start time.", form.errors.get("preferred_end_time", []))
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any("correct the highlighted fields" in str(message).lower() for message in messages))
