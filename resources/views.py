from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import role_required

from .forms import ResourceForm
from .models import Resource


@login_required
def resource_list(request):
    resources = Resource.objects.all().order_by("name")
    return render(request, "resources/resource_list.html", {"resources": resources})


@role_required("admin")
def resource_create(request):
    form = ResourceForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, "Resource created.")
        return redirect("resource_list")
    return render(request, "resources/resource_form.html", {"form": form, "title": "Add resource"})


@role_required("admin")
def resource_update(request, pk):
    resource = get_object_or_404(Resource, pk=pk)
    form = ResourceForm(request.POST or None, instance=resource)
    if form.is_valid():
        form.save()
        messages.success(request, "Resource updated.")
        return redirect("resource_list")
    return render(request, "resources/resource_form.html", {"form": form, "title": "Edit resource"})


@role_required("admin")
def resource_delete(request, pk):
    resource = get_object_or_404(Resource, pk=pk)
    if request.method == "POST":
        try:
            resource.delete()
            messages.success(request, "Resource deleted.")
        except ProtectedError:
            messages.error(request, "Cannot delete this resource because it has bookings.")
        return redirect("resource_list")
    return render(request, "resources/resource_confirm_delete.html", {"resource": resource})

@login_required
def resource_detail(request, pk):
    resource = get_object_or_404(Resource, pk=pk)
    return render(request, "resources/resource_detail.html", {"resource": resource})

@role_required("staff", "admin")
@require_POST
def resource_set_status(request, pk):
    resource = get_object_or_404(Resource, pk=pk)
    new_status = request.POST.get("status")
    if new_status in Resource.Status.values:
        resource.status = new_status
        resource.save()
        messages.success(request, f"{resource.name} marked {resource.get_status_display().lower()}.")
    else:
        messages.error(request, "Invalid status.")
    return redirect("resource_list")