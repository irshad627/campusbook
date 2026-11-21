from django.test import TestCase
from django.urls import reverse

from bookings.models import Booking
from core.helpers import PASSWORD, at, fmt, make_user
from resources.models import Resource

from .models import EquipmentCheckout


class EquipmentTestCase(TestCase):
    def setUp(self):
        self.student = make_user("stu", "student")
        self.lecturer = make_user("lec", "lecturer")
        self.staff = make_user("staff1", "staff")
        self.lab = Resource.objects.create(
            name="Lab 3", resource_type="room", location="Block A", capacity=100)
        self.projector = Resource.objects.create(
            name="HP Projector", resource_type="equipment",
            location="Store", student_bookable=True)

    def login(self, user):
        self.client.login(username=user.username, password=PASSWORD)

    def booking(self, resource, status=Booking.Status.APPROVED, start=None, end=None):
        return Booking.objects.create(
            resource=resource, requester=self.student,
            start_time=start or at(1, 14), end_time=end or at(1, 15),
            purpose="Test", status=status,
        )

    def checkout(self, booking):
        return EquipmentCheckout.objects.create(booking=booking, checked_out_by=self.staff)


class CheckoutQueueTests(EquipmentTestCase):
    def test_rooms_do_not_appear_in_checkout_queue(self):  # Test 49
        self.booking(self.lab)
        self.login(self.staff)
        response = self.client.get(reverse("checkout_queue"))
        self.assertNotContains(response, "Lab 3")

    def test_only_approved_equipment_is_queued(self):  # Test 50
        booking = self.booking(self.projector, status=Booking.Status.REQUESTED)
        self.login(self.staff)
        self.assertNotContains(self.client.get(reverse("checkout_queue")), "HP Projector")
        booking.status = Booking.Status.APPROVED
        booking.save()
        self.assertContains(self.client.get(reverse("checkout_queue")), "HP Projector")

    def test_student_cannot_open_checkout_queue(self):
        self.login(self.student)
        self.assertEqual(self.client.get(reverse("checkout_queue")).status_code, 403)


class CheckoutTests(EquipmentTestCase):
    def test_staff_can_check_out_equipment(self):  # Test 33
        booking = self.booking(self.projector)
        self.login(self.staff)
        self.client.post(reverse("checkout_issue", args=[booking.pk]))
        record = EquipmentCheckout.objects.get()
        self.assertEqual(record.checked_out_by, self.staff)
        self.assertIsNone(record.returned_at)
        self.assertNotContains(self.client.get(reverse("checkout_queue")), "HP Projector")
        self.assertContains(self.client.get(reverse("checked_out_list")), "HP Projector")

    def test_room_cannot_be_checked_out(self):
        booking = self.booking(self.lab)
        self.login(self.staff)
        response = self.client.post(
            reverse("checkout_issue", args=[booking.pk]), follow=True)
        self.assertContains(response, "Only equipment can be checked out.")
        self.assertFalse(EquipmentCheckout.objects.exists())

    def test_same_booking_cannot_be_checked_out_twice(self):
        booking = self.booking(self.projector)
        self.login(self.staff)
        self.client.post(reverse("checkout_issue", args=[booking.pk]))
        response = self.client.post(
            reverse("checkout_issue", args=[booking.pk]), follow=True)
        self.assertContains(response, "already been checked out")
        self.assertEqual(EquipmentCheckout.objects.count(), 1)

    def test_overdue_item_is_flagged(self):  # Test 34
        booking = self.booking(self.projector, start=at(-1, 10), end=at(-1, 11))
        self.login(self.staff)
        self.client.post(reverse("checkout_issue", args=[booking.pk]))
        self.assertContains(self.client.get(reverse("checked_out_list")), "OVERDUE")
        overview = self.client.get(reverse("staff_overview"))
        self.assertNotContains(overview, "Nothing is overdue.")
        self.assertContains(overview, "HP Projector")


class CheckinTests(EquipmentTestCase):
    def test_damaged_return_blocks_future_bookings(self):  # Test 35
        record = self.checkout(self.booking(self.projector))
        self.login(self.staff)
        self.client.post(
            reverse("checkout_return", args=[record.pk]),
            {"condition": "damaged", "notes": "Broken lens"})
        record.refresh_from_db()
        self.projector.refresh_from_db()
        self.assertIsNotNone(record.returned_at)
        self.assertEqual(record.return_condition, "damaged")
        self.assertEqual(record.notes, "Broken lens")
        self.assertEqual(self.projector.status, Resource.Status.DAMAGED)

        self.login(self.lecturer)
        response = self.client.post(reverse("booking_create"), {
            "resource": self.projector.pk, "start_time": fmt(at(2, 14)),
            "end_time": fmt(at(2, 15)), "purpose": "Lecture", "attendees": 1,
        })
        self.assertContains(
            response, "HP Projector is currently damaged and cannot be booked.")

    def test_good_return_keeps_equipment_available(self):
        record = self.checkout(self.booking(self.projector))
        self.login(self.staff)
        self.client.post(reverse("checkout_return", args=[record.pk]),
                         {"condition": "good", "notes": ""})
        record.refresh_from_db()
        self.projector.refresh_from_db()
        self.assertEqual(record.return_condition, "good")
        self.assertEqual(self.projector.status, Resource.Status.AVAILABLE)
        self.assertNotContains(
            self.client.get(reverse("checked_out_list")), "HP Projector")

    def test_return_needs_post(self):
        record = self.checkout(self.booking(self.projector))
        self.login(self.staff)
        response = self.client.get(reverse("checkout_return", args=[record.pk]))
        self.assertEqual(response.status_code, 405)