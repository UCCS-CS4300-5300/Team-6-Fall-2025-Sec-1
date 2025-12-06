"""Shared helpers for interacting with the Google Places API."""
from __future__ import annotations

import json
import requests
from django.conf import settings

PLACES_ENDPOINT = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = (
    "places.displayName,places.formattedAddress,"
    "places.websiteUri,places.photos"
)


class PlacesPayloadError(ValueError):
    """Raised when the client payload is invalid."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def parse_text_query(raw_body: bytes) -> str:
    """Return the trimmed text query from the JSON request body."""
    try:
        payload = json.loads(raw_body or b"{}")
    except json.JSONDecodeError as exc:
        raise PlacesPayloadError("Invalid JSON") from exc

    text_query = str(payload.get("textQuery", "")).strip()
    if not text_query:
        raise PlacesPayloadError("textQuery is required")
    return text_query


def fetch_places(text_query: str, *, timeout: int = 10) -> list[dict]:
    """Call the text search endpoint and return formatted place dictionaries."""
    payload = {"textQuery": text_query}
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": settings.GOOGLE_PLACES_API_KEY,
        "X-Goog-FieldMask": FIELD_MASK,
    }

    response = requests.post(
        PLACES_ENDPOINT,
        json=payload,
        headers=headers,
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    places = data.get("places", [])
    return _decorate_photo_urls(places)


def _decorate_photo_urls(places: list[dict]) -> list[dict]:
    """Add local media URLs for every returned photo reference."""
    for place in places:
        photos = place.get("photos", [])
        place["photos"] = [
            f"/place_photos/{photo['name']}"
            for photo in photos
            if isinstance(photo, dict) and "name" in photo
        ]
    return places
