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
from django.views.decorators.http import require_http_methods
from django.utils.dateparse import parse_datetime
from django.contrib.auth.decorators import login_required
from openai import OpenAI, OpenAIError

from .forms import ItineraryForm
from .models import BreakTime, BudgetItem, Day, Itinerary
from .prompt_utils import (
    _build_overrides_block,
    _collect_additional_guidance,
    _flight_prompt_details,
    _format_break_times,
    _format_budget,
    _format_date_range,
    _format_day_notes,
    _hotel_plan_summary,
    _meals_line,
    _season_hint,
    _summarize_party,
    collect_day_fragments,
)


def _create_break_times(request, itinerary_obj: Itinerary) -> None:
    """Create BreakTime rows from POSTed form data."""

    # Extract the lists of break time fields from the POST data.
    break_start_times = request.POST.getlist("break_start_time[]")
    break_end_times = request.POST.getlist("break_end_time[]")
    break_purposes = request.POST.getlist("break_purpose[]")

    # Iterate over however many rows the user attempted to submit.
    max_length = max(len(break_start_times), len(break_end_times), len(break_purposes))
    for idx in range(max_length):
        start = break_start_times[idx] if idx < len(break_start_times) else ""
        end = break_end_times[idx] if idx < len(break_end_times) else ""
        purpose = break_purposes[idx] if idx < len(break_purposes) else ""

        # Ignore partially filled rows to avoid invalid entries.
        if not (start and end):
            continue

        # Persist each completed break window.
        BreakTime.objects.create(
            itinerary=itinerary_obj,
            start_time=start,
            end_time=end,
            purpose=purpose.strip(),
        )

def _create_budget_items(request, itinerary_obj: Itinerary) -> None:
    """Create BudgetItem rows from POSTed form data."""
    budget_categories = request.POST.getlist("budget_category[]")
    budget_custom_categories = request.POST.getlist("budget_custom_category[]")
    budget_amounts = request.POST.getlist("budget_amount[]")

    # Each index represents a single budget row from the UI.
    for category, custom_category, amount in zip(
        budget_categories,
        budget_custom_categories,
        budget_amounts,
    ):
        # Drop rows that never received an amount.
        if not amount:
            continue

        # Persist each budget item.
        BudgetItem.objects.create(
            itinerary=itinerary_obj,
            category=category,
            custom_category=(custom_category if category == "Other" else ""),
            amount=amount,
        )


def _create_days(request, itinerary_obj: Itinerary) -> None:
    """Create Day rows from POSTed form data."""

    # Iterate over the number of days specified in the itinerary.
    num_days = itinerary_obj.num_days
    for day_index in range(1, num_days + 1):
        day_date = request.POST.get(f"day_{day_index}_date")

        # Skip days without a date to avoid invalid entries.
        if not day_date:
            continue

        # Get the various per-day fields from the form.
        day_notes = request.POST.get(f"day_{day_index}_notes", "")
        wake_override = request.POST.get(f"day_{day_index}_wake_override") or None
        bed_override = request.POST.get(f"day_{day_index}_bed_override") or None
        constraints = request.POST.get(f"day_{day_index}_constraints", "")
        must_do = request.POST.get(f"day_{day_index}_must_do", "")

        Day.objects.create(
            itinerary=itinerary_obj,
            day_number=day_index,
            date=day_date,
            notes=day_notes,
            wake_override=wake_override,
            bed_override=bed_override,
            constraints=constraints,
            must_do=must_do,
        )

