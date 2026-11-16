from django.conf import settings
from django.db import models

from resources.models import Resource


class Booking(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        APPROVED = "approved", "Approved"
        DENIED = "denied", "Denied"
        CANCELED = "canceled", "Canceled"
        COMPLETE = "complete", "Complete"

    resource = models.ForeignKey(Resource, on_delete=models.PROTECT, related_name="bookings")
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bookings")
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    purpose = models.CharField(max_length=255)
    attendees = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.REQUESTED)
    denial_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    #Makes it easier to display data
    def __str__(self):
        return f"{self.resource} - {self.requester} ({self.start_time:%Y-%m-%d %H:%M})"