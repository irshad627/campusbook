from django.db import models


class Resource(models.Model):
    class ResourceType(models.TextChoices):
        ROOM = "room", "Room"
        EQUIPMENT = "equipment", "Equipment"

    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        DAMAGED = "damaged", "Damaged"
        UNAVAILABLE = "unavailable", "Unavailable"

    name = models.CharField(max_length=100)
    resource_type = models.CharField(
        max_length=10,
        choices=ResourceType.choices,
    )
    location = models.CharField(max_length=150)
    capacity = models.PositiveIntegerField(null=True, blank=True)
    features = models.TextField(blank=True)

    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.AVAILABLE,
    )

    student_bookable = models.BooleanField(default=False)

    shared = models.BooleanField(
        default=False,
        help_text="Tick for spaces many people can use at once (e.g. a library). Bookings are limited by total attendees vs capacity.",
    )

    def __str__(self):
        return self.name