def _fetch_flight_details(flight_number: str) -> Optional[dict]:
    """Call AviationStack to fetch flight details for a given flight number."""

    # Dont call API if we lack a flight number or API key.
    if not flight_number or not os.environ['AVIATIONSTACK_API_KEY']:
        return None

    # Build and send the request to AviationStack.
    params = {
        "access_key": os.environ['AVIATIONSTACK_API_KEY'],
        "flight_iata": flight_number.strip().upper(),
    }

    # Perform the HTTP GET request to the AviationStack API.
    response = requests.get(
        "http://api.aviationstack.com/v1/flights",
        params=params,
        timeout=15,
    )

    # Raise an error for bad responses.
    response.raise_for_status()

    # Parse the JSON payload and handle API-level errors.
    payload = response.json()

    # Handle API-level errors indicated in the payload.
    if isinstance(payload, dict) and payload.get("error"):
        raise requests.RequestException(payload["error"].get("info", "API error"))

    # Extract flight details from the response.
    flights = payload.get("data") or []

    # Return None when no matching flights were found.
    if not flights:
        return None

    # Inspect the first matching flight record.
    flight = flights[0]

    # Normalize the airline name and flight number.
    airline = (flight.get("airline") or {}).get("name") or ""
    number = (flight.get("flight") or {}).get("iata") or flight_number

    # Helper to extract details from a flight section.
    def _extract(section_name: str) -> dict:
        """Return code, name, and timestamp for a flight section."""
        section = flight.get(section_name) or {}
        return {
            "code": section.get("iata") or "",
            "name": section.get("airport") or "",
            "time": section.get("scheduled") or section.get("estimated") or "",
        }

    # Extract departure and arrival info.
    departure_info = _extract("departure")
    arrival_info = _extract("arrival")

    # Return the normalized flight details.
    return {
        "flight_number": number,
        "airline": airline,
        "departure_airport": departure_info["code"],
        "departure_airport_name": departure_info["name"],
        "departure_time": departure_info["time"],
        "arrival_airport": arrival_info["code"],
        "arrival_airport_name": arrival_info["name"],
        "arrival_time": arrival_info["time"],
    }


