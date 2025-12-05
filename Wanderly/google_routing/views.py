"""
Views for the google_routing app.

This module renders a demo form for entering multiple addresses and uses
Google's Geocoding, Routes, and Static Maps APIs to compute an optimized
driving route, convert raw API units (meters, seconds) into friendly values,
and display the result as a static map image with distance and duration.
"""
from urllib.parse import urlencode
import requests
from django.conf import settings
from django.shortcuts import render
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from .forms import AddressForm

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
ROUTES_ENDPOINT = "https://routes.googleapis.com/directions/v2:computeRoutes"
STATIC_MAPS_URL = "https://maps.googleapis.com/maps/api/staticmap"

# Function to quickly convert meters to miles becuase google returns meters
def meters_to_miles(meters: float | int | None) -> float | int | None:
    """
    Convert a distance in meters (as returned by Google APIs) to miles.
    Returns None unchanged if the input is None.
    """
    if meters is None:
        return None
    return meters / 1609.344

# Function to convert googles seconds string: '1234s' to
# Hours, minutes
def seconds_to_human(seconds_str: str | None) -> str | None:
    """
    Routes API returns duration in seconds, we want hours, minutes, seconds
    """
    if not seconds_str or not seconds_str.endswith("s"):
        return None
    try:
        total = int(seconds_str[:-1])
    except ValueError:
        return None
    hours, rem = divmod(total, 3600)
    mins, _ = divmod(rem, 60)
    if hours and mins:
        return f"{hours} h {mins} min"
    if hours:
        return f"{hours} h"
    return f"{mins} min"


def _geocode_place_id(address, key):
    """Return place_id for a free-form address using Geocoding API."""
    r = requests.get(GEOCODE_URL, params={"address": address, "key": key}, timeout=15)
    r.raise_for_status()
    data = r.json()
    if data.get("status") != "OK" or not data.get("results"):
        return None
    return data["results"][0].get("place_id")

def _build_static_map_url(encoded_polyline, markers, size="640x480"):
    """
    Build a Static Maps URL that draws the route and shows markers.
    Use the BROWSER key here (safe if referrer-restricted).
    """
    params = [
        ("size", size),
        ("key", settings.GOOGLE_MAPS_BROWSER_KEY),
        # Draw the route from the encoded polyline
        ("path", f"enc:{encoded_polyline}"),
    ]
    # Add markers for each stop (A, B, C…)
    label_ord = ord("A")
    for lat, lng in markers:
        label = chr(label_ord) if label_ord <= ord("Z") else ""
        params.append(("markers", f"label:{label}|{lat},{lng}"))
        label_ord += 1

    # Build query manually to keep multiple 'markers' params
    query = urlencode(params, doseq=True)
    return f"{STATIC_MAPS_URL}?{query}"

def route_demo(request):
    """
    GET: show the form with N address inputs (default 2).
    POST is handled by compute_route to keep responsibilities clear.
    """
    try:
        n = int(request.GET.get("n", "2"))
    except ValueError:
        n = 2
    n = max(2, min(n, 10))  # sane bounds

    stops = [s.strip() for s in request.GET.getlist("stops") if s.strip()]
    if len(stops) > 10:
        stops = stops[:10]
    if stops:
        n = max(n, min(len(stops), 10))

    forms_list = []
    for i in range(n):
        initial = {"address": stops[i]} if i < len(stops) else None
        forms_list.append(AddressForm(prefix=f"f{i}", initial=initial))

    return render(
        request,
        "google_routing/route_demo.html",
        {
            "forms_list": forms_list,
            "GOOGLE_MAPS_BROWSER_KEY": settings.GOOGLE_MAPS_BROWSER_KEY,
        },
    )


def _bind_address_forms(request, count: int) -> tuple[list[AddressForm], list[str]]:
    """Bind POSTed address forms and return the cleaned addresses."""
    forms = [AddressForm(request.POST, prefix=f"f{i}") for i in range(count)]
    addresses = []
    for form in forms:
        if form.is_valid():
            value = form.cleaned_data.get("address")
            if value:
                addresses.append(value)
    return forms, addresses


