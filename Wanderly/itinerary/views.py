"""Controls the views and requests for the itinerary module."""

import json
import os
import sys
import threading
from typing import List, Optional
import requests

from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from openai import OpenAI, OpenAIError

from .forms import ItineraryForm
from .models import BreakTime, BudgetItem, Day, Itinerary


def _create_break_times(request, itinerary_obj: Itinerary) -> None:
    """Create BreakTime rows from POSTed form data."""
    break_start_times = request.POST.getlist("break_start_time[]")
    break_end_times = request.POST.getlist("break_end_time[]")

    for start, end in zip(break_start_times, break_end_times):
        if start and end:
            # pylint: disable=no-member
            BreakTime.objects.create(
                itinerary=itinerary_obj,
                start_time=start,
                end_time=end,
            )

def _create_budget_items(request, itinerary_obj: Itinerary) -> None:
    """Create BudgetItem rows from POSTed form data."""
    budget_categories = request.POST.getlist("budget_category[]")
    budget_custom_categories = request.POST.getlist("budget_custom_category[]")
    budget_amounts = request.POST.getlist("budget_amount[]")

    for category, custom_category, amount in zip(
        budget_categories,
        budget_custom_categories,
        budget_amounts,
    ):
        if amount:  # Only save if amount is provided
            # pylint: disable=no-member
            BudgetItem.objects.create(
                itinerary=itinerary_obj,
                category=category,
                custom_category=(custom_category if category == "Other" else ""),
                amount=amount,
            )


def _create_days(request, itinerary_obj: Itinerary) -> None:
    """Create Day rows from POSTed form data."""
    num_days = itinerary_obj.num_days
    for day_index in range(1, num_days + 1):
        day_date = request.POST.get(f"day_{day_index}_date")
        day_notes = request.POST.get(f"day_{day_index}_notes", "")

        if day_date:  # Only save if date is provided
            # pylint: disable=no-member
            Day.objects.create(
                itinerary=itinerary_obj,
                day_number=day_index,
                date=day_date,
                notes=day_notes,
            )

def _format_break_times(itinerary_obj: Itinerary) -> str:
    """Return a human-readable break time string for an itinerary."""
    # pylint: disable=no-member
    break_times = BreakTime.objects.filter(itinerary=itinerary_obj)
    if not break_times.exists():
        return "None"

    return ", ".join(f"{bt.start_time}-{bt.end_time}" for bt in break_times)


def _format_budget(itinerary_obj: Itinerary) -> str:
    """Return a human-readable budget string for an itinerary."""
    # pylint: disable=no-member
    budget_items = BudgetItem.objects.filter(itinerary=itinerary_obj)
    if not budget_items.exists():
        return "Flexible"

    budget_parts: List[str] = []
    for item in budget_items:
        label = (
            item.custom_category
            if item.category == "Other" and item.custom_category
            else item.category
        )
        budget_parts.append(f"{label}: ${item.amount}")
    return ", ".join(budget_parts)


def _format_day_notes(itinerary_obj: Itinerary) -> str:
    """Return extra notes string describing per-day notes, if any."""
    # pylint: disable=no-member
    day_notes_qs = Day.objects.filter(itinerary=itinerary_obj).order_by("day_number")
    day_note_lines = [
        f"Day {day.day_number} ({day.date}): {day.notes}"
        for day in day_notes_qs
        if day.notes
    ]

    if not day_note_lines:
        return ""

    joined = "\n".join(day_note_lines)
    return f"User preferences for specific days:\n{joined}\n\n"


def _build_location_context(itinerary_obj: Itinerary) -> str:
    """Build location context lines for the AI prompt."""
    destination = getattr(itinerary_obj, "destination", "")
    place_id = getattr(itinerary_obj, "place_id", "")
    latitude = getattr(itinerary_obj, "latitude", None)
    longitude = getattr(itinerary_obj, "longitude", None)

    location_context_parts: List[str] = []
    if destination:
        location_context_parts.append(f"- Destination: {destination}")
    if place_id:
        location_context_parts.append(f"- Place ID: {place_id}")
    if latitude is not None and longitude is not None:
        location_context_parts.append(f"- Coordinates: {latitude}, {longitude}")
    return "\n".join(location_context_parts) or "- Destination not provided"


