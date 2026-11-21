from django.test import TestCase
from django.urls import reverse

from bookings.models import Booking
from core.helpers import PASSWORD, at, make_user
from equipment.models import EquipmentCheckout
from resources.models import Resource


class ReportTestCase(TestCase):
    def setUp(self):
        self.student = make_user("stu", "student")
        self.lecturer = make_user("lec", "lecturer")
        self.staff = make_user("staff1", "staff")
        self.admin = make_user("adm", "admin")
        self.lab = Resource.objects.create(
            name="Lab 3", resource_type="room", location="Block A", capacity=100)
        self.library = Resource.objects.create(
            name="Library", resource_type="room", location="Block B", capacity=30)
        self.projector = Resource.objects.create(
            name="HP Projector", resource_type="equipment", location="Store")

    def login(self, user):
        self.client.login(username=user.username, password=PASSWORD)

    def booking(self, resource, requester, start, end, status):
        return Booking.objects.create(
            resource=resource, requester=requester, start_time=start,
            end_time=end, purpose="Test", status=status)


class AdminReportTests(ReportTestCase):
    def test_booking_summary_counts_by_status(self):  # Test 39
        S = Booking.Status
        for status in (S.REQUESTED, S.REQUESTED, S.APPROVED, S.DENIED):
            self.booking(self.lab, self.student, at(1, 14), at(1, 15), status)
        self.login(self.admin)
        response = self.client.get(reverse("booking_summary"))
        self.assertEqual(dict(response.context["rows"]), {
            "Requested": 2, "Approved": 1, "Denied": 1, "Canceled": 0, "Complete": 0,
        })
        self.assertEqual(response.context["total"], 4)

    def test_booking_summary_respects_date_range(self):  # Test 39
        self.booking(self.lab, self.student, at(1, 14), at(1, 15), Booking.Status.APPROVED)
        self.login(self.admin)
        response = self.client.get(
            reverse("booking_summary"), {"start": "2000-01-01", "end": "2000-01-02"})
        self.assertEqual(response.context["total"], 0)

    def test_utilization_counts_approved_and_complete_only(self):  # Test 39
        S = Booking.Status
        self.booking(self.lab, self.student, at(-3, 10), at(-3, 11), S.APPROVED)
        self.booking(self.lab, self.student, at(-2, 10), at(-2, 11), S.COMPLETE)
        self.booking(self.lab, self.student, at(-1, 10), at(-1, 11), S.REQUESTED)
        self.login(self.admin)
        response = self.client.get(reverse("resource_utilization"))
        resources = list(response.context["resources"])
        counts = {r.name: r.approved_count for r in resources}
        self.assertEqual(counts, {"Lab 3": 2, "Library": 0, "HP Projector": 0})
        self.assertEqual(resources[0].name, "Lab 3")

    def test_admin_reports_are_admin_only(self):
        for user in (self.student, self.lecturer, self.staff):
            self.login(user)
            self.assertEqual(self.client.get(reverse("booking_summary")).status_code, 403)
            self.assertEqual(
                self.client.get(reverse("resource_utilization")).status_code, 403)


class StaffReportTests(ReportTestCase):
    def test_staff_overview_shows_pending_overdue_and_damaged(self):  # Test 39
        S = Booking.Status
        self.booking(self.lab, self.student, at(1, 14), at(1, 15), S.REQUESTED)
        overdue = self.booking(
            self.projector, self.student, at(-1, 10), at(-1, 11), S.APPROVED)
        EquipmentCheckout.objects.create(booking=overdue, checked_out_by=self.staff)
        self.library.status = Resource.Status.DAMAGED
        self.library.save()
        self.login(self.staff)
        response = self.client.get(reverse("staff_overview"))
        self.assertEqual(response.context["pending_count"], 1)
        self.assertEqual(response.context["out_count"], 1)
        self.assertEqual(len(response.context["overdue"]), 1)
        self.assertEqual(list(response.context["damaged"]), [self.library])

    def test_staff_overview_is_staff_only(self):
        self.login(self.student)
        self.assertEqual(self.client.get(reverse("staff_overview")).status_code, 403)
        self.login(self.staff)
        self.assertEqual(self.client.get(reverse("staff_overview")).status_code, 200)


class LecturerReportTests(ReportTestCase):
    def test_my_summary_counts_only_own_bookings(self):  # Test 39
        S = Booking.Status
        self.booking(self.lab, self.lecturer, at(2, 9), at(2, 10), S.REQUESTED)
        self.booking(self.lab, self.lecturer, at(3, 9), at(3, 10), S.APPROVED)
        self.booking(self.lab, self.student, at(4, 9), at(4, 10), S.APPROVED)
        self.login(self.lecturer)
        response = self.client.get(reverse("my_booking_summary"))
        rows = dict(response.context["rows"])
        self.assertEqual(rows["Requested"], 1)
        self.assertEqual(rows["Approved"], 1)
        self.assertEqual(response.context["total"], 2)
        self.assertEqual(len(response.context["upcoming"]), 1)

    def test_my_summary_is_open_to_every_role(self):
        for user in (self.student, self.lecturer, self.staff, self.admin):
            self.login(user)
            response = self.client.get(reverse("my_booking_summary"))
            self.assertEqual(response.status_code, 200)

    def test_my_summary_needs_login(self):
        self.client.logout()
        response = self.client.get(reverse("my_booking_summary"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)