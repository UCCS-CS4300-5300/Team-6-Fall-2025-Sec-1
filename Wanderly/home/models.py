from django.db import models
from django.contrib.auth.models import User


class timeResponce(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)  # Attach Data to User
    # itinerary = models.ForeignKey('itinerary.Itinerary', on_delete=models.CASCADE) # Attach Data to Itinerary