def _build_budget_guidance(itinerary_obj: Itinerary, num_days: int) -> str:
    """Build budget guidance lines for the AI prompt."""
    budget_items_qs = BudgetItem.objects.filter(itinerary=itinerary_obj)
    budget_lines: List[str] = []
    for item in budget_items_qs:
        label = (
            item.custom_category
            if item.category == "Other" and item.custom_category
            else item.category
        )
        per_day_amount = (
            float(item.amount) / float(num_days)
            if num_days
            else float(item.amount)
        )
        if label.lower() == "accommodation":
            guidance = (
                f"- {label}: ${item.amount} target nightly max "
                f"(if this is a trip total, stay near ${per_day_amount:.2f} per night)."
            )
        else:
            guidance = (
                f"- {label}: ${item.amount} total "
                f"(~${per_day_amount:.2f} per day)."
            )
        budget_lines.append(guidance)

    if budget_lines:
        return "\n".join(budget_lines)
    return (
        "- Flexible budget: No explicit budgets provided. Default to affordable, "
        "mainstream options."
    )


def _build_ai_prompt(itinerary_obj: Itinerary) -> str:
    """Build the user message sent to the OpenAI model."""
    wake_time = getattr(itinerary_obj, "wake_up_time", "")
    bed_time = getattr(itinerary_obj, "bed_time", "")
    num_days = getattr(itinerary_obj, "num_days", 1)

    break_times_str = _format_break_times(itinerary_obj)
    extra_notes = _format_day_notes(itinerary_obj)
    location_context = _build_location_context(itinerary_obj)
    budget_guidance = _build_budget_guidance(itinerary_obj, num_days)

    return f"""
You are an expert travel planner. Build a realistic itinerary that strictly respects the
provided constraints and budgets.

Trip Details:
{location_context}
- Number of days: {num_days}
- Wake up time: {wake_time}
- Bed time: {bed_time}
- Break times: {break_times_str}

Budget Guidance (treat amounts as per-trip unless noted):
{budget_guidance}

{extra_notes}Constraints you must follow:
- Only recommend real, currently operating, year-round places and activities. If you are
  not confident a venue exists or operates year-round, provide a generic, location-based
  option instead of inventing a name.
- Align all activities and their cost_estimate values with the provided budget categories.
  Distribute each category budget across the trip and keep each day's recommendations
  within those limits. When a category is missing, keep costs modest.
- If an Accommodation budget is provided, include at least one lodging recommendation
  within that budget (use the amount as nightly max when possible; otherwise use the
  per-night share of the total). Provide a realistic nightly price range in cost_estimate.
- Always include an "accommodation" object with a real hotel name and full street address;
  if unsure, pick a well-known chain in the destination with a reasonable nightly price
  in range.
- Keep transportation choices consistent with any Transportation budget; prefer walkable
  or transit-friendly options to avoid overruns.
- Respect wake/bed times and break times; give 4-6 activities per day covering the day.
- Avoid seasonal-only events and temporary exhibitions unless they are reliably available
  year-round.

Respond in JSON with exactly this shape:
{{
  "accommodation": {{
    "name": "Hotel name (real)",
    "address": "Street, City, Country",
    "price_per_night": "$150-$180",
    "notes": "One sentence on why it fits the budget/location."
  }},
  "days": [
    {{
      "day_number": 1,
      "title": "Arrival & Exploration",
      "activities": [
        {{
          "time": "9:00 AM",
          "name": "Activity name",
          "description": "Brief description",
          "duration": "2 hours",
          "cost_estimate": "$50"
        }}
      ]
    }}
  ]
}}

Ensure the schedule spans from wake time to bed time, honoring break times, and that
accommodation and activities stay within the budgets above.
"""


