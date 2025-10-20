from django.shortcuts import render
import requests
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import json
from django.views.decorators.csrf import csrf_exempt

# Load location_based_discovery template
def location_based_discovery(request):
    return render(request, 'location_based_discovery.html')

# GET tourist attractions with Google Places API
@csrf_exempt
@require_http_methods(["POST"])
def text_search(request):
    try:
        # Manually add "tourist attractions" to the location to get nearby attractions
        data = json.loads(request.body)
        text_query = data.get('textQuery', '') + " tourist attractions"
        
        if not text_query:
            return JsonResponse({'error': 'textQuery is required'}, status=400)
        
        # New Places API endpoint
        url = 'https://places.googleapis.com/v1/places:searchText'
        
        # Request payload with just the search text (for now)
        payload = {
            'textQuery': text_query,
        }

        # Headers with Google Places API key and field mask with properties to return
        headers = {
            'Content-Type': 'application/json',
            'X-Goog-Api-Key': settings.GOOGLE_PLACES_API_KEY,
            'X-Goog-FieldMask': data.get('fieldMask', 'places.displayName,places.formattedAddress,places.websiteUri')
        }
        
        # Send POST request and check for success response
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        
        return JsonResponse(response.json())
    
    # Return error for invalid JSON format
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    # Return error for server-side error
    except requests.exceptions.RequestException as e:
        return JsonResponse({'error': str(e)}, status=500)
