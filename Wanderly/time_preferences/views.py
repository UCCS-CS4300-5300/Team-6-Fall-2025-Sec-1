"""Views for managing time preference settings."""
import json
import uuid
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.forms.models import model_to_dict
from django.shortcuts import redirect, render

from .constants import TIME_PREFERENCE_FIELDS
from .forms import TimePreferenceForm


@login_required
def itinerary(request):
    """creates a request for itinerary object"""
    last_pref = request.user.time_preferences.first()

    if request.method == "POST":
        form = TimePreferenceForm(request.POST)
        if form.is_valid():
            preference = form.save(user=request.user)

            if getattr(settings, "CREATE_JSON_OUTPUT", False):
                export_payload = {
                    "preference_id": preference.id,
                    "user_id": preference.user_id,
                    "created_at": preference.created_at.isoformat(),
                    "wake_up_time": preference.wake_up_time.isoformat()
                    if preference.wake_up_time else None,
                    "sleep_time": preference.sleep_time.isoformat()
                     if preference.sleep_time else None,
                    "enable_meals": preference.enable_meals,
                    "breakfast_time": preference.breakfast_time.isoformat()
                    if preference.breakfast_time else None,
                    "lunch_time": preference.lunch_time.isoformat()
                    if preference.lunch_time else None,
                    "dinner_time": preference.dinner_time.isoformat()
                    if preference.dinner_time else None,
                    "break_frequency": preference.break_frequency,
                    "break_duration": preference.break_duration,
                    "schedule_strictness": preference.schedule_strictness,
                    "preferred_start_time": preference.preferred_start_time.isoformat()
                    if preference.preferred_start_time else None,
                    "preferred_end_time": preference.preferred_end_time.isoformat()
                    if preference.preferred_end_time else None,
                }

                export_dir = Path(settings.BASE_DIR) / "time_preferences" / "json"
                export_dir.mkdir(parents=True, exist_ok=True)
                export_path = export_dir / f"{uuid.uuid4()}.json"
                export_path.write_text(json.dumps(export_payload, indent=2))

            messages.success(request, "Time preferences saved.")
            return redirect("time_preferences:itinerary")
        messages.error(request, "Please correct the highlighted fields.")
    else:
        initial = None
        if last_pref:
            initial = model_to_dict(last_pref, fields=TIME_PREFERENCE_FIELDS)
        form = TimePreferenceForm(initial=initial)

    return render(
        request,
        "time_preferences/timePref.html",
        {
            "form": form,
            "has_existing": last_pref is not None,
        },
    )