def _geocode_addresses(addresses: list[str]) -> tuple[list[str] | None, str | None]:
    """Turn each address into a place_id; return failing address when geocoding fails."""
    place_ids = []
    api_key = settings.GOOGLE_ROUTES_SERVER_KEY or settings.GOOGLE_MAPS_BROWSER_KEY
    for address in addresses:
        pid = _geocode_place_id(address, api_key)
        if not pid:
            return None, address
        place_ids.append(pid)
    return place_ids, None


def _request_route_data(place_ids: list[str]) -> tuple[dict | None, str | None, int]:
    """Call the Routes API and return the first route, or an error."""
    payload = {
        "origin": {"placeId": place_ids[0]},
        "destination": {"placeId": place_ids[-1]},
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
        "optimizeWaypointOrder": True,
        "intermediates": [{"placeId": pid} for pid in place_ids[1:-1]],
        "polylineEncoding": "ENCODED_POLYLINE",
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": settings.GOOGLE_ROUTES_SERVER_KEY,
        "X-Goog-FieldMask": (
            "routes.polyline.encodedPolyline,"
            "routes.legs.startLocation,routes.legs.endLocation,"
            "routes.optimizedIntermediateWaypointIndex,"
            "routes.distanceMeters,routes.duration"
        ),
    }
    response = requests.post(ROUTES_ENDPOINT, headers=headers, json=payload, timeout=20)
    if response.status_code != 200:
        return None, f"Routes API error: {response.text}", response.status_code

    routes = response.json().get("routes", [])
    if not routes:
        return None, "No route returned.", 404
    return routes[0], None, 200


def _extract_leg_markers(legs: list[dict]) -> list[tuple[float, float]]:
    """Return coordinates for the first and last legs."""
    markers = []
    if legs:
        start = legs[0].get("startLocation", {}).get("latLng", {})
        end = legs[-1].get("endLocation", {}).get("latLng", {})
        if start:
            markers.append((start.get("latitude"), start.get("longitude")))
        if end:
            markers.append((end.get("latitude"), end.get("longitude")))
    return [marker for marker in markers if all(marker)]


def _build_route_result(route: dict) -> dict:
    """Prepare the route details for template rendering."""
    encoded = route.get("polyline", {}).get("encodedPolyline", "")
    return {
        "distance_m": meters_to_miles(route.get("distanceMeters")),
        "duration": seconds_to_human(route.get("duration")),
        "optimized_idx": route.get("optimizedIntermediateWaypointIndex", []),
        "static_map_src": _build_static_map_url(
            encoded,
            _extract_leg_markers(route.get("legs", [])),
        ),
    }


def _render_route_page(request, forms_list, *, error=None, status=200, result=None):
    """Render the shared template with optional error or result payloads."""
    context = {"forms_list": forms_list}
    if error:
        context["error"] = error
    if result:
        context["result"] = result
    return render(request, "google_routing/route_demo.html", context, status=status)


@require_POST
@csrf_exempt
def compute_route(request):
    """
    Handles the plain HTML form POST (no JS).
    - Reads N from hidden input
    - Validates at least 2 non-empty addresses
    - Geocodes to place_ids
    - Calls Routes API
    - Renders a static map image with the route
    """

    try:
        n = int(request.POST.get("n", "2"))
    except ValueError:
        n = 2
    n = max(2, min(n, 10))

    forms_list, addresses = _bind_address_forms(request, n)
    if len(addresses) < 2:
        return _render_route_page(
            request,
            forms_list,
            error="Please enter at least an origin and a destination.",
            status=400,
        )

    place_ids, failed_address = _geocode_addresses(addresses)
    if place_ids is None:
        return _render_route_page(
            request,
            forms_list,
            error=f"Could not geocode: {failed_address}",
            status=400,
        )

    route, error_message, status_code = _request_route_data(place_ids)
    if route is None:
        return _render_route_page(
            request,
            forms_list,
            error=error_message,
            status=status_code,
        )

    return _render_route_page(
        request,
        forms_list,
        result=_build_route_result(route),
    )
