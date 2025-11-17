import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


# Validate the sign-in flow for anonymous and authenticated paths.
class SignInTests(TestCase):
    def setUp(self):
        self.url = reverse("sign_in")
        self.password = "testpass123"
        self.user = User.objects.create_user(
            username="login@example.com",
            email="login@example.com",
            password=self.password,
        )

    # Sign-in page should render for anonymous users with the correct template.
    def test_sign_in_page_renders(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/login.html")

    # Valid credentials should authenticate the user and redirect to the homepage.
    def test_sign_in_with_valid_credentials(self):
        response = self.client.post(
            self.url,
            {"username": self.user.username, "password": self.password},
            follow=True,
        )
        self.assertRedirects(response, reverse("index"))
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    # Invalid credentials should keep the user on the form and display errors.
    def test_sign_in_with_invalid_credentials(self):
        response = self.client.post(
            self.url, {"username": self.user.username, "password": "wrongpass"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/login.html")
        self.assertTrue(response.context["form"].errors)


# Exercise the registration flow to ensure users can create accounts.
class RegistrationTests(TestCase):
    def setUp(self):
        self.url = reverse("register")

    # Registration page should render with the expected template.
    def test_register_page_renders(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/register.html")

    # Matching form data should create a new user and log them in.
    def test_register_creates_user_and_logs_in(self):
        payload = {
            "first_name": "Jamie",
            "last_name": "River",
            "email": "jamie@example.com",
            "password1": "StrongPass123!",
            "password2": "StrongPass123!",
        }
        response = self.client.post(self.url, payload, follow=True)
        self.assertRedirects(response, reverse("index"))
        self.assertTrue(User.objects.filter(email=payload["email"]).exists())
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    # Mismatched passwords should keep the user on the form and surface errors.
    def test_register_with_password_mismatch(self):
        payload = {
            "first_name": "Alex",
            "last_name": "Stone",
            "email": "alex@example.com",
            "password1": "Mismatch123!",
            "password2": "Mismatch321!",
        }
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email=payload["email"]).exists())
        self.assertTrue(response.context["form"].errors)

    # When authenticate returns None, the user should be created but redirected to sign-in.
    @patch("user_auth.views.authenticate")
    def test_register_prompts_sign_in_if_authenticate_fails(self, mock_authenticate):
        mock_authenticate.return_value = None
        payload = {
            "first_name": "Casey",
            "last_name": "River",
            "email": "casey@example.com",
            "password1": "StrongPass123!",
            "password2": "StrongPass123!",
        }
        response = self.client.post(self.url, payload, follow=True)
        self.assertRedirects(response, reverse("sign_in"))
        self.assertTrue(User.objects.filter(email=payload["email"]).exists())
        self.assertFalse(response.wsgi_request.user.is_authenticated)


# Confirm sign-out clears authentication and redirects appropriately.
class SignOutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="logout@example.com",
            email="logout@example.com",
            password="logoutpass123",
        )
        self.client.login(username=self.user.username, password="logoutpass123")

    # Signing out should remove the session and redirect home.
    def test_sign_out_logs_user_out(self):
        session = self.client.session
        session["google_profile_picture"] = "https://example.com/avatar.png"
        session["google_sub"] = "sub-789"
        session.save()

        response = self.client.get(reverse("sign_out"), follow=True)
        self.assertRedirects(response, reverse("index"))
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertNotIn("google_profile_picture", self.client.session)
        self.assertNotIn("google_sub", self.client.session)
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any("signed out" in str(message).lower() for message in messages))


