"""
Unit tests for itinerary functionality.
"""
from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path
import sys
import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.contrib.messages import get_messages
from django.test import Client, TestCase
from django.urls import include, path, reverse
from django.utils import timezone
from openai import OpenAIError

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

TEMPLATE_STRINGS = {
    "itinerary.html": "itinerary template",
    "itinerary_detail.html": "itinerary detail template",
    "navbar.html": "",
}

# Configure minimal Django settings so the tests can run without a full project.
if not settings.configured:
    settings.configure(
        SECRET_KEY="test-secret-key",
        INSTALLED_APPS=[
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.sessions",
            "django.contrib.messages",
            "django.contrib.staticfiles",
            "itinerary",
        ],
        DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
        ROOT_URLCONF="test_itinerary",
        MIDDLEWARE=[
            "django.middleware.security.SecurityMiddleware",
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.middleware.common.CommonMiddleware",
            "django.middleware.csrf.CsrfViewMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "django.contrib.messages.middleware.MessageMiddleware",
        ],
        TEMPLATES=[
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "DIRS": [],
                "APP_DIRS": False,
                "OPTIONS": {
                    "loaders": [("django.template.loaders.locmem.Loader", TEMPLATE_STRINGS)],
                    "context_processors": [
                        "django.template.context_processors.debug",
                        "django.template.context_processors.request",
                        "django.contrib.auth.context_processors.auth",
                        "django.contrib.messages.context_processors.messages",
                    ],
                },
            }
        ],
        USE_TZ=True,
        OPENAI_API_KEY="test-api-key",
        STATIC_URL="/static/",
    )
    import django

    django.setup()

from itinerary.forms import ItineraryForm
from itinerary.models import BreakTime, BudgetItem, Day, Itinerary
from itinerary.views import _build_ai_prompt

urlpatterns = [
    path("", include(("itinerary.urls", "itinerary"), namespace="itinerary")),
]


