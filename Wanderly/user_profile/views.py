""" Views for user profile app """
from django.shortcuts import render


def user_profile(request):
    """ Route to render user profile page """
    return render(request, "profile/profile.html")
