from django.conf import settings
from django.db import models

from bookings.models import Booking


class EquipmentCheckout(models.Model):
    class Condition(models.TextChoices):
        GOOD = "good", "Good"
        DAMAGED = "damaged", "Damaged"

    booking = models.OneToOneField(Booking, on_delete=models.PROTECT, related_name="checkout")
    checked_out_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="checkouts_issued"
    )
    checked_out_at = models.DateTimeField(auto_now_add=True)
    returned_at = models.DateTimeField(null=True, blank=True)
    return_condition = models.CharField(
        max_length=10, choices=Condition.choices, blank=True
    )
    notes = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.booking.resource} - {self.booking.requester}"