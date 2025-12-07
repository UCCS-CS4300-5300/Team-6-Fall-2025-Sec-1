"""Helper functions for building AI itinerary prompts."""
from __future__ import annotations

from typing import Set

from .models import BreakTime, BudgetItem, Day, Itinerary


def _format_break_times(itinerary_obj: Itinerary) -> str:
    """Return a human-readable break time string for an itinerary."""
    break_times = BreakTime.objects.filter(itinerary=itinerary_obj)
    if not break_times.exists():
        return "None"
    return ", ".join(f"{bt.start_time}-{bt.end_time}" for bt in break_times)


def _format_budget(itinerary_obj: Itinerary) -> str:
    """Return a human-readable budget string for an itinerary."""
    budget_items = BudgetItem.objects.filter(itinerary=itinerary_obj)
    if not budget_items.exists():
        return "Flexible"
    parts = []
    for item in budget_items:
        label = (
            item.custom_category
            if item.category == "Other" and item.custom_category
            else item.category
        )
        parts.append(f"{label}: ${item.amount}")
    return ", ".join(parts)


def collect_day_fragments(day: Day, override_text: str = "") -> list[str]:
    """Return the shared note/must-do/constraint fragments for a Day."""
    fragments = []
    if day.notes:
        fragments.append(day.notes)
    if day.must_do:
        fragments.append(f"Must-do: {day.must_do}")
    if day.constraints:
        fragments.append(f"Constraints: {day.constraints}")
    if override_text:
        fragments.append(override_text)
    return fragments


def _format_day_notes(itinerary_obj: Itinerary) -> str:
    """Return extra notes string describing per-day notes, if any."""
    day_notes_qs = Day.objects.filter(itinerary=itinerary_obj).order_by("day_number")
    lines = []
    for day in day_notes_qs:
        override_text = ""
        if day.wake_override or day.bed_override:
            override_text = (
                f"Custom wake/bed: {day.wake_override or 'same'} / {day.bed_override or 'same'}"
            )
        fragments = collect_day_fragments(day, override_text)
        if fragments:
            joined = "; ".join(fragments)
            lines.append(f"Day {day.day_number} ({day.date}): {joined}")
    if not lines:
        return ""
    joined = "\n".join(lines)
    return f"User preferences for specific days:\n{joined}\n\n"


def _format_date_range(start_date, end_date) -> str:
    """Return a friendly date range string."""
    if start_date and end_date:
        return f"{start_date:%B %d, %Y} through {end_date:%B %d, %Y}"
    if start_date:
        return f"Start date: {start_date:%B %d, %Y}"
    if end_date:
        return f"End date: {end_date:%B %d, %Y}"
    return ""


def _summarize_party(itinerary_obj: Itinerary) -> str:
    """Return a sentence fragment describing the traveler count."""
    adults = getattr(itinerary_obj, "party_adults", 1)
    children = getattr(itinerary_obj, "party_children", 0)
    summary = f"{adults} adult{'s' if adults != 1 else ''}"
    if children:
        summary += f" and {children} child{'ren' if children != 1 else ''}"
    return summary


def _meals_line(itinerary_obj: Itinerary) -> str:
    """Return guidance describing which meals should become explicit stops."""
    selections = []
    if itinerary_obj.include_breakfast:
        selections.append("breakfast")
    if itinerary_obj.include_lunch:
        selections.append("lunch")
    if itinerary_obj.include_dinner:
        selections.append("dinner")
    if selections:
        joined = ", ".join(selections)
        return f"{joined} (schedule meal stops only for these selections)"
    return (
        "No planned meals; skip dedicated meal stops unless explicitly requested elsewhere"
    )