# Verify the Google OAuth callback handles edge cases and success paths.
class AuthReceiverTests(TestCase):
    def setUp(self):
        self.url = reverse("auth_receiver")
        # Ensure a value for GOOGLE_OAUTH_CLIENT_ID is present during the tests
        os.environ.setdefault("GOOGLE_OAUTH_CLIENT_ID", "test-google-client-id")

    # Only POST requests should be accepted by the endpoint.
    def test_get_request_returns_method_not_allowed(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    # Missing credential payloads should return a bad request.
    def test_missing_credential_returns_bad_request(self):
        response = self.client.post(self.url, data={})
        self.assertEqual(response.status_code, 400)

    # Responses lacking an email should yield a bad request status.
    @patch("user_auth.views.id_token.verify_oauth2_token")
    def test_missing_email_returns_bad_request(self, mock_verify):
        mock_verify.return_value = {
            "given_name": "Nameless",
            "family_name": "User",
            "sub": "google-sub-000",
            "picture": "https://example.com/avatar.png",
        }
        response = self.client.post(self.url, data={"credential": "fake-token"})
        self.assertEqual(response.status_code, 400)

    # Valid credential payload should create a new user when needed.
    @patch("user_auth.views.id_token.verify_oauth2_token")
    def test_valid_token_creates_user_and_logs_in(self, mock_verify):
        mock_verify.return_value = {
            "email": "googleuser@example.com",
            "given_name": "Google",
            "family_name": "User",
            "sub": "google-sub-123",
            "picture": "https://example.com/avatar.png",
        }
        response = self.client.post(self.url, data={"credential": "fake-token"})
        self.assertRedirects(response, reverse("index"))
        self.assertTrue(User.objects.filter(email="googleuser@example.com").exists())
        self.assertIn("_auth_user_id", self.client.session)

    # Existing users should be re-used rather than duplicated.
    @patch("user_auth.views.id_token.verify_oauth2_token")
    def test_valid_token_reuses_existing_user(self, mock_verify):
        existing = User.objects.create_user(
            username="existing@example.com",
            email="existing@example.com",
            password="unused",
            first_name="Existing",
            last_name="User",
        )
        mock_verify.return_value = {
            "email": "existing@example.com",
            "given_name": "Existing",
            "family_name": "User",
            "sub": "google-sub-999",
            "picture": "https://example.com/avatar.png",
        }
        response = self.client.post(self.url, data={"credential": "fake-token"})
        self.assertRedirects(response, reverse("index"))
        self.assertEqual(User.objects.filter(email="existing@example.com").count(), 1)
        self.assertEqual(int(self.client.session["_auth_user_id"]), existing.id)


"""Tests for the user_auth app."""
import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


class ResetPasswordViewTests(TestCase):
    """Exercise the reset password flow end-to-end."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="wanderer",
            email="wanderer@example.com",
            password="OldPass!234",
            first_name="Test",
            last_name="User",
        )
        self.url = reverse("reset_password")

    def test_requires_authentication(self):
        """Unauthenticated users should be redirected to the sign-in page."""
        response = self.client.get(self.url)
        expected_redirect = f"{reverse('sign_in')}?next={self.url}"
        self.assertRedirects(response, expected_redirect, fetch_redirect_response=False)

    def test_get_renders_form_when_authenticated(self):
        """Logged-in users can reach the page and see the password form."""
        self.client.login(username="wanderer", password="OldPass!234")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/changePass.html")
        self.assertIn("form", response.context)

    def test_successful_password_change(self):
        """A valid submission updates the password and redirects home."""
        self.client.login(username="wanderer", password="OldPass!234")
        response = self.client.post(
            self.url,
            {
                "old_password": "OldPass!234",
                "new_password1": "NewPass!987",
                "new_password2": "NewPass!987",
            },
        )
        self.assertRedirects(response, reverse("index"), fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewPass!987"))


class ForgotPasswordFlowTests(TestCase):
    """Test the email-based password reset process."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="seeker",
            email="seeker@example.com",
            password="OldPassword!1",
        )
        self.request_url = reverse("forgot_password_request")

    def test_request_page_renders_form(self):
        response = self.client.get(self.request_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/forgotPassRequest.html")
        self.assertIn("form", response.context)

    def test_check_email_page_shows_masked_email_and_countdown(self):
        self.client.post(self.request_url, {"email": self.user.email})
        response = self.client.get(reverse("forgot_password_check_email"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["masked_email"], "s****r@example.com")
        self.assertGreater(response.context["countdown_seconds"], 0)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_request_post_sends_email_and_redirects(self):
        response = self.client.post(self.request_url, {"email": self.user.email})
        self.assertRedirects(
            response, reverse("forgot_password_check_email"), fetch_redirect_response=False
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.user.email, mail.outbox[0].to)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_resend_sends_another_email(self):
        self.client.post(self.request_url, {"email": self.user.email})
        mail.outbox.clear()
        response = self.client.post(reverse("forgot_password_resend"))
        self.assertRedirects(
            response, reverse("forgot_password_check_email"), fetch_redirect_response=False
        )
        self.assertEqual(len(mail.outbox), 1)

    def test_resend_without_session_redirects_to_request(self):
        response = self.client.post(reverse("forgot_password_resend"))
        self.assertRedirects(
            response, reverse("forgot_password_request"), fetch_redirect_response=False
        )

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_reset_link_updates_password(self):
        self.client.post(self.request_url, {"email": self.user.email})
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        match = re.search(r"/auth/forgot-password/set/[^/]+/[^/]+/", body)
        self.assertIsNotNone(match, body)
        reset_path = match.group(0)

        response = self.client.get(reset_path)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/forgotPassSet.html")

        response = self.client.post(
            reset_path,
            {
                "new_password1": "BrandNew!55",
                "new_password2": "BrandNew!55",
            },
        )
        self.assertRedirects(
            response, reverse("forgot_password_complete"), fetch_redirect_response=False
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("BrandNew!55"))

    def test_invalid_token_redirects_to_request(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        response = self.client.get(reverse("forgot_password_set", args=[uid, "invalid-token"]))
        self.assertRedirects(
            response, reverse("forgot_password_request"), fetch_redirect_response=False
        )
