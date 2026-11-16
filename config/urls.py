from django.contrib import admin
from django.urls import include, path

from accounts import views as accounts_views
from core import views as core_views
from resources import views as resource_views
from bookings import views as booking_views
from equipment import views as equipment_views
from reports import views as report_views
from notifications import views as notification_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/register/", accounts_views.register, name="register"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("resources/", resource_views.resource_list, name="resource_list"),
    path("resources/add/", resource_views.resource_create, name="resource_create"),
    path("resources/<int:pk>/edit/", resource_views.resource_update, name="resource_update"),
    path("resources/<int:pk>/delete/", resource_views.resource_delete, name="resource_delete"),
    path("", core_views.home, name="home"),
    path("resources/<int:pk>/", resource_views.resource_detail, name="resource_detail"),
    path("bookings/new/", booking_views.booking_create, name="booking_create"),
    path("bookings/", booking_views.my_bookings, name="my_bookings"),
    path("bookings/pending/", booking_views.pending_bookings, name="pending_bookings"),
    path("bookings/<int:pk>/approve/", booking_views.booking_approve, name="booking_approve"),
    path("bookings/<int:pk>/deny/", booking_views.booking_deny, name="booking_deny"),   
    path("bookings/<int:pk>/cancel/", booking_views.booking_cancel, name="booking_cancel"),
    path("resources/<int:pk>/availability/", booking_views.availability, name="availability"),
    path("equipment/checkout/", equipment_views.checkout_queue, name="checkout_queue"),
    path("equipment/checkout/<int:pk>/", equipment_views.checkout_issue, name="checkout_issue"),
    path("equipment/out/", equipment_views.checked_out_list, name="checked_out_list"),
    path("equipment/out/<int:pk>/return/", equipment_views.checkout_return, name="checkout_return"),
    path("resources/<int:pk>/status/", resource_views.resource_set_status, name="resource_set_status"),
    path("reports/bookings/", report_views.booking_summary, name="booking_summary"),
    path("reports/utilization/", report_views.resource_utilization, name="resource_utilization"),
    path("reports/staff/", report_views.staff_overview, name="staff_overview"),
    path("reports/my-summary/", report_views.my_booking_summary, name="my_booking_summary"),
    path("bookings/recurring/", booking_views.recurring_create, name="recurring_create"),
    path("notifications/", notification_views.notification_list, name="notification_list"),
    path("notifications/read/", notification_views.mark_all_read, name="mark_all_read"),
]