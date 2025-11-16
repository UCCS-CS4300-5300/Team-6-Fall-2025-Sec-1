"""Tests for the user_auth app."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class ResetPasswordViewTests(TestCase):
    """Exercise the reset password flow end-to-end."""

    def setUp(self):
        self.user = User.objects.create_user(
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
