import datetime

from django.test import TestCase
from django.urls import reverse

from core.helpers import PASSWORD, at, fmt, make_user
from notifications.models import Notification
from resources.models import Resource

from .models import Booking

HOUR = datetime.timedelta(hours=1)


class BookingTestCase(TestCase):
    def setUp(self):
        self.student = make_user("stu", "student")
        self.student2 = make_user("stu2", "student")
        self.lecturer = make_user("lec", "lecturer")
        self.staff = make_user("staff1", "staff")
        self.admin = make_user("adm", "admin")
        self.lab = Resource.objects.create(
            name="Lab 3", resource_type="room", location="Block A", capacity=100
        )
        self.library = Resource.objects.create(
            name="Library", resource_type="room", location="Block B",
            capacity=30, shared=True, student_bookable=True,
        )
        self.projector = Resource.objects.create(
            name="HP Projector", resource_type="equipment",
            location="Store", student_bookable=True,
        )

    def login(self, user):
        self.client.login(username=user.username, password=PASSWORD)

    def make_booking(self, resource, requester, start, end,
                     status=Booking.Status.REQUESTED, attendees=1, purpose="Test"):
        return Booking.objects.create(
            resource=resource, requester=requester, start_time=start,
            end_time=end, purpose=purpose, attendees=attendees, status=status,
        )

    def post_booking(self, resource, start, end, attendees=1, purpose="Test"):
        return self.client.post(reverse("booking_create"), {
            "resource": resource.pk, "start_time": fmt(start),
            "end_time": fmt(end), "purpose": purpose, "attendees": attendees,
        })

    def post_recurring(self, resource, start, end, weeks, attendees=1):
        return self.client.post(reverse("recurring_create"), {
            "resource": resource.pk, "start_time": fmt(start),
            "end_time": fmt(end), "purpose": "Weekly class",
            "attendees": attendees, "weeks": weeks,
        })

    def act(self, name, booking, data=None):
        return self.client.post(reverse(name, args=[booking.pk]), data or {})


class ErrorMessageTests(BookingTestCase):
    def test_past_date_is_rejected(self):  # Test 1
        self.login(self.lecturer)
        past = at(-1, 14)
        response = self.post_booking(self.lab, past, past + HOUR)
        self.assertContains(response, "You cannot book a time in the past.")
        self.assertEqual(Booking.objects.count(), 0)

    def test_end_before_start_is_rejected(self):  # Test 2
        self.login(self.lecturer)
        response = self.post_booking(self.lab, at(1, 15), at(1, 14))
        self.assertContains(response, "End time must be after the start time.")
        self.assertEqual(Booking.objects.count(), 0)

    def test_over_capacity_is_rejected(self):  # Test 3
        self.login(self.lecturer)
        response = self.post_booking(self.lab, at(1, 14), at(1, 15), attendees=200)
        self.assertContains(response, "Lab 3 seats 100, but you entered 200 attendees.")
        self.assertEqual(Booking.objects.count(), 0)

    def test_double_booking_is_rejected(self):  # Test 4
        self.make_booking(self.lab, self.lecturer, at(1, 14), at(1, 15),
                          status=Booking.Status.APPROVED)
        self.login(self.lecturer)
        start = at(1, 14, 30)
        response = self.post_booking(self.lab, start, start + HOUR)
        self.assertContains(response, "This resource is already booked for part of that time.")
        self.assertEqual(Booking.objects.count(), 1)

    def test_damaged_equipment_cannot_be_booked(self):  # Test 5
        self.projector.status = Resource.Status.DAMAGED
        self.projector.save()
        self.login(self.lecturer)
        response = self.post_booking(self.projector, at(1, 14), at(1, 15))
        self.assertContains(response, "HP Projector is currently damaged and cannot be booked.")
        self.assertEqual(Booking.objects.count(), 0)

    def test_student_cannot_book_restricted_room(self):  # Test 6
        self.login(self.student)
        response = self.post_booking(self.lab, at(1, 14), at(1, 15))
        self.assertContains(response, "Students cannot book Lab 3.")
        self.assertEqual(Booking.objects.count(), 0)

    def test_shared_space_full_is_rejected(self):  # Test 7
        self.make_booking(self.library, self.student, at(1, 14), at(1, 15),
                          status=Booking.Status.APPROVED, attendees=20)
        self.login(self.student2)
        response = self.post_booking(self.library, at(1, 14), at(1, 15), attendees=15)
        self.assertContains(response, "Only 10 spaces are left in Library for that time.")
        self.assertEqual(Booking.objects.count(), 1)

    def test_recurring_session_too_long_is_rejected(self):  # Test 8
        self.login(self.lecturer)
        response = self.post_recurring(self.lab, at(1, 9), at(3, 17), weeks=4)
        self.assertContains(response, "A recurring session must be shorter than one day.")
        self.assertEqual(Booking.objects.count(), 0)

    def test_recurring_clash_is_rejected(self):  # Test 9
        self.make_booking(self.lab, self.student, at(8, 14), at(8, 15),
                          status=Booking.Status.APPROVED)
        self.login(self.lecturer)
        response = self.post_recurring(self.lab, at(1, 14), at(1, 15), weeks=2)
        self.assertContains(response, "Clashes with approved bookings on:")
        self.assertEqual(Booking.objects.count(), 1)

    def test_blank_purpose_is_rejected(self):  # Test 15
        self.login(self.lecturer)
        response = self.post_booking(self.lab, at(1, 14), at(1, 15), purpose="")
        self.assertContains(response, "This field is required.")
        self.assertEqual(Booking.objects.count(), 0)