class ItineraryViewTests(TestCase):
    """Exercise the primary itinerary builder view."""

    def setUp(self):
        self.client = Client()
        self.url = reverse("itinerary:itinerary")
        self.valid_post_data = {
            "destination": "Paris",
            "place_id": "some-place",
            "latitude": "48.8566",
            "longitude": "2.3522",
            "num_days": 2,
            "start_date": "2025-01-01",
            "end_date": "2025-01-02",
            "wake_up_time": "08:00",
            "bed_time": "22:00",
            "energy_level": "balanced",
            "include_breakfast": "on",
            "include_lunch": "on",
            "include_dinner": "on",
            "dietary_notes": "",
            "mobility_notes": "",
            "trip_purpose": "leisure",
            "party_adults": 2,
            "party_children": 0,
            "arrival_datetime": "",
            "arrival_airport": "",
            "departure_datetime": "",
            "departure_airport": "",
            "overall_budget_min": "1000",
            "overall_budget_max": "2500",
            "activity_priorities": "1. Eiffel Tower\n2. Seine Cruise",
            "mood_tags": "relaxing,cultural",
            "break_start_time[]": ["12:00"],
            "break_end_time[]": ["13:00"],
            "break_purpose[]": ["Lunch"],
            "budget_category[]": ["Food"],
            "budget_custom_category[]": [""],
            "budget_amount[]": ["500"],
            "day_1_date": "2025-01-01",
            "day_1_notes": "Visit Eiffel Tower",
            "day_1_must_do": "Eiffel Tower top view",
            "day_2_date": "2025-01-02",
            "day_2_notes": "",
            "day_2_must_do": "",
        }

    def _mock_openai(self, mock_openai, ai_response=None):
        """Return a MagicMock configured for the OpenAI client."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(ai_response or {"days": []})
        mock_client.chat.completions.create.return_value = mock_response
        return mock_client

    def test_get_request_success(self):
        """Render the itinerary builder and verify the form context."""
        # Issue GET request to load the builder page.
        response = self.client.get(self.url)

        # Ensure template and form exist in the context.
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "itinerary.html")
        self.assertIsInstance(response.context["form"], ItineraryForm)

    def test_get_retrieves_ai_itinerary_from_session(self):
        """Ensure the GET view does not leak AI results."""
        # Perform GET request.
        response = self.client.get(self.url)

        # Confirm context excludes AI data for the builder form.
        self.assertNotIn("ai_itinerary_days", response.context)

    @patch("itinerary.views.OpenAI")
    def test_post_creates_itinerary_and_related_objects(self, mock_openai):
        """Create itinerary plus break, budget, and day rows."""
        # Mock OpenAI so the request flows normally.
        self._mock_openai(mock_openai)

        # Submit POST request with valid payload.
        self.client.post(self.url, self.valid_post_data)

        # Assert itinerary data persisted.
        itinerary = Itinerary.objects.get()
        self.assertEqual(itinerary.destination, "Paris")
        self.assertEqual(itinerary.num_days, 2)

        # Confirm related models were created.
        self.assertEqual(BreakTime.objects.count(), 1)
        self.assertEqual(str(BreakTime.objects.first().start_time), "12:00:00")
        self.assertEqual(BudgetItem.objects.count(), 1)
        self.assertEqual(BudgetItem.objects.first().amount, Decimal("500"))
        self.assertEqual(Day.objects.count(), 2)

    @patch("itinerary.views.OpenAI")
    def test_post_skips_empty_values(self, mock_openai):
        """Ignore partially filled dynamic rows."""
        # Mock OpenAI to avoid API work.
        self._mock_openai(mock_openai)

        # Submit payload with blank dynamic entries.
        data = self.valid_post_data.copy()
        data["break_start_time[]"] = ["12:00", ""]
        data["break_end_time[]"] = ["13:00", ""]
        data["budget_amount[]"] = ["500", ""]
        data["day_2_date"] = ""
        self.client.post(self.url, data)

        # Verify empty rows were ignored.
        self.assertEqual(BreakTime.objects.count(), 1)
        self.assertEqual(BudgetItem.objects.count(), 1)
        self.assertEqual(Day.objects.count(), 1)

    @patch("itinerary.views.OpenAI")
    def test_post_handles_custom_budget_category(self, mock_openai):
        """Store custom categories when the user selects Other."""
        # Mock OpenAI and submit payload containing custom category.
        self._mock_openai(mock_openai)
        data = self.valid_post_data.copy()
        data["budget_category[]"] = ["Other"]
        data["budget_custom_category[]"] = ["Souvenirs"]
        self.client.post(self.url, data)

        # Ensure the custom category persisted.
        budget = BudgetItem.objects.first()
        self.assertEqual(budget.category, "Other")
        self.assertEqual(budget.custom_category, "Souvenirs")

    @patch("itinerary.views.OpenAI")
    def test_post_redirects_with_success_message(self, mock_openai):
        """Redirect to detail view and surface success notifications."""
        # Mock OpenAI response.
        self._mock_openai(mock_openai)

        # Submit valid form and follow redirect.
        response = self.client.post(self.url, self.valid_post_data, follow=True)

        # Verify success message is present.
        self.assertEqual(response.status_code, 200)
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any("Itinerary created successfully" in str(msg) for msg in messages))

    def test_invalid_form_shows_error(self):
        """Keep user on builder page when validation fails."""
        # Create intentionally invalid payload.
        invalid_data = {
            "destination": "",
            "start_date": "2025-01-01",
            "end_date": "2025-01-03",
            "num_days": 3,
            "wake_up_time": "08:00",
            "bed_time": "22:00",
            "energy_level": "balanced",
            "trip_purpose": "leisure",
            "party_adults": 1,
            "party_children": 0,
        }

        # Submit invalid data.
        response = self.client.post(self.url, invalid_data)

        # Confirm no itinerary was saved and an error message was attached.
        self.assertEqual(Itinerary.objects.count(), 0)
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any("Please correct the errors below" in str(msg) for msg in messages))

    @patch("itinerary.views._fetch_flight_details")
    @patch("itinerary.views.OpenAI")
    def test_post_autofills_flight_details(self, mock_openai, mock_fetch):
        """Populate arrival data when a flight number is supplied."""
        # Configure OpenAI mock.
        self._mock_openai(mock_openai)

        # Stub flight details returned by AviationStack.
        mock_fetch.return_value = {
            "flight_number": "UA123",
            "airline": "United Airlines",
            "arrival_airport": "DEN",
            "arrival_airport_name": "Denver International",
            "arrival_time": "2025-01-01T15:00:00Z",
            "departure_airport": "ORD",
            "departure_airport_name": "Chicago O'Hare",
            "departure_time": "2025-01-01T11:00:00Z",
        }

        # Submit itinerary containing a flight number.
        data = self.valid_post_data.copy()
        data["arrival_flight_number"] = "UA123"
        self.client.post(self.url, data)

        # Verify the itinerary includes API-derived flight data.
        itinerary = Itinerary.objects.get()
        self.assertTrue(mock_fetch.called)
        self.assertIn("Denver International (DEN)", itinerary.arrival_airport)
        self.assertEqual(itinerary.arrival_airline, "United Airlines")
        self.assertIsNotNone(itinerary.arrival_datetime)


class AncillaryViewTests(TestCase):
    """Validate supplementary AJAX and helper views."""

    def setUp(self):
        self.client = Client()

    @patch("itinerary.views._fetch_flight_details")
    def test_flight_lookup_returns_details(self, mock_fetch):
        """Return normalized flight details when lookup succeeds."""
        # Stub lookup data.
        mock_fetch.return_value = {
            "flight_number": "UA123",
            "airline": "United",
            "arrival_airport": "DEN",
            "arrival_airport_name": "Denver International",
            "arrival_time": "2025-01-01T15:00:00Z",
            "departure_airport": "ORD",
            "departure_airport_name": "Chicago O'Hare",
            "departure_time": "2025-01-01T11:00:00Z",
        }

        # Issue AJAX request with flight number payload.
        response = self.client.post(
            reverse("itinerary:flight_lookup"),
            data=json.dumps({"flight_number": "UA123"}),
            content_type="application/json",
        )

        # Confirm JSON payload echoes the mock data.
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["airline"], "United")
        self.assertEqual(payload["arrival_airport"], "DEN")

    def test_find_itinerary_redirects_on_success(self):
        """Resolve a known access code and redirect to detail view."""
        # Build itinerary record to look up.
        itinerary = Itinerary.objects.create(
            destination="Tokyo",
            wake_up_time=time(8, 0),
            bed_time=time(22, 0),
            start_date=date(2025, 3, 1),
            end_date=date(2025, 3, 3),
            num_days=3,
        )

        # Post the matching access code.
        response = self.client.post(
            reverse("itinerary:find_itinerary"),
            {"access_code": itinerary.access_code},
        )

        # Ensure the user is redirected to the itinerary detail page.
        self.assertEqual(response.status_code, 302)
        self.assertIn(itinerary.access_code, response.url)


class PromptBuilderTests(TestCase):
    """Exercise the AI prompt assembly helper."""

    def setUp(self):
        self.itinerary = Itinerary.objects.create(
            destination="Lisbon",
            wake_up_time=time(7, 30),
            bed_time=time(22, 30),
            start_date=date(2025, 5, 1),
            end_date=date(2025, 5, 3),
            num_days=3,
            trip_purpose="leisure",
            energy_level="high",
            include_breakfast=True,
            include_lunch=False,
            include_dinner=False,
            arrival_airport="LIS",
            arrival_airline="TAP",
            arrival_datetime=timezone.make_aware(datetime(2025, 5, 1, 8, 0)),
            departure_airport="LIS",
            departure_airline="TAP",
            departure_datetime=timezone.make_aware(datetime(2025, 5, 3, 20, 0)),
            auto_suggest_hotel=True,
            overall_budget_max=Decimal("2000"),
        )
        Day.objects.create(
            itinerary=self.itinerary,
            day_number=1,
            date=date(2025, 5, 1),
            notes="Meet friends",
            must_do="Pastel de nata tasting",
        )

    def test_prompt_mentions_flights_and_hotel(self):
        """Verify flights, hotels, and budgets are surfaced in the prompt."""
        # Build prompt text for the configured itinerary.
        prompt = _build_ai_prompt(self.itinerary)

        # Confirm various sections are present.
        self.assertIn("Flights:", prompt)
        self.assertIn("Hotel / lodging:", prompt)
        self.assertIn("Budget categories:", prompt)
        self.assertIn("Need Wanderly to recommend", prompt)

    def test_prompt_respects_meal_choices(self):
        """Ensure meal toggles alter the prompt text."""
        # Disable all meals.
        self.itinerary.include_breakfast = False
        self.itinerary.include_lunch = False
        self.itinerary.include_dinner = False
        self.itinerary.save()

        # Build prompt and verify the fallback instruction.
        prompt = _build_ai_prompt(self.itinerary)
        self.assertIn("No planned meals", prompt)


class OpenAIIntegrationTests(TestCase):
    """Test OpenAI API integration scenarios."""

    def setUp(self):
        self.client = Client()
        self.url = reverse("itinerary:itinerary")
        self.post_data = {
            "destination": "Tokyo",
            "place_id": "tokyo",
            "latitude": "35.6762",
            "longitude": "139.6503",
            "num_days": 1,
            "start_date": "2025-02-01",
            "end_date": "2025-02-01",
            "wake_up_time": "07:00",
            "bed_time": "23:00",
            "energy_level": "high",
            "include_breakfast": "on",
            "include_lunch": "on",
            "include_dinner": "on",
            "dietary_notes": "",
            "mobility_notes": "",
            "trip_purpose": "adventure",
            "party_adults": 1,
            "party_children": 0,
            "arrival_datetime": "",
            "arrival_airport": "",
            "departure_datetime": "",
            "departure_airport": "",
            "overall_budget_min": "500",
            "overall_budget_max": "1500",
            "activity_priorities": "",
            "mood_tags": "",
            "break_start_time[]": ["12:00"],
            "break_end_time[]": ["13:00"],
            "break_purpose[]": ["Lunch"],
            "budget_category[]": ["Food"],
            "budget_custom_category[]": [""],
            "budget_amount[]": ["1000"],
            "day_1_date": "2025-02-01",
            "day_1_notes": "Explore temples",
            "day_1_must_do": "Senso-ji Temple",
        }

    def _mock_openai(self, mock_openai, ai_data=None):
        """Return a MagicMock configured for OpenAI responses."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(ai_data or {"days": []})
        mock_client.chat.completions.create.return_value = mock_response
        return mock_client

    @patch("itinerary.views.OpenAI")
    def test_openai_client_created_with_api_key(self, mock_openai):
        """Ensure the OpenAI client is instantiated with the configured key."""
        # Prepare mock and submit form within overridden settings.
        self._mock_openai(mock_openai)
        with self.settings(OPENAI_API_KEY="test-key"):
            self.client.post(self.url, self.post_data)

        # Confirm client factory was called with that key.
        mock_openai.assert_called_once_with(api_key="test-key")

    @patch("itinerary.views.OpenAI")
    def test_ai_itinerary_stored_in_session(self, mock_openai):
        """Persist AI response and surface it in the redirect."""
        # Mock a simple AI payload.
        ai_data = {"days": [{"day_number": 1, "title": "Day 1", "activities": []}]}
        self._mock_openai(mock_openai, ai_data)

        # Submit itinerary and follow redirect.
        response = self.client.post(self.url, self.post_data, follow=True)

        # Confirm itinerary JSON persisted and appears in context.
        itinerary = Itinerary.objects.first()
        self.assertEqual(itinerary.ai_itinerary, ai_data["days"])
        rendered_days = response.context["ai_itinerary_days"]
        simplified = [{k: v for k, v in day.items() if k != "form_day"} for day in rendered_days]
        self.assertEqual(simplified, ai_data["days"])

    @patch("itinerary.views.OpenAI")
    def test_openai_error_shows_message_but_creates_itinerary(self, mock_openai):
        """Surface an error when OpenAI fails but still persist data."""
        # Force OpenAI to raise an error.
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = OpenAIError("API Error")

        # Submit itinerary and follow redirect.
        response = self.client.post(self.url, self.post_data, follow=True)

        # Ensure the itinerary exists and error message was logged.
        self.assertEqual(Itinerary.objects.count(), 1)
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(
            any("We were unable to generate an AI-powered itinerary" in str(msg) for msg in messages)
        )

    @patch("itinerary.views.OpenAI")
    def test_prompt_handles_empty_break_times_and_budget(self, mock_openai):
        """Validate prompt text handles missing breaks and budgets."""
        # Mock OpenAI to capture prompt payload.
        mock_client = self._mock_openai(mock_openai)

        # Submit data without breaks or budgets.
        data = self.post_data.copy()
        data["break_start_time[]"] = []
        data["break_end_time[]"] = []
        data["budget_category[]"] = []
        data["budget_amount[]"] = []
        self.client.post(self.url, data)

        # Examine the generated user message.
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        user_message = call_kwargs["messages"][0]["content"]
        self.assertIn("Break windows: None", user_message)
        self.assertIn("Budget categories: Flexible", user_message)


