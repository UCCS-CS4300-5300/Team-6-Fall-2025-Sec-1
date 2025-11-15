"""
Views for mood questionnaire and Google Places text search.
"""

import logging
import json
import re
import requests
from django.shortcuts import render
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from openai import OpenAI, OpenAIError
from .forms import MoodForm
from .models import MoodResponse

logger = logging.getLogger(__name__)

def mood_questionnaire(request):
    ''' Get the AI Response from the mood form inputs'''
    if request.method == 'POST':
        form = MoodForm(request.POST)
        if form.is_valid():
            # Save to database, disable pylint since this is valid Django code
            # pylint: disable=no-member
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

                user_message = (
                    "User mood questionnaire responses:\n"
                    f"- Destination: {form.cleaned_data['destination']}\n"
                    f"- Adventurousness level: {form.cleaned_data['adventurous']}/5\n"
                    f"- Energy level: {form.cleaned_data['energy']}/5\n"
                    f"- Interests: {', '.join(form.cleaned_data['what_do_you_enjoy'])}\n\n"
                    "Consider these responses to a mood questionnaire and suggest "
                    f"5 activities in {form.cleaned_data['destination']} that "
                    "would suit the user's mood. Return ONLY a valid JSON array of objects "
                    "that have the following fields: title, description, why_recommended, "
                    "duration, type. Do not include any text outside the JSON."
                )

                response = client.chat.completions.create(
                    model="gpt-5-mini",
                    messages=[
                        {"role": "user", "content": user_message}
                    ]
                )

                ai_response = response.choices[0].message.content
                logger.info("OpenAI response: %s", ai_response)

                # parse the json for easy printing
                try:
                    activities = json.loads(ai_response)
                    if not isinstance(activities, list):
                        activities = [activities]
                except json.JSONDecodeError as e:
                    logger.warning("Failed to parse JSON response: %s", e)
                    logger.warning("OpenAI response text: %s", ai_response)
                    json_match = re.search(r'\[.*\]', ai_response, re.DOTALL)
                    if json_match:
                        try:
                            activities = json.loads(json_match.group())
                            if not isinstance(activities, list):
                                activities = [activities]
                        except json.JSONDecodeError as e2:
                            logger.error("Failed to parse extracted JSON: %s", str(e2))
                            logger.error(
                                "Extracted JSON was: %s", json_match.group()
                            )
                            error_message = (
                                "Could not parse activity recommendations."
                                "Check server logs for details."
                            )
                            activities = []
                    else:
                        logger.error(
                            "No JSON array found in response. Full response: %s",
                            ai_response,
                        )
                        error_message = (
                                "Could not parse activity recommendations."
                                "Check server logs for details."
                        )
                        activities = []

            except OpenAIError as e:
                logger.error("OpenAI API error: %s", e)
                error_message = f"Error from OpenAI API: {e}"
                activities = []

            except (json.JSONDecodeError, TypeError) as e:
                logger.error("Error parsing OpenAI response: %s", e)
                error_message = "Invalid response format from OpenAI."
                activities = []

            except requests.exceptions.RequestException as e:
                logger.error("Network error calling OpenAI API: %s", e)
                error_message = "Network error communicating with OpenAI."
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
    ''' Call for New Google Places API text search endpoint '''
    try:
        data = json.loads(request.body)
        text_query = data.get('textQuery', '')
        if not text_query:
            return JsonResponse({'error': 'textQuery is required'}, status=400)
        # New Places API endpoint
        url = 'https://places.googleapis.com/v1/places:searchText'
        # Request payload with just the search text
        payload = {
            'textQuery': text_query,
        }

        # Headers with Google Places API key and field mask with properties to return
        headers = {
            'Content-Type': 'application/json',
            'X-Goog-Api-Key': settings.GOOGLE_PLACES_API_KEY,
            'X-Goog-FieldMask':
            'places.displayName,places.formattedAddress,places.websiteUri,places.photos',
        }

        # Send POST request and check for success response
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        response_data = response.json()
        # Process photos to add actual media URLs
        places = response_data.get('places', [])
        for place in places:
            photos = place.get('photos', [])
            place['photos'] = [
                f"/place_photos/{photo['name']}"
                for photo in photos if isinstance(photo, dict) and 'name' in photo
            ]
        return JsonResponse({'places': places})
    # Return error for invalid JSON format
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    # Return error for server-side error
    except requests.exceptions.RequestException:
        return JsonResponse({'error': 'Failed to fetch data from Google Places API'}, status=502)
