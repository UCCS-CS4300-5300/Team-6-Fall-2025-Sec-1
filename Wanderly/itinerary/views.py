"""Controls the views and requests for the itinerary module"""
from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings
from .models import Itinerary, BreakTime, BudgetItem, Day
from .forms import ItineraryForm
from openai import OpenAI

def itinerary(request):
    """View for creating and displaying itineraries"""
    if request.method == 'POST':
        form = ItineraryForm(request.POST)

        if form.is_valid():
            # Save the main itinerary
            itinerary_obj = form.save()

            # Process break times
            break_start_times = request.POST.getlist('break_start_time[]')
            break_end_times = request.POST.getlist('break_end_time[]')

            for start, end in zip(break_start_times, break_end_times):
                if start and end:
                    BreakTime.objects.create(
                        itinerary=itinerary_obj,
                        start_time=start,
                        end_time=end,
                    )

            # Process budget items
            budget_categories = request.POST.getlist('budget_category[]')
            budget_custom_categories = request.POST.getlist(
                'budget_custom_category[]'
            )
            budget_amounts = request.POST.getlist('budget_amount[]')

            for category, custom_category, amount in zip(
                budget_categories,
                budget_custom_categories,
                budget_amounts,
            ):
                if amount:  # Only save if amount is provided
                    BudgetItem.objects.create(
                        itinerary=itinerary_obj,
                        category=category,
                        custom_category=(
                            custom_category if category == 'Other' else ''
                        ),
                        amount=amount,
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
                        notes=day_notes,
                    )

            # ChatGPT call to generate itinerary
            ai_itinerary_days = None
            try:
                import json
                client = OpenAI(api_key=settings.OPENAI_API_KEY)

                # itinerary details
                destination = getattr(itinerary_obj, "destination", "")
                wake_time = getattr(itinerary_obj, "wake_up_time", "")
                bed_time = getattr(itinerary_obj, "bed_time", "")
                num_days = getattr(itinerary_obj, "num_days", 1)

                # Break times string
                break_times = BreakTime.objects.filter(
                    itinerary=itinerary_obj
                )
                if break_times.exists():
                    break_times_str = ", ".join(
                        f"{bt.start_time}-{bt.end_time}"
                        for bt in break_times
                    )
                else:
                    break_times_str = "None"

                # Budget string
                budget_items = BudgetItem.objects.filter(
                    itinerary=itinerary_obj
                )
                if budget_items.exists():
                    budget_parts = []
                    for bi in budget_items:
                        label = (
                            bi.custom_category
                            if bi.category == "Other" and bi.custom_category
                            else bi.category
                        )
                        budget_parts.append(f"{label}: ${bi.amount}")
                    budget_str = ", ".join(budget_parts)
                else:
                    budget_str = "Flexible"

                # Day notes string
                day_notes_qs = Day.objects.filter(
                    itinerary=itinerary_obj
                ).order_by('day_number')
                day_note_lines = [
                    f"Day {d.day_number} ({d.date}): {d.notes}"
                    for d in day_notes_qs
                    if d.notes
                ]
                day_notes_str = "\n".join(day_note_lines)

                if day_notes_str:
                    extra_notes = (
                        "User preferences for specific days:\n"
                        f"{day_notes_str}\n\n"
                    )
                else:
                    extra_notes = ""

                user_message = f"""
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

                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "user", "content": user_message}
                    ],
                    response_format={"type": "json_object"},
                )

                ai_response = response.choices[0].message.content
                ai_itinerary_days = json.loads(ai_response).get('days', [])

            except Exception as e:
                messages.error(request, f"Error generating AI itinerary: {e}")
                ai_itinerary_days = None

            # Store AI itinerary in the session so it can be shown after redirect
            if ai_itinerary_days:
                import json
                request.session['ai_itinerary_days'] = json.dumps(
                    ai_itinerary_days
                )

            messages.success(request, 'Itinerary created successfully!')
            return redirect('itinerary:itinerary')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ItineraryForm()

    # Pull any AI itinerary result from the session (if coming from a redirect)
    import json
    ai_itinerary_json = request.session.pop('ai_itinerary_days', None)
    ai_itinerary_days = (
        json.loads(ai_itinerary_json) if ai_itinerary_json else None
    )

    # Get recent itineraries to display
    recent_itineraries = Itinerary.objects.all()[:5]

    context = {
        'form': form,
        'recent_itineraries': recent_itineraries,
        'ai_itinerary_days': ai_itinerary_days,
    }

    return render(request, "itinerary.html", context)
