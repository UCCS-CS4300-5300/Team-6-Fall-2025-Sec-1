from django.shortcuts import render
import os
 
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from google.oauth2 import id_token
from google.auth.transport import requests

# Homepage
def index(request):
    return render(request, 'index.html')



@csrf_exempt
def sign_in(request):
    return render(request, 'registration/login.html')
 
@csrf_exempt
# This view is called by Google after the user has authenticated.
def auth_receiver(request):
    """
    Google calls this URL after the user has signed in with their Google account.
    """
    print('Inside')
    token = request.POST['credential']
 
    try:
        user_data = id_token.verify_oauth2_token(
            token, requests.Request(), os.environ['GOOGLE_OAUTH_CLIENT_ID']
        )
    except ValueError:
        return HttpResponse(status=403)
 
    # In a real app, I'd also save any new user here to the database.
    # You could also authenticate the user here using the details from Google (https://docs.djangoproject.com/en/4.2/topics/auth/default/#how-to-log-a-user-in)
    request.session['user_data'] = user_data
 
    return redirect('index')


# Sign out the user
def sign_out(request):
    del request.session['user_data']
    return redirect('sign_in')