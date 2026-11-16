from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from accounts.decorators import role_required
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from django.core.exceptions import PermissionDenied
import datetime
from resources.models import Resource
from django.db import transaction
from .forms import RecurringBookingForm
from notifications.models import Notification
from django.db.models import Sum

from .forms import BookingForm
from .models import Booking

from django.utils import timezone


def complete_past_bookings():
    Booking.objects.filter(
        status=Booking.Status.APPROVED,
        end_time__lt=timezone.now(),
    ).update(status=Booking.Status.COMPLETE)


def slot_is_blocked(resource, start, end, attendees, exclude_pk=None):
    """True if the resource cannot take this booking for that time window."""
    overlapping = Booking.objects.filter(
        resource=resource,
        status=Booking.Status.APPROVED,
        start_time__lt=end,
        end_time__gt=start,
    )
    if exclude_pk:
        overlapping = overlapping.exclude(pk=exclude_pk)
    if resource.shared and resource.capacity:
        already = overlapping.aggregate(total=Sum("attendees"))["total"] or 0
        return already + attendees > resource.capacity
    return overlapping.exists()


@login_required
def booking_create(request):
    form = BookingForm(request.POST or None, user=request.user)
    if form.is_valid():
        booking = form.save(commit=False)
        booking.requester = request.user
        booking.status = "requested"
        booking.save()
        messages.success(request, "Booking request submitted.")
        return redirect("my_bookings")
    return render(request, "bookings/booking_form.html", {"form": form})

@login_required
def my_bookings(request):
    complete_past_bookings()
    bookings = (
        Booking.objects.filter(requester=request.user)
        .select_related("resource")
        .order_by("-start_time")
    )
    return render(request, "bookings/my_bookings.html", {"bookings": bookings})

@role_required("staff", "admin")
def pending_bookings(request):
    complete_past_bookings()
    bookings = (
        Booking.objects.filter(status=Booking.Status.REQUESTED)
        .select_related("resource", "requester")
        .order_by("start_time")
    )
    return render(request, "bookings/pending_bookings.html", {"bookings": bookings})

@role_required("staff", "admin")
@require_POST
def booking_approve(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    if slot_is_blocked(
        booking.resource,
        booking.start_time,
        booking.end_time,
        booking.attendees,
        exclude_pk=booking.pk,
    ):
        messages.error(
            request,
            "Cannot approve: not enough room or an overlapping approved booking.",
        )
    else:
        booking.status = Booking.Status.APPROVED
        booking.save()
        messages.success(request, "Booking approved.")
        Notification.objects.create(
            user=booking.requester,
            message=f"Your booking for {booking.resource.name} on {booking.start_time:%Y-%m-%d %H:%M} was approved.",
        )
    return redirect("pending_bookings")


@role_required("staff", "admin")
@require_POST
def booking_deny(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    booking.status = Booking.Status.DENIED
    booking.denial_reason = request.POST.get("reason", "")
    booking.save()
    messages.success(request, "Booking denied.")
    reason = booking.denial_reason or "no reason given"
    Notification.objects.create(
        user=booking.requester,
        message=f"Your booking for {booking.resource.name} on {booking.start_time:%Y-%m-%d %H:%M} was denied ({reason}).",
    )
    return redirect("pending_bookings")

@login_required
@require_POST
def booking_cancel(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    is_owner = booking.requester == request.user
    is_staff_role = request.user.role in ("staff", "admin")
    if not (is_owner or is_staff_role):
        raise PermissionDenied
    if booking.status not in (Booking.Status.REQUESTED, Booking.Status.APPROVED):
        messages.error(request, "This booking can no longer be canceled.")
    else:
        booking.status = Booking.Status.CANCELED
        booking.save()
        messages.success(request, "Booking canceled.")
        if booking.requester != request.user:
            Notification.objects.create(
                user=booking.requester,
                message=f"Your booking for {booking.resource.name} on {booking.start_time:%Y-%m-%d %H:%M} was canceled by staff.",
            )
    if is_staff_role and not is_owner:
        return redirect("pending_bookings")
    return redirect("my_bookings")

@login_required
def availability(request, pk):
    resource = get_object_or_404(Resource, pk=pk)
    date_str = request.GET.get("date")
    try:
        day = datetime.date.fromisoformat(date_str) if date_str else timezone.localdate()
    except ValueError:
        day = timezone.localdate()

    complete_past_bookings()
    bookings = (
        Booking.objects.filter(
            resource=resource,
            status__in=[Booking.Status.REQUESTED, Booking.Status.APPROVED],
            start_time__date__lte=day,
            end_time__date__gte=day,
        )
        .select_related("requester")
        .order_by("start_time")
    )

    return render(
        request,
        "bookings/availability.html",
        {"resource": resource, "day": day, "bookings": bookings},
    )

@role_required("lecturer", "admin")
def recurring_create(request):
    form = RecurringBookingForm(request.POST or None, user=request.user)
    if form.is_valid():
        data = form.cleaned_data
        weeks = data["weeks"]
        clashes = []
        for i in range(weeks):
            offset = datetime.timedelta(weeks=i)
            start = data["start_time"] + offset
            end = data["end_time"] + offset
            if slot_is_blocked(data["resource"], start, end, data["attendees"]):
                clashes.append(start.strftime("%Y-%m-%d"))
        if clashes:
            form.add_error(None, "Clashes with approved bookings on: " + ", ".join(clashes))
        else:
            with transaction.atomic():
                for i in range(weeks):
                    offset = datetime.timedelta(weeks=i)
                    Booking.objects.create(
                        resource=data["resource"],
                        requester=request.user,
                        start_time=data["start_time"] + offset,
                        end_time=data["end_time"] + offset,
                        purpose=data["purpose"],
                        attendees=data["attendees"],
                        status=Booking.Status.REQUESTED,
                    )
            messages.success(request, f"{weeks} weekly bookings requested.")
            return redirect("my_bookings")
    return render(request, "bookings/recurring_form.html", {"form": form})