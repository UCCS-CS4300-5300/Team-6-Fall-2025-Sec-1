from datetime import time
import pytest
from django.urls import reverse

from itinerary.models import Itinerary

@pytest.mark.django_db
def test_itinerary_list_requires_login(client):
    url = reverse("itinerary:itinerary_list")
    resp = client.get(url)
    # Default login_required behavior is redirect (302)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]  # adjust if your login URL is different