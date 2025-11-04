import json
from django.test import TestCase, Client
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
