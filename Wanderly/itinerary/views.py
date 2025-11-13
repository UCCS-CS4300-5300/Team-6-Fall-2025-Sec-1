from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Itinerary, BreakTime, BudgetItem, Day
from .forms import ItineraryForm


def itinerary(request):
    """View for creating and displaying itineraries"""
    if request.method == 'POST':
        # Create the main itinerary
        form = ItineraryForm(request.POST)

        if form.is_valid():
            # Save the main itinerary
            itinerary_obj = form.save()

            # Process break times
            break_start_times = request.POST.getlist('break_start_time[]')
            break_end_times = request.POST.getlist('break_end_time[]')

            for start, end in zip(break_start_times, break_end_times):
                if start and end:  # Only save if both times are provided
                    BreakTime.objects.create(
                        itinerary=itinerary_obj,
                        start_time=start,
                        end_time=end
                    )

            # Process budget items
            budget_categories = request.POST.getlist('budget_category[]')
            budget_custom_categories = request.POST.getlist('budget_custom_category[]')
            budget_amounts = request.POST.getlist('budget_amount[]')

            for category, custom_category, amount in zip(budget_categories, budget_custom_categories, budget_amounts):
                if amount:  # Only save if amount is provided
                    BudgetItem.objects.create(
                        itinerary=itinerary_obj,
                        category=category,
                        custom_category=custom_category if category == 'Other' else '',
                        amount=amount
                    )

            # Process days
            num_days = itinerary_obj.num_days
            for i in range(1, num_days + 1):
                day_date = request.POST.get(f'day_{i}_date')
                day_notes = request.POST.get(f'day_{i}_notes', '')

                if day_date:  # Only save if date is provided
                    Day.objects.create(
                        itinerary=itinerary_obj,
                        day_number=i,
                        date=day_date,
                        notes=day_notes
                    )

            messages.success(request, 'Itinerary created successfully!')
            return redirect('itinerary:itinerary')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ItineraryForm()

    # Get recent itineraries to display
    recent_itineraries = Itinerary.objects.all()[:5]

    context = {
        'form': form,
        'recent_itineraries': recent_itineraries,
    }

    return render(request, "itinerary.html", context)