from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from bookings.models import Booking

from .models import EquipmentCheckout
from django.utils import timezone


@role_required("staff", "admin")
def checkout_queue(request):
    bookings = (
        Booking.objects.filter(
            status=Booking.Status.APPROVED,
            resource__resource_type="equipment",
            checkout__isnull=True,
        )
        .select_related("resource", "requester")
        .order_by("start_time")
    )
    return render(request, "equipment/checkout_queue.html", {"bookings": bookings})


@role_required("staff", "admin")
@require_POST
def checkout_issue(request, pk):
    booking = get_object_or_404(Booking, pk=pk, status=Booking.Status.APPROVED)
    if booking.resource.resource_type != "equipment":
        messages.error(request, "Only equipment can be checked out.")
    elif hasattr(booking, "checkout"):
        messages.error(request, "This booking has already been checked out.")
    else:
        EquipmentCheckout.objects.create(booking=booking, checked_out_by=request.user)
        messages.success(request, "Equipment checked out.")
    return redirect("checkout_queue")

@role_required("staff", "admin")
def checked_out_list(request):
    checkouts = (
        EquipmentCheckout.objects.filter(returned_at__isnull=True)
        .select_related("booking__resource", "booking__requester")
        .order_by("booking__end_time")
    )
    now = timezone.now()
    for c in checkouts:
        c.is_overdue = c.booking.end_time < now
    return render(request, "equipment/checked_out_list.html", {"checkouts": checkouts})


@role_required("staff", "admin")
@require_POST
def checkout_return(request, pk):
    checkout = get_object_or_404(EquipmentCheckout, pk=pk, returned_at__isnull=True)
    condition = request.POST.get("condition", "good")
    if condition not in EquipmentCheckout.Condition.values:
        condition = "good"
    checkout.returned_at = timezone.now()
    checkout.return_condition = condition
    checkout.notes = request.POST.get("notes", "")
    checkout.save()
    if condition == EquipmentCheckout.Condition.DAMAGED:
        resource = checkout.booking.resource
        resource.status = resource.Status.DAMAGED
        resource.save()
    messages.success(request, "Equipment checked in.")
    return redirect("checked_out_list")