def _autofill_flight_data(itinerary_obj: Itinerary) -> None:
    """Populate arrival/departure fields by calling the flight API when needed."""
    # Track which fields were modified so we can issue a minimal save.
    updates = set()

    # Helper to assign fetched flight details to the itinerary object.
    def assign(details, prefix: str):
        """Copy normalized API values onto the itinerary object."""

        # When the API returned nothing we do not touch the model.
        if not details:
            return

        # Build the attribute names for this prefix (arrival/departure).
        airport_field = f"{prefix}_airport"
        datetime_field = f"{prefix}_datetime"
        airline_field = f"{prefix}_airline"

        # Extract the airport name and code from the API response.
        name = details.get(f"{prefix}_airport_name") or ""
        code = details.get(f"{prefix}_airport") or ""

        # Default to whichever value is available.
        airport_value = ""
        if name and code:
            airport_value = f"{name} ({code})"
        else:
            airport_value = name or code

        # Pull out the ISO timestamp string returned by AviationStack.
        time_value = details.get(f"{prefix}_time")

        # Persist the airport string when one exists.
        if airport_value:
            setattr(itinerary_obj, airport_field, airport_value)
            updates.add(airport_field)

        # Parse the ISO timestamp into a Python datetime for storage.
        if time_value:
            parsed = parse_datetime(time_value)
            if parsed:
                setattr(itinerary_obj, datetime_field, parsed)
                updates.add(datetime_field)

        # Persist the airline name if available.
        airline_value = details.get("airline") or ""
        if airline_value:
            setattr(itinerary_obj, airline_field, airline_value)
            updates.add(airline_field)

    try:
        # Attempt to auto-populate arrival info when the user only supplied a flight number.
        if itinerary_obj.arrival_flight_number and (
            not itinerary_obj.arrival_datetime or not itinerary_obj.arrival_airport
        ):
            assign(_fetch_flight_details(itinerary_obj.arrival_flight_number), "arrival")
    except requests.RequestException:
        pass

    try:
        # Attempt to auto-populate departure info when only the flight number is known.
        if itinerary_obj.departure_flight_number and (
            not itinerary_obj.departure_datetime or not itinerary_obj.departure_airport
        ):
            assign(_fetch_flight_details(itinerary_obj.departure_flight_number), "departure")
    except requests.RequestException:
        pass

    # Only hit the database when at least one field was updated.
    if updates:
        itinerary_obj.save(update_fields=list(updates))


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

    # Extract core itinerary fields for easier access.
    wake_time = getattr(itinerary_obj, "wake_up_time", "")
    bed_time = getattr(itinerary_obj, "bed_time", "")
    num_days = getattr(itinerary_obj, "num_days", 1)
    start_date = getattr(itinerary_obj, "start_date", None)
    end_date = getattr(itinerary_obj, "end_date", None)
    date_range = _format_date_range(start_date, end_date)
    meals_line = _meals_line(itinerary_obj)
    flight_ctx = _flight_prompt_details(itinerary_obj, num_days)
    hotel_summary, has_hotel_details, needs_hotel_suggestion = _hotel_plan_summary(
        itinerary_obj
    )

    # Build additional prompt sections.
    season_hint = _season_hint(start_date, end_date)
    overrides_block = _build_overrides_block(
        itinerary_obj,
        wake_time,
        bed_time,
        flight_ctx["excluded_days"],
    )

    # Collect any additional guidance the user provided.
    additional_guidance = _collect_additional_guidance(
        itinerary_obj,
        flight_ctx["has_arrival"],
        flight_ctx["has_departure"],
        has_hotel_details,
        needs_hotel_suggestion,
    )

    # Build and return the full prompt string using the helper output.
    return f"""
You are Wanderly's itinerary planner bot. Produce a JSON-only response; do not include prose.

=== Traveler Profile ===
Destination: {getattr(itinerary_obj, "destination", "")}
Dates: {date_range or 'Flexible'}
Party: {_summarize_party(itinerary_obj)}
Trip purpose: {itinerary_obj.get_trip_purpose_display()}
Energy level: {itinerary_obj.get_energy_level_display()}
Downtime required: {"Yes" if itinerary_obj.downtime_required else "No"}

=== Daily Rhythm & Meals ===
Wake time: {wake_time}
Bed time: {bed_time}
Flight-day wake/bed note: {flight_ctx['wake_note'] or 'Not applicable'}
Break windows: {_format_break_times(itinerary_obj)}
Meals to include: {meals_line}
Dietary notes: {itinerary_obj.dietary_notes or 'None'}
Mobility notes: {itinerary_obj.mobility_notes or 'None'}

=== Logistics ===
Flights:
{flight_ctx['block']}
Hotel / lodging: {hotel_summary}
Overall budget ceiling: ${itinerary_obj.overall_budget_max or 'Flexible'}
Budget categories: {_format_budget(itinerary_obj)}
Season / weather cue: {season_hint or 'Season unspecified'}

=== Additional Guidance ===
{additional_guidance}

=== Per-Day Overrides ===
{_format_day_notes(itinerary_obj) or 'No special per-day instructions were provided.'}
- Respect must-do items and constraints on the specified days.
- When arrival/departure flights exist, align Day 1 and the final day with those times.
- Wake/bed overrides by day:
{overrides_block}
{flight_ctx['tail_guidance']}

=== Output Contract ===
Respond with JSON shaped exactly like this example (real content, no comments):
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
      "title": "Arrival & Evening Stroll",
      "summary": "Brief human-readable summary of the day.",
      "activities": [
        {{
          "time": "09:00 AM",
          "name": "Garden of the Gods Hike",
          "description": "Short description explaining why this stop fits the traveler.",
          "duration": "2 hours",
          "cost_estimate": "$25",
          "must_do": true,
          "place_query": "Garden of the Gods Visitor Center, Colorado Springs",
          "requires_place": true
        }},
        {{
          "time": "08:30 PM",
          "name": "Night stroll downtown",
          "description": "Leisurely walk to window-shop and enjoy live music.",
          "duration": "1.5 hours",
          "cost_estimate": "$0",
          "must_do": false,
          "place_query": "",
          "requires_place": false
        }}
      ]
    }}
  ]
}}

Rules:
1. Provide 4-6 activities per day spanning wake to bed times. Use per-day overrides to adjust times.
2. Only set "requires_place": true when you reference a specific venue (restaurant, museum,
   tour operator, etc.). Generic activities (walk downtown, rest at hotel) must have
   "requires_place": false and an empty "place_query".
3. For any meal, coffee shop, nightlife, or ticketed attraction, list an actual venue name with
   city/neighborhood context inside "place_query". If you cannot confidently cite a real place,
   mark "requires_place": false and say the stop is flexible or traveler-choice.
4. Never fabricate venue names. If no venue is available, leave "place_query" empty and set
   "requires_place": false so the UI hides the ratings panel.
5. Keep activities safe, legal, and culturally appropriate.
   Skip anything that could be closed or unrealistic.
6. Align cost_estimate values with the traveler's budget distribution;
   spread spending through the trip.
7. Only add meal stops for meals the traveler selected. If they unchecked one,
   skip dedicated stops unless it is part of a must-do request.
8. Use the provided flight numbers exactly as supplied and cite the real airline
   from that data; never invent placeholder flights.
9. Any time you recommend a hotel, include a realistic nightly price or price
   range in the cost_estimate field using the existing "$" formatting.
10. Mention downtime or flexibility explicitly when the traveler asked for it.
11. If information is missing (no flights, no hotel), explicitly note
   "Arrival time TBD" or "Hotel TBD" instead of inventing details.
12. Use the season/weather cue to avoid out-of-season recommendations.
13. Reference the user's Activities & Notes when choosing venues. Match
   requested cuisine/vibes and state the cuisine style in the description.
14. When arrival flight info exists, Day 1 must begin with the arrival block
   described above; keep it concise and non-sensitive.
15. When hotel info exists, add a timed check-in block. If no hotel was supplied
   but the user asked Wanderly to pick one, choose a reasonable hotel within
   budget for their party and include it before the first set of activities with
   a price range in cost_estimate.
16. Do not repeat the same dining venue across the itinerary unless the traveler
   explicitly demanded it; vary restaurants/bars/coffee shops day-to-day.
17. Before returning the answer, double-check that your JSON matches the schema
   exactly and can be parsed without errors.
"""


