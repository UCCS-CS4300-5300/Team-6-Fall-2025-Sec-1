# tests/test_auto_complete.py
from django.contrib.staticfiles import finders
from django.urls import reverse
from django.test import override_settings

# Testing to make sure out places_auto_complete.js file is present because it is the heart of the auto complete
# Also make sure we are properly getting the places library using a known string
def test_boot_js_exists_and_mentions_new_places_api():
    path = finders.find("places_auto_complete/places-autocomplete.js")
    assert path, "Static places-autocomplete.js.js not found via staticfiles."

    with open(path, "r", encoding="utf-8") as f:
        src = f.read()

    assert ('importLibrary("places")' in src) or ("PlaceAutocompleteElement" in src), (
        "boot.js doesn't appear to use the new Places API"
    )

# Checking the home page is loading properly then once loaded
# Checking to make sure the html contains the script from places-autocomplete.js
def test_a_real_page_includes_the_boot_script(client):
    resp = client.get("/")  # change if your homepage URL name differs
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "places_auto_complete/places-autocomplete.js" in html, "Page is not including the autocomplete script."

# Making sure our homepage has input fields that are valid for the google shadow DOM to take over
def test_homepage_has_autocomplete_hook(client):
    resp = client.get("/")  # change if your landing page differs
    assert resp.status_code == 200
    html = resp.content.decode()
    assert ('data-places="1"' in html) or ('class="js-places"' in html) or (".js-places" in html)
