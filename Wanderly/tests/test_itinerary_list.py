from datetime import time
import pytest
from django.urls import reverse

from itinerary.models import Itinerary

@pytest.mark.django_db
def test_itinerary_list_requires_login(client):
    """
    Testing to  ake sure you cannot access /itinerary/list/
    without being logged in, and making sure it redirects to 
    the login page.
    """
    url = reverse("itinerary:itinerary_list")
    resp = client.get(url)
    # Default login_required behavior is redirect (302)
    assert resp.status_code == 302
    assert "/auth/sign-in/" in resp.headers["Location"]  # adjust if your login URL is different

@pytest.mark.django_db
def test_itinerary_list_shows_only_current_users_itineraries(client, django_user_model):
    """
    Creating two users, and 3 itieraries 2 for user a and 1 for user b
    then loggin in as user a and makign sure their 2 are there
    and user b's is not.
    """
    # Create two users
    user_a = django_user_model.objects.create_user(
        username="alice", password="password123"
    )
    user_b = django_user_model.objects.create_user(
        username="bob", password="password123"
    )

    # Create itineraries for each user
    itin_a1 = Itinerary.objects.create(
        user=user_a,
        destination="Norman, Oklahoma",
        wake_up_time=time(7, 0),
        bed_time=time(22, 0),
        num_days=3,
    )
    itin_a2 = Itinerary.objects.create(
        user=user_a,
        destination="Denver, Colorado",
        wake_up_time=time(8, 0),
        bed_time=time(23, 0),
        num_days=2,
    )
    itin_b1 = Itinerary.objects.create(
        user=user_b,
        destination="Seattle, Washington",
        wake_up_time=time(9, 0),
        bed_time=time(21, 0),
        num_days=4,
    )

    # Log in as user_a
    client.login(username="alice", password="password123")

    url = reverse("itinerary:itinerary_list")
    resp = client.get(url)

    assert resp.status_code == 200
    content = resp.content.decode()

    # Should see Alice's itineraries
    assert itin_a1.destination in content
    assert itin_a2.destination in content

    # Should NOT see Bob's itinerary
    assert itin_b1.destination not in content

@pytest.mark.django_db
def test_itinerary_list_shows_message_when_no_itineraries(client, django_user_model):
    """
    Testing to make sure when a user has no itineraries the proper message is displayed. 
    """
    user = django_user_model.objects.create_user(
        username="charlie", password="password123"
    )

    client.login(username="charlie", password="password123")

    url = reverse("itinerary:itinerary_list")
    resp = client.get(url)

    assert resp.status_code == 200
    content = resp.content.decode()

    assert "You don't have any itineraries yet" in content