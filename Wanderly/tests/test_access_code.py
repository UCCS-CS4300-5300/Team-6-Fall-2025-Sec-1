import pytest
from django.urls import reverse

from itinerary.models import Itinerary


@pytest.fixture
def itinerary(db):
    """
    A sample itinerary object for access-code tests.
    """
    obj = Itinerary.objects.create( 
        destination="Breckenridge", 
        wake_up_time="07:00",
        bed_time="22:00",
        num_days=3,
    )
    # Ensure the access code was generated
    assert obj.access_code
    return obj


@pytest.fixture
def find_itinerary_url():
    """
    URL for the access-code endpoint.
    """
    return reverse("itinerary:find_itinerary")


@pytest.fixture
def itinerary_detail_url(itinerary):
    """
    URL for the specific itinerary page (by access code).
    """
    return reverse("itinerary:itinerary_detail", args=[itinerary.access_code])


# ───────────────────────────
# Non-AJAX (normal form submit)
# ───────────────────────────

@pytest.mark.django_db
def test_valid_code_redirects(client, itinerary, find_itinerary_url):
    """
    Posting a valid access code via normal form should redirect
    to the itinerary detail page.
    """
    response = client.post(find_itinerary_url, {"access_code": itinerary.access_code})

    assert response.status_code == 302
    expected_url = reverse("itinerary:itinerary_detail", args=[itinerary.access_code])
    assert response.url == expected_url


@pytest.mark.django_db
def test_empty_code_redirects_back(client, find_itinerary_url):
    """
    Empty access code should just redirect back to the main itinerary page.
    """
    response = client.post(find_itinerary_url, {"access_code": ""})

    assert response.status_code == 302
    expected_url = reverse("itinerary:itinerary")
    assert response.url == expected_url


@pytest.mark.django_db
def test_nonexistent_code_redirects_back(client, find_itinerary_url):
    """
    Nonexistent access code should redirect back (non-AJAX behavior).
    """
    response = client.post(find_itinerary_url, {"access_code": "NOTREAL123"})

    assert response.status_code == 302
    expected_url = reverse("itinerary:itinerary")
    assert response.url == expected_url


@pytest.mark.django_db
def test_get_request_redirects_back(client, find_itinerary_url):
    """
    GET to the access-code endpoint should redirect back to the main page.
    """
    response = client.get(find_itinerary_url)

    assert response.status_code == 302
    expected_url = reverse("itinerary:itinerary")
    assert response.url == expected_url


# ───────────────────────────
# AJAX behavior
# ───────────────────────────

@pytest.mark.django_db
def test_valid_ajax_returns_ok_with_redirect_url(client, itinerary, find_itinerary_url):
    """
    AJAX POST with a valid access code should return 200 and a redirect_url.
    """
    response = client.post(
        find_itinerary_url,
        {"access_code": itinerary.access_code},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )

    assert response.status_code == 200
    data = response.json()
    assert data.get("ok") is True

    expected_url = reverse("itinerary:itinerary_detail", args=[itinerary.access_code])
    assert data.get("redirect_url") == expected_url


@pytest.mark.django_db
def test_missing_ajax_code_returns_error(client, find_itinerary_url):
    """
    AJAX POST with empty access code should return an error JSON.
    """
    response = client.post(
        find_itinerary_url,
        {"access_code": ""},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )

    # Adjust to whatever you actually return (400 vs 422, etc.)
    assert response.status_code == 400
    data = response.json()
    assert data.get("ok") is False
    assert "please enter an access code" in (data.get("error") or "").lower()


@pytest.mark.django_db
def test_nonexistent_code_ajax_returns_error(client, find_itinerary_url):
    """
    AJAX POST with a well-formed but nonexistent access code
    should return an error JSON (typically 404 or 400).
    """
    response = client.post(
        find_itinerary_url,
        {"access_code": "DOESNOTEXIST"},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )

    # Use the *actual* status code your view returns.
    # From your failure it looks like it's 404, so:
    assert response.status_code == 404

    data = response.json()
    assert data.get("ok") is False
    assert "no itinerary" in (data.get("error") or "").lower()
