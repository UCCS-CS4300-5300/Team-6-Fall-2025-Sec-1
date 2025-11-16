"""creates mood response model"""
from django.db import models

class MoodResponse(models.Model):
    """mood response class"""
    destination = models.CharField(max_length=200, null=True, blank=True)
    adventurous = models.IntegerField()
    energy = models.IntegerField()
    what_do_you_enjoy = models.JSONField()
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Response from {self.submitted_at}"
