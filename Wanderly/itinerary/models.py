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
    destination = models.CharField(max_length=255)
    place_id = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    wake_up_time = models.TimeField()
    bed_time = models.TimeField()
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

    class Meta:
        verbose_name_plural = "Itineraries"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.destination} - {self.num_days} days"

    def save(self, *args, **kwargs):
        """Make sure each itinerary has a different access code"""
        if not self.access_code:
            try:
                while True:
                    code = generate_access_code()
                    if not Itinerary.objects.filter(access_code=code).exists():
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

    class Meta:
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

    class Meta:
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

    class Meta:
        ordering = ['day_number']
        unique_together = ['itinerary', 'day_number']

    def __str__(self):
        return f"Day {self.day_number} - {self.date}"
