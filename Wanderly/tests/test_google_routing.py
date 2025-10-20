import json
from unittest.mock import patch, Mock

import pytest
from django.test import Client
from django.urls import reverse
from django.conf import settings

@pytest.fixture
def client():
    return Client()

def test_route_demo_renders_and_has_browser_key(client):
    url = reverse("route_demo")
    resp = client.get(url)
    assert resp.status_code == 200
    # Context contains the key (provided by settings)
    assert "GOOGLE_MAPS_BROWSER_KEY" in resp.context
    # The rendered HTML should include the Google Maps script with ?key=
    body = resp.content.decode()
    assert "maps.googleapis.com/maps/api/js?key=" in body

def test_compute_route_requires_post(client):
    url = reverse("compute_route")
    resp = client.get(url)
    assert resp.status_code == 405  # @require_POST enforces this

def test_compute_route_needs_two_place_ids(client):
    url = reverse("compute_route")
    payload = {"place_ids": ["ONLY_ORIGIN"]}
    resp = client.post(url, data=json.dumps(payload), content_type="application/json")
    assert resp.status_code == 400
    assert "Need at least origin and destination" in resp.json()["error"]

@patch("google_routing.views.requests.post")
def test_compute_route_happy_path(mock_post, client):
    # Mock a minimal, successful Routes API response
    mock_data = {
        "routes": [{
            "polyline": {"encodedPolyline": "abcd1234"},
            "optimizedIntermediateWaypointIndex": [0],
            "distanceMeters": 12345,
            "duration": "1111s",
        }]
    }
    mock_post.return_value = Mock(status_code=200, json=lambda: mock_data)

    url = reverse("compute_route")
    payload = {"place_ids": ["PID_ORIG", "PID_DEST"]}
    resp = client.post(url, data=json.dumps(payload), content_type="application/json")
    assert resp.status_code == 200
    data = resp.json()
    assert data["encoded_polyline"] == "abcd1234"
    assert data["distance_meters"] == 12345
    assert data["duration"] == "1111s"

    # Verify request headers include our server key + field mask
    _, kwargs = mock_post.call_args
    headers = kwargs["headers"]
    assert headers["X-Goog-Api-Key"] == settings.GOOGLE_ROUTES_SERVER_KEY
    assert "X-Goog-FieldMask" in headers

@patch("google_routing.views.requests.post")
def test_compute_route_propagates_google_error(mock_post, client):
    mock_post.return_value = Mock(status_code=400, text="Bad Request")
    url = reverse("compute_route")
    payload = {"place_ids": ["PID_ORIG", "PID_DEST"]}
    resp = client.post(url, data=json.dumps(payload), content_type="application/json")
    assert resp.status_code == 400
    assert "Routes API error" in resp.json()["error"]