def _format_flight_line(
    direction: str,
    dt_value,
    airport_label: str,
    airline_label: str,
    flight_number: str,
) -> str:
    """Return a descriptive bullet summarizing a single direction of travel."""
    if not any([dt_value, airport_label, airline_label, flight_number]):
        return ""
    normalized_number = (flight_number or "").upper()
    if airline_label and normalized_number:
        prefix = f"{airline_label} Flight {normalized_number}"
    elif airline_label:
        prefix = f"{airline_label} Flight"
    elif normalized_number:
        prefix = f"Flight {normalized_number}"
    else:
        prefix = "Flight"
    verb = "arrives at" if direction == "arrival" else "departs from"
    time_hint = dt_value.strftime("%B %d at %I:%M %p") if dt_value else ""
    suffix_parts = []
    if airport_label:
        suffix_parts.append(f"{verb} {airport_label}")
    if time_hint:
        suffix_parts.append(f"on {time_hint}")
    suffix = ", ".join(suffix_parts)
    return f"- {prefix} {suffix}." if suffix else f"- {prefix}."


def _flight_prompt_details(itinerary_obj: Itinerary, num_days: int) -> dict:
    """Collect reusable blocks/flags for the flight portion of the prompt."""
    has_arrival_info = bool(
        itinerary_obj.arrival_datetime
        or itinerary_obj.arrival_airport
        or itinerary_obj.arrival_flight_number
    )
    has_departure_info = bool(
        itinerary_obj.departure_datetime
        or itinerary_obj.departure_airport
        or itinerary_obj.departure_flight_number
    )
    flight_lines = []
    arrival_line = _format_flight_line(
        "arrival",
        itinerary_obj.arrival_datetime,
        itinerary_obj.arrival_airport,
        itinerary_obj.arrival_airline,
        itinerary_obj.arrival_flight_number,
    )
    departure_line = _format_flight_line(
        "departure",
        itinerary_obj.departure_datetime,
        itinerary_obj.departure_airport,
        itinerary_obj.departure_airline,
        itinerary_obj.departure_flight_number,
    )
    if arrival_line:
        flight_lines.append(arrival_line)
    if departure_line:
        flight_lines.append(departure_line)
    flight_block = "\n".join(flight_lines) or "No flights provided."

    excluded_days: Set[int] = set()
    if has_arrival_info:
        excluded_days.add(1)
    if has_departure_info and num_days:
        excluded_days.add(num_days)

    wake_note = ""
    if has_arrival_info or has_departure_info:
        impacted = []
        if has_arrival_info:
            impacted.append("Day 1 (arrival day)")
        if has_departure_info and num_days:
            impacted.append(f"Day {num_days} (departure day)")
        wake_note = (
            "Ignore typical wake/bed expectations on "
            + " and ".join(impacted)
            + " because flights dictate those schedules."
        )

    if has_arrival_info or has_departure_info:
        tail_guidance = (
            "- Do not schedule activities before the arrival flight lands or "
            "within 1 hour of the departure flight; mention this buffer in "
            "your plan if applicable."
        )
    else:
        tail_guidance = (
            "- Flights were not provided, so treat the trip as fully "
            "land-based with no arrival/departure buffers."
        )

    return {
        "block": flight_block,
        "has_arrival": has_arrival_info,
        "has_departure": has_departure_info,
        "excluded_days": excluded_days,
        "wake_note": wake_note,
        "tail_guidance": tail_guidance,
    }


def _hotel_plan_summary(itinerary_obj: Itinerary) -> tuple[str, bool, bool]:
    """Summarize lodging instructions and track whether AI help is required."""
    has_details = any(
        [
            itinerary_obj.hotel_address,
            itinerary_obj.hotel_name,
            itinerary_obj.hotel_check_in,
            itinerary_obj.hotel_check_out,
        ]
    )
    needs_suggestion = bool(itinerary_obj.auto_suggest_hotel and not has_details)
    if has_details:
        parts = []
        if itinerary_obj.hotel_address:
            parts.append(itinerary_obj.hotel_address)
        if itinerary_obj.hotel_name:
            parts.append(itinerary_obj.hotel_name)
        if itinerary_obj.hotel_check_in:
            parts.append(f"Check-in {itinerary_obj.hotel_check_in:%B %d at %I:%M %p}")
        if itinerary_obj.hotel_check_out:
            parts.append(f"Check-out {itinerary_obj.hotel_check_out:%B %d at %I:%M %p}")
        summary = " | ".join(parts)
    elif needs_suggestion:
        summary = (
            f"Need Wanderly to recommend a {_summarize_party(itinerary_obj)} hotel "
            f"within the ${itinerary_obj.overall_budget_max or 'Flexible'} budget."
        )
    else:
        summary = (
            "Traveler will arrange their own lodging; do not recommend or invent a hotel."
        )
    return summary, has_details, needs_suggestion


