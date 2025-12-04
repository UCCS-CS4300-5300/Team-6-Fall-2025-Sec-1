"""Controls the views and requests for the itinerary module."""
import json
import os
from typing import List, Optional
import requests

from django.conf import settings
from django.http import JsonResponse
from django.urls import reverse
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from openai import OpenAI, OpenAIError

from .forms import ItineraryForm
from .models import BreakTime, BudgetItem, Day, Itinerary


def _create_break_times(request, itinerary_obj: Itinerary) -> None:
    """Create BreakTime rows from POSTed form data."""
    break_start_times = request.POST.getlist("break_start_time[]")
    break_end_times = request.POST.getlist("break_end_time[]")
    break_purposes = request.POST.getlist("break_purpose[]")

    max_length = max(len(break_start_times), len(break_end_times), len(break_purposes))
    for idx in range(max_length):
        start = break_start_times[idx] if idx < len(break_start_times) else ""
        end = break_end_times[idx] if idx < len(break_end_times) else ""
        purpose = break_purposes[idx] if idx < len(break_purposes) else ""
        if start and end:
            # pylint: disable=no-member
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
        wake_override = request.POST.get(f"day_{day_index}_wake_override")
        bed_override = request.POST.get(f"day_{day_index}_bed_override")
        constraints = request.POST.get(f"day_{day_index}_constraints", "")
        must_do = request.POST.get(f"day_{day_index}_must_do", "")

        if day_date:  # Only save if date is provided
            # pylint: disable=no-member
            Day.objects.create(
                itinerary=itinerary_obj,
                day_number=day_index,
                date=day_date,
                notes=day_notes,
                wake_override=wake_override or None,
                bed_override=bed_override or None,
                constraints=constraints,
                must_do=must_do,
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
    day_note_lines = []
    for day in day_notes_qs:
        fragments = []
        if day.notes:
            fragments.append(day.notes)
        if day.must_do:
            fragments.append(f"Must-do: {day.must_do}")
        if day.constraints:
            fragments.append(f"Constraints: {day.constraints}")
        if day.wake_override or day.bed_override:
            fragments.append(
                f"Custom wake/bed: {day.wake_override or 'same'} / {day.bed_override or 'same'}"
            )
        if fragments:
            joined = "; ".join(fragments)
            day_note_lines.append(f"Day {day.day_number} ({day.date}): {joined}")

    if not day_note_lines:
        return ""

    joined = "\n".join(day_note_lines)
    return f"User preferences for specific days:\n{joined}\n\n"


def _build_ai_prompt(itinerary_obj: Itinerary) -> str:
    """Build the user message sent to the OpenAI model."""
    destination = getattr(itinerary_obj, "destination", "")
    wake_time = getattr(itinerary_obj, "wake_up_time", "")
    bed_time = getattr(itinerary_obj, "bed_time", "")
    num_days = getattr(itinerary_obj, "num_days", 1)
    start_date = getattr(itinerary_obj, "start_date", None)
    end_date = getattr(itinerary_obj, "end_date", None)
    trip_purpose = itinerary_obj.get_trip_purpose_display()
    adults = getattr(itinerary_obj, "party_adults", 1)
    children = getattr(itinerary_obj, "party_children", 0)

    break_times_str = _format_break_times(itinerary_obj)
    budget_str = _format_budget(itinerary_obj)
    extra_notes = _format_day_notes(itinerary_obj)
    date_range = ""
    if start_date and end_date:
        date_range = f"{start_date:%B %d, %Y} through {end_date:%B %d, %Y}"
    elif start_date:
        date_range = f"Start date: {start_date:%B %d, %Y}"

    party_summary = f"{adults} adult{'s' if adults != 1 else ''}"
    if children:
        party_summary += f" and {children} child{'ren' if children != 1 else ''}"

    meal_preferences = []
    if itinerary_obj.include_breakfast:
        meal_preferences.append("breakfast")
    if itinerary_obj.include_lunch:
        meal_preferences.append("lunch")
    if itinerary_obj.include_dinner:
        meal_preferences.append("dinner")
    meals_line = ", ".join(meal_preferences) if meal_preferences else "No planned meals"

    flight_lines = []
    if itinerary_obj.arrival_datetime:
        arrival_airport = itinerary_obj.arrival_airport or "unspecified airport"
        flight_lines.append(
            f"- Arrival flight reaches {arrival_airport} on "
            f"{itinerary_obj.arrival_datetime:%B %d at %I:%M %p}."
        )
    if itinerary_obj.departure_datetime:
        departure_airport = itinerary_obj.departure_airport or "unspecified airport"
        flight_lines.append(
            f"- Departure flight leaves {departure_airport} on "
            f"{itinerary_obj.departure_datetime:%B %d at %I:%M %p}."
        )
    flight_block = "\n".join(flight_lines) or "No flights provided."

    hotel_summary = "Hotel TBD"
    if (
        itinerary_obj.hotel_address
        or itinerary_obj.hotel_name
        or itinerary_obj.hotel_check_in
        or itinerary_obj.hotel_check_out
    ):
        hotel_parts = []
        if itinerary_obj.hotel_address:
            hotel_parts.append(itinerary_obj.hotel_address)
        if itinerary_obj.hotel_name:
            hotel_parts.append(itinerary_obj.hotel_name)
        if itinerary_obj.hotel_check_in:
            hotel_parts.append(f"Check-in {itinerary_obj.hotel_check_in:%B %d at %I:%M %p}")
        if itinerary_obj.hotel_check_out:
            hotel_parts.append(f"Check-out {itinerary_obj.hotel_check_out:%B %d at %I:%M %p}")
        hotel_summary = " | ".join(hotel_parts)

    season_hint = ""
    ref_date = start_date or end_date
    if ref_date:
        month = ref_date.month
        if month in (12, 1, 2):
            season_hint = f"Travel month: {ref_date:%B} (expect winter conditions)."
        elif month in (3, 4, 5):
            season_hint = f"Travel month: {ref_date:%B} (spring shoulder season)."
        elif month in (6, 7, 8):
            season_hint = f"Travel month: {ref_date:%B} (peak summer weather)."
        else:
            season_hint = f"Travel month: {ref_date:%B} (autumn conditions)."

    override_lines = []
    # pylint: disable=no-member
    for day in Day.objects.filter(itinerary=itinerary_obj).order_by("day_number"):
        if day.wake_override or day.bed_override:
            override_lines.append(
                f"- Day {day.day_number}: wake at {day.wake_override or wake_time}, bed by {day.bed_override or bed_time}"
            )
    overrides_block = "\n".join(override_lines) or "None supplied; use the global wake/bed times."

    return f"""
You are Wanderly's itinerary planner bot. Produce a JSON-only response; do not include prose.

=== Traveler Profile ===
Destination: {destination}
Dates: {date_range or 'Flexible'}
Party: {party_summary}
Trip purpose: {trip_purpose}
Energy level: {itinerary_obj.get_energy_level_display()}
Downtime required: {"Yes" if itinerary_obj.downtime_required else "No"}

=== Daily Rhythm & Meals ===
Wake time: {wake_time}
Bed time: {bed_time}
Break windows: {break_times_str}
Meals to include: {meals_line}
Dietary notes: {itinerary_obj.dietary_notes or 'None'}
Mobility notes: {itinerary_obj.mobility_notes or 'None'}

=== Logistics ===
Flights:
{flight_block}
Hotel / lodging: {hotel_summary}
Overall budget ceiling: ${itinerary_obj.overall_budget_max or 'Flexible'}
Budget categories: {budget_str}
Season / weather cue: {season_hint or 'Season unspecified'}

=== Per-Day Overrides ===
{extra_notes or 'No special per-day instructions were provided.'}
- Respect must-do items and constraints on the specified days.
- When arrival/departure flights exist, align Day 1 and the final day with those times.
- Wake/bed overrides by day:
{overrides_block}
- Do not schedule activities before the arrival flight lands or within 1 hour of the departure flight; mention this buffer in your plan if applicable.

=== Output Contract ===
Respond with JSON shaped exactly like this example (real content, no comments):
{{
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
2. Only set "requires_place": true when you reference a specific venue (restaurant, museum, tour operator, etc.).
   Generic activities (walk downtown, rest at hotel) must have "requires_place": false and an empty "place_query".
3. For any meal, coffee shop, nightlife, or ticketed attraction, list an actual venue name with city/neighborhood context inside "place_query".
   If you cannot confidently cite a real place, mark "requires_place": false and say the stop is flexible or traveler-choice.
4. Never fabricate venue names. If no venue is available, leave "place_query" empty and set "requires_place": false so the UI will hide ratings.
5. Keep activities safe, legal, and culturally appropriate. Skip anything that could be closed or unrealistic.
6. Align cost_estimate values with the traveler's budget and category emphasis, distributing spending through the trip.
7. Mention downtime or flexibility explicitly when the traveler asked for it.
8. If information is missing (no flights, no hotel), explicitly note "Arrival time TBD" or "Hotel TBD" instead of inventing details.
9. Use the season/weather cue to avoid out-of-season recommendations.
10. Reference the user's Activities & Notes when choosing venues—if they request a cuisine or vibe for a day, pick a restaurant/coffee shop that matches it and state the cuisine in the description.
11. Do not repeat the same dining venue across the itinerary unless the traveler explicitly demanded it; vary restaurants/bars/coffee shops day-to-day.
12. Before returning the answer, double-check that your JSON matches the schema exactly and can be parsed without errors.
"""


def _generate_ai_itinerary(itinerary_obj: Itinerary) -> Optional[list]:
    """Call OpenAI to generate an itinerary. Return a list of days or None."""
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    user_message = _build_ai_prompt(itinerary_obj)

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": user_message}],
            response_format={"type": "json_object"},
        )
        ai_response = response.choices[0].message.content
        parsed = json.loads(ai_response)
        return parsed.get("days", [])
    except (OpenAIError, json.JSONDecodeError, KeyError, ValueError):
        # The calling view is responsible for displaying a user-facing error.
        return None


