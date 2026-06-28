from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import AuditLog, FinanceSettings
from .services import create_audit_log, get_finance_settings

User = get_user_model()


class CorePageTests(TestCase):
    def test_home_page_renders(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Workflow Agency")

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_authenticated_dashboard_renders(self):
        user = User.objects.create_user(
            username="dashboarduser",
            email="dashboarduser@example.com",
            phone_number="254744444444",
            password="StrongPass123!",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recommended opportunities")


class FinanceSettingsTests(TestCase):
    def test_finance_settings_load_returns_singleton(self):
        first = get_finance_settings()
        second = get_finance_settings()

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(FinanceSettings.objects.count(), 1)

    def test_audit_log_can_record_changes(self):
        user = User.objects.create_user(
            username="auditor",
            email="auditor@example.com",
            phone_number="254755555555",
            password="StrongPass123!",
        )
        settings_obj = get_finance_settings()

        audit = create_audit_log(
            action=AuditLog.Action.FINANCE_SETTING_CHANGED,
            actor=user,
            instance=settings_obj,
            changes={"activation_fee": {"old": "185.00", "new": "200.00"}},
        )

        self.assertEqual(audit.actor, user)
        self.assertEqual(audit.action, AuditLog.Action.FINANCE_SETTING_CHANGED)
        self.assertEqual(audit.changes["activation_fee"]["new"], "200.00")
