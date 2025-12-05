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
from django.utils.dateparse import parse_datetime
from openai import OpenAI, OpenAIError

from .forms import ItineraryForm
from .models import BreakTime, BudgetItem, Day, Itinerary


def _create_break_times(request, itinerary_obj: Itinerary) -> None:
    """Create BreakTime rows from POSTed form data."""
    # Parallel arrays from the dynamic break inputs.
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

        # pylint: disable=no-member
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

def _format_break_times(itinerary_obj: Itinerary) -> str:
    """Return a human-readable break time string for an itinerary."""

    # Query all break rows associated with this itinerary.
    break_times = BreakTime.objects.filter(itinerary=itinerary_obj)

    # When no entries exist we explicitly say "None".
    if not break_times.exists():
        return "None"

    # Convert each break slot to "start-end" form and join with commas.
    return ", ".join(f"{bt.start_time}-{bt.end_time}" for bt in break_times)


def _format_budget(itinerary_obj: Itinerary) -> str:
    """Return a human-readable budget string for an itinerary."""

    # Query all budget rows associated with this itinerary.
    budget_items = BudgetItem.objects.filter(itinerary=itinerary_obj)

    # A missing budget is treated as "Flexible" spending.
    if not budget_items.exists():
        return "Flexible"

    # Collect each formatted segment before return.
    budget_parts: List[str] = []
    for item in budget_items:
        # Use the custom label when the user provided one under "Other".
        label = (
            item.custom_category
            if item.category == "Other" and item.custom_category
            else item.category
        )
        budget_parts.append(f"{label}: ${item.amount}")

    # Return a compact comma-separated summary.
    return ", ".join(budget_parts)


def _format_day_notes(itinerary_obj: Itinerary) -> str:
    """Return extra notes string describing per-day notes, if any."""
    # pylint: disable=no-member
    day_notes_qs = Day.objects.filter(itinerary=itinerary_obj).order_by("day_number")

    # Store each day's notes string for later concatenation.
    day_note_lines = []
    for day in day_notes_qs:

        # Build up a list of snippets for this day (notes, must-do, etc.).
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

        # Only append entries that actually contain text.
        if fragments:
            joined = "; ".join(fragments)
            day_note_lines.append(f"Day {day.day_number} ({day.date}): {joined}")

    # When no per-day metadata exists we return an empty string.
    if not day_note_lines:
        return ""

    # Combine all of the lines into a single summary block.
    joined = "\n".join(day_note_lines)
    return f"User preferences for specific days:\n{joined}\n\n"


