import datetime

from django.db.models import Count, Q
from django.shortcuts import render
from django.utils import timezone

from accounts.decorators import role_required
from bookings.models import Booking
from resources.models import Resource
from equipment.models import EquipmentCheckout

@role_required("admin")
def booking_summary(request):
    today = timezone.localdate()

    def parse(value, default):
        try:
            return datetime.date.fromisoformat(value) if value else default
        except ValueError:
            return default

    start = parse(request.GET.get("start"), today - datetime.timedelta(days=30))
    end = parse(request.GET.get("end"), today)

    bookings = Booking.objects.filter(
        created_at__date__gte=start,
        created_at__date__lte=end,
    )
    counts = {
        row["status"]: row["total"]
        for row in bookings.values("status").annotate(total=Count("id"))
    }
    rows = [
        (label, counts.get(value, 0))
        for value, label in Booking.Status.choices
    ]
    return render(
        request,
        "reports/booking_summary.html",
        {"start": start, "end": end, "rows": rows, "total": bookings.count()},
    )

@role_required("admin")
def resource_utilization(request):
    today = timezone.localdate()

    def parse(value, default):
        try:
            return datetime.date.fromisoformat(value) if value else default
        except ValueError:
            return default

    start = parse(request.GET.get("start"), today - datetime.timedelta(days=30))
    end = parse(request.GET.get("end"), today)

    resources = (
        Resource.objects.annotate(
            approved_count=Count(
                "bookings",
                filter=Q(
                    bookings__status__in=[Booking.Status.APPROVED, Booking.Status.COMPLETE],
                    bookings__start_time__date__gte=start,
                    bookings__start_time__date__lte=end,
                ),
            )
        )
        .order_by("-approved_count", "name")
    )
    return render(
        request,
        "reports/resource_utilization.html",
        {"start": start, "end": end, "resources": resources},
    )


@role_required("staff", "admin")
def staff_overview(request):
    now = timezone.now()
    pending_count = Booking.objects.filter(status=Booking.Status.REQUESTED).count()
    out_now = EquipmentCheckout.objects.filter(returned_at__isnull=True)
    overdue = out_now.filter(booking__end_time__lt=now).select_related(
        "booking__resource", "booking__requester"
    )
    damaged = Resource.objects.filter(status=Resource.Status.DAMAGED)
    return render(
        request,
        "reports/staff_overview.html",
        {
            "pending_count": pending_count,
            "out_count": out_now.count(),
            "overdue": overdue,
            "damaged": damaged,
        },
    )

@role_required("lecturer", "admin", "student", "staff")
def my_booking_summary(request):
    bookings = Booking.objects.filter(requester=request.user)
    counts = {
        row["status"]: row["total"]
        for row in bookings.values("status").annotate(total=Count("id"))
    }
    rows = [
        (label, counts.get(value, 0))
        for value, label in Booking.Status.choices
    ]
    upcoming = (
        bookings.filter(
            status=Booking.Status.APPROVED,
            start_time__gte=timezone.now(),
        )
        .select_related("resource")
        .order_by("start_time")
    )
    return render(
        request,
        "reports/my_booking_summary.html",
        {"rows": rows, "total": bookings.count(), "upcoming": upcoming},
    )