class WorkflowTests(BookingTestCase):
    def test_new_booking_starts_as_requested(self):  # Test 23
        self.login(self.student)
        response = self.post_booking(self.library, at(1, 14), at(1, 15))
        self.assertRedirects(response, reverse("my_bookings"))
        booking = Booking.objects.get()
        self.assertEqual(booking.status, Booking.Status.REQUESTED)
        self.assertEqual(booking.requester, self.student)
        self.assertContains(self.client.get(reverse("my_bookings")), "Requested")

    def test_staff_can_approve_and_requester_is_notified(self):  # Test 24
        booking = self.make_booking(self.lab, self.student, at(1, 14), at(1, 15))
        self.login(self.staff)
        self.act("booking_approve", booking)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.APPROVED)
        self.assertTrue(Notification.objects.filter(
            user=self.student, message__contains="was approved").exists())

    def test_denial_stores_reason_and_notifies(self):  # Test 25
        booking = self.make_booking(self.lab, self.student, at(1, 14), at(1, 15))
        self.login(self.staff)
        self.act("booking_deny", booking, {"reason": "Out of order"})
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.DENIED)
        self.assertEqual(booking.denial_reason, "Out of order")
        self.assertTrue(Notification.objects.filter(
            user=self.student, message__contains="denied (Out of order)").exists())
        self.login(self.student)
        self.assertContains(self.client.get(reverse("my_bookings")), "Out of order")

    def test_approval_rechecks_for_clashes(self):  # Test 26
        first = self.make_booking(self.lab, self.lecturer, at(1, 14), at(1, 15))
        second = self.make_booking(self.lab, self.lecturer, at(1, 14, 30), at(1, 15, 30))
        self.login(self.staff)
        self.act("booking_approve", first)
        response = self.act("booking_approve", second)
        response = self.client.get(response.url)
        self.assertContains(response, "Cannot approve: not enough room or an overlapping approved booking.")
        second.refresh_from_db()
        self.assertEqual(second.status, Booking.Status.REQUESTED)

    def test_approval_respects_shared_capacity(self):  # Test 26 (shared)
        self.make_booking(self.library, self.student, at(1, 14), at(1, 15),
                          status=Booking.Status.APPROVED, attendees=20)
        pending = self.make_booking(self.library, self.student2, at(1, 14), at(1, 15),
                                    attendees=15)
        self.login(self.staff)
        self.act("booking_approve", pending)
        pending.refresh_from_db()
        self.assertEqual(pending.status, Booking.Status.REQUESTED)

    def test_requester_can_cancel_own_booking(self):  # Test 27
        booking = self.make_booking(self.library, self.student, at(1, 14), at(1, 15))
        self.login(self.student)
        self.act("booking_cancel", booking)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CANCELED)

    def test_other_student_cannot_cancel_booking(self):  # extra permission check
        booking = self.make_booking(self.library, self.student, at(1, 14), at(1, 15))
        self.login(self.student2)
        response = self.act("booking_cancel", booking)
        self.assertEqual(response.status_code, 403)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.REQUESTED)

    def test_canceled_slot_can_be_booked_again(self):  # Test 28
        booking = self.make_booking(self.lab, self.lecturer, at(1, 14), at(1, 15),
                                    status=Booking.Status.APPROVED)
        self.login(self.lecturer)
        self.act("booking_cancel", booking)
        response = self.post_booking(self.lab, at(1, 14), at(1, 15))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            Booking.objects.filter(status=Booking.Status.REQUESTED).count(), 1)

    def test_staff_cancel_notifies_requester(self):  # Test 29
        booking = self.make_booking(self.lab, self.student, at(1, 14), at(1, 15))
        self.login(self.staff)
        self.act("booking_cancel", booking)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CANCELED)
        self.assertTrue(Notification.objects.filter(
            user=self.student, message__contains="canceled by staff").exists())

    def test_past_approved_booking_becomes_complete(self):  # Test 30
        booking = self.make_booking(self.lab, self.student, at(-2, 10), at(-2, 11),
                                    status=Booking.Status.APPROVED)
        self.login(self.student)
        self.client.get(reverse("my_bookings"))
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.COMPLETE)

    def test_shared_space_allows_overlap_within_capacity(self):  # Test 31
        self.make_booking(self.library, self.student, at(1, 14), at(1, 15),
                          status=Booking.Status.APPROVED, attendees=15)
        self.login(self.student2)
        response = self.post_booking(self.library, at(1, 14), at(1, 15), attendees=10)
        self.assertEqual(response.status_code, 302)
        new = Booking.objects.get(requester=self.student2)
        self.login(self.staff)
        self.act("booking_approve", new)
        new.refresh_from_db()
        self.assertEqual(new.status, Booking.Status.APPROVED)

    def test_students_see_only_their_own_bookings(self):  # Test 45
        self.make_booking(self.library, self.student, at(1, 14), at(1, 15),
                          purpose="Student one purpose")
        self.make_booking(self.library, self.student2, at(2, 14), at(2, 15),
                          purpose="Student two purpose")
        self.login(self.student)
        response = self.client.get(reverse("my_bookings"))
        self.assertContains(response, "Student one purpose")
        self.assertNotContains(response, "Student two purpose")

    def test_approve_needs_post_and_staff_role(self):  # Test 46
        booking = self.make_booking(self.lab, self.student, at(1, 14), at(1, 15))
        self.login(self.staff)
        response = self.client.get(reverse("booking_approve", args=[booking.pk]))
        self.assertEqual(response.status_code, 405)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.REQUESTED)
        self.login(self.student)
        response = self.act("booking_approve", booking)
        self.assertEqual(response.status_code, 403)

    def test_lecturer_can_book_restricted_room(self):  # Test 48
        self.login(self.lecturer)
        response = self.post_booking(self.lab, at(1, 14), at(1, 15))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Booking.objects.count(), 1)


