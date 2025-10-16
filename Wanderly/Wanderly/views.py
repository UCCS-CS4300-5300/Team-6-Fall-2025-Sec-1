# System imports
import os
 
# Django imports
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt

# Google OAuth imports
from google.oauth2 import id_token
from google.auth.transport import requests

# Local imports
from .forms import RegistrationForm


# Homepage
def index(request):
    return render(request, 'index.html')



@csrf_exempt
def sign_in(request):
    form = AuthenticationForm(request, data=request.POST or None)

    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        login(request, user)
        messages.success(request, "Welcome back to Wanderly!")
        return redirect('index')

    # Render the login form html and add form to context
    return render(request, 'registration/login.html', {'form': form})

@csrf_exempt
def register(request):
    # Get registration form
    form = RegistrationForm(request.POST or None)

    # If the form is submitted and valid, create the user
    if ((request.method == "POST") and (form.is_valid())):

        # Create the user in the database
        user = form.save()

        # Automatically sign in the user after registration
        authenticated_user = authenticate(
            request, username=user.username, password=form.cleaned_data["password1"]
        )

        # If user was authenticated, log them in and redirect to homepage
        if authenticated_user:
            login(request, authenticated_user)

            # Give seccess message
            messages.success(request, "Welcome to Wanderly! Your account is ready.")

            # Redirect to homepage
            return redirect('index')
        
        # If user was not authenticated, redirect to sign in page
        messages.success(request, "Account created. Please sign in.")
        return redirect('sign_in')

    # Render the registration form html and add form to context
    return render(request, 'registration/register.html', {'form': form})


# Sign out the user
def sign_out(request):
    # logout the user
    logout(request)
    
    # Send sign out message
    messages.success(request, "You have been signed out.")

    # Clear all session data
    request.session.flush()
    
    return redirect('index')


@csrf_exempt
def forgot_password(request):
    return render(request, 'registration/forgotPass.html')
 

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

