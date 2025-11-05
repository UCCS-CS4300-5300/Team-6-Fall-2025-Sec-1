from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.shortcuts import resolve_url
from django.test import TestCase, override_settings
from django.urls import reverse

from budgets.models import Budget, BudgetItem


class BudgetPlannerViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="budgeter",
            email="budgeter@example.com",
            password="pass1234",
        )
        self.url = reverse("budgets:itinerary_budget")

    def test_get_requires_authentication(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        login_url = resolve_url(settings.LOGIN_URL)
        self.assertTrue(response.headers["Location"].startswith(f"{login_url}?next="))

    def test_get_returns_budget_template(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "budgets/itineraryBudget.html")

    @override_settings(CREATE_JSON_OUTPUT=True)
    def test_post_creates_budget_items_and_json_file(self):
        self.client.force_login(self.user)
        export_dir = Path(settings.BASE_DIR) / "budgets" / "json"
        existing_files = set(export_dir.glob("*.json")) if export_dir.exists() else set()

        payload = {
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "0",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-category": BudgetItem.TRANSPORTATION,
            "items-0-custom_category": "",
            "items-0-amount": "250",
        }

        response = self.client.post(self.url, payload, follow=True)
        self.assertRedirects(response, self.url)
        self.assertEqual(Budget.objects.count(), 1)
        self.assertEqual(BudgetItem.objects.count(), 1)

        new_files = set(export_dir.glob("*.json")) - existing_files
        self.assertTrue(new_files)
        for path in new_files:
            data = path.read_text()
            self.assertIn('"amount": 250.0', data)
            path.unlink(missing_ok=True)

    def test_post_without_changes_shows_error(self):
        self.client.force_login(self.user)
        payload = {
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "0",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-category": "",
            "items-0-custom_category": "",
            "items-0-amount": "",
        }

        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, 200)
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any("highlighted errors" in str(message).lower() for message in messages))
