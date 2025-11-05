from django.shortcuts import render
import requests
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
import json

# GET place information with New Google Places API text_search
@require_http_methods(["POST"])
def text_search(request):
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
            'X-Goog-FieldMask': 'places.displayName,places.formattedAddress,places.websiteUri,places.photos',
        }

        # Send POST request and check for success response
        response = requests.post(url, json=payload, headers=headers)
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
    except requests.exceptions.RequestException as e:
        return JsonResponse({'error': 'Failed to fetch data from Google Places API'}, status=502)

# Fetch place photo from Google Places API
def place_photos(request, photo_name):
    try:
        if not photo_name.startswith("places/"):
            return JsonResponse({'error': 'Invalid photo name'}, status=400)

        url = f"https://places.googleapis.com/v1/{photo_name}/media?maxWidthPx=800"
        
        headers = {
            'X-Goog-Api-Key': settings.GOOGLE_PLACES_API_KEY,
        }
        
        response = requests.get(url, headers=headers, allow_redirects=True)
        response.raise_for_status()
        
        # Return the image
        return HttpResponse(response.content, content_type=response.headers.get('Content-Type', 'image/jpeg'))
        
    except requests.exceptions.RequestException as e:
        return JsonResponse({'error': str(e)}, status=500)