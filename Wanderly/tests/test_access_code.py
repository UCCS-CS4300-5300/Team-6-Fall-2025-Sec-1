import pytest
from django.urls import reverse

from itinerary.models import Itinerary

@pytest.fixture
def itinerary():
    """
    A itinerary object for access-code tests
    """
    return Itinerary.objects.create(
        destination="Breckenridge",
        wake_up_time="07:00",
        bed_time="22:00",
        num_days=3,
    )

@pytest.fixture
def find_itinerary_url():
    """
    URL for the access-code endpoint
    """
    return reverse("itinerary:find_itinerary")

@pytest.mark.django_db
def test_valid_code_redirects(client, itinerary, find_itinerary_url):
    response = client.post(find_itinerary_url, {"access_code": str(itinerary.id)})

    assert response.status_code == 302
    expected_url = reverse("itinerary:itinerary_detail", args=[itinerary.id])
    assert response.url == expected_url

@pytest.mark.django_db
def test_empty_code_redirects_back(client, find_itinerary_url):
    response = client.post(find_itinerary_url, {"access_code": ""})

    assert response.status_code == 302
    expected_url = reverse("itinerary:itinerary")
    assert response.url == expected_url

@pytest.mark.django_db
# Change this test to something like length once access code is implemented
def test_non_numberic_code_redirects_back(client, find_itinerary_url):
    response = client.post(find_itinerary_url, {"access_code": "123a5"})

    assert response.status_code == 302
    expected_url = reverse("itinerary:itinerary")
    assert response.url == expected_url

@pytest.mark.django_db
def test_non_existing_code_redirects_back(client, find_itinerary_url):
    response = client.post(find_itinerary_url, {"access_code": "99999999999"})

    assert response.status_code == 302
    expected_url = reverse("itinerary:itinerary")
    assert response.url == expected_url

@pytest.mark.django_db
def test_get_request_redirects_back(client, find_itinerary_url):
    response = client.get(find_itinerary_url)

    assert response.status_code == 302
    expected_url = reverse("itinerary:itinerary")
    assert response.url == expected_url

@pytest.mark.django_db
def test_valid_ajax_returns_ok_with_redirect_url(client, itinerary, find_itinerary_url):
    response = client.post(
        find_itinerary_url,
        {"access_code": str(itinerary.id)},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )

    assert response.status_code == 200
    data = response.json()
    assert data.get("ok") is True

    expected_url = reverse("itinerary:itinerary_detail", args=[itinerary.id])
    assert data.get("redirect_url") == expected_url

@pytest.mark.django_db
def test_non_numeric_ajax_returns_error(client, find_itinerary_url):
    response = client.post(
        find_itinerary_url,
        {"access_code": "abc"},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )

    assert response.status_code == 400
    data = response.json()
    assert data.get("ok") is False
    assert "number" in (data.get("error") or "").lower()


@pytest.mark.django_db
def test_nonexistent_id_ajax_returns_error(client, find_itinerary_url):
    response = client.post(
        find_itinerary_url,
        {"access_code": "999999"},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )

    # You might be returning 404 or 400; adjust if needed
    assert response.status_code in (400, 404)
    data = response.json()
    assert data.get("ok") is False
    assert "no itinerary" in (data.get("error") or "").lower()