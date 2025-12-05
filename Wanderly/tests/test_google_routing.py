import pytest
from unittest.mock import patch, Mock
from django.urls import reverse
from django.test import Client

@pytest.fixture
def client():
    return Client()

def _fake_geocode_ok(place_id="PID_X"):
    return {"status":"OK","results":[{"place_id": place_id}]}

def _fake_geocode_fail():
    return {"status":"REQUEST_DENIED","error_message":"not allowed","results":[]}

def _fake_routes_ok():
    return {
        "routes": [{
            "polyline": {"encodedPolyline": "abcd1234"},
            "distanceMeters": 32186,         # ~20.0 miles
            "duration": "5400s",             # 1 h 30 min
            "optimizedIntermediateWaypointIndex": [0],
            "legs": [
                {"startLocation":{"latLng":{"latitude":39.0,"longitude":-105.0}}},
                {"endLocation":{"latLng":{"latitude":39.7,"longitude":-104.9}}},
            ],
        }]
    }

def test_route_demo_renders(client):
    resp = client.get(reverse("google_routing:route_demo"))
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "Multi-Stop Route Planner" in html  # or another stable marker
    # We do NOT assert the Maps JS script anymore.

def test_compute_route_requires_post(client):
    # With @require_POST, GET should be 405
    resp = client.get(reverse("google_routing:compute_route"))
    assert resp.status_code == 405

@patch("google_routing.views.requests.get")
def test_geocoding_failure_shows_error(mock_get, client):
    mock_get.return_value = Mock(status_code=200, json=_fake_geocode_fail)
    data = {"n":"2","f0-address":"Bad Addr","f1-address":"Denver, CO"}
    resp = client.post(reverse("google_routing:compute_route"), data=data)
    assert resp.status_code in (400, 200)
    assert ("Could not geocode" in resp.content.decode()
            or "Geocoding" in resp.content.decode())

@patch("google_routing.views.requests.get")
@patch("google_routing.views.requests.post")
def test_happy_path_renders_distance_duration_and_map(mock_post, mock_get, client):
    mock_get.return_value = Mock(status_code=200, json=_fake_geocode_ok)
    mock_post.return_value = Mock(status_code=200, json=_fake_routes_ok)

    data = {
        "n": "2",
        "f0-address": "Colorado Springs, CO",
        "f1-address": "Denver, CO",
    }
    resp = client.post(reverse("google_routing:compute_route"), data=data)
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "20.0 mi" in body
    assert "1 h 30 min" in body
    assert "/maps/api/staticmap" in body  # Static Maps image present

@patch("google_routing.views.requests.get")
@patch("google_routing.views.requests.post")
def test_routes_failure_propagates_error(mock_post, mock_get, client):
    mock_get.return_value = Mock(status_code=200, json=_fake_geocode_ok)
    mock_post.return_value = Mock(status_code=400, text="Bad Request")
    data = {"n":"2","f0-address":"Colorado Springs, CO","f1-address":"Denver, CO"}
    resp = client.post(reverse("google_routing:compute_route"), data=data)
    assert resp.status_code == 400
    assert "Routes API error" in resp.content.decode()


def test_converters():
    from google_routing.views import meters_to_miles, seconds_to_human
    assert round(meters_to_miles(1609.344), 3) == 1.000
    assert meters_to_miles(None) is None
    assert seconds_to_human("5400s") == "1 h 30 min"
    assert seconds_to_human("3600s") == "1 h"
    assert seconds_to_human("90s") == "1 min"
    assert seconds_to_human("oops") is None
