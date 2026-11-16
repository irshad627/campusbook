from django import forms
from django.db.models import Sum
from django.utils import timezone
import datetime

from .models import Booking


class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ("resource", "start_time", "end_time", "purpose", "attendees")
        widgets = {
            "start_time": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "end_time": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_time")
        end = cleaned.get("end_time")
        if start and end:
            if end <= start:
                raise forms.ValidationError("End time must be after the start time.")
            if start < timezone.now():
                raise forms.ValidationError("You cannot book a time in the past.")

        resource = cleaned.get("resource")

        if resource and resource.status != resource.Status.AVAILABLE:
            raise forms.ValidationError(
                f"{resource.name} is currently {resource.get_status_display().lower()} and cannot be booked."
            )

        if (
            resource
            and self.user
            and self.user.role == "student"
            and not resource.student_bookable
        ):
            raise forms.ValidationError(
                f"Students cannot book {resource.name}. Please choose a student-bookable resource."
            )

        attendees = cleaned.get("attendees")

        if resource and attendees and resource.capacity:
            if attendees > resource.capacity:
                raise forms.ValidationError(
                    f"{resource.name} seats {resource.capacity}, but you entered {attendees} attendees."
                )

        if start and end and resource:
            overlapping = Booking.objects.filter(
                resource=resource,
                status=Booking.Status.APPROVED,
                start_time__lt=end,
                end_time__gt=start,
            )
            if resource.shared and resource.capacity:
                already = overlapping.aggregate(total=Sum("attendees"))["total"] or 0
                if already + (attendees or 1) > resource.capacity:
                    raise forms.ValidationError(
                        f"Only {max(resource.capacity - already, 0)} spaces are left in {resource.name} for that time."
                    )
            elif overlapping.exists():
                raise forms.ValidationError(
                    "This resource is already booked for part of that time."
                )

        return cleaned


class RecurringBookingForm(BookingForm):
    weeks = forms.IntegerField(
        min_value=2,
        max_value=15,
        initial=10,
        help_text="Repeat weekly for this many weeks (including the first).",
    )

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_time")
        end = cleaned.get("end_time")
        if start and end and end - start >= datetime.timedelta(days=1):
            raise forms.ValidationError(
                "A recurring session must be shorter than one day."
            )
        return cleaned