'''
Calls for New Google Places API Endpoint
'''

import requests
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods

from Wanderly.google_places import (
    PlacesPayloadError,
    fetch_places,
    parse_text_query,
)

# GET place information with New Google Places API text_search
@require_http_methods(["POST"])
def text_search(request):
    ''' Call for New Google Places API text search endpoint '''
    try:
        text_query = parse_text_query(request.body)
        places = fetch_places(text_query, timeout=10)
        return JsonResponse({'places': places})

    # Return error for invalid JSON format
    except PlacesPayloadError as exc:
        return JsonResponse({'error': str(exc)}, status=exc.status_code)
    # Return error for server-side error
    except requests.exceptions.RequestException:
        return JsonResponse({'error': 'Failed to fetch data from Google Places API'}, status=502)

# Fetch place photo from Google Places API
def place_photos(response, photo_name):
    ''' Call for New Google Places API place photos endpoint '''
    try:
        if not photo_name.startswith("places/"):
            return JsonResponse({'error': 'Invalid photo name'}, status=400)

        url = f"https://places.googleapis.com/v1/{photo_name}/media?maxWidthPx=800"

        headers = {
            'X-Goog-Api-Key': settings.GOOGLE_PLACES_API_KEY,
        }

        response = requests.get(url, headers=headers, allow_redirects=True, timeout=10)
        response.raise_for_status()

        # Return the image
        return HttpResponse(
            response.content,
            content_type=response.headers.get('Content-Type', 'image/jpeg')
        )

    except requests.exceptions.RequestException as e:
        return JsonResponse({'error': str(e)}, status=500)