def _fetch_flight_details(flight_number: str) -> Optional[dict]:
    """Call AviationStack to fetch flight details for a given flight number."""

    # Dont call API if we lack a flight number or API key.
    if not flight_number or not os.environ['AVIATIONSTACK_API_KEY']:
        return None

    # Build the AviationStack query parameters using the supplied flight number.
    params = {
        "access_key": os.environ['AVIATIONSTACK_API_KEY'],
        "flight_iata": flight_number.strip().upper(),
    }

    # Call API to retrieve the flight data.
    response = requests.get(
        "http://api.aviationstack.com/v1/flights",
        params=params,
        timeout=15,
    )

    # Raise for any HTTP errors to standardize error handling upstream.
    response.raise_for_status()

    # Parse the returned payload into JSON.
    payload = response.json()

    # AviationStack can return error dicts instead of HTTP errors, so handle that.
    if isinstance(payload, dict) and payload.get("error"):
        raise requests.RequestException(payload["error"].get("info", "API error"))
    
    # Grab the data array and gracefully handle empty responses.
    flights = payload.get("data") or []
    if not flights:
        return None

    # We only need the first matching flight for this UI flow.
    flight = flights[0]

    # Extract the airline name for later display.
    airline = (flight.get("airline") or {}).get("name") or ""

    # Normalize the flight number field from the API.
    number = (flight.get("flight") or {}).get("iata") or flight_number

    # Capture both the departure and arrival sections for reuse.
    departure = flight.get("departure") or {}
    arrival = flight.get("arrival") or {}

    def _extract(section):
        """Return code, full name, and timestamp string for a flight section."""
        # When the section is missing we return canonical empty values.
        if not section:
            return "", "", ""
        
        # Pull out the short IATA code if present.
        airport_code = section.get("iata") or ""

        # Pull out the human readable airport name.
        airport_name = section.get("airport") or ""

        # Prefer the scheduled time but fall back to the estimated timestamp.
        time_raw = section.get("scheduled") or section.get("estimated") or ""
        return airport_code, airport_name, time_raw

    # Parse the departure bundle into a tuple of values.
    departure_code, departure_name, departure_time = _extract(departure)
    
    # Parse the arrival bundle into a tuple of values.
    arrival_code, arrival_name, arrival_time = _extract(arrival)

    # Return a normalized dictionary that the rest of the codebase understands.
    return {
        "flight_number": number,
        "airline": airline,
        "departure_airport": departure_code,
        "departure_airport_name": departure_name,
        "departure_time": departure_time,
        "arrival_airport": arrival_code,
        "arrival_airport_name": arrival_name,
        "arrival_time": arrival_time,
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


def _build_ai_prompt(itinerary_obj: Itinerary) -> str:
    """Build the user message sent to the OpenAI model."""
    
    # Extract core itinerary fields for easier access.
    destination = getattr(itinerary_obj, "destination", "")
    wake_time = getattr(itinerary_obj, "wake_up_time", "")
    bed_time = getattr(itinerary_obj, "bed_time", "")
    num_days = getattr(itinerary_obj, "num_days", 1)
    start_date = getattr(itinerary_obj, "start_date", None)
    end_date = getattr(itinerary_obj, "end_date", None)
    trip_purpose = itinerary_obj.get_trip_purpose_display()
    adults = getattr(itinerary_obj, "party_adults", 1)
    children = getattr(itinerary_obj, "party_children", 0)

    # Text fragments reused across multiple sections.
    break_times_str = _format_break_times(itinerary_obj)
    budget_str = _format_budget(itinerary_obj)
    extra_notes = _format_day_notes(itinerary_obj)

    # Format the date range string.
    date_range = ""

    # Build date range when both dates are present.
    if (start_date) and (end_date):
        date_range = f"{start_date:%B %d, %Y} through {end_date:%B %d, %Y}"

    # Handle the end-date-only case.
    elif start_date:
        date_range = f"Start date: {start_date:%B %d, %Y}"

    # Mention how many people are in the party.
    party_summary = f"{adults} adult{'s' if adults != 1 else ''}"
    if children:
        party_summary += f" and {children} child{'ren' if children != 1 else ''}"

    # Convey which meals should turn into explicit stops.
    meal_preferences = []
    if itinerary_obj.include_breakfast:
        meal_preferences.append("breakfast")
    if itinerary_obj.include_lunch:
        meal_preferences.append("lunch")
    if itinerary_obj.include_dinner:
        meal_preferences.append("dinner")
    if meal_preferences:
        joined_meals = ", ".join(meal_preferences)
        meals_line = f"{joined_meals} (schedule meal stops only for these selections)"
    else:
        meals_line = "No planned meals; skip dedicated meal stops unless explicitly requested elsewhere"

    # Summarize the flight plan into bullet points.
    def _format_flight_line(direction: str, dt_value, airport_label: str, airline_label: str, flight_number: str) -> str:
        """Return a descriptive bullet without performing additional API lookups."""

        # Skip empty flight entries.
        if not any([dt_value, airport_label, airline_label, flight_number]):
            return ""
        
        # Build the flight line prefix.
        normalized_number = (flight_number or "").upper()

        # Construct the prefix and suffix parts.
        if airline_label and normalized_number:
            prefix = f"{airline_label} Flight {normalized_number}"
        elif airline_label:
            prefix = f"{airline_label} Flight"
        elif normalized_number:
            prefix = f"Flight {normalized_number}"
        else:
            prefix = "Flight"
        if direction == "arrival":
            verb = "arrives at"
        else:
            verb = "departs from"
        time_hint = dt_value.strftime("%B %d at %I:%M %p") if dt_value else ""
        suffix_parts = []

        # Append airport and time hints when available.
        if airport_label:
            suffix_parts.append(f"{verb} {airport_label}")

        # Append time hint when available.
        if time_hint:
            suffix_parts.append(f"on {time_hint}")

        # Join the suffix parts into a single string.
        suffix = ", ".join(suffix_parts)

        # Return the full formatted line.
        return f"- {prefix} {suffix}." if suffix else f"- {prefix}."

    # Flights are optional. Provide a bullet per direction so the AI respects buffers.
    flight_lines = []

    # Format arrival and departure flight lines when data exists.
    arrival_line = _format_flight_line(
        "arrival",
        itinerary_obj.arrival_datetime,
        itinerary_obj.arrival_airport,
        itinerary_obj.arrival_airline,
        itinerary_obj.arrival_flight_number,
    )

    # Format departure flight line.
    departure_line = _format_flight_line(
        "departure",
        itinerary_obj.departure_datetime,
        itinerary_obj.departure_airport,
        itinerary_obj.departure_airline,
        itinerary_obj.departure_flight_number,
    )

    # Append non-empty flight lines to the block.
    if arrival_line:
        flight_lines.append(arrival_line)

    # Append departure line if present.
    if departure_line:
        flight_lines.append(departure_line)

    # Combine flight lines into a single block or note absence.
    flight_block = "\n".join(flight_lines) or "No flights provided."

    # Summarize the lodging plan, defaulting to "Hotel TBD" so the model doesn't invent one.
    hotel_summary = "Hotel TBD"

    # Determine if we have enough hotel details to avoid suggesting one.
    has_hotel_details = any(
        [
            itinerary_obj.hotel_address,
            itinerary_obj.hotel_name,
            itinerary_obj.hotel_check_in,
            itinerary_obj.hotel_check_out,
        ]
    )

    # Determine if we need to ask the AI to suggest a hotel.
    needs_hotel_suggestion = bool(itinerary_obj.auto_suggest_hotel and not has_hotel_details)

    # Build the hotel summary line based on available data.
    if has_hotel_details:
        hotel_parts = [] # Collect hotel details into parts.

        # Append each available hotel detail.
        if itinerary_obj.hotel_address:
            hotel_parts.append(itinerary_obj.hotel_address)
        if itinerary_obj.hotel_name:
            hotel_parts.append(itinerary_obj.hotel_name)
        if itinerary_obj.hotel_check_in:
            hotel_parts.append(f"Check-in {itinerary_obj.hotel_check_in:%B %d at %I:%M %p}")
        if itinerary_obj.hotel_check_out:
            hotel_parts.append(f"Check-out {itinerary_obj.hotel_check_out:%B %d at %I:%M %p}")
        hotel_summary = " | ".join(hotel_parts)

    # If no hotel was provided but the user wants a suggestion, inform the AI.
    elif needs_hotel_suggestion:
        hotel_summary = (
            f"Need Wanderly to recommend a hotel suitable for {party_summary} "
            f"within the ${itinerary_obj.overall_budget_max or 'Flexible'} budget."
        )

    # Provide a seasonal/weather hint based on trip dates.
    season_hint = ""

    # Determine the reference date for seasonality (start or end date).
    ref_date = start_date or end_date

    # Build a seasonal hint when we have a reference date.
    if (ref_date):
        month = ref_date.month
        if month in (12, 1, 2):
            season_hint = f"Travel month: {ref_date:%B} (expect winter conditions)."
        elif month in (3, 4, 5):
            season_hint = f"Travel month: {ref_date:%B} (spring shoulder season)."
        elif month in (6, 7, 8):
            season_hint = f"Travel month: {ref_date:%B} (peak summer weather)."
        else:
            season_hint = f"Travel month: {ref_date:%B} (autumn conditions)."

    # Determine if arrival/departure flights exist to adjust wake/bed guidance.
    has_arrival_info = bool(
        itinerary_obj.arrival_datetime
        or itinerary_obj.arrival_airport
        or itinerary_obj.arrival_flight_number
    )

    # Determine if departure flight info exists.
    has_departure_info = bool(
        itinerary_obj.departure_datetime
        or itinerary_obj.departure_airport
        or itinerary_obj.departure_flight_number
    )

    # Build a note about flight-driven wake/bed times when applicable.
    flight_wake_note = ""

    # When either arrival or departure info exists, inform the AI.
    if has_arrival_info or has_departure_info:
        impacted_sections = []

        # Identify which days are affected by flight schedules.
        if has_arrival_info:
            impacted_sections.append("Day 1 (arrival day)")

        # Identify departure day when applicable.
        if has_departure_info and num_days:
            impacted_sections.append(f"Day {num_days} (departure day)")

        # Build the flight-driven wake/bed note.
        flight_wake_note = (
            "Ignore typical wake/bed expectations on "
            + " and ".join(impacted_sections)
            + " because flights dictate those schedules."
        )

    # Gather any per-day overrides to feed into the prompt in a machine-friendly list,
    # skipping the arrival/departure days so flights can control those timelines.
    override_lines = []

    # Determine which days to exclude from wake/bed overrides.
    flight_excluded_days = set()

    # Exclude arrival day when applicable.
    if has_arrival_info:
        flight_excluded_days.add(1)

    # Exclude departure day when applicable.
    if has_departure_info and num_days:
        flight_excluded_days.add(num_days)
    
    # Iterate over each Day to find wake/bed overrides.
    for day in Day.objects.filter(itinerary=itinerary_obj).order_by("day_number"):
        if day.day_number in flight_excluded_days:
            continue

        # Only include days that have at least one override.
        if day.wake_override or day.bed_override:
            override_lines.append(
                f"- Day {day.day_number}: wake at {day.wake_override or wake_time}, bed by {day.bed_override or bed_time}"
            )

    # Build the final overrides block for the prompt.
    if override_lines:
        overrides_block = "\n".join(override_lines)

        # Append a note about excluded days when applicable.
        if flight_excluded_days:
            overrides_block += (
                "\n(Arrival/departure days are omitted because flights override wake/bed windows.)"
            )
    else: # No overrides were provided.
        overrides_block = "None supplied; use the global wake/bed times."

    # Build additional guidance based on flights and hotel data.
    guidance_lines = []

    # Arrival flight guidance.
    if has_arrival_info:
        guidance_lines.append(
            "Day 1 must begin with an \"Arrival Flight\" block summarizing the airline, flight number, "
            "arrival airport, and arrival time (omit PNR). Ignore the typical wake/bed windows for this day."
        )
        guidance_lines.append(
            "Even if overrides are configured, do not enforce wake/bed times on the arrival day; anchor the schedule around the flight."
        )

    # Hotel check-in guidance.
    if has_hotel_details:
        check_in_str = (
            f"{itinerary_obj.hotel_check_in:%I:%M %p}"
            if itinerary_obj.hotel_check_in
            else "the typical afternoon check-in window"
        )

        # Determine a label for the hotel in the guidance.
        hotel_label = itinerary_obj.hotel_name or itinerary_obj.hotel_address or "the hotel"
        guidance_lines.append(
            f"Include a dedicated \"Check in at {hotel_label}\" block timed near {check_in_str}, "
            "and remind travelers to wind down or return there when appropriate."
        )

    # Hotel suggestion guidance.
    elif needs_hotel_suggestion:
        guidance_lines.append(
            "No hotel was provided, so choose a realistic hotel that fits the party size and budget ceiling, "
            "mention it explicitly before the first full day, include a nightly price range in the cost_estimate field, "
            "and respect its check-in/out windows."
        )

    # Departure flight guidance.
    if has_departure_info:
        guidance_lines.append(
            "On the final day ignore typical wake/bed times and instead shape the schedule around the departure flight, leaving a buffer of at least one hour beforehand."
        )

    # Combine all additional guidance lines into a single block.
    additional_guidance = "\n".join(guidance_lines) or "None."

    # Build and return the full prompt string.
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
Flight-day wake/bed note: {flight_wake_note or 'Not applicable'}
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

=== Additional Guidance ===
{additional_guidance}

=== Per-Day Overrides ===
{extra_notes or 'No special per-day instructions were provided.'}
- Respect must-do items and constraints on the specified days.
- When arrival/departure flights exist, align Day 1 and the final day with those times.
- Wake/bed overrides by day:
{overrides_block}
{"- Do not schedule activities before the arrival flight lands or within 1 hour of the departure flight; mention this buffer in your plan if applicable." if has_arrival_info or has_departure_info else "- Flights were not provided, so treat the trip as fully land-based with no arrival/departure buffers."}

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
7. Only add meal stops for the meals the traveler selected; if they unchecked a meal, skip dedicated stops for it unless it is explicitly part of a must-do request.
8. Use the provided flight numbers exactly as supplied and cite the real airline from that data; never invent placeholder airlines or flight codes.
9. Any time you recommend a hotel (user-provided or Wanderly-suggested), include a realistic nightly price or price range in the cost_estimate field using the existing "$" formatting.
10. Mention downtime or flexibility explicitly when the traveler asked for it.
11. If information is missing (no flights, no hotel), explicitly note "Arrival time TBD" or "Hotel TBD" instead of inventing details.
12. Use the season/weather cue to avoid out-of-season recommendations.
13. Reference the user's Activities & Notes when choosing venues-if they request a cuisine or vibe for a day, pick a restaurant/coffee shop that matches it and state the cuisine in the description.
14. When arrival flight info exists, Day 1 must begin with the arrival block described above; keep it concise and non-sensitive.
15. When hotel info exists, add a timed check-in block; if no hotel was supplied but the user asked Wanderly to pick one, choose a reasonable hotel within budget for their party and include it before the first set of activities, again including a price range in cost_estimate.
16. Do not repeat the same dining venue across the itinerary unless the traveler explicitly demanded it; vary restaurants/bars/coffee shops day-to-day.
17. Before returning the answer, double-check that your JSON matches the schema exactly and can be parsed without errors.
"""


def _generate_ai_itinerary(itinerary_obj: Itinerary) -> Optional[list]:
    """Call OpenAI to generate an itinerary. Return a list of days or None."""

    # Instantiate the client with the configured API key.
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    # Build the structured prompt text for this itinerary.
    user_message = _build_ai_prompt(itinerary_obj)

    try:
        # Ask the model for a JSON object; OpenAI enforces structured output.
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": user_message}],
            response_format={"type": "json_object"},
        )

        # Pull the JSON payload and parse it into a Python dict.
        ai_response = response.choices[0].message.content
        parsed = json.loads(ai_response)

        # Return just the list of days, defaulting to [] when missing.
        return parsed.get("days", [])
    
    except (OpenAIError, json.JSONDecodeError, KeyError, ValueError):
        # Any error during AI call or parsing results in a None return.
        return None


def itinerary(request):
    """
    Render the itinerary builder or process a submission.

    POST flow:
      1. Validate/persist the Itinerary model.
      2. Persist related rows (breaks, budgets, per-day customizations).
      3. Call OpenAI for the JSON plan and store it (even if empty) for later viewing.
    GET flow simply seeds an empty form. Validation errors fall through to re-render.
    """

    #
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

            # Kick off AI generation and store the structured result if present.
            ai_itinerary_days = _generate_ai_itinerary(itinerary_obj)

            # Handle the case where AI generation failed.
            if ai_itinerary_days is None:
                messages.error(
                    request,
                    "We were unable to generate an AI-powered itinerary at this time.",
                )
            else:
                # Save the generated itinerary days onto the model.
                itinerary_obj.ai_itinerary = ai_itinerary_days
                itinerary_obj.save(update_fields=["ai_itinerary"])

            # Redirect to the detail view upon success.
            messages.success(request, "Itinerary created successfully!")

            # Redirect to the itinerary detail page.
            return redirect("itinerary:itinerary_detail", itinerary_obj.access_code)

        # Validation failed: fall through and re-render with errors.
        messages.error(request, "Please correct the errors below.")
    else:
        # Render a blank form for GET requests.
        form = ItineraryForm()

    # Render template with whichever form instance we have (blank or bound).
    context = {
        "form": form,
    }

    return render(request, "itinerary.html", context)

def itinerary_detail(request, access_code: str):
    """Display a generated itinerary."""

    # Fetch the itinerary or return 404 if not found.
    itinerary_obj = get_object_or_404(Itinerary, access_code=access_code.upper())

    # Pull the AI-generated itinerary days (if any).
    ai_itinerary_days = itinerary_obj.ai_itinerary or []

    # Query all persisted Day rows for this itinerary.
    trip_days_qs = itinerary_obj.days.all()

    # Build a lookup map of day_number -> Day row for quick access.
    day_lookup = {day.day_number: day for day in trip_days_qs}

    # Helper to format time objects without leading zeros.
    def format_time_label(value):
        """Format a time object for display without leading zero."""

        # Return blank strings when no time exists.
        if not value:
            return ""
        
        # Format in 12-hour style and strip any leading zero.
        return value.strftime("%I:%M %p").lstrip("0")

    # Store enriched AI day dictionaries for template rendering.
    enriched_days = []

    # Iterate over each AI-generated day to normalize data.
    for day in ai_itinerary_days:

        # Copy each AI entry so we can mutate without modifying the stored JSON.
        copied = dict(day)

        # Link to the corresponding Day row for metadata access.
        copied["form_day"] = day_lookup.get(day.get("day_number"))

        # Pull the list of activities for this day.
        activities = copied.get("activities", [])

        # Normalize each activity within the day.
        for activity in activities:

            # Normalize place data so templates only request reviews when a venue exists.
            place_query = (activity.get("place_query") or "").strip()

            # Determine whether this activity requires a specific place lookup.
            requires_place = bool(place_query) and place_query.lower() != "not req"

            # When no place is required, clear out the query to avoid confusion.
            if not requires_place:
                place_query = ""

            # Update the activity in place.
            activity["place_query"] = place_query
            activity["requires_place"] = requires_place

        # Append the enriched day to the final list.
        enriched_days.append(copied)

    # Build helper data for rendering the per-day annotations panel.
    day_notes_display = []

    # Iterate over each Day row to extract notes, must-dos, constraints, and overrides.
    for day in trip_days_qs:
        fragments = []

        # Build up a list of snippets for this day (notes, must-do, etc.).
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

        # Only append entries that actually contain text.
        if fragments:
            day_notes_display.append(
                {
                    "day_number": day.day_number,
                    "date": day.date,
                    "text": "; ".join(fragments),
                }
            )

    # Bundle everything needed by the template layer.
    context = {
        "itinerary": itinerary_obj,
        "ai_itinerary_days": enriched_days,
        "break_times": itinerary_obj.break_times.all(),
        "budget_items": itinerary_obj.budget_items.all(),
        "trip_days": trip_days_qs,
        "day_notes_display": day_notes_display,
    }

    # Surface a message when no AI-generated details exist.
    if (not ai_itinerary_days):
        # Surface a message when the AI output is missing/empty.
        messages.error(
            request,
            "This itinerary is missing generated details.",
        )

    # Render the finalized page with enriched day data.
    return render(request, "itinerary_detail.html", context)


def itinerary_list(request):
    """Load the list of current itineraries."""
    return render(request, "itinerary_list.html")


def _itinerary_error_response(request, is_ajax, message, status_code):
    """
    Return a consistent error response for itinerary lookups.

    AJAX callers get JSON payloads so the front-end can surface errors inline,
    while regular form submissions fall back to Django messages + redirect.
    """

    # Determine response format based on caller expectations.
    if is_ajax:
        # Return a structured response the front-end can consume.
        return JsonResponse({"ok": False, "error": message}, status=status_code)
    
    # Non-AJAX flows rely on Django messages + redirect to the form.
    messages.error(request, message)
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
    if (not details):
        return JsonResponse({"error": "No flight found for that number"}, status=404)

    # Return the normalized details for JavaScript to consume.
    return JsonResponse(details)


def find_itinerary(request):
    """
    Takes an access code from the user (currently the itinerary ID)
    then redirect to the matching itinerary detail page.
    """

    # Determine whether the caller expects a JSON response.
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    # Only the POST route is supported for access lookups.
    if request.method != "POST":
        return _itinerary_error_response(request, is_ajax, "Invalid request method.", 405)

    # Pull the trimmed code from the submitted form data.
    code = request.POST.get("access_code", "").strip()

    # Reject empty codes immediately.
    if not code:
        return _itinerary_error_response(request, is_ajax, "Please enter an access code.", 400)

    # Attempt to look up the itinerary by its public access code.
    itinerary_obj = Itinerary.objects.filter(access_code=code).first()  # pylint: disable=no-member

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
