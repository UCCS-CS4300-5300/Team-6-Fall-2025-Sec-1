"""Controls the views for the mood app"""
import logging
import json
import re
from django.shortcuts import render
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from openai import OpenAI, OpenAIError
from Wanderly.google_places import (
    PlacesPayloadError,
    fetch_places,
    parse_text_query,
)
from .forms import MoodForm
from .models import MoodResponse


logger = logging.getLogger(__name__)

def mood_questionnaire(request):
    """Mood questionnaire request form"""
    if request.method == 'POST':
        form = MoodForm(request.POST)
        if form.is_valid():
            mood_response = MoodResponse.objects.create(
                destination=form.cleaned_data['destination'],
                adventurous=form.cleaned_data['adventurous'],
                energy=form.cleaned_data['energy'],
                what_do_you_enjoy=form.cleaned_data['what_do_you_enjoy']
            )

            # Call OpenAI API with form data
            ai_response = None
            activities = []
            error_message = None

            try:
                client = OpenAI(api_key=settings.OPENAI_API_KEY)

                #formats data to send in openai prompt
                user_message = f"""
User mood questionnaire responses:
- Destination: {form.cleaned_data['destination']}
- Adventurousness level: {form.cleaned_data['adventurous']}/5
- Energy level: {form.cleaned_data['energy']}/5
- Interests: {', '.join(form.cleaned_data['what_do_you_enjoy'])}

Consider these responses to a mood questionnaire and suggest 5 activities in {form.cleaned_data
['destination']} that would suit the user's mood - return ONLY a valid JSON array with objects
 that have the following fields: title, description, why_recommended, duration, type. Do not include 
any text outside the JSON.
"""

                response = client.chat.completions.create(
                    model="gpt-5-mini",
                    messages=[
                        {"role": "user", "content": user_message}
                    ]
                )

                ai_response = response.choices[0].message.content
                logger.info("OpenAI response: %s", {ai_response})

                # parse the json for easy printing
                try:
                    activities = json.loads(ai_response)
                    if not isinstance(activities, list):
                        activities = [activities]
                except json.JSONDecodeError as e:
                    logger.warning("Failed to parse JSON response: %s", {str(e)})
                    logger.warning("OpenAI response text: %s", {ai_response})
                    json_match = re.search(r'\[.*\]', ai_response, re.DOTALL)
                    if json_match:
                        try:
                            activities = json.loads(json_match.group())
                            if not isinstance(activities, list):
                                activities = [activities]
                        except json.JSONDecodeError as e2:
                            logger.error("Failed to parse extracted JSON: %s", str(e2))
                            logger.error("Extracted JSON was: %s", json_match.group())
                            error_message = "Could not parse activity recommendations." \
                                "Check server logs for details."
                            activities = []
                    else:
                        logger.error("No JSON array found in response." \
                            "Full response was: %s", ai_response)
                        error_message = "Could not parse activity recommendations." \
                            "Check server logs for details."
                        activities = []

            except (OpenAIError, json.JSONDecodeError, KeyError, ValueError) as exc:
                logger.error("Error calling OpenAI API: %s", exc)
                error_message = f"Error getting recommendations: {exc}"
                activities = []


            # formats in a way that can be displayed on the results page
            context = {
                'destination': form.cleaned_data['destination'],
                'adventurous': form.cleaned_data['adventurous'],
                'energy': form.cleaned_data['energy'],
                'interests': form.cleaned_data['what_do_you_enjoy'],
                'activities': activities,
                'error': error_message,
                'mood_response_id': mood_response.id
            }

            return render(request, 'mood_results.html', context)
    else:
        form = MoodForm()

    return render(request, 'mood_questionnaire.html', {'form': form})


# GET place information with New Google Places API text_search
@require_http_methods(["POST"])
def text_search(request):
    """Search text for google autocomplete"""
    try:
        text_query = parse_text_query(request.body)
        places = fetch_places(text_query, timeout=60)
        return JsonResponse({'places': places})
    # Return error for invalid JSON format
    except PlacesPayloadError as exc:
        return JsonResponse({'error': str(exc)}, status=exc.status_code)
