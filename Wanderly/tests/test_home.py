import json
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.templatetags.static import static
from django.urls import reverse
from unittest.mock import patch, Mock
from home.views import text_search, place_photos
import requests

"""
New Google Places API Text Search POST Request Testing
"""
class TextSearchTestCase(TestCase):
    def setUp(self):
        self.c = Client()
        self.url = reverse('text_search')
    
    @patch('home.views.requests.post')
    def test_successful_response(self, mock_post):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            'places': [
                {
                    'displayName': 'Papas Pizzaria',
                    'formattedAddress': "123 ABC Street",
                    'websiteUri': 'www.papaspizzaria.com',
                    'photos': [{'name': 'places/photo1'}],
                }
            ]
        }

        mock_post.return_value = mock_response

        response = self.c.post(
            self.url,
            data=json.dumps({'textQuery': 'Colorado Springs'}),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('places', data)
        self.assertTrue(isinstance(data['places'], list))
        self.assertTrue(data['places'][0]['photos'][0].startswith('/place_photos/'))
    
    def test_missing_text_query(self):        
        response = self.c.post(
            self.url,
            data={},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'textQuery is required')
    
    def test_empty_text_query(self):        
        response = self.c.post(
            self.url,
            data={'textQuery': ''},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'textQuery is required')

    def test_invalid_json(self):
        response = self.c.post(
            self.url,
            data={'invalid json'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'Invalid JSON')

    @patch('home.views.requests.post')
    def test_request_exception(self, mock_post):
        mock_post.side_effect = requests.exceptions.RequestException('API Error')
        
        response = self.c.post(
            self.url,
            data={'textQuery': 'Colorado Springs'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 502)
        self.assertIn('error', response.json())

"""
New Google Places API Place Photos GET Request Testing
"""
class PlacePhotosViewTests(TestCase):
    def setUp(self):
        self.c = Client()

    def test_invalid_photo_name(self):
        response = self.c.get(reverse('place_photos', args=['invalid_name']))
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())

    @patch('home.views.requests.get')
    def test_successful_response_image(self, mock_get):
        mock_response = Mock()
        mock_response.content = b'image-bytes'
        mock_response.headers = {'Content-Type': 'image/jpeg'}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        response = self.c.get(reverse('place_photos', args=['places/photo1']))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/jpeg')

    @patch('home.views.requests.get')
    def test_request_exception_returns_500(self, mock_get):
        mock_get.side_effect = requests.exceptions.RequestException('Network error')
        response = self.c.get(reverse('place_photos', args=['places/photo1']))
        self.assertEqual(response.status_code, 500)
        self.assertIn('error', response.json())

'''
Test the Home Contents
'''
# Exercise the public homepage to ensure the key UI elements render correctly.
class HomePageTests(TestCase):

    def setUp(self):
        self.url = reverse("index")

    # Anonymous visitors should receive a 200 response rendered with the expected template.
    def test_homepage_renders_for_anonymous(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "index.html")

    # Verify the static sections (hero + features + footer) render the expected copy.
    def test_homepage_contains_expected_static_sections(self):
        response = self.client.get(self.url)
        content = response.content.decode()

        # Hero copy
        self.assertIn("Welcome to Wanderly. Here for all your travel planning needs.", content)

        # Main Discovery Section
        self.assertIn("Explore The World Around You", content)
        self.assertIn("Find Your Next Step", content)

    # Ensure the hero image reference matches the expected static asset path.
    def test_homepage_static_images_reference(self):
        expected_src_1 = static("mountains.jpg")
        expected_src_2 = static("water-hut-image.jpg")
        response = self.client.get(self.url)
        self.assertIn(expected_src_1, response.content.decode())
        self.assertIn(expected_src_2, response.content.decode())

    # Anonymous users should see a login call-to-action and no authenticated dropdown.
    def test_anonymous_sees_login_button_only(self):
        response = self.client.get(self.url)
        content = response.content.decode()
        self.assertIn("Log In", content)
        self.assertNotIn("My Portfolios", content)
        self.assertNotIn("Sign Out", content)

    # Signed in users should see the personalized greeting and dropdown options.
    def test_authenticated_user_sees_dropdown(self):
        user = get_user_model().objects.create_user(
            username="alex@example.com",
            email="alex@example.com",
            password="testpass123",
            first_name="Alex",
            last_name="McFly",
        )
        self.client.login(username="alex@example.com", password="testpass123")

        response = self.client.get(self.url)
        content = response.content.decode()

        self.assertIn("Hello, Alex M.", content)
        self.assertIn("My Profile", content)
        self.assertIn(f'href="{reverse("sign_out")}"', content)
    
    # Making sure the access code model is loaded into the home page
    # checking that the name exists in the response
    def test_home_has_access_code_modal(self):
        response = self.client.get("/")
        assert "accessCodeModal" in response.content.decode()