def itinerary(request):
    """View for creating and displaying itineraries."""
    if request.method == "POST":
        form = ItineraryForm(request.POST)

        if form.is_valid():
            itinerary_obj = form.save()

            _create_break_times(request, itinerary_obj)
            _create_budget_items(request, itinerary_obj)
            _create_days(request, itinerary_obj)

            ai_itinerary_days = _generate_ai_itinerary(itinerary_obj)
            if ai_itinerary_days is None:
                messages.error(
                    request,
                    "We were unable to generate an AI-powered itinerary at this time.",
                )
            else:
                # Persist whatever we got back (including empty lists) so it is available later.
                itinerary_obj.ai_itinerary = ai_itinerary_days
                itinerary_obj.save(update_fields=["ai_itinerary"])

            messages.success(request, "Itinerary created successfully!")
            return redirect("itinerary:itinerary_detail", itinerary_obj.access_code)

        # No `else` needed; if the form is invalid we fall through and re-render.
        messages.error(request, "Please correct the errors below.")
    else:
        form = ItineraryForm()

    context = {
        "form": form,
    }

    return render(request, "itinerary.html", context)

def itinerary_detail(request, access_code: str):
    """Display a generated itinerary."""
    itinerary_obj = get_object_or_404(Itinerary, access_code=access_code.upper())
    ai_itinerary_days = itinerary_obj.ai_itinerary or []
    trip_days_qs = itinerary_obj.days.all()
    day_lookup = {day.day_number: day for day in trip_days_qs}
    def format_time_label(value):
        """Format a time object for display without leading zero."""
        if not value:
            return ""
        return value.strftime("%I:%M %p").lstrip("0")
    enriched_days = []
    for day in ai_itinerary_days:
        copied = dict(day)
        copied["form_day"] = day_lookup.get(day.get("day_number"))
        activities = copied.get("activities", [])
        for activity in activities:
            place_query = (activity.get("place_query") or "").strip()
            requires_place = bool(place_query) and place_query.lower() != "not req"
            if not requires_place:
                place_query = ""
            activity["place_query"] = place_query
            activity["requires_place"] = requires_place
        enriched_days.append(copied)

    day_notes_display = []
    for day in trip_days_qs:
        fragments = []
        if day.notes:
            fragments.append(day.notes)
        if day.must_do:
            fragments.append(f"Must-do: {day.must_do}")
        if day.constraints:
            fragments.append(f"Constraints: {day.constraints}")
        if day.wake_override or day.bed_override:
            fragments.append(
                "Custom wake/bed: "
                f"{format_time_label(day.wake_override or itinerary_obj.wake_up_time)} / "
                f"{format_time_label(day.bed_override or itinerary_obj.bed_time)}"
            )
        if fragments:
            day_notes_display.append(
                {
                    "day_number": day.day_number,
                    "date": day.date,
                    "text": "; ".join(fragments),
                }
            )

    context = {
        "itinerary": itinerary_obj,
        "ai_itinerary_days": enriched_days,
        "break_times": itinerary_obj.break_times.all(),
        "budget_items": itinerary_obj.budget_items.all(),
        "trip_days": trip_days_qs,
        "day_notes_display": day_notes_display,
    }

    if not ai_itinerary_days:
        messages.error(
            request,
            "This itinerary is missing generated details.",
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
    Takes an access code from the user (currently the itinerary ID)
    then redirect to the matching itinerary detail page.
    """

    # Checking to make sure the request is ajax to /itinerary/access/
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    # Making sure the request is post so only coming from the form
    if request.method != "POST":
        return _itinerary_error_response(request, is_ajax, "Invalid request method.", 405)

    # Getting the access_code from the request
    code = request.POST.get("access_code", "").strip()

    # If there was no code return a response
    if not code:
        return _itinerary_error_response(request, is_ajax, "Please enter an access code.", 400)

    # Grab the itinerary object from the database using the itinerary_id
    itinerary_obj = Itinerary.objects.filter(access_code=code).first() # pylint: disable=no-member

    # If there is no itinerary with that id return a repsonse
    if itinerary_obj is None:
        return _itinerary_error_response(
            request,
            is_ajax,
            "No itinerary found with that access code.",
            404,
        )

    # Success
    detail_url = reverse("itinerary:itinerary_detail", args=[itinerary_obj.access_code])

    if is_ajax:
        return JsonResponse({"ok": True, "redirect_url": detail_url})

    return redirect(detail_url)


# ------------- Reviews -------------

@require_http_methods(["POST"])
def place_reviews(request):
    """Fetch ratings and reviews for a place using Google Places API."""

    # Parse JSON payload
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

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
    place = (place_data.get("places") or [{}])[0]
    reviews = place.get("reviews", [])[:5]  # include positive & negative

    # Format and return response
    opening_hours = place.get("regularOpeningHours") or {}

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