class RecurringTests(BookingTestCase):
    def test_recurring_creates_one_booking_per_week(self):  # Test 32
        self.login(self.lecturer)
        response = self.post_recurring(self.lab, at(1, 14), at(1, 15), weeks=4)
        self.assertRedirects(response, reverse("my_bookings"))
        self.assertEqual(Booking.objects.count(), 4)
        self.assertFalse(
            Booking.objects.exclude(status=Booking.Status.REQUESTED).exists())
        starts = list(Booking.objects.order_by("start_time")
                      .values_list("start_time", flat=True))
        for earlier, later in zip(starts, starts[1:]):
            self.assertEqual(later - earlier, datetime.timedelta(weeks=1))

    def test_each_occurrence_is_reviewed_separately(self):  # Test 47
        self.login(self.lecturer)
        self.post_recurring(self.lab, at(1, 14), at(1, 15), weeks=3)
        first, second, third = Booking.objects.order_by("start_time")
        self.login(self.staff)
        self.act("booking_approve", first)
        self.act("booking_deny", second, {"reason": "Room closed"})
        for booking in (first, second, third):
            booking.refresh_from_db()
        self.assertEqual(first.status, Booking.Status.APPROVED)
        self.assertEqual(second.status, Booking.Status.DENIED)
        self.assertEqual(third.status, Booking.Status.REQUESTED)


class AvailabilityTests(BookingTestCase):
    def test_availability_page_shows_bookings_and_free_days(self):  # Test 51
        self.make_booking(self.lab, self.lecturer, at(1, 14), at(1, 15),
                          status=Booking.Status.APPROVED)
        self.login(self.student)
        url = reverse("availability", args=[self.lab.pk])
        busy = self.client.get(url, {"date": at(1, 9).strftime("%Y-%m-%d")})
        self.assertContains(busy, "lec")
        self.assertContains(busy, "Approved")
        free = self.client.get(url, {"date": at(5, 9).strftime("%Y-%m-%d")})
        self.assertContains(free, "free all day")