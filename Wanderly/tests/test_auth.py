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
    @patch("Wanderly.views.authenticate")
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


# Ensure the forgotten password page renders as expected.
class ForgotPasswordTests(TestCase):
    # Forgot password view should return a simple 200 response.
    def test_forgot_password_page_renders(self):
        response = self.client.get(reverse("forgot_password"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/forgotPass.html")


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
    @patch("Wanderly.views.id_token.verify_oauth2_token")
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
    @patch("Wanderly.views.id_token.verify_oauth2_token")
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
    @patch("Wanderly.views.id_token.verify_oauth2_token")
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

