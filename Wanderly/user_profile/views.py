from django.shortcuts import render


def userProfile(request):
    return render(request, "profile/profile.html")