def _generate_ai_itinerary(itinerary_obj: Itinerary) -> Optional[dict]:
    """Call OpenAI to generate an itinerary. Return structured payload or None."""

    # Instantiate the client with the configured API key.
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    # Build the structured prompt text for this itinerary.
    user_message = _build_ai_prompt(itinerary_obj)

    try:
        # Ask the model for a JSON object; OpenAI enforces structured output.
        response = client.chat.completions.create(
            model="gpt-5.1",
            messages=[{"role": "user", "content": user_message}],
            response_format={"type": "json_object"},
        )

        # Pull the JSON payload and parse it into a Python dict.
        ai_response = response.choices[0].message.content
        return json.loads(ai_response)

    except (OpenAIError, json.JSONDecodeError, KeyError, ValueError):
        # Any error during AI call or parsing results in a None return.
        return None


def _normalize_ai_payload(payload: Optional[dict]):
    """Normalize AI payload for storage while preserving backward compatibility."""
    if payload is None:
        return None
    if isinstance(payload, dict):
        if set(payload.keys()) == {"days"}:
            return payload.get("days")
        return payload
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


def _format_time_label(value):
    """Format time values without a leading zero."""
    if not value:
        return ""
    return value.strftime("%I:%M %p").lstrip("0")


def _enrich_ai_days(itinerary_obj: Itinerary, trip_days: list[Day]) -> list[dict]:
    """Attach per-day metadata and normalize activities for template rendering."""

    # Enrich each AI-generated day with its corresponding Day model.
    ai_payload = itinerary_obj.ai_itinerary or []
    if isinstance(ai_payload, dict):
        ai_itinerary_days = ai_payload.get("days", [])
    else:
        ai_itinerary_days = ai_payload

    # Build a lookup of Day objects by day number for easy access.
    day_lookup = {day.day_number: day for day in trip_days}

    # Enrich each AI day with its Day model and normalize activities.
    enriched_days = []

    # Iterate over each day in the AI-generated itinerary.
    for day in ai_itinerary_days:

        # Copy the day dict to avoid mutating the original.
        copied = dict(day)

        # Link to the corresponding Day model instance.
        copied["form_day"] = day_lookup.get(day.get("day_number"))

        # Normalize each activity's place_query and requires_place fields.
        for activity in copied.get("activities", []):
            place_query = (activity.get("place_query") or "").strip()
            requires_place = bool(place_query) and place_query.lower() != "not req"
            activity["place_query"] = place_query if requires_place else ""
            activity["requires_place"] = requires_place

        # Append the enriched day to the result list.
        enriched_days.append(copied)

    # Return the list of enriched days.
    return enriched_days


def _build_day_notes_display(itinerary_obj: Itinerary, trip_days: list[Day]) -> list[dict]:
    """Return display records describing per-day notes and overrides."""

    # Build a list of day notes for display in the detail view.
    display = []

    # Iterate over each Day to collect its fragments.
    for day in trip_days:

        # Build override text if applicable.
        override_text = ""

        # Check for wake/bed overrides.
        if day.wake_override or day.bed_override:
            override_text = (
                "Custom wake/bed: "
                f"{_format_time_label(day.wake_override or itinerary_obj.wake_up_time)} / "
                f"{_format_time_label(day.bed_override or itinerary_obj.bed_time)}"
            )

        # Append notes if they exist.
        fragments = collect_day_fragments(day, override_text)

        # Only add days with at least one fragment.
        if fragments:
            display.append(
                {
                    "day_number": day.day_number,
                    "date": day.date,
                    "text": "; ".join(fragments),
                }
            )

    # Return the built display list.
    return display