class ItineraryDetailTemplateTests(TestCase):
    """Ensure the itinerary detail template renders review controls properly."""

    def setUp(self):
        arrival_dt = timezone.make_aware(datetime(2025, 3, 1, 8, 0))
        departure_dt = timezone.make_aware(datetime(2025, 3, 5, 18, 0))
        self.itinerary = Itinerary.objects.create(
            destination="Paris",
            wake_up_time=time(8, 0),
            bed_time=time(22, 0),
            start_date=date(2025, 3, 1),
            end_date=date(2025, 3, 5),
            trip_purpose="leisure",
            party_adults=2,
            party_children=0,
            arrival_airport="CDG",
            arrival_datetime=arrival_dt,
            departure_airport="CDG",
            departure_datetime=departure_dt,
        )
        self.itinerary.ai_itinerary = [
            {
                "day_number": 1,
                "title": "Arrival & Exploration",
                "activities": [
                    {
                        "time": "9:00 AM",
                        "name": "Morning Coffee Tour",
                        "description": "Taste the best cafés in town.",
                        "duration": "2 hours",
                        "cost_estimate": "$40",
                        "place_query": "Morning Coffee Tour Paris",
                        "requires_place": True,
                    },
                    {
                        "time": "10:00 PM",
                        "name": "Hotel Wind-Down",
                        "description": "Rest at the hotel.",
                        "duration": "1 hour",
                        "cost_estimate": "$0",
                        "place_query": "",
                        "requires_place": False,
                    },
                ],
            }
        ]
        self.itinerary.save(update_fields=["ai_itinerary"])
        Day.objects.create(
            itinerary=self.itinerary,
            day_number=1,
            date=date(2025, 3, 1),
            notes="Visit Louvre",
            must_do="Louvre highlights tour",
            constraints="Dinner at 8 PM",
            wake_override=time(9, 0),
            bed_override=time(23, 0),
        )

    def _get_detail_response(self):
        url = reverse("itinerary:itinerary_detail", args=[self.itinerary.access_code])
        return self.client.get(url)

    def test_activity_rating_display(self):
        """Check that rating placeholders render for place-bound activities."""
        # Render itinerary detail page.
        response = self._get_detail_response()
        html = response.content.decode()

        # Validate rating badge markup for the first activity.
        self.assertIn('class="activity-rating badge bg-light text-dark" data-rating', html)
        self.assertIn("Morning Coffee Tour Paris", html)

    def test_reviews_button_state(self):
        """Ensure reviews button is disabled until JS loads details."""
        # Render itinerary detail page.
        response = self._get_detail_response()
        html = response.content.decode()

        # Confirm disabled state is present.
        self.assertIn('data-review-btn disabled', html)

    def test_reviews_modal_functionality(self):
        """Confirm ARIA attributes exist on the reviews modal."""
        # Render itinerary detail page.
        response = self._get_detail_response()
        html = response.content.decode()

        # Ensure modal markup exists with accessible attributes.
        self.assertIn('id="reviewsModal"', html)
        self.assertIn('role="dialog"', html)
        self.assertIn('id="reviewsPlaceTitle"', html)
        self.assertIn('id="reviewsList"', html)
