""" System imports"""
import os

""" Django imports """
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    get_user_model,
    login,
    logout,
    update_session_auth_hash,
)
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm
from django.contrib.auth.tokens import default_token_generator
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.csrf import csrf_exempt

""" Google OAuth imports """
from google.auth.transport import requests
from google.oauth2 import id_token

""" Local imports """
from .forms import ChangePasswordForm, RegistrationForm, ResetPasswordForm

# Get the user model
User = get_user_model()


def _mask_email_address(email):
    """Mask the local part of an email for display."""
    # Simple masking: show first and last character of local part, mask the rest
    if not email or "@" not in email:
        return email
    local, _, domain = email.partition("@")
    if len(local) <= 2:
        masked_local = local[0] + "*"
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked_local}@{domain}"


# --------------------- user authentication views --------------------- #

def sign_in(request):
    """Render the login form and handle credentials submission."""
    form = AuthenticationForm(request, data=request.POST or None)

    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        login(request, user)
        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])
        messages.success(request, "Welcome back to Wanderly!")
        return redirect("index")

    # Render the login form html and add form to context
    return render(request, "registration/login.html", {"form": form})


def register(request):
    """Create a new user account and log them in."""
    # Get registration form
    form = RegistrationForm(request.POST or None)

    # If the form is submitted and valid, create the user
    if (request.method == "POST") and form.is_valid():
        # Create the user in the database
        user = form.save()

        # Automatically sign in the user after registration
        authenticated_user = authenticate(
            request, username=user.username, password=form.cleaned_data["password1"]
        )

        # If user was authenticated, log them in and redirect to homepage
        if authenticated_user:
            login(request, authenticated_user)
            authenticated_user.last_login = timezone.now()
            authenticated_user.save(update_fields=["last_login"])

            # Give seccess message
            messages.success(request, "Welcome to Wanderly! Your account is ready.")

            # Redirect to homepage
            return redirect("index")

        # If user was not authenticated, redirect to sign in page
        messages.success(request, "Account created. Please sign in.")
        return redirect("sign_in")

    # Render the registration form html and add form to context
    return render(request, "registration/register.html", {"form": form})


def sign_out(request):
    """Clear the current session and redirect home."""
    # logout the user
    logout(request)

    # Remove any Google-specific session data
    request.session.pop("google_profile_picture", None)
    request.session.pop("google_sub", None)

    # Send sign out message
    messages.success(request, "You have been signed out.")

    return redirect("index")


@login_required(login_url=reverse_lazy("sign_in"))
def reset_password(request):
    """Allow an authenticated user to change their password."""

    # If the form is submitted
    if request.method == "POST":

        # Get change password form data
        form = ChangePasswordForm(request.user, request.POST)

        # check if form is valid using clean_ methods
        if form.is_valid():
            user = form.save()                          # Save the new password
            update_session_auth_hash(request, user)     # Keep the user logged in
            messages.success(request, "Your password has been updated.")
            return redirect("index")                    # Redirect to homepage
    else:
        form = ChangePasswordForm(request.user)

    # render the change password page w/ form context
    return render(request, "registration/changePass.html", {"form": form})


@csrf_exempt
def auth_receiver(request):
    """Handle the Google sign-in callback and log the user in."""

    # Only allow POST requests from the Google callback
    if request.method != "POST":
        return HttpResponse(status=405)

    # Extract the credential (ID token) from the request
    token = request.POST.get("credential")
    if not token:
        return HttpResponse(status=400)

    # Verify the token with Google to obtain the user payload
    try:
        user_data = id_token.verify_oauth2_token(
            token, requests.Request(), os.environ["GOOGLE_OAUTH_CLIENT_ID"]
        )
    except ValueError:
        return HttpResponse(status=403)

    # Pull the identity details we care about from the verified payload
    email = user_data.get("email")
    first_name = user_data.get("given_name", "")
    last_name = user_data.get("family_name", "")
    google_sub = user_data.get("sub")
    #picture = user_data.get("picture", "")

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

    # Log the user in via Django's session framework
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    user.last_login = timezone.now()
    user.save(update_fields=["last_login"])

    # Send welcome message
    messages.success(request, "Welcome to Wanderly!")

    # Redirect to homepage
    return redirect("index")


