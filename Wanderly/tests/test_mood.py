import pytest
from django.urls import reverse
from django.test import Client
from mood.models import MoodResponse
from mood.forms import MoodForm
from unittest.mock import patch, MagicMock
import json

@pytest.mark.django_db
class TestMoodResponse:
    """Test the MoodResponse model"""
    
    def test_create_mood_response(self):
        """Test creating a mood response"""
        response = MoodResponse.objects.create(
            adventurous=3,
            energy=4,
            what_do_you_enjoy=['hiking', 'museums']
        )
        assert response.id is not None
        assert response.adventurous == 3
        assert response.energy == 4
        assert response.what_do_you_enjoy == ['hiking', 'museums']
        assert response.submitted_at is not None
    
    def test_mood_response_str(self):
        """Test string representation of mood response"""
        response = MoodResponse.objects.create(
            adventurous=2,
            energy=5,
            what_do_you_enjoy=['hiking']
        )
        assert "Response from" in str(response)
        assert str(response.submitted_at) in str(response)
    
    def test_json_field_stores_list(self):
        """Test that JSONField correctly stores list data"""
        interests = ['hiking', 'water_adventures', 'museums']
        response = MoodResponse.objects.create(
            adventurous=1,
            energy=1,
            what_do_you_enjoy=interests
        )
        response.refresh_from_db()
        assert response.what_do_you_enjoy == interests
        assert isinstance(response.what_do_you_enjoy, list)


@pytest.mark.django_db
class TestMoodForm:
    """Test the MoodForm"""
    
    def test_form_valid_data(self):
        """Test form with valid data"""
        form_data = {
            'adventurous': '3',
            'energy': '4',
            'what_do_you_enjoy': ['hiking', 'museums']
        }
        form = MoodForm(data=form_data)
        assert form.is_valid()
    
    def test_form_invalid_adventurous(self):
        """Test form with invalid adventurous value"""
        form_data = {
            'adventurous': '6', 
            'energy': '3',
            'what_do_you_enjoy': ['hiking']
        }
        form = MoodForm(data=form_data)
        assert not form.is_valid()
        assert 'adventurous' in form.errors
    
    def test_form_invalid_energy(self):
        """Test form with invalid energy value"""
        form_data = {
            'adventurous': '3',
            'energy': '0',  # Out of range
            'what_do_you_enjoy': ['hiking']
        }
        form = MoodForm(data=form_data)
        assert not form.is_valid()
        assert 'energy' in form.errors
    
    def test_form_missing_interests(self):
        """Test form without interests selected"""
        form_data = {
            'adventurous': '3',
            'energy': '4',
            'what_do_you_enjoy': []
        }
        form = MoodForm(data=form_data)
        assert not form.is_valid()
        assert 'what_do_you_enjoy' in form.errors
    
    def test_form_multiple_interests(self):
        """Test form with multiple interests"""
        form_data = {
            'adventurous': '3',
            'energy': '4',
            'what_do_you_enjoy': ['hiking', 'museums', 'try_new_foods']
        }
        form = MoodForm(data=form_data)
        assert form.is_valid()
        assert len(form.cleaned_data['what_do_you_enjoy']) == 3
    
    def test_form_fields_exist(self):
        """Test that all expected fields exist"""
        form = MoodForm()
        assert 'adventurous' in form.fields
        assert 'energy' in form.fields
        assert 'what_do_you_enjoy' in form.fields
    
    def test_form_field_labels(self):
        """Test form field labels"""
        form = MoodForm()
        assert form.fields['adventurous'].label == "How adventurous are you feeling?"
        assert form.fields['energy'].label == "What is your energy level?"


@pytest.mark.django_db
class TestMoodViews_Basics:
    """Basic questionnaire view tests (GET/POST)"""

    @pytest.fixture
    def client(self):
        return Client()
    
    def test_get_mood_questionnaire(self, client):
        """GET shows the form"""
        response = client.get(reverse('mood:mood_questionnaire'))
        assert response.status_code == 200
        assert 'form' in response.context
        assert isinstance(response.context['form'], MoodForm)

    def test_post_invalid_data(self, client):
        """POST invalid keeps you on form and does not create DB rows"""
        form_data = {
            'adventurous': '7',  # Invalid
            'energy': '4',
            'what_do_you_enjoy': ['hiking']
        }
        response = client.post(reverse('mood:mood_questionnaire'), data=form_data)
        assert response.status_code == 200
        assert 'form' in response.context
        assert response.context['form'].errors
        assert MoodResponse.objects.count() == 0
    
    def test_post_missing_required_field(self, client):
        """Missing interests -> error and no DB rows"""
        form_data = {
            'adventurous': '3',
            'energy': '4',
            # missing what_do_you_enjoy
        }
        response = client.post(reverse('mood:mood_questionnaire'), data=form_data)
        assert response.status_code == 200
        assert response.context['form'].errors
        assert MoodResponse.objects.count() == 0


