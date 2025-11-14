from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings
from .models import Itinerary, BreakTime, BudgetItem, Day
from .forms import ItineraryForm
from openai import OpenAI


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

            # --- Call ChatGPT to generate an itinerary ---
            ai_itinerary = None
            try:
                client = OpenAI(api_key=settings.OPENAI_API_KEY)

                # Adjust field names here if your Itinerary model uses different ones
                destination = getattr(itinerary_obj, "destination", "")
                time_prefs = getattr(itinerary_obj, "time_preferences", "")
                budget = getattr(itinerary_obj, "budget", "")
                days = getattr(itinerary_obj, "num_days", num_days)

                user_message = f"""
Destination: {destination}
Time preferences: {time_prefs}
Budget: {budget}
Number of days: {days}

Make a detailed travel itinerary considering this information.
"""

                response = client.chat.completions.create(
                    model="gpt-5-mini",
                    messages=[
                        {"role": "user", "content": user_message}
                    ]
                )

                ai_itinerary = response.choices[0].message.content

            except Exception as e:
                # If something goes wrong with the API call, just show an error and continue
                messages.error(request, f"Error generating AI itinerary: {e}")
                ai_itinerary = None

            # Store AI itinerary in the session so it can be shown after redirect
            if ai_itinerary:
                request.session['ai_itinerary'] = ai_itinerary

            messages.success(request, 'Itinerary created successfully!')
            return redirect('itinerary:itinerary')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ItineraryForm()

    # Pull any AI itinerary result from the session (if coming from a redirect)
    ai_itinerary = request.session.pop('ai_itinerary', None)

    # Get recent itineraries to display
    recent_itineraries = Itinerary.objects.all()[:5]

    context = {
        'form': form,
        'recent_itineraries': recent_itineraries,
        'ai_itinerary': ai_itinerary,
    }

    return render(request, "itinerary.html", context)
