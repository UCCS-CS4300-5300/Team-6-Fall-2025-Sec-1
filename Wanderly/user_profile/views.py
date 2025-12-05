""" Views for user profile app """
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from itinerary.models import Itinerary


@login_required
def user_profile(request):
    """Render the authenticated user's profile dashboard."""
    today = timezone.now().date()
    user_itineraries = (
        Itinerary.objects.filter(user=request.user)
        .order_by("-start_date", "-created_at")
    )
    itinerary_count = user_itineraries.count()
    upcoming_trip = (
        user_itineraries.filter(start_date__gte=today)
        .order_by("start_date")
        .first()
    )
    recent_itineraries = list(user_itineraries[:5])

    context = {
        "itinerary_count": itinerary_count,
        "upcoming_trip": upcoming_trip,
        "recent_itineraries": recent_itineraries,
    }
    return render(request, "profile/profile.html", context)