def _generate_ai_itinerary(itinerary_obj: Itinerary) -> Optional[dict]:
    """Call OpenAI to generate an itinerary. Return JSON payload or None."""
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    user_message = _build_ai_prompt(itinerary_obj)

    try:
        response = client.chat.completions.create(
            model="gpt-5.1",
            messages=[{"role": "user", "content": user_message}],
            response_format={"type": "json_object"},
        )
        ai_response = response.choices[0].message.content
        parsed = json.loads(ai_response)
        return parsed
    except (OpenAIError, json.JSONDecodeError, KeyError, ValueError):
        # The calling view is responsible for displaying a user-facing error.
        return None


def _normalize_ai_payload(payload: Optional[dict]):
    """Normalize AI payload for storage while preserving richer structures when present."""
    if payload is None:
        return None
    if isinstance(payload, dict):
        # If the payload only contains days, store the list for backward compatibility.
        if set(payload.keys()) == {"days"}:
            return payload.get("days")
    return payload


def _generate_and_persist_async(itinerary_id: int) -> None:
    """Background worker to generate and persist an AI itinerary."""
    try:
        itinerary_obj = Itinerary.objects.get(pk=itinerary_id)
    except Itinerary.DoesNotExist:
        return

    payload = _generate_ai_itinerary(itinerary_obj)
    if payload is None:
        return

    normalized = _normalize_ai_payload(payload)
    itinerary_obj.ai_itinerary = normalized
    itinerary_obj.save(update_fields=["ai_itinerary"])


def _should_generate_inline() -> bool:
    """Return True when running under test to avoid threaded DB access."""
    return "pytest" in sys.modules


def itinerary(request):
    """View for creating and displaying itineraries."""
    if request.method == "POST":
        form = ItineraryForm(request.POST)

        if form.is_valid():
            itinerary_obj = form.save()

            _create_break_times(request, itinerary_obj)
            _create_budget_items(request, itinerary_obj)
            _create_days(request, itinerary_obj)

            if _should_generate_inline():
                ai_payload = _generate_ai_itinerary(itinerary_obj)
                if ai_payload is None:
                    messages.error(
                        request,
                        "We were unable to generate an AI-powered itinerary at this time.",
                    )
                else:
                    normalized = _normalize_ai_payload(ai_payload)
                    itinerary_obj.ai_itinerary = normalized
                    itinerary_obj.save(update_fields=["ai_itinerary"])
                    messages.success(
                        request,
                        "Itinerary created successfully. AI details generated.",
                    )
            else:
                # Kick off AI generation in the background so the request is fast.
                threading.Thread(
                    target=_generate_and_persist_async,
                    args=(itinerary_obj.id,),
                    daemon=True,
                ).start()

                messages.success(
                    request,
                    "Itinerary created successfully. We're generating the AI details in the "
                    "background; refresh the detail page in a few moments.",
                )
            return redirect("itinerary:itinerary_detail", access_code=itinerary_obj.access_code)

        # No `else` needed; if the form is invalid we fall through and re-render.
        messages.error(request, "Please correct the errors below.")
    else:
        form = ItineraryForm()

    context = {
        "form": form,
    }

    return render(request, "itinerary.html", context)

def itinerary_detail(request, access_code: str):
    """Display a generated itinerary via access code."""
    itinerary_obj = get_object_or_404(Itinerary, access_code=access_code)
    raw_ai_payload = itinerary_obj.ai_itinerary
    is_generating = raw_ai_payload is None
    ai_itinerary_raw = raw_ai_payload or {}
    if isinstance(ai_itinerary_raw, list):
        # Backward compatibility for older saved itineraries.
        ai_itinerary_raw = {"days": ai_itinerary_raw}
    ai_itinerary_days = ai_itinerary_raw.get("days", [])
    accommodation_info = ai_itinerary_raw.get("accommodation")
    accommodation_budget = itinerary_obj.budget_items.filter(category="Accommodation").first()

    context = {
        "itinerary": itinerary_obj,
        "ai_itinerary_days": ai_itinerary_days,
        "accommodation_info": accommodation_info,
        "accommodation_budget": accommodation_budget,
        "break_times": itinerary_obj.break_times.all(),
        "budget_items": itinerary_obj.budget_items.all(),
        "trip_days": itinerary_obj.days.all(),
        "is_generating": is_generating,
    }

    if is_generating:
        messages.info(
            request,
            "We're still generating the AI itinerary. This page will refresh automatically "
            "when it's ready.",
        )
    elif not ai_itinerary_days:
        messages.warning(
            request,
            "We couldn't find an AI itinerary for this trip yet. Please wait a moment and "
            "try again.",
        )

    return render(request, "itinerary_detail.html", context)

