from django.test import TestCase
from django.urls import reverse

from bookings.models import Booking
from core.helpers import PASSWORD, at, make_user

from .models import Resource


class ResourceTestCase(TestCase):
    def setUp(self):
        self.student = make_user("stu", "student")
        self.staff = make_user("staff1", "staff")
        self.admin = make_user("adm", "admin")
        self.lab = Resource.objects.create(
            name="Lab 3", resource_type="room", location="Block A", capacity=100
        )

    def login(self, user):
        self.client.login(username=user.username, password=PASSWORD)

    def data(self, **overrides):
        data = {
            "name": "Seminar Room", "resource_type": "room",
            "location": "Block C", "capacity": 20, "features": "Whiteboard",
        }
        data.update(overrides)
        return data


class ResourceCrudTests(ResourceTestCase):
    def test_admin_can_create_resource(self):  # Test 42
        self.login(self.admin)
        response = self.client.post(reverse("resource_create"), self.data(), follow=True)
        self.assertContains(response, "Resource created.")
        self.assertContains(response, "Seminar Room")
        self.assertTrue(Resource.objects.filter(name="Seminar Room").exists())

    def test_admin_can_edit_resource(self):  # Test 43
        self.login(self.admin)
        url = reverse("resource_update", args=[self.lab.pk])
        response = self.client.post(url, self.data(name="Lab 3", location="Block Z"), follow=True)
        self.assertContains(response, "Resource updated.")
        detail = self.client.get(reverse("resource_detail", args=[self.lab.pk]))
        self.assertContains(detail, "Block Z")

    def test_blank_name_is_rejected(self):  # Test 44
        self.login(self.admin)
        response = self.client.post(reverse("resource_create"), self.data(name=""))
        self.assertContains(response, "This field is required.")
        self.assertEqual(Resource.objects.count(), 1)

    def test_negative_capacity_is_rejected(self):  # Test 44
        self.login(self.admin)
        response = self.client.post(reverse("resource_create"), self.data(capacity=-5))
        self.assertContains(response, "greater than or equal to 0")
        self.assertEqual(Resource.objects.count(), 1)

    def test_student_cannot_change_resources(self):  # permissions
        self.login(self.student)
        self.assertEqual(
            self.client.post(reverse("resource_create"), self.data()).status_code, 403)
        self.assertEqual(
            self.client.post(reverse("resource_update", args=[self.lab.pk]),
                             self.data()).status_code, 403)
        self.assertEqual(
            self.client.post(reverse("resource_delete", args=[self.lab.pk])).status_code, 403)
        self.assertEqual(Resource.objects.count(), 1)

    def test_everyone_logged_in_can_view_resources(self):
        self.login(self.student)
        self.assertContains(self.client.get(reverse("resource_list")), "Lab 3")
        self.assertEqual(
            self.client.get(reverse("resource_detail", args=[self.lab.pk])).status_code, 200)


class ResourceDeleteTests(ResourceTestCase):
    def test_resource_with_bookings_cannot_be_deleted(self):  # Test 10
        Booking.objects.create(
            resource=self.lab, requester=self.student, start_time=at(1, 14),
            end_time=at(1, 15), purpose="Class",
        )
        self.login(self.admin)
        response = self.client.post(
            reverse("resource_delete", args=[self.lab.pk]), follow=True)
        self.assertContains(
            response, "Cannot delete this resource because it has bookings.")
        self.assertTrue(Resource.objects.filter(pk=self.lab.pk).exists())

    def test_delete_asks_for_confirmation_first(self):  # Test 37
        spare = Resource.objects.create(
            name="Spare Room", resource_type="room", location="Block D", capacity=10)
        self.login(self.admin)
        url = reverse("resource_delete", args=[spare.pk])
        page = self.client.get(url)
        self.assertContains(page, "Are you sure")
        self.assertTrue(Resource.objects.filter(pk=spare.pk).exists())
        self.client.post(url)
        self.assertFalse(Resource.objects.filter(pk=spare.pk).exists())


class ResourceStatusTests(ResourceTestCase):
    def test_staff_can_repair_resource(self):  # Test 36
        self.lab.status = Resource.Status.DAMAGED
        self.lab.save()
        self.login(self.staff)
        self.client.post(reverse("resource_set_status", args=[self.lab.pk]),
                         {"status": "available"})
        self.lab.refresh_from_db()
        self.assertEqual(self.lab.status, Resource.Status.AVAILABLE)

    def test_invalid_status_is_rejected(self):
        self.login(self.staff)
        response = self.client.post(
            reverse("resource_set_status", args=[self.lab.pk]),
            {"status": "banana"}, follow=True)
        self.assertContains(response, "Invalid status.")
        self.lab.refresh_from_db()
        self.assertEqual(self.lab.status, Resource.Status.AVAILABLE)

    def test_student_cannot_change_status(self):
        self.login(self.student)
        response = self.client.post(
            reverse("resource_set_status", args=[self.lab.pk]), {"status": "damaged"})
        self.assertEqual(response.status_code, 403)
        self.lab.refresh_from_db()
        self.assertEqual(self.lab.status, Resource.Status.AVAILABLE)