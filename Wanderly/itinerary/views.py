from django.shortcuts import render

# Create your views here.
def itinerary(request):
    return render(request, "itinerary.html")