@pytest.mark.django_db
class TestMoodViews_QuestionnaireMarkup:
    """Ensure critical questionnaire markup/content is present—labels, options, CSRF"""

    @pytest.fixture
    def client(self):
        return Client()

    def test_questionnaire_contains_labels_and_options(self, client):
        resp = client.get(reverse('mood:mood_questionnaire'))
        html = resp.content.decode()
        # Labels present
        assert "How adventurous are you feeling?" in html
        assert "What is your energy level?" in html
        # Interests options present (checkbox values/labels from template)
        assert 'id="interest_hiking"' in html
        assert 'value="water_adventures"' in html
        assert 'value="sight_seeing"' in html
        assert 'value="museums"' in html
        assert 'value="try_new_foods"' in html
        assert 'value="concert_sporting"' in html
        assert 'value="local_market"' in html
        # CSRF token field present
        assert 'csrfmiddlewaretoken' in html


@pytest.mark.django_db
class TestIntegrationAndAIHandling:
    """Integration tests for the complete flow + AI JSON parsing behaviors"""

    @pytest.fixture
    def client(self):
        return Client()

    def _valid_form_data(self):
        return {
            'adventurous': '4',
            'energy': '5',
            'what_do_you_enjoy': ['hiking', 'try_new_foods', 'museums']
        }

    @patch('mood.views.OpenAI')
    def test_complete_user_flow_array(self, mock_openai_class, client):
        """Happy path: AI returns an array of activities"""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_msg = MagicMock()
        mock_msg.content = json.dumps([
            {
                "title": "Sunrise Hike",
                "description": "Catch stunning views on a moderate trail",
                "why_recommended": "Matches high energy + adventurous",
                "duration": "2-3 hours",
                "type": "outdoor"
            }
        ])
        mock_choice = MagicMock(message=mock_msg)
        mock_completion = MagicMock(choices=[mock_choice])
        mock_client.chat.completions.create.return_value = mock_completion

        # GET -> show form
        r1 = client.get(reverse('mood:mood_questionnaire'))
        assert r1.status_code == 200

        # POST -> results page
        r2 = client.post(reverse('mood:mood_questionnaire'), data=self._valid_form_data())
        assert r2.status_code == 200
        assert MoodResponse.objects.count() == 1
        assert r2.context['activities'] and isinstance(r2.context['activities'], list)
        # The title should render on the page
        assert "Sunrise Hike" in r2.content.decode()
        # Results page shows mood badges/summary
        assert "Your Mood Profile" in r2.content.decode()

    @patch('mood.views.OpenAI')
    def test_ai_returns_single_object_wrapped_into_list(self, mock_openai_class, client):
        """AI returns a single object; view should wrap to a list"""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_msg = MagicMock()
        mock_msg.content = json.dumps({
            "title": "Food Truck Crawl",
            "description": "Try multiple new foods downtown",
            "why_recommended": "High energy & food interest",
            "duration": "1-2 hours",
            "type": "food"
        })
        mock_choice = MagicMock(message=mock_msg)
        mock_completion = MagicMock(choices=[mock_choice])
        mock_client.chat.completions.create.return_value = mock_completion

        r = client.post(reverse('mood:mood_questionnaire'), data=self._valid_form_data())
        assert r.status_code == 200
        assert isinstance(r.context['activities'], list)
        assert len(r.context['activities']) == 1
        assert "Food Truck Crawl" in r.content.decode()

    @patch('mood.views.OpenAI')
    def test_ai_messy_text_with_array_extraction(self, mock_openai_class, client):
        """AI returns extra text around a JSON array; regex extraction should parse it"""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        messy = """
        Sure, here are some ideas:
        [
          {"title": "Museum Hop", "description": "Explore local museums", "why_recommended": "You like museums", "duration": "2 hrs", "type": "indoor"},
          {"title": "Local Market Visit", "description": "Browse artisan goods", "why_recommended": "Matches interest in markets", "duration": "1-2 hrs", "type": "shopping"}
        ]
        Enjoy!
        """
        mock_msg = MagicMock()
        mock_msg.content = messy
        mock_choice = MagicMock(message=mock_msg)
        mock_completion = MagicMock(choices=[mock_choice])
        mock_client.chat.completions.create.return_value = mock_completion

        r = client.post(reverse('mood:mood_questionnaire'), data=self._valid_form_data())
        assert r.status_code == 200
        acts = r.context['activities']
        assert isinstance(acts, list) and len(acts) == 2
        html = r.content.decode()
        assert "Museum Hop" in html
        assert "Local Market Visit" in html

    @patch('mood.views.OpenAI')
    def test_ai_no_json_shows_friendly_error(self, mock_openai_class, client):
        """No JSON at all -> user sees a friendly error and no activities"""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_msg = MagicMock()
        mock_msg.content = "Here's a poem about hiking instead of JSON."
        mock_choice = MagicMock(message=mock_msg)
        mock_completion = MagicMock(choices=[mock_choice])
        mock_client.chat.completions.create.return_value = mock_completion

        r = client.post(reverse('mood:mood_questionnaire'), data=self._valid_form_data())
        assert r.status_code == 200
        assert r.context['activities'] == []
        assert r.context['error']  # error message surfaced
        # Error banner visible on results template
        assert "Could not parse activity recommendations" in r.content.decode()

    @patch('mood.views.OpenAI')
    def test_openai_exception_is_handled(self, mock_openai_class, client):
        """If OpenAI call throws, an error should be shown and activities empty"""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = RuntimeError("boom")

        r = client.post(reverse('mood:mood_questionnaire'), data=self._valid_form_data())
        assert r.status_code == 200
        assert r.context['activities'] == []
        assert r.context['error']
        assert "Error getting recommendations" in r.content.decode()

    @patch('mood.views.OpenAI')
    def test_context_contains_mood_response_id(self, mock_openai_class, client):
        """Ensure mood_response_id is included in results context"""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_msg = MagicMock()
        mock_msg.content = json.dumps([{
            "title": "Evening Walk", "description": "Light walk", "why_recommended": "Chill", "duration": "45m", "type": "outdoor"
        }])
        mock_choice = MagicMock(message=mock_msg)
        mock_completion = MagicMock(choices=[mock_choice])
        mock_client.chat.completions.create.return_value = mock_completion

        r = client.post(reverse('mood:mood_questionnaire'), data=self._valid_form_data())
        assert r.status_code == 200
        assert 'mood_response_id' in r.context
        # The saved object exists and id matches type
        assert isinstance(r.context['mood_response_id'], int)

    @patch('mood.views.OpenAI')
    def test_results_renders_interest_badges_and_profile(self, mock_openai_class, client):
        """Results page shows interests as badges and the mood profile header"""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_msg = MagicMock()
        mock_msg.content = json.dumps([])
        mock_choice = MagicMock(message=mock_msg)
        mock_completion = MagicMock(choices=[mock_choice])
        mock_client.chat.completions.create.return_value = mock_completion

        data = {
            'adventurous': '2',
            'energy': '3',
            'what_do_you_enjoy': ['museums', 'local_market']
        }
        r = client.post(reverse('mood:mood_questionnaire'), data=data)
        html = r.content.decode()
        # Mood summary section + badges
        assert "Your Mood Profile" in html  # summary header
        assert "museums" in html and "local_market" in html  # badges rendered

    @patch('mood.views.OpenAI')
    def test_results_supports_name_and_why_fields(self, mock_openai_class, client):
        """Template supports 'name' in place of 'title' and 'why' in place of 'description'"""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        # Use alternate keys that the template knows how to display
        payload = [{
            "name": "Downtown Stroll",
            "why": "Gentle, low-key activity when energy is moderate",
            "type": "leisure",
            "duration": "1 hour",
            "why_recommended": "Matches interests, easy to do nearby"
        }]
        mock_msg = MagicMock()
        mock_msg.content = json.dumps(payload)
        mock_choice = MagicMock(message=mock_msg)
        mock_completion = MagicMock(choices=[mock_choice])
        mock_client.chat.completions.create.return_value = mock_completion

        r = client.post(reverse('mood:mood_questionnaire'), data=self._valid_form_data())
        html = r.content.decode()
        assert "Downtown Stroll" in html
        assert "Gentle, low-key activity when energy is moderate" in html