def itinerary_list(request):
    ''' Load the list of current itineraries '''
    return render(request, "itinerary_list.html")


def _itinerary_error_response(request, is_ajax, message, status_code):
    """Return a consistent error response for itinerary lookups."""
    if is_ajax:
        return JsonResponse({"ok": False, "error": message}, status=status_code)
    messages.error(request, message)
    return redirect("itinerary:itinerary")


def find_itinerary(request):
    """
    Lookup an itinerary by access code and redirect or return JSON.

    Non-AJAX requests mirror the form behavior and redirect either to the
    itinerary landing page or the detail page. AJAX requests return a JSON
    payload with ``ok``/``error`` metadata.
    """

    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    redirect_home = redirect("itinerary:itinerary")

    if request.method != "POST":
        return _itinerary_error_response(request, is_ajax, "Invalid request method.", 405)

    access_code = request.POST.get("access_code", "").strip()
    if not access_code:
        return _missing_access_code_response(is_ajax, redirect_home)

    itinerary_obj = Itinerary.objects.filter(access_code=access_code).first()  # pylint: disable=no-member
    if itinerary_obj is None:
        return _missing_itinerary_response(is_ajax, redirect_home)

    detail_url = reverse("itinerary:itinerary_detail", args=[access_code])
    if is_ajax:
        return JsonResponse({"ok": True, "redirect_url": detail_url})
    return redirect(detail_url)


def _missing_access_code_response(is_ajax: bool, redirect_home):
    """Return appropriate response when access code is missing."""
    if is_ajax:
        return JsonResponse(
            {"ok": False, "error": "Please enter an access code."},
            status=400,
        )
    return redirect_home


def _missing_itinerary_response(is_ajax: bool, redirect_home):
    """Return appropriate response when itinerary lookup fails."""
    if is_ajax:
        return JsonResponse(
            {"ok": False, "error": "No itinerary found for that code."},
            status=404,
        )
    return redirect_home


@require_POST
def place_reviews(request):
    """Fetch ratings and reviews for a place using Google Places API."""

    # Parse JSON payload
    try:
        payload = json.loads(request.body.decode() or "{}")
    except json.JSONDecodeError:
        payload = {}

    # Validate required field
    query = payload.get("query", "").strip()
    if not query:
        return JsonResponse({"error": "query required"}, status=400)

    # Set up headers for Google Places API request
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": os.environ['GOOGLE_PLACES_RATINGS_API_KEY'],
        "X-Goog-FieldMask": (
            "places.id,places.displayName,places.rating,"
            "places.userRatingCount,places.reviews"
        ),
    }

    # Call Google Places API text search endpoint
    try:
        text_resp = requests.post(
            "https://places.googleapis.com/v1/places:searchText",
            headers=headers,
            json={"textQuery": query},
            timeout=10,
        )

        # Raise error for bad responses
        text_resp.raise_for_status()

        # Parse response JSON
        place_data = text_resp.json()

    # Handle request exceptions
    except requests.RequestException:
        return JsonResponse({"error": "Failed to contact Google Places"}, status=502)

    # Extract place info and reviews
    place = (place_data.get("places") or [{}])[0]
    reviews = place.get("reviews", [])[:5]  # include positive & negative

    # Format and return response
    return JsonResponse({
        "name": place.get("displayName", {}).get("text"),
        "rating": place.get("rating"),
        "count": place.get("userRatingCount"),
        "reviews": [
            {
                "text": r.get("text", {}).get("text"),
                "rating": r.get("rating"),
                "author": r.get("authorAttribution", {}).get("displayName"),
            }
            for r in reviews
        ],
    })
