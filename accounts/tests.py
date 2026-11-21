from django.test import TestCase

from .models import User

PASSWORD = "testpass12345"


class AuthenticationTests(TestCase):
    def setUp(self):
        User.objects.create_user("stu", password=PASSWORD, role="student")

    def register(self, **overrides):
        data = {"username": "newuser", "password1": PASSWORD, "password2": PASSWORD}
        data.update(overrides)
        return self.client.post("/accounts/register/", data)

    # Test 40
    def test_register_creates_student_and_logs_in(self):
        response = self.register()
        self.assertRedirects(response, "/")
        self.assertEqual(User.objects.get(username="newuser").role, "student")
        self.assertContains(self.client.get("/"), "newuser (Student)")

    # Test 41
    def test_logout_then_login(self):
        self.register()
        response = self.client.post("/accounts/logout/")
        self.assertRedirects(response, "/accounts/login/")
        response = self.client.post(
            "/accounts/login/", {"username": "newuser", "password": PASSWORD}
        )
        self.assertRedirects(response, "/")
        self.assertContains(self.client.get("/"), "newuser (Student)")

    # Test 11
    def test_wrong_password_shows_error(self):
        response = self.client.post(
            "/accounts/login/", {"username": "stu", "password": "wrongpass"}
        )
        self.assertContains(response, "Your username or password was incorrect.")

    # Test 12
    def test_weak_password_is_rejected(self):
        response = self.register(password1="abc", password2="abc")
        self.assertContains(response, "too short")
        self.assertFalse(User.objects.filter(username="newuser").exists())

    # Test 13
    def test_mismatched_passwords_are_rejected(self):
        response = self.register(password2="differentpass99")
        self.assertContains(response, "The two password fields")
        self.assertFalse(User.objects.filter(username="newuser").exists())

    # Test 14
    def test_duplicate_username_is_rejected(self):
        response = self.register(username="stu")
        self.assertContains(response, "already exists")
        self.assertEqual(User.objects.filter(username="stu").count(), 1)

    # Extra: nobody can pick their own role when registering
    def test_registration_ignores_role_field(self):
        self.register(role="admin")
        self.assertEqual(User.objects.get(username="newuser").role, "student")


class PermissionTests(TestCase):
    def setUp(self):
        for name, role in [
            ("stu", "student"),
            ("lec", "lecturer"),
            ("staff1", "staff"),
            ("adm", "admin"),
        ]:
            User.objects.create_user(name, password=PASSWORD, role=role)

    def login(self, name):
        self.client.login(username=name, password=PASSWORD)

    def home(self, name):
        self.login(name)
        return self.client.get("/")

    # Tests 16 to 20
    def test_student_cannot_add_resource(self):
        self.login("stu")
        self.assertEqual(self.client.get("/resources/add/").status_code, 403)

    def test_student_cannot_see_pending_requests(self):
        self.login("stu")
        self.assertEqual(self.client.get("/bookings/pending/").status_code, 403)

    def test_student_cannot_make_recurring_booking(self):
        self.login("stu")
        self.assertEqual(self.client.get("/bookings/recurring/").status_code, 403)

    def test_student_cannot_see_admin_report(self):
        self.login("stu")
        self.assertEqual(self.client.get("/reports/bookings/").status_code, 403)

    def test_lecturer_cannot_see_admin_report(self):
        self.login("lec")
        self.assertEqual(self.client.get("/reports/bookings/").status_code, 403)

    # Test 21
    def test_logged_out_user_is_sent_to_login(self):
        response = self.client.get("/bookings/")
        self.assertRedirects(response, "/accounts/login/?next=/bookings/")

    # Test 22
    def test_student_nav_links(self):
        response = self.home("stu")
        self.assertContains(response, "Request booking")
        self.assertNotContains(response, "Pending requests")
        self.assertNotContains(response, "Recurring booking")
        self.assertNotContains(response, "Booking report")

    def test_lecturer_nav_links(self):
        response = self.home("lec")
        self.assertContains(response, "Recurring booking")
        self.assertContains(response, "My summary")
        self.assertNotContains(response, "Pending requests")
        self.assertNotContains(response, "Booking report")

    def test_staff_nav_links(self):
        response = self.home("staff1")
        self.assertContains(response, "Pending requests")
        self.assertContains(response, "Equipment check-out")
        self.assertContains(response, "Staff overview")
        self.assertNotContains(response, "Recurring booking")
        self.assertNotContains(response, "Booking report")

    def test_admin_nav_links(self):
        response = self.home("adm")
        self.assertContains(response, "Booking report")
        self.assertContains(response, "Utilization report")
        self.assertContains(response, "Pending requests")
        self.assertContains(response, "Admin site")

    # Test 52
    def test_changing_role_changes_access(self):
        user = User.objects.get(username="stu")
        self.login("stu")
        self.assertEqual(self.client.get("/bookings/recurring/").status_code, 403)

        user.role = "lecturer"
        user.save()
        self.assertEqual(self.client.get("/bookings/recurring/").status_code, 200)

        user.role = "student"
        user.save()
        self.assertEqual(self.client.get("/bookings/recurring/").status_code, 403)