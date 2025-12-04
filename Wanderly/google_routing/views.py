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

@require_POST
@csrf_exempt
# pylint: disable=too-many-locals
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

    # Rebuild the same number of forms and bind POST data
    forms_list = [AddressForm(request.POST, prefix=f"f{i}") for i in range(n)]
    addresses = []
    for f in forms_list:
        if f.is_valid() and f.cleaned_data.get("address"):
            addresses.append(f.cleaned_data["address"])

    if len(addresses) < 2:
        # Re-render with error
        return render(
            request,
            "google_routing/route_demo.html",
            {
                "forms_list": forms_list,
                "error": "Please enter at least an origin and a destination.",
            },
            status=400,
        )

    # 1) Geocode → place_ids
    place_ids = []
    for addr in addresses:
        pid = _geocode_place_id(
            addr,
            settings.GOOGLE_ROUTES_SERVER_KEY or settings.GOOGLE_MAPS_BROWSER_KEY
        )
        if not pid:
            return render(
                request,
                "google_routing/route_demo.html",
                {
                    "forms_list": forms_list,
                    "error": f"Could not geocode: {addr}",
                },
                status=400,
            )
        place_ids.append(pid)

    # Also collect lat/lng for markers (reuse geocode results to avoid extra calls)
    # If you want precise marker positions, modify _geocode_place_id to also return lat/lng.

    # 2) Routes API
    origin_pid = place_ids[0]
    destination_pid = place_ids[-1]
    intermediates = [{"placeId": pid} for pid in place_ids[1:-1]]

    payload = {
        "origin": {"placeId": origin_pid},
        "destination": {"placeId": destination_pid},
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
        "optimizeWaypointOrder": True,
        "intermediates": intermediates,
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
    r = requests.post(ROUTES_ENDPOINT, headers=headers, json=payload, timeout=20)
    if r.status_code != 200:
        return render(
            request,
            "google_routing/route_demo.html",
            {
                "forms_list": forms_list,
                "error": f"Routes API error: {r.text}",
            },
            status=r.status_code,
        )

    data = r.json()
    routes = data.get("routes", [])
    if not routes:
        return render(
            request,
            "google_routing/route_demo.html",
            {"forms_list": forms_list, "error": "No route returned."},
            status=404,
        )

    route = routes[0]
    encoded = route.get("polyline", {}).get("encodedPolyline", "")
    distance_m = route.get("distanceMeters")
    duration = route.get("duration")
    optimized_idx = route.get("optimizedIntermediateWaypointIndex", [])

    # Marker positions from legs (start/end of first/last leg); enough for quick pins
    markers = []
    legs = route.get("legs", [])
    if legs:
        # Start of first leg = origin
        s = legs[0].get("startLocation", {}).get("latLng", {})
        if s:
            markers.append((s.get("latitude"), s.get("longitude")))
        # End of last leg = destination
        e = legs[-1].get("endLocation", {}).get("latLng", {})
        if e:
            markers.append((e.get("latitude"), e.get("longitude")))

    static_map_src = _build_static_map_url(encoded, [m for m in markers if all(m)])

    miles = meters_to_miles(distance_m)
    human_readable_duration = seconds_to_human(duration)
    print(f"{miles}: miles. {human_readable_duration}: duration")
    # Re-render page with results
    return render(
        request,
        "google_routing/route_demo.html",
        {
            "forms_list": forms_list,
            "result": {
                "distance_m": miles,
                "duration": human_readable_duration,
                "optimized_idx": optimized_idx,
                "static_map_src": static_map_src,
            },
        },
    )
