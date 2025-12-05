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
        """Create a sample user we can authenticate with."""
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
        """Seed a user and remember the request URL."""
        self.user = get_user_model().objects.create_user(
            username="seeker",
            email="seeker@example.com",
            password="OldPassword!1",
        )
        self.request_url = reverse("forgot_password_request")

    def test_request_page_renders_form(self):
        """GET /forgot-password/ renders the request template."""
        response = self.client.get(self.request_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/forgotPassRequest.html")
        self.assertIn("form", response.context)

    def test_check_email_page_shows_masked_email_and_countdown(self):
        """After submission, the check-email page shows masked info."""
        self.client.post(self.request_url, {"email": self.user.email})
        response = self.client.get(reverse("forgot_password_check_email"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["masked_email"], "s****r@example.com")
        self.assertGreater(response.context["countdown_seconds"], 0)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_request_post_sends_email_and_redirects(self):
        """Posting a valid email triggers an email and redirect."""
        response = self.client.post(self.request_url, {"email": self.user.email})
        self.assertRedirects(
            response, reverse("forgot_password_check_email"), fetch_redirect_response=False
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.user.email, mail.outbox[0].to)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_resend_sends_another_email(self):
        """Submitting the resend endpoint fires a second email."""
        self.client.post(self.request_url, {"email": self.user.email})
        mail.outbox.clear()
        response = self.client.post(reverse("forgot_password_resend"))
        self.assertRedirects(
            response, reverse("forgot_password_check_email"), fetch_redirect_response=False
        )
        self.assertEqual(len(mail.outbox), 1)

    def test_resend_without_session_redirects_to_request(self):
        """If session data is missing we bounce back to the request page."""
        response = self.client.post(reverse("forgot_password_resend"))
        self.assertRedirects(
            response, reverse("forgot_password_request"), fetch_redirect_response=False
        )

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_reset_link_updates_password(self):
        """Following the emailed link lets the user choose a new password."""
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
        """Invalid or expired links should send the user back to the start."""
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        response = self.client.get(reverse("forgot_password_set", args=[uid, "invalid-token"]))
        self.assertRedirects(
            response, reverse("forgot_password_request"), fetch_redirect_response=False
        )
