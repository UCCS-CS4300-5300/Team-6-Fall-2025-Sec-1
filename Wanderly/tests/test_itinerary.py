"""
Unit tests for itinerary views.py
"""
from datetime import date, datetime, time

import json
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.conf import settings
from django.utils import timezone

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

from django.urls import include, path, reverse
from django.contrib.messages import get_messages
from django.test import TestCase, Client
from openai import OpenAIError

from itinerary.models import Itinerary, BreakTime, BudgetItem, Day
from itinerary.forms import ItineraryForm

# Minimal URL configuration that mirrors how the app is namespaced in production.
urlpatterns = [
    path("", include(("itinerary.urls", "itinerary"), namespace="itinerary")),
]


class ItineraryViewTests(TestCase):
    """Test itinerary view GET and POST requests"""

    def setUp(self):
        self.client = Client()
        self.url = reverse('itinerary:itinerary')
        self.valid_post_data = {
            'destination': 'Paris',
            'place_id': 'some-place',
            'latitude': '48.8566',
            'longitude': '2.3522',
            'num_days': 2,
            'start_date': '2025-01-01',
            'end_date': '2025-01-02',
            'wake_up_time': '08:00',
            'bed_time': '22:00',
            'energy_level': 'balanced',
            'include_breakfast': 'on',
            'include_lunch': 'on',
            'include_dinner': 'on',
            'dietary_notes': '',
            'mobility_notes': '',
            'trip_purpose': 'leisure',
            'party_adults': 2,
            'party_children': 0,
            'arrival_datetime': '',
            'arrival_airport': '',
            'departure_datetime': '',
            'departure_airport': '',
            'overall_budget_min': '1000',
            'overall_budget_max': '2500',
            'activity_priorities': '1. Eiffel Tower\n2. Seine Cruise',
            'mood_tags': 'relaxing,cultural',
            'break_start_time[]': ['12:00'],
            'break_end_time[]': ['13:00'],
            'break_purpose[]': ['Lunch'],
            'budget_category[]': ['Food'],
            'budget_custom_category[]': [''],
            'budget_amount[]': ['500'],
            'day_1_date': '2025-01-01',
            'day_1_notes': 'Visit Eiffel Tower',
            'day_1_must_do': 'Eiffel Tower top view',
            'day_2_date': '2025-01-02',
            'day_2_notes': '',
            'day_2_must_do': '',
        }

    def _mock_openai(self, mock_openai, ai_response=None):
        """Helper to setup OpenAI mock"""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(ai_response or {"days": []})
        mock_client.chat.completions.create.return_value = mock_response
        return mock_client

    def test_get_request_success(self):
        """Test GET request returns form and template"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'itinerary.html')
        self.assertIsInstance(response.context['form'], ItineraryForm)

    def test_get_retrieves_ai_itinerary_from_session(self):
        """Test GET request does not include ai_itinerary_days in context"""
        response = self.client.get(self.url)

        # ai_itinerary_days should not be in context for the itinerary form view
        self.assertNotIn('ai_itinerary_days', response.context)

    @patch('itinerary.views.OpenAI')
    def test_post_creates_itinerary_and_related_objects(self, mock_openai):
        """Test POST creates itinerary, break times, budget items, and days"""
        self._mock_openai(mock_openai)
        
        response = self.client.post(self.url, self.valid_post_data)
        
        # Check itinerary created
        self.assertEqual(Itinerary.objects.count(), 1)
        itinerary = Itinerary.objects.first()
        self.assertEqual(itinerary.destination, 'Paris')
        self.assertEqual(itinerary.num_days, 2)
        
        # Check break times created
        self.assertEqual(BreakTime.objects.count(), 1)
        break_time = BreakTime.objects.first()
        self.assertEqual(str(break_time.start_time), '12:00:00')
        
        # Check budget items created
        self.assertEqual(BudgetItem.objects.count(), 1)
        budget = BudgetItem.objects.first()
        self.assertEqual(budget.category, 'Food')
        self.assertEqual(budget.amount, Decimal('500'))
        
        # Check days created
        self.assertEqual(Day.objects.count(), 2)

    @patch('itinerary.views.OpenAI')
    def test_post_skips_empty_values(self, mock_openai):
        """Test empty break times, budgets, and dates are skipped"""
        self._mock_openai(mock_openai)
        
        data = self.valid_post_data.copy()
        data['break_start_time[]'] = ['12:00', '']
        data['break_end_time[]'] = ['13:00', '']
        data['budget_amount[]'] = ['500', '']
        data['day_2_date'] = ''
        
        response = self.client.post(self.url, data)
        
        self.assertEqual(BreakTime.objects.count(), 1)
        self.assertEqual(BudgetItem.objects.count(), 1)
        self.assertEqual(Day.objects.count(), 1)

    @patch('itinerary.views.OpenAI')
    def test_post_handles_custom_budget_category(self, mock_openai):
        """Test custom budget category handling"""
        self._mock_openai(mock_openai)
        
        data = self.valid_post_data.copy()
        data['budget_category[]'] = ['Other']
        data['budget_custom_category[]'] = ['Souvenirs']
        
        response = self.client.post(self.url, data)
        
        budget = BudgetItem.objects.first()
        self.assertEqual(budget.category, 'Other')
        self.assertEqual(budget.custom_category, 'Souvenirs')

    @patch('itinerary.views.OpenAI')
    def test_post_redirects_with_success_message(self, mock_openai):
        """Test successful POST redirects with success message"""
        self._mock_openai(mock_openai)
        
        response = self.client.post(self.url, self.valid_post_data, follow=True)
        
        self.assertEqual(response.status_code, 200)
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any('Itinerary created successfully' in str(m) for m in messages))

    def test_invalid_form_shows_error(self):
        """Test invalid form displays error message"""
        invalid_data = {
            'destination': '',
            'start_date': '2025-01-01',
            'end_date': '2025-01-03',
            'num_days': 3,
            'wake_up_time': '08:00',
            'bed_time': '22:00',
            'energy_level': 'balanced',
            'trip_purpose': 'leisure',
            'party_adults': 1,
            'party_children': 0,
        }
        response = self.client.post(self.url, invalid_data)
        
        self.assertEqual(Itinerary.objects.count(), 0)
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any('Please correct the errors below' in str(m) for m in messages))


class OpenAIIntegrationTests(TestCase):
    """Test OpenAI API integration"""

    def setUp(self):
        self.client = Client()
        self.url = reverse('itinerary:itinerary')
        self.post_data = {
            'destination': 'Tokyo',
            'place_id': 'tokyo',
            'latitude': '35.6762',
            'longitude': '139.6503',
            'num_days': 1,
            'start_date': '2025-02-01',
            'end_date': '2025-02-01',
            'wake_up_time': '07:00',
            'bed_time': '23:00',
            'energy_level': 'high',
            'include_breakfast': 'on',
            'include_lunch': 'on',
            'include_dinner': 'on',
            'dietary_notes': '',
            'mobility_notes': '',
            'trip_purpose': 'adventure',
            'party_adults': 1,
            'party_children': 0,
            'arrival_datetime': '',
            'arrival_airport': '',
            'departure_datetime': '',
            'departure_airport': '',
            'overall_budget_min': '500',
            'overall_budget_max': '1500',
            'activity_priorities': '',
            'mood_tags': '',
            'break_start_time[]': ['12:00'],
            'break_end_time[]': ['13:00'],
            'break_purpose[]': ['Lunch'],
            'budget_category[]': ['Food'],
            'budget_custom_category[]': [''],
            'budget_amount[]': ['1000'],
            'day_1_date': '2025-02-01',
            'day_1_notes': 'Explore temples',
            'day_1_must_do': 'Senso-ji Temple',
        }

    def _mock_openai(self, mock_openai, ai_data=None):
        """Helper to setup OpenAI mock"""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(ai_data or {"days": []})
        mock_client.chat.completions.create.return_value = mock_response
        return mock_client

    @patch('itinerary.views.OpenAI')
    def test_openai_client_created_with_api_key(self, mock_openai):
        """Test OpenAI client instantiated with API key"""
        self._mock_openai(mock_openai)
        
        with self.settings(OPENAI_API_KEY='test-key'):
            self.client.post(self.url, self.post_data)
        
        mock_openai.assert_called_once_with(api_key='test-key')



    @patch('itinerary.views.OpenAI')
    def test_ai_itinerary_stored_in_session(self, mock_openai):
        """Test AI response stored in database and displayed on detail page"""
        ai_data = {"days": [{"day_number": 1, "title": "Day 1", "activities": []}]}
        self._mock_openai(mock_openai, ai_data)

        response = self.client.post(self.url, self.post_data, follow=True)

        # AI itinerary should be stored in database
        itinerary = Itinerary.objects.first()
        self.assertIsNotNone(itinerary)
        self.assertEqual(itinerary.ai_itinerary, ai_data['days'])

        # And should be available in the detail page context after redirect
        rendered_days = response.context['ai_itinerary_days']
        simplified = [
            {k: v for k, v in day.items() if k != "form_day"}
            for day in rendered_days
        ]
        self.assertEqual(simplified, ai_data['days'])

    @patch('itinerary.views.OpenAI')
    def test_openai_error_shows_message_but_creates_itinerary(self, mock_openai):
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = OpenAIError("API Error")
        
        response = self.client.post(self.url, self.post_data, follow=True)
        
        self.assertEqual(Itinerary.objects.count(), 1)
        
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(
            any('We were unable to generate an AI-powered itinerary at this time.' in str(m)
                for m in messages)
        )

    @patch('itinerary.views.OpenAI')
    def test_prompt_handles_empty_break_times_and_budget(self, mock_openai):
        """Test prompt formatting with no breaks or budget"""
        mock_client = self._mock_openai(mock_openai)
        
        data = self.post_data.copy()
        data['break_start_time[]'] = []
        data['break_end_time[]'] = []
        data['budget_category[]'] = []
        data['budget_amount[]'] = []
        
        self.client.post(self.url, data)
        
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        user_message = call_kwargs['messages'][0]['content']
        
        self.assertIn('None', user_message)  # Break times
        self.assertIn('Flexible', user_message)  # Budget


# Template-focused tests for itinerary_detail.html.
class ItineraryDetailTemplateTests(TestCase):
    """Ensure the itinerary detail template renders expected review controls."""

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
                    }
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
        """The activity card includes the rating placeholder and query metadata."""
        response = self._get_detail_response()
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()

        self.assertIn('class="activity-rating badge bg-light text-dark" data-rating', html)
        self.assertIn("Loading...", html)
        self.assertIn(
            'data-place-query="Morning Coffee Tour Paris"',
            html,
        )

    def test_reviews_button_state(self):
        """Reviews buttons render disabled initially to prevent premature clicks."""
        response = self._get_detail_response()
        html = response.content.decode()
        self.assertIn('data-review-btn disabled', html)

    def test_reviews_modal_functionality(self):
        """Modal markup includes the ARIA roles/targets required for accessibility."""
        response = self._get_detail_response()
        html = response.content.decode()
        self.assertIn('id="reviewsModal"', html)
        self.assertIn('role="dialog"', html)
        self.assertIn('id="reviewsPlaceTitle"', html)
        self.assertIn('id="reviewsList"', html)
