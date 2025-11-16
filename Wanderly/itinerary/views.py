"""Controls the views and requests for the itinerary module."""

import json
from typing import Iterable, List, Optional

from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect, render
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


def _store_ai_itinerary_in_session(request, ai_itinerary_days: Iterable[dict]) -> None:
    """Persist AI itinerary in the session so it can be displayed after redirect."""
    request.session["ai_itinerary_days"] = json.dumps(list(ai_itinerary_days))


def _pop_ai_itinerary_from_session(request) -> Optional[list]:
    """Retrieve any AI itinerary stored in the session and decode it."""
    ai_itinerary_json = request.session.pop("ai_itinerary_days", None)
    if not ai_itinerary_json:
        return None

    try:
        return json.loads(ai_itinerary_json)
    except json.JSONDecodeError:
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
            if ai_itinerary_days:
                _store_ai_itinerary_in_session(request, ai_itinerary_days)
            else:
                messages.error(
                    request,
                    "We were unable to generate an AI-powered itinerary at this time.",
                )

            messages.success(request, "Itinerary created successfully!")
            return redirect("itinerary:itinerary")

        # No `else` needed; if the form is invalid we fall through and re-render.
        messages.error(request, "Please correct the errors below.")
    else:
        form = ItineraryForm()

    ai_itinerary_days = _pop_ai_itinerary_from_session(request)
    # pylint: disable=no-member
    recent_itineraries = Itinerary.objects.all()[:5]

    context = {
        "form": form,
        "recent_itineraries": recent_itineraries,
        "ai_itinerary_days": ai_itinerary_days,
    }

    return render(request, "itinerary.html", context)

def itinerary_list(request):
    ''' Load the list of current itineraries '''
    return render(request, "itinerary_list.html")
