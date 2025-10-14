from django.db import models

class MoodResponse(models.Model):
    adventurous = models.IntegerField()
    energy = models.IntegerField()
    what_do_you_enjoy = models.JSONField() 
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Response from {self.submitted_at}"