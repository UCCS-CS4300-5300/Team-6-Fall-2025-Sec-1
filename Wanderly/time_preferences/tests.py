"""Smoke tests for the time_preferences app."""

from django.test import TestCase

from .forms import TimePreferenceForm


class TimePreferencesSmokeTests(TestCase):
    """Placeholder tests to keep pytest happy until real ones exist."""

    def test_form_has_expected_fields(self):
        """Basic sanity check that the form instantiates with key fields."""
        form = TimePreferenceForm()
        for field_name in ("wake_up_time", "sleep_time", "break_frequency"):
            with self.subTest(field=field_name):
                self.assertIn(field_name, form.fields)
