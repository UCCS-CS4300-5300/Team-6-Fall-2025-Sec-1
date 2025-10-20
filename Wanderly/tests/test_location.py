import json
from django.test import TestCase, Client
from unittest.mock import patch, Mock
from location_based_discovery.views import text_search
import requests

"""
HTTP Request Testing
"""
class TextSearchTestCase(TestCase):
    def setUp(self):
        self.c = Client()
        self.url = "/location-discovery/text_search/"
    
    @patch('location_based_discovery.views.requests.post')
    def test_successful_response(self, mock_post):
        mock_post.return_value.json.return_value = {
            'places': [
                {
                    'displayName': {'text': 'Papas Pizzaria'},
                    'formattedAddress': "123 ABC Street",
                    'websiteUri': 'www.papaspizzaria.com'
                }
            ]
        }
        mock_post.return_value.raise_for_status = Mock()
        
        response = self.c.post(
            self.url,
            data={'textQuery': 'Colorado Springs'},
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('places', data)
        self.assertEqual(data['places'][0]['displayName']['text'], 'Papas Pizzaria')
    
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

    @patch('location_based_discovery.views.requests.post')
    def test_request_exception(self, mock_post):
        mock_post.side_effect = requests.exceptions.RequestException('API Error')
        
        response = self.c.post(
            self.url,
            data={'textQuery': 'Colorado Springs'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 500)
        self.assertIn('error', response.json())