def forgot_password_request(request):
    """Display and process the forgot-password request form."""
    # Get password reset form
    form = PasswordResetForm(request.POST or None)

    #  If the form is submitted and valid, send the reset email
    if request.method == "POST" and form.is_valid():

        # Store the email in session
        request.session["password_reset_email"] = form.cleaned_data["email"]

        # Send the password reset email
        form.save(
            request=request,
            use_https=request.is_secure(),
            subject_template_name="registration/emails/password_reset_subject.txt",
            email_template_name="registration/emails/password_reset_body.txt",
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            extra_email_context={
                "protocol": "https" if request.is_secure() else "http",
                "domain": request.get_host(),
                "site_name": "Wanderly",
            },
        )

        # Show success message
        messages.success(
            request,
            "If an account with that email exists, a password reset link has been sent.",
        )

        # Redirect to check email page
        return redirect("forgot_password_check_email")

    return render(request, "registration/forgotPassRequest.html", {"form": form})

def forgot_password_check_email(request):
    """Show the countdown and masked email after a reset link is sent."""

    # Get the email from session
    email = request.session.get("password_reset_email")

    # Get countdown seconds from settings
    countdown_seconds = getattr(settings, "PASSWORD_RESET_TIMEOUT", 300)

    # Set up context for template
    context = {
        "masked_email": _mask_email_address(email) if email else None,
        "countdown_seconds": countdown_seconds,
        "resend_enabled": email is not None,
    }
    return render(request, "registration/forgotPassCheckEmail.html", context)


def forgot_password_resend(request):
    """Send another reset email using the address stored in session."""

    # Get the email from session
    email = request.session.get("password_reset_email")

    # If no email in session, redirect back with error
    if not email:
        messages.error(request, "We couldn't find your email. Please enter it again.")
        return redirect("forgot_password_request")

    # Resend the password reset email
    form = PasswordResetForm({"email": email})
    if form.is_valid():
        form.save(
            request=request,
            use_https=request.is_secure(),
            subject_template_name="registration/emails/password_reset_subject.txt",
            email_template_name="registration/emails/password_reset_body.txt",
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            extra_email_context={
                "protocol": "https" if request.is_secure() else "http",
                "domain": request.get_host(),
                "site_name": "Wanderly",
            },
        )
        messages.success(request, "We sent another password reset link.")
    else:
        messages.error(request, "Unable to resend the reset email right now.")

    return redirect("forgot_password_check_email")


def forgot_password_set(request, uidb64, token):
    """Validate the reset token and accept a new password."""
    # Decode the user ID from the base64 string
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)

    # Handle exceptions for invalid decoding or user not found
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    # Check if the token is valid for the user
    if (not user) or (not default_token_generator.check_token(user, token)):
        messages.error(
            request,
            "The password reset link is invalid or has expired. Please request a new one.",
        )
        return redirect("forgot_password_request")

    # If the form is submitted
    if request.method == "POST":
        form = ResetPasswordForm(user, request.POST) # Get reset password form data
        if form.is_valid():                          # Validate the form
            form.save()                              # Save the new password
            request.session.pop("password_reset_email", None)
            messages.success(request, "Your password has been reset. You can sign in now.")

            # Redirect to the password reset complete page
            return redirect("forgot_password_complete")
    else:
        form = ResetPasswordForm(user)

    return render(request, "registration/forgotPassSet.html", {"form": form})


def forgot_password_complete(request):
    """Render a confirmation screen once the password is reset."""
    # Render the password reset complete page
    return render(request, "registration/forgotPassComplete.html")
