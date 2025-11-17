import pytest
from django.urls import reverse
from django.test import Client
from mood.models import MoodResponse
from mood.forms import MoodForm
from unittest.mock import patch, MagicMock
import json
from django.contrib.messages import get_messages
from openai import OpenAIError


@pytest.mark.django_db
class TestMoodResponse:
    """Test the MoodResponse model"""

    def test_create_mood_response(self):
        response = MoodResponse.objects.create(
            destination='Paris',
            adventurous=3,
            energy=4,
            what_do_you_enjoy=['hiking', 'museums']
        )
        assert response.id is not None
        assert response.destination == 'Paris'
        assert response.adventurous == 3
        assert response.energy == 4
        assert response.what_do_you_enjoy == ['hiking', 'museums']
        assert response.submitted_at is not None

    def test_mood_response_str(self):
        response = MoodResponse.objects.create(
            destination='Tokyo',
            adventurous=2,
            energy=5,
            what_do_you_enjoy=['hiking']
        )
        assert "Response from" in str(response)
        assert str(response.submitted_at) in str(response)

    def test_json_field_stores_list(self):
        interests = ['hiking', 'water_adventures', 'museums']
        response = MoodResponse.objects.create(
            destination='London',
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
        form_data = {
            'destination': 'Paris',
            'adventurous': '3',
            'energy': '4',
            'what_do_you_enjoy': ['hiking', 'museums']
        }
        form = MoodForm(data=form_data)
        assert form.is_valid(), f"Form errors: {form.errors}"

    def test_form_invalid_adventurous(self):
        form_data = {
            'destination': 'Tokyo',
            'adventurous': '6',  # out of allowed range
            'energy': '3',
            'what_do_you_enjoy': ['hiking']
        }
        form = MoodForm(data=form_data)
        assert not form.is_valid()
        assert 'adventurous' in form.errors

    def test_form_invalid_energy(self):
        form_data = {
            'destination': 'New York',
            'adventurous': '3',
            'energy': '0',  # out of allowed range
            'what_do_you_enjoy': ['hiking']
        }
        form = MoodForm(data=form_data)
        assert not form.is_valid()
        assert 'energy' in form.errors

    def test_form_missing_interests(self):
        form_data = {
            'destination': 'London',
            'adventurous': '3',
            'energy': '4',
            'what_do_you_enjoy': []
        }
        form = MoodForm(data=form_data)
        assert not form.is_valid()
        assert 'what_do_you_enjoy' in form.errors

    def test_form_multiple_interests(self):
        form_data = {
            'destination': 'Barcelona',
            'adventurous': '3',
            'energy': '4',
            'what_do_you_enjoy': ['hiking', 'museums', 'try_new_foods']
        }
        form = MoodForm(data=form_data)
        assert form.is_valid(), f"Form errors: {form.errors}"
        assert len(form.cleaned_data['what_do_you_enjoy']) == 3

    def test_form_fields_exist(self):
        form = MoodForm()
        assert 'destination' in form.fields
        assert 'adventurous' in form.fields
        assert 'energy' in form.fields
        assert 'what_do_you_enjoy' in form.fields

    def test_form_field_labels(self):
        form = MoodForm()
        assert form.fields['destination'].label == "Where are you traveling to?"
        assert form.fields['adventurous'].label == "How adventurous are you feeling?"
        assert form.fields['energy'].label == "What is your energy level?"


@pytest.mark.django_db
class TestMoodViews:
    """Basic view behavior (GET + invalid POST)"""

    @pytest.fixture
    def client(self):
        return Client()

    def test_get_mood_questionnaire(self, client):
        resp = client.get(reverse('mood:mood_questionnaire'))
        assert resp.status_code == 200
        assert 'form' in resp.context
        assert isinstance(resp.context['form'], MoodForm)

    def test_post_invalid_data(self, client):
        form_data = {
            'destination': 'Rome',
            'adventurous': '7',  # invalid
            'energy': '4',
            'what_do_you_enjoy': ['hiking']
        }
        resp = client.post(reverse('mood:mood_questionnaire'), data=form_data)
        assert resp.status_code == 200
        assert 'form' in resp.context
        assert resp.context['form'].errors
        assert MoodResponse.objects.count() == 0

    def test_post_missing_required_field(self, client):
        form_data = {
            'adventurous': '3',
            'energy': '4',
            # missing destination + interests
        }
        resp = client.post(reverse('mood:mood_questionnaire'), data=form_data)
        assert resp.status_code == 200
        assert resp.context['form'].errors
        assert MoodResponse.objects.count() == 0


@pytest.mark.django_db
class TestIntegrationAndAIHandling:
    """Covers JSON list/object, noisy extraction, no-JSON error, and exception paths."""

    @pytest.fixture
    def client(self):
        return Client()

    def _mock_openai_response(self, content: str):
        """Utility to build a mock OpenAI client that returns `content` as message.content."""
        mock_openai_instance = MagicMock()
        mock_message = MagicMock()
        mock_message.content = content
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]
        mock_openai_instance.chat.completions.create.return_value = mock_completion
        return mock_openai_instance

    def _valid_form_data(self):
        return {
            'destination': 'Paris',
            'adventurous': '4',
            'energy': '5',
            'what_do_you_enjoy': ['hiking', 'try_new_foods', 'museums']
        }

    @patch('mood.views.OpenAI')
    def test_json_already_a_list(self, mock_openai_class, client):
        """Happy path: AI returns a JSON list."""
        mock_openai_class.return_value = self._mock_openai_response(
            json.dumps([{"activity": "hiking", "reason": "You like outdoors"}])
        )
        resp = client.post(reverse('mood:mood_questionnaire'), data=self._valid_form_data())
        assert resp.status_code == 200

        # DB row saved
        assert MoodResponse.objects.count() == 1

        # Context pieces
        assert 'activities' in resp.context
        assert isinstance(resp.context['activities'], list)
        assert len(resp.context['activities']) >= 1
        assert resp.context.get('error') in (None, "", False)

        # mood_response_id included
        assert 'mood_response_id' in resp.context
        assert isinstance(resp.context['mood_response_id'], int)

    @patch('mood.views.OpenAI')
    def test_json_single_object_wrapped_into_list(self, mock_openai_class, client):
        """AI returns a single JSON object -> view should wrap into a list."""
        mock_openai_class.return_value = self._mock_openai_response(
            json.dumps({"activity": "museums", "reason": "You enjoy culture"})
        )
        resp = client.post(reverse('mood:mood_questionnaire'), data=self._valid_form_data())
        assert resp.status_code == 200
        assert MoodResponse.objects.count() == 1
        assert 'activities' in resp.context
        assert isinstance(resp.context['activities'], list)
        assert len(resp.context['activities']) == 1
        assert 'mood_response_id' in resp.context

    @patch('mood.views.OpenAI')
    def test_messy_text_with_embedded_json_array(self, mock_openai_class, client):
        """AI returns extra prose with an embedded [...] JSON array -> regex extraction branch."""
        messy = (
            "Sure! Here are ideas you'll love:\n\n"
            "Some preface text users shouldn't see.\n"
            "[{\"activity\": \"street_food_tour\"}, {\"activity\": \"river_walk\"}]"
            "\nHope that helps!"
        )
        mock_openai_class.return_value = self._mock_openai_response(messy)

        resp = client.post(reverse('mood:mood_questionnaire'), data=self._valid_form_data())
        assert resp.status_code == 200
        assert MoodResponse.objects.count() == 1
        assert 'activities' in resp.context
        assert isinstance(resp.context['activities'], list)
        assert len(resp.context['activities']) == 2
        assert resp.context.get('error') in (None, "", False)
        assert 'mood_response_id' in resp.context

    @patch('mood.views.OpenAI')
    def test_no_json_found_sets_error_and_empty_activities(self, mock_openai_class, client):
        """AI returns text with no JSON -> error path with activities == []."""
        mock_openai_class.return_value = self._mock_openai_response(
            "Totally unstructured opinionated paragraph with zero JSON."
        )
        resp = client.post(reverse('mood:mood_questionnaire'), data=self._valid_form_data())
        assert resp.status_code == 200
        assert MoodResponse.objects.count() == 1  # DB save still happens before AI parse
        assert 'activities' in resp.context
        assert resp.context['activities'] == []
        # Error string present
        assert resp.context.get('error')
        assert 'mood_response_id' in resp.context
