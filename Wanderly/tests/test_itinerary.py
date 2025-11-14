"""
Unit tests for itinerary views.py
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.messages import get_messages
from unittest.mock import patch, MagicMock
from decimal import Decimal
import json

from itinerary.models import Itinerary, BreakTime, BudgetItem, Day
from itinerary.forms import ItineraryForm


class ItineraryViewTests(TestCase):
    """Test itinerary view GET and POST requests"""

    def setUp(self):
        self.client = Client()
        self.url = reverse('itinerary:itinerary')
        self.valid_post_data = {
            'destination': 'Paris',
            'num_days': 2,
            'wake_up_time': '08:00',
            'bed_time': '22:00',
            'break_start_time[]': ['12:00'],
            'break_end_time[]': ['13:00'],
            'budget_category[]': ['Food'],
            'budget_custom_category[]': [''],
            'budget_amount[]': ['500'],
            'day_1_date': '2025-01-01',
            'day_1_notes': 'Visit Eiffel Tower',
            'day_2_date': '2025-01-02',
            'day_2_notes': '',
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

    def test_get_displays_recent_itineraries(self):
        """Test recent itineraries limited to 5"""
        for i in range(7):
            Itinerary.objects.create(
                destination=f'Destination {i}',
                num_days=3,
                wake_up_time='08:00',
                bed_time='22:00'
            )
        response = self.client.get(self.url)
        self.assertEqual(len(response.context['recent_itineraries']), 5)

    def test_get_retrieves_ai_itinerary_from_session(self):
        """Test AI itinerary retrieved and removed from session"""
        ai_data = [{"day_number": 1, "title": "Day 1", "activities": []}]
        session = self.client.session
        session['ai_itinerary_days'] = json.dumps(ai_data)
        session.save()
        
        response = self.client.get(self.url)
        self.assertEqual(response.context['ai_itinerary_days'], ai_data)
        
        # Should be removed after retrieval
        response = self.client.get(self.url)
        self.assertIsNone(response.context['ai_itinerary_days'])

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
        invalid_data = {'destination': '', 'num_days': 3}
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
            'num_days': 1,
            'wake_up_time': '07:00',
            'bed_time': '23:00',
            'break_start_time[]': ['12:00'],
            'break_end_time[]': ['13:00'],
            'budget_category[]': ['Food'],
            'budget_custom_category[]': [''],
            'budget_amount[]': ['1000'],
            'day_1_date': '2025-02-01',
            'day_1_notes': 'Explore temples',
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
        """Test AI response stored in session"""
        ai_data = {"days": [{"day_number": 1, "title": "Day 1", "activities": []}]}
        self._mock_openai(mock_openai, ai_data)
        
        response = self.client.post(self.url, self.post_data, follow=True)
        
        self.assertEqual(response.context['ai_itinerary_days'], ai_data['days'])

    @patch('itinerary.views.OpenAI')
    def test_openai_error_shows_message_but_creates_itinerary(self, mock_openai):
        """Test API error displays message but still creates itinerary"""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        
        response = self.client.post(self.url, self.post_data, follow=True)
        
        # Itinerary still created
        self.assertEqual(Itinerary.objects.count(), 1)
        
        # Error message shown
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any('Error generating AI itinerary' in str(m) for m in messages))

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