def itinerary(request):
    """
    Render the itinerary builder or process a submission.

    POST flow:
      1. Validate/persist the Itinerary model.
      2. Persist related rows (breaks, budgets, per-day customizations).
      3. Call OpenAI for the JSON plan and store it (even if empty) for later viewing.
    GET flow simply seeds an empty form. Validation errors fall through to re-render.
    """

    # Handle form submissions.
    if request.method == "POST":

        # Bind POST data to the form for validation.
        form = ItineraryForm(request.POST)

        # Continue only when the form passes validation.
        if form.is_valid():
            # Persist the base Itinerary record.
            itinerary_obj = form.save(commit=False)

            # Link to the authenticated user if available.
            if request.user.is_authenticated:
                itinerary_obj.user = request.user
            itinerary_obj.save()

            # Persist related rows from dynamic form sections.
            _create_break_times(request, itinerary_obj)
            _create_budget_items(request, itinerary_obj)
            _create_days(request, itinerary_obj)

            # If flight numbers were provided, try to auto-populate airports/times.
            _autofill_flight_data(itinerary_obj)

            if _should_generate_inline():
                ai_payload = _generate_ai_itinerary(itinerary_obj)
                if ai_payload is None:
                    messages.error(
                        request,
                        "We were unable to generate an AI-powered itinerary at this time.",
                        extra_tags="itinerary",
                    )
                else:
                    normalized = _normalize_ai_payload(ai_payload)
                    itinerary_obj.ai_itinerary = normalized
                    itinerary_obj.save(update_fields=["ai_itinerary"])
                    messages.success(
                        request,
                        "Itinerary created successfully. AI details generated.",
                        extra_tags="itinerary",
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
                    extra_tags="itinerary",
                )

            return redirect("itinerary:itinerary_detail", itinerary_obj.access_code)

        # Validation failed: fall through and re-render with errors.
        messages.error(request, "Please correct the errors below.", extra_tags="itinerary")
    else:
        # Render a blank form for GET requests.
        form = ItineraryForm()

    # Render template with whichever form instance we have (blank or bound).
    context = {
        "form": form,
    }

    return render(request, "itinerary.html", context)

def itinerary_detail(request, access_code: str):
    """Display a generated itinerary via access code."""
    itinerary_obj = get_object_or_404(Itinerary, access_code=access_code.upper())

    raw_payload = itinerary_obj.ai_itinerary
    is_generating = raw_payload is None

    if isinstance(raw_payload, dict):
        structured_payload = raw_payload
    elif isinstance(raw_payload, list):
        structured_payload = {"days": raw_payload}
    else:
        structured_payload = {}

    ai_itinerary_days = structured_payload.get("days", [])
    accommodation_info = structured_payload.get("accommodation")
    accommodation_budget = itinerary_obj.budget_items.filter(category="Accommodation").first()

    trip_days = list(itinerary_obj.days.all())
    enriched_days = _enrich_ai_days(itinerary_obj, trip_days)
    day_notes_display = _build_day_notes_display(itinerary_obj, trip_days)

    context = {
        "itinerary": itinerary_obj,
        "ai_itinerary_days": enriched_days,
        "accommodation_info": accommodation_info,
        "accommodation_budget": accommodation_budget,
        "break_times": itinerary_obj.break_times.all(),
        "budget_items": itinerary_obj.budget_items.all(),
        "trip_days": trip_days,
        "day_notes_display": day_notes_display,
        "is_generating": is_generating,
    }

    if is_generating:
        messages.info(
            request,
            "We're still generating the AI itinerary. This page will refresh automatically "
            "when it's ready.",
            extra_tags="itinerary",
        )
    elif not ai_itinerary_days:
        messages.warning(
            request,
            "We couldn't find an AI itinerary for this trip yet. Please wait a moment and "
            "try again.",
            extra_tags="itinerary",
        )

    return render(request, "itinerary_detail.html", context)

@login_required(login_url='sign_in')
def itinerary_list(request):
    ''' Load the list of current itineraries for current user.'''
    itineraries = Itinerary.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "itinerary_list.html", {"itineraries": itineraries})

