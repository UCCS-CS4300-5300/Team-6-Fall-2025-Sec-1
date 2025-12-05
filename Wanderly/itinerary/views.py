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


def _build_ai_prompt(itinerary_obj: Itinerary) -> str:
    """Build the user message sent to the OpenAI model."""
    destination = getattr(itinerary_obj, "destination", "")
    wake_time = getattr(itinerary_obj, "wake_up_time", "")
    bed_time = getattr(itinerary_obj, "bed_time", "")
    num_days = getattr(itinerary_obj, "num_days", 1)

    break_times_str = _format_break_times(itinerary_obj)
    budget_str = _format_budget(itinerary_obj)
    extra_notes = _format_day_notes(itinerary_obj)

    return f"""
Create a detailed travel itinerary for {destination}.

Trip Details:
- Number of days: {num_days}
- Wake up time: {wake_time}
- Bed time: {bed_time}
- Break times: {break_times_str}
- Budget: {budget_str}

{extra_notes}Please provide a JSON response with the following structure:
{{
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

Make sure each day has 4-6 activities covering the full day from wake time
to bed time, respecting break times.
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

    context = {
        "itinerary": itinerary_obj,
        "ai_itinerary_days": ai_itinerary_days,
        "break_times": itinerary_obj.break_times.all(),
        "budget_items": itinerary_obj.budget_items.all(),
        "trip_days": itinerary_obj.days.all(),
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
