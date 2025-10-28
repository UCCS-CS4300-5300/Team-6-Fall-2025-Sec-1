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
        # ensure there is a response and that the input matches what is posted
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
        # Refresh from database
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
class TestMoodViews:
    """Test the mood questionnaire views"""
    
    @pytest.fixture
    def client(self):
        """Provide a Django test client"""
        return Client()
    
    def test_get_mood_questionnaire(self, client):
        """Test GET request to mood questionnaire"""
        response = client.get(reverse('mood:mood_questionnaire'))
        assert response.status_code == 200
        assert 'form' in response.context
        assert isinstance(response.context['form'], MoodForm)
    
    
    def test_post_invalid_data(self, client):
        """Test POST request with invalid data"""
        form_data = {
            'adventurous': '7',  # Invalid
            'energy': '4',
            'what_do_you_enjoy': ['hiking']
        }
        response = client.post(reverse('mood:mood_questionnaire'), data=form_data)
        
        #ensure reloads without errors
        assert response.status_code == 200
        assert 'form' in response.context
        assert response.context['form'].errors
        
        assert MoodResponse.objects.count() == 0
    
    def test_post_missing_required_field(self, client):
        """Test POST request with missing required field"""
        form_data = {
            'adventurous': '3',
            'energy': '4',
            # Missing entry
        }
        response = client.post(reverse('mood:mood_questionnaire'), data=form_data)
        
        assert response.status_code == 200
        assert response.context['form'].errors
        assert MoodResponse.objects.count() == 0


@pytest.mark.django_db
class TestIntegration:
    """Integration tests for the complete flow"""
    
    @pytest.fixture
    def client(self):
        return Client()
    
    @patch('mood.views.OpenAI')  # mocks the openai class
    def test_complete_user_flow(self, mock_openai_class, client):
        """Test complete user flow from form to database"""

        # create a mock for openai class
        mock_openai_instance = MagicMock()
        mock_openai_class.return_value = mock_openai_instance

        #creates a mock response with correct structure
        mock_completion = MagicMock()
        mock_message = MagicMock()
        #make sure response can be parsed as  json
        mock_message.content = json.dumps({
            "activity": "hiking",
            "reason": "Based on your adventurous spirit and high energy level, hiking would be perfect!"
        })

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_completion.choices = [mock_choice]

        # mock return
        mock_openai_instance.chat.completions.create.return_value = mock_completion
        
        response = client.get(reverse('mood:mood_questionnaire'))
        assert response.status_code == 200
        
        #post
        form_data = {
            'adventurous': '4',
            'energy': '5',
            'what_do_you_enjoy': ['hiking', 'try_new_foods', 'museums']
        }
        
        response = client.post(reverse('mood:mood_questionnaire'), data=form_data)

        assert response.status_code == 200
        
        # check database
        assert MoodResponse.objects.count() == 1
        mood = MoodResponse.objects.first()
        assert mood.adventurous == 4
        assert mood.energy == 5
        assert len(mood.what_do_you_enjoy) == 3
        
        # ensure timestamp is recent
        from django.utils import timezone
        time_diff = timezone.now() - mood.submitted_at
        assert time_diff.total_seconds() < 5  # Within 5 seconds