"""Creates itinerary models with the space for the form data"""
import string
import secrets
from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator

def generate_access_code():
    """
    Function to generate access code for each itinerary object.
    8-character code with numbers and letters
    """
    ac_alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(ac_alphabet) for _ in range(8))


class Itinerary(models.Model):
    """Main itinerary model storing trip information"""
    TRIP_PURPOSE_CHOICES = [
        ("leisure", "Leisure"),
        ("family", "Family"),
        ("adventure", "Adventure"),
        ("relaxed", "Relaxed"),
        ("business", "Business"),
    ]
    ENERGY_CHOICES = [
        ("easy", "Easy-going"),
        ("balanced", "Balanced"),
        ("high", "High energy"),
    ]

    destination = models.CharField(max_length=255)
    place_id = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    hotel_address = models.CharField(max_length=255, blank=True)
    hotel_name = models.CharField(max_length=255, blank=True)
    hotel_place_id = models.CharField(max_length=255, blank=True)
    hotel_check_in = models.DateTimeField(null=True, blank=True)
    hotel_check_out = models.DateTimeField(null=True, blank=True)
    wake_up_time = models.TimeField()
    bed_time = models.TimeField()
    start_date = models.DateField()
    end_date = models.DateField()
    trip_purpose = models.CharField(max_length=32, choices=TRIP_PURPOSE_CHOICES, default="leisure")
    energy_level = models.CharField(max_length=16, choices=ENERGY_CHOICES, default="balanced")
    include_breakfast = models.BooleanField(default=True)
    include_lunch = models.BooleanField(default=True)
    include_dinner = models.BooleanField(default=True)
    dietary_notes = models.TextField(blank=True)
    mobility_notes = models.TextField(blank=True)
    downtime_required = models.BooleanField(default=False)
    party_adults = models.PositiveIntegerField(default=1)
    party_children = models.PositiveIntegerField(default=0)
    arrival_datetime = models.DateTimeField(null=True, blank=True)
    arrival_airport = models.CharField(max_length=64, blank=True)
    departure_datetime = models.DateTimeField(null=True, blank=True)
    departure_airport = models.CharField(max_length=64, blank=True)
    overall_budget_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    num_days = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(30)])
    ai_itinerary = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    access_code = models.CharField(
        max_length=8,
        unique=True,
        editable=False,
        blank=True,
        null=True,
    )

    class Meta:  # pylint: disable=too-few-public-methods
        """Model metadata for itineraries."""
        verbose_name_plural = "Itineraries"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.destination} - {self.num_days} days"

    def clean(self):
        """Ensure dates are valid."""
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError("End date must be on or after the start date.")

    def save(self, *args, **kwargs):
        """Make sure each itinerary has a different access code"""
        if self.start_date and self.end_date:
            day_span = (self.end_date - self.start_date).days + 1
            self.num_days = max(1, min(day_span, 30))

        if not self.access_code:
            try:
                while True:
                    code = generate_access_code()
                    if not Itinerary.objects.filter(access_code=code).exists():  # pylint: disable=no-member
                        self.access_code = code
                        break
            except Exception as exc:
                raise ValidationError(
                    "There was an error generating an access code for this itinerary. "
                    "Please try again."
                ) from exc
        super().save(*args, **kwargs)

class BreakTime(models.Model):
    """Break times during the day"""
    itinerary = models.ForeignKey(Itinerary, on_delete=models.CASCADE, related_name='break_times')
    start_time = models.TimeField()
    end_time = models.TimeField()
    purpose = models.CharField(max_length=64, blank=True)

    class Meta:  # pylint: disable=too-few-public-methods
        """Ordering for break times."""
        ordering = ['start_time']

    def __str__(self):
        return f"{self.start_time} - {self.end_time}"


class BudgetItem(models.Model):
    """Budget items for the trip"""
    CATEGORY_CHOICES = [
        ('Accommodation', 'Accommodation'),
        ('Transportation', 'Transportation'),
        ('Food & Dining', 'Food & Dining'),
        ('Activities', 'Activities'),
        ('Shopping', 'Shopping'),
        ('Other', 'Other'),
    ]

    itinerary = models.ForeignKey(Itinerary, on_delete=models.CASCADE, related_name='budget_items')
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    custom_category = models.CharField(max_length=100, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])

    class Meta:  # pylint: disable=too-few-public-methods
        """Ordering for budget items."""
        ordering = ['category']

    def __str__(self):
        if self.category == 'Other' and self.custom_category:
            return f"{self.custom_category}: ${self.amount}"
        return f"{self.category}: ${self.amount}"


class Day(models.Model):
    """Individual days of the trip"""
    itinerary = models.ForeignKey(Itinerary, on_delete=models.CASCADE, related_name='days')
    day_number = models.IntegerField(validators=[MinValueValidator(1)])
    date = models.DateField()
    notes = models.TextField(blank=True)
    wake_override = models.TimeField(null=True, blank=True)
    bed_override = models.TimeField(null=True, blank=True)
    constraints = models.TextField(blank=True)
    must_do = models.TextField(blank=True)

    class Meta:  # pylint: disable=too-few-public-methods
        """Ordering and uniqueness for days."""
        ordering = ['day_number']
        unique_together = ['itinerary', 'day_number']

    def __str__(self):
        return f"Day {self.day_number} - {self.date}"