def _itinerary_error_response(request, is_ajax, message, status_code):
    """
    Return a consistent error response for itinerary lookups.

    AJAX callers get JSON payloads so the front-end can surface errors inline,
    while regular form submissions fall back to Django messages + redirect.
    """

    # AJAX callers get structured JSON responses.
    if is_ajax:
        # Return a structured response the front-end can consume.
        return JsonResponse({"ok": False, "error": message}, status=status_code)

    # Regular form submissions use Django messages.
    messages.error(request, message, extra_tags="itinerary")

    # Redirect back to the main itinerary lookup page.
    return redirect("itinerary:itinerary")


@require_http_methods(["POST"])
def flight_lookup(request):
    """AJAX endpoint to fetch arrival/departure info from a flight number."""
    # Parse JSON payload
    try:

        payload = json.loads(request.body or "{}")

    # Handle malformed JSON gracefully.
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

    # Pull the trimmed flight number string from the payload.
    flight_number = (payload.get("flight_number") or "").strip()

    # Reject empty flight numbers immediately.
    if not flight_number:
        return JsonResponse({"error": "flight_number is required"}, status=400)

    # Call the helper to fetch flight details.
    try:
        # Perform the AviationStack lookup using the helper.
        details = _fetch_flight_details(flight_number)

    # Handle request exceptions from the helper.
    except requests.RequestException:
        return JsonResponse({"error": "Failed to contact flight lookup service"}, status=502)

    # Handle cases where no flight was found.
    if not details:
        return JsonResponse({"error": "No flight found for that number"}, status=404)

    # Return the normalized details for JavaScript to consume.
    return JsonResponse(details)


def find_itinerary(request):
    """
    Lookup an itinerary by access code and redirect or return JSON.

    Non-AJAX requests mirror the form behavior and redirect either to the
    itinerary landing page or the detail page. AJAX requests return a JSON
    payload with ``ok``/``error`` metadata.
    """

    # Determine whether the caller expects a JSON response.
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    redirect_home = redirect("itinerary:itinerary")

    # Only the POST route is supported for access lookups.
    if request.method != "POST":
        return _itinerary_error_response(request, is_ajax, "Invalid request method.", 405)

    # Pull the trimmed code from the submitted form data.
    code = request.POST.get("access_code", "").strip()

    # Reject empty codes immediately.
    if not code:
        return _itinerary_error_response(request, is_ajax, "Please enter an access code.", 400)

    # Attempt to look up the itinerary by its public access code.
    itinerary_obj = Itinerary.objects.filter(access_code=code).first()

    # Surface a friendly error if the code does not exist.
    if itinerary_obj is None:
        return _itinerary_error_response(
            request,
            is_ajax,
            "No itinerary found with that access code.",
            404,
        )

    # Redirect to the detail view upon success.
    detail_url = reverse("itinerary:itinerary_detail", args=[itinerary_obj.access_code])
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
            "places.userRatingCount,places.reviews,"
            "places.formattedAddress,places.primaryTypeDisplayName,"
            "places.regularOpeningHours.openNow,"
            "places.regularOpeningHours.weekdayDescriptions"
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
    # Inspect the first matching place record if any exist.
    place = (place_data.get("places") or [{}])[0]
    # Limit to five reviews to keep payload sizes manageable.
    reviews = place.get("reviews", [])[:5]

    # Format and return response
    opening_hours = place.get("regularOpeningHours") or {}

    # Return the normalized data structure consumed by the UI.
    return JsonResponse({
        "name": place.get("displayName", {}).get("text"),
        "rating": place.get("rating"),
        "count": place.get("userRatingCount"),
        "address": place.get("formattedAddress"),
        "primary_type": (place.get("primaryTypeDisplayName") or {}).get("text"),
        "open_now": opening_hours.get("openNow"),
        "hours": opening_hours.get("weekdayDescriptions") or [],
        "reviews": [
            {
                "text": r.get("text", {}).get("text"),
                "rating": r.get("rating"),
                "author": r.get("authorAttribution", {}).get("displayName"),
            }
            for r in reviews
        ],
    })


@login_required(login_url="sign_in")
@require_http_methods(["POST"])
def delete_itinerary(request, access_code: str):
    """Delete an itinerary owned by the current user."""
    itinerary_obj = get_object_or_404(
        Itinerary,
        access_code=access_code.upper(),
        user=request.user,
    )
    itinerary_obj.delete()
    messages.success(request, "Itinerary deleted successfully.")
    return redirect("itinerary:itinerary_list")