def _season_hint(start_date, end_date) -> str:
    """Return a short blurb describing expected weather."""
    ref_date = start_date or end_date
    if not ref_date:
        return ""
    month = ref_date.month
    if month in (12, 1, 2):
        return f"Travel month: {ref_date:%B} (expect winter conditions)."
    if month in (3, 4, 5):
        return f"Travel month: {ref_date:%B} (spring shoulder season)."
    if month in (6, 7, 8):
        return f"Travel month: {ref_date:%B} (peak summer weather)."
    return f"Travel month: {ref_date:%B} (autumn conditions)."


def _build_overrides_block(
    itinerary_obj: Itinerary,
    wake_time,
    bed_time,
    excluded_days: Set[int],
) -> str:
    """Summarize per-day wake/bed overrides for the prompt."""
    override_lines = []
    for day in Day.objects.filter(itinerary=itinerary_obj).order_by("day_number"):
        if day.day_number in excluded_days:
            continue
        if day.wake_override or day.bed_override:
            override_lines.append(
                (
                    f"- Day {day.day_number}: wake at "
                    f"{day.wake_override or wake_time}, "
                    f"bed by {day.bed_override or bed_time}"
                )
            )
    if not override_lines:
        return "None supplied; use the global wake/bed times."

    block = "\n".join(override_lines)
    if excluded_days:
        block += "\n(Arrival/departure days are omitted because flights override wake/bed windows.)"
    return block


def _collect_additional_guidance(
    itinerary_obj: Itinerary,
    has_arrival_info: bool,
    has_departure_info: bool,
    has_hotel_details: bool,
    needs_hotel_suggestion: bool,
) -> str:
    """Return extra guardrails for the AI response."""
    guidance_lines = []
    if has_arrival_info:
        guidance_lines.append(
            "Day 1 must begin with an \"Arrival Flight\" block summarizing "
            "the airline, flight number, arrival airport, and arrival time "
            "(omit PNR). Ignore the typical wake/bed windows for this day."
        )
        guidance_lines.append(
            "Even if overrides are configured, do not enforce wake/bed times "
            "on the arrival day; anchor the schedule around the flight."
        )
    if has_hotel_details:
        check_in_str = (
            f"{itinerary_obj.hotel_check_in:%I:%M %p}"
            if itinerary_obj.hotel_check_in
            else "the typical afternoon check-in window"
        )
        hotel_label = itinerary_obj.hotel_name or itinerary_obj.hotel_address or "the hotel"
        guidance_lines.append(
            f"Include a dedicated \"Check in at {hotel_label}\" block timed near {check_in_str}, "
            "and remind travelers to wind down or return there when appropriate."
        )
    elif needs_hotel_suggestion:
        guidance_lines.append(
            "No hotel was provided, so choose a realistic hotel that fits "
            "the party size and budget ceiling, mention it explicitly "
            "before the first full day, include a nightly price range in the "
            "cost_estimate field, and respect its check-in/out windows."
        )
    if has_departure_info:
        guidance_lines.append(
            "On the final day ignore typical wake/bed times and instead shape "
            "the schedule around the departure flight, leaving a buffer of at "
            "least one hour beforehand."
        )
    if not has_hotel_details and not needs_hotel_suggestion:
        guidance_lines.append(
            "The traveler will secure their own lodging; leave the accommodation "
            "object null and avoid naming or recommending any hotel."
        )
    return "\n".join(guidance_lines) or "None."
