from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class ReportsViewTests(TestCase):
    def test_admin_dashboard_requires_staff(self):
        user = User.objects.create_user(
            username="normalreportuser",
            email="normalreportuser@example.com",
            phone_number="254799999991",
            password="StrongPass123!",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("admin_dashboard"))

        self.assertEqual(response.status_code, 302)

    def test_admin_dashboard_renders_for_staff(self):
        staff = User.objects.create_user(
            username="staffreportuser",
            email="staffreportuser@example.com",
            phone_number="254799999992",
            password="StrongPass123!",
            is_staff=True,
        )
        self.client.force_login(staff)

        response = self.client.get(reverse("admin_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Finance settings")
        self.assertContains(response, "Wallet buckets")
