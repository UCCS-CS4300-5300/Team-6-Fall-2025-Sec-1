from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import (
    ItineraryBudgetForm,
    ItineraryBudgetItemFormSet,
    ItineraryLocationForm,
    ItineraryTimePreferenceForm,
)
from .models import Itinerary, ItineraryBudgetItem


@login_required
def itinerary_time_preferences(request):
    """Step 1: Collect time preferences."""
    # Get partial itinerary from session if it exists
    itinerary_id = request.session.get("itinerary_id")
    itinerary = None
    if itinerary_id:
        try:
            itinerary = Itinerary.objects.get(id=itinerary_id, user=request.user)
        except Itinerary.DoesNotExist:
            request.session.pop("itinerary_id", None)

    if request.method == "POST":
        form = ItineraryTimePreferenceForm(request.POST, instance=itinerary)
        if form.is_valid():
            # Create or update itinerary
            if not itinerary:
                itinerary = Itinerary(user=request.user, location="")

            # Update time preference fields
            itinerary.wake_up_time = form.cleaned_data.get("wake_up_time")
            itinerary.sleep_time = form.cleaned_data.get("sleep_time")
            itinerary.enable_meals = form.cleaned_data.get("enable_meals")
            itinerary.breakfast_time = form.cleaned_data.get("breakfast_time")
            itinerary.lunch_time = form.cleaned_data.get("lunch_time")
            itinerary.dinner_time = form.cleaned_data.get("dinner_time")
            itinerary.break_frequency = form.cleaned_data.get("break_frequency")
            itinerary.break_duration = form.cleaned_data.get("break_duration")
            itinerary.schedule_strictness = form.cleaned_data.get("schedule_strictness")
            itinerary.preferred_start_time = form.cleaned_data.get("preferred_start_time")
            itinerary.preferred_end_time = form.cleaned_data.get("preferred_end_time")
            itinerary.save()

            # Store in session
            request.session["itinerary_id"] = itinerary.id

            messages.success(request, "Time preferences saved.")
            return redirect("itinerary:budget")
        else:
            messages.error(request, "Please correct the highlighted fields.")
    else:
        form = ItineraryTimePreferenceForm(instance=itinerary)

    return render(
        request,
        "itinerary/time_preferences.html",
        {
            "form": form,
            "step": 1,
        },
    )


@login_required
def itinerary_budget(request):
    """Step 2: Collect budget information."""
    itinerary_id = request.session.get("itinerary_id")
    if not itinerary_id:
        messages.warning(request, "Please start with time preferences.")
        return redirect("itinerary:time_preferences")

    try:
        itinerary = Itinerary.objects.get(id=itinerary_id, user=request.user)
    except Itinerary.DoesNotExist:
        request.session.pop("itinerary_id", None)
        messages.error(request, "Itinerary not found. Please start over.")
        return redirect("itinerary:time_preferences")

    if request.method == "POST":
        budget_form = ItineraryBudgetForm(request.POST, instance=itinerary)
        formset = ItineraryBudgetItemFormSet(request.POST, prefix="items")

        if budget_form.is_valid() and formset.is_valid():
            # Save total budget
            budget_form.save()

            # Save budget items if any
            if any(form.has_changed() for form in formset):
                # Delete existing items
                itinerary.budget_items.all().delete()

                for form in formset:
                    if not form.has_changed():
                        continue
                    item = form.save(commit=False)
                    item.itinerary = itinerary
                    item.save()

            messages.success(request, "Budget saved.")
            return redirect("itinerary:location")
        else:
            messages.error(request, "Please fix the highlighted errors and try again.")
    else:
        budget_form = ItineraryBudgetForm(instance=itinerary)
        formset = ItineraryBudgetItemFormSet(prefix="items")

    context = {
        "budget_form": budget_form,
        "formset": formset,
        "budget_other_value": ItineraryBudgetItem.OTHER,
        "step": 2,
    }
    return render(request, "itinerary/budget.html", context)


@login_required
def itinerary_location(request):
    """Step 3: Collect location."""
    itinerary_id = request.session.get("itinerary_id")
    if not itinerary_id:
        messages.warning(request, "Please start with time preferences.")
        return redirect("itinerary:time_preferences")

    try:
        itinerary = Itinerary.objects.get(id=itinerary_id, user=request.user)
    except Itinerary.DoesNotExist:
        request.session.pop("itinerary_id", None)
        messages.error(request, "Itinerary not found. Please start over.")
        return redirect("itinerary:time_preferences")

    if request.method == "POST":
        form = ItineraryLocationForm(request.POST, instance=itinerary)
        if form.is_valid():
            form.save()

            # Clear session
            request.session.pop("itinerary_id", None)

            messages.success(request, "Itinerary created successfully!")
            return redirect("itinerary:summary", itinerary_id=itinerary.id)
        else:
            messages.error(request, "Please correct the highlighted fields.")
    else:
        form = ItineraryLocationForm(instance=itinerary)

    return render(
        request,
        "itinerary/location.html",
        {
            "form": form,
            "step": 3,
        },
    )


@login_required
def itinerary_summary(request, itinerary_id):
    """Display the completed itinerary."""
    try:
        itinerary = Itinerary.objects.get(id=itinerary_id, user=request.user)
    except Itinerary.DoesNotExist:
        messages.error(request, "Itinerary not found.")
        return redirect("itinerary:time_preferences")

    return render(
        request,
        "itinerary/summary.html",
        {
            "itinerary": itinerary,
        },
    )
