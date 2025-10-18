from django.contrib.auth import get_user_model
from django.test import TestCase
from django.templatetags.static import static
from django.urls import reverse


# Exercise the public homepage to ensure the key UI elements render correctly.
class HomePageTests(TestCase):

    def setUp(self):
        self.url = reverse("index")

    # Anonymous visitors should receive a 200 response rendered with the expected template.
    def test_homepage_renders_for_anonymous(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "index.html")

    # Verify the static sections (hero + features + footer) render the expected copy.
    def test_homepage_contains_expected_static_sections(self):
        response = self.client.get(self.url)
        content = response.content.decode()

        # Hero copy
        self.assertIn("Welcome to Wanderly. Here for all your travel planning needs.", content)

        # Feature cards
        self.assertIn("Personalized Itinerary Generation", content)
        self.assertIn("Route Optimization", content)
        self.assertIn("Budget Range", content)

        # Footer links
        self.assertIn("About", content)
        self.assertIn("Privacy Policy", content)

    # Ensure the hero image reference matches the expected static asset path.
    def test_homepage_static_image_reference(self):
        expected_src = static("vacation_image.jpg")
        response = self.client.get(self.url)
        self.assertIn(expected_src, response.content.decode())

    # Navbar should contain the brand and primary navigation links.
    def test_navbar_links_present(self):
        response = self.client.get(self.url)
        content = response.content.decode()
        self.assertIn('href="/#features"', content)
        self.assertIn('href="/mood/"', content)
        self.assertIn('href="/"', content)

    # Anonymous users should see a login call-to-action and no authenticated dropdown.
    def test_anonymous_sees_login_button_only(self):
        response = self.client.get(self.url)
        content = response.content.decode()
        self.assertIn("Log In", content)
        self.assertNotIn("My Portfolios", content)
        self.assertNotIn("Sign Out", content)

    # Signed in users should see the personalized greeting and dropdown options.
    def test_authenticated_user_sees_dropdown(self):
        user = get_user_model().objects.create_user(
            username="alex@example.com",
            email="alex@example.com",
            password="testpass123",
            first_name="Alex",
            last_name="McFly",
        )
        self.client.login(username="alex@example.com", password="testpass123")

        response = self.client.get(self.url)
        content = response.content.decode()

        self.assertIn("Hello, Alex M.", content)
        self.assertIn("My Portfolios", content)
        self.assertIn('href="/sign-out/"', content)
