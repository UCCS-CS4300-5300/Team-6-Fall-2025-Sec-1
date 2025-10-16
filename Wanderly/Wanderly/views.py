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
from django.contrib.auth.decorators import login_required # Use for vies that require login

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
    
    # Remove any Google-specific session data
    request.session.pop('google_profile_picture', None)
    request.session.pop('google_sub', None)

    # Send sign out message
    messages.success(request, "You have been signed out.")

    return redirect('sign_in')


@csrf_exempt
def forgot_password(request):
    return render(request, 'registration/forgotPass.html')
 

@csrf_exempt
def auth_receiver(request):
    """
    Handle the POST request from Google's sign-in widget and authenticate the user in Django.
    """
    # Only allow POST requests from the Google callback
    if request.method != "POST":
        return HttpResponse(status=405)

    # Extract the credential (ID token) from the request
    token = request.POST.get('credential')
    if not token:
        return HttpResponse(status=400)

    # Verify the token with Google to obtain the user payload
    try:
        user_data = id_token.verify_oauth2_token(
            token, requests.Request(), os.environ['GOOGLE_OAUTH_CLIENT_ID']
        )
    except ValueError:
        return HttpResponse(status=403)

    # Pull the identity details we care about from the verified payload
    email = user_data.get("email")
    first_name = user_data.get("given_name", "")
    last_name = user_data.get("family_name", "")
    google_sub = user_data.get("sub")
    picture = user_data.get("picture")

    if not email:
        return HttpResponse(status=400)

    # Try to find an existing Django user account for this email
    user = User.objects.filter(email__iexact=email).first()

    if not user:
        # Create a unique username from the email or Google subject
        base_username = email or google_sub or "wanderly_user"
        username = base_username
        suffix = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}_{suffix}"
            suffix += 1

        # Create a new user with an unusable password (Google-only auth)
        user = User.objects.create(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
        )
        user.set_unusable_password()
        user.save()
    else:
        # Optionally update missing name fields from Google data
        updated_fields = []
        if first_name and not user.first_name:
            user.first_name = first_name
            updated_fields.append("first_name")
        if last_name and not user.last_name:
            user.last_name = last_name
            updated_fields.append("last_name")
        if updated_fields:
            user.save(update_fields=updated_fields)

    # Log the user in via Django's session framework
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')

    # Store Google-specific details for display convenience
    request.session['google_profile_picture'] = picture or request.session.get('google_profile_picture')
    request.session['google_sub'] = google_sub or request.session.get('google_sub')

    messages.success(request, "Welcome to Wanderly!")
    return redirect('index')

