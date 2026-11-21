from django.test import TestCase
from django.urls import reverse

from core.helpers import PASSWORD, make_user

from .models import Notification


class NotificationTests(TestCase):
    def setUp(self):
        self.student = make_user("stu", "student")
        self.other = make_user("other", "student")
        Notification.objects.create(user=self.student, message="First note")
        Notification.objects.create(user=self.student, message="Second note")
        Notification.objects.create(user=self.other, message="Secret for other")
        self.client.login(username="stu", password=PASSWORD)

    def test_nav_shows_unread_count(self):  # Test 38
        self.assertContains(self.client.get("/"), "Notifications (2)")

    def test_list_shows_only_own_notifications(self):
        response = self.client.get(reverse("notification_list"))
        self.assertContains(response, "First note")
        self.assertNotContains(response, "Secret for other")

    def test_mark_all_read_clears_count(self):  # Test 38
        response = self.client.post(reverse("mark_all_read"))
        self.assertRedirects(response, reverse("notification_list"))
        self.assertContains(self.client.get("/"), "Notifications (0)")
        self.assertFalse(
            Notification.objects.filter(user=self.student, is_read=False).exists())
        self.assertTrue(
            Notification.objects.filter(user=self.other, is_read=False).exists())

    def test_mark_all_read_needs_post(self):
        self.assertEqual(self.client.get(reverse("mark_all_read")).status_code, 405)

    def test_logged_out_user_is_sent_to_login(self):
        self.client.logout()
        response = self.client.get(reverse("notification_list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)