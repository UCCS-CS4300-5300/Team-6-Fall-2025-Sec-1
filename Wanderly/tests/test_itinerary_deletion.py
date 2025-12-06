from datetime import time, date
import pytest
from django.urls import reverse

from itinerary.models import Itinerary, BreakTime, BudgetItem, Day

@pytest.mark.django_db
def test_delete_itinerary_requires_login(client, django_user_model):
    """
    Creating a user than an itinerary and not logging in then trying to delete
    at the end making the the itinerary is still there
    """
    # Create a user and itinerary
    user = django_user_model.objects.create_user(
        username="alice", password="password123"
    )
    itin = Itinerary.objects.create(
        user=user,
        destination="Test City",
        wake_up_time=time(7, 0),
        bed_time=time(22, 0),
        num_days=2,
    )

    url = reverse("itinerary:delete_itinerary", args=[itin.access_code])
    resp = client.post(url)

    # Not logged in → should redirect to login
    assert resp.status_code == 302
    assert "/auth/sign-in/" in resp.headers["Location"]  # or use reverse("sign_in")

    # Itinerary should still exist
    assert Itinerary.objects.filter(pk=itin.pk).exists()


@pytest.mark.django_db
def test_owner_can_delete_itinerary(client, django_user_model):
    """
    Creating a user and itinerary under that user, making suer
    it can be deleted once logged in.
    """
    user = django_user_model.objects.create_user(
        username="alice", password="password123"
    )
    itin = Itinerary.objects.create(
        user=user,
        destination="Test City",
        wake_up_time=time(7, 0),
        bed_time=time(22, 0),
        num_days=2,
    )

    client.login(username="alice", password="password123")

    url = reverse("itinerary:delete_itinerary", args=[itin.access_code])
    resp = client.post(url)

    # Should redirect back to itinerary list
    assert resp.status_code == 302
    assert reverse("itinerary:itinerary_list") == resp.headers["Location"]

    # Itinerary should be gone
    assert not Itinerary.objects.filter(pk=itin.pk).exists()


@pytest.mark.django_db
def test_non_owner_cannot_delete_itinerary(client, django_user_model):
    """
    Creating a user with an itinerary, then logging in as someone
    else then trying to delete their itinerary
    at the end check to make sure it still there
    """
    owner = django_user_model.objects.create_user(
        username="owner", password="password123"
    )
    other = django_user_model.objects.create_user(
        username="intruder", password="password123"
    )

    itin = Itinerary.objects.create(
        user=owner,
        destination="Owner City",
        wake_up_time=time(7, 0),
        bed_time=time(22, 0),
        num_days=3,
    )

    client.login(username="intruder", password="password123")

    url = reverse("itinerary:delete_itinerary", args=[itin.access_code])
    resp = client.post(url)

    # Because of user=request.user in get_object_or_404 → this should be 404
    assert resp.status_code == 404

    # Itinerary is still there
    assert Itinerary.objects.filter(pk=itin.pk).exists()


@pytest.mark.django_db
def test_deleting_itinerary_cascades_related_models(client, django_user_model):
    """
    Creating an itinerary with a munch of different models like break time, budget 
    and day. Then making sure when we delete the itinerary they are also deleted.
    """
    user = django_user_model.objects.create_user(
        username="alice", password="password123"
    )
    itin = Itinerary.objects.create(
        user=user,
        destination="Cascade City",
        wake_up_time=time(7, 0),
        bed_time=time(22, 0),
        num_days=1,
    )

    # Create related objects
    BreakTime.objects.create(
        itinerary=itin,
        start_time=time(12, 0),
        end_time=time(13, 0),
    )
    BudgetItem.objects.create(
        itinerary=itin,
        category="Food & Dining",
        custom_category="",
        amount=25,
    )
    Day.objects.create(
        itinerary=itin,
        day_number=1,
        date=date(2025, 1, 1),
        notes="Test day",
    )

    client.login(username="alice", password="password123")

    url = reverse("itinerary:delete_itinerary", args=[itin.access_code])
    client.post(url)

    # Itinerary gone
    assert not Itinerary.objects.filter(pk=itin.pk).exists()
    # Related rows gone
    assert not BreakTime.objects.exists()
    assert not BudgetItem.objects.exists()
    assert not Day.objects.exists()