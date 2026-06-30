from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.services import get_finance_settings
from payments.models import MpesaTransaction
from wallets.services import get_wallet


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
        self.assertContains(response, "Disable jobs")
        self.assertContains(response, "Disable chat")

    def test_ledger_export_requires_staff_and_returns_csv(self):
        staff = User.objects.create_user(
            username="csvstaffuser",
            email="csvstaffuser@example.com",
            phone_number="254799999993",
            password="StrongPass123!",
            is_staff=True,
        )
        self.client.force_login(staff)

        response = self.client.get(reverse("export_ledger_csv"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("ledger-export.csv", response["Content-Disposition"])

    def test_staff_can_record_manual_activation_fee(self):
        staff = User.objects.create_user(
            username="activationstaff",
            email="activationstaff@example.com",
            phone_number="254799999994",
            password="StrongPass123!",
            is_staff=True,
        )
        referrer = User.objects.create_user(
            username="activationreferrer",
            email="activationreferrer@example.com",
            phone_number="254799999995",
            password="StrongPass123!",
            status=User.AccountStatus.ACTIVE,
            activation_status=User.ActivationStatus.ACTIVATED,
        )
        user = User.objects.create_user(
            username="manualactivateuser",
            email="manualactivateuser@example.com",
            phone_number="254799999996",
            password="StrongPass123!",
            referred_by=referrer,
        )
        self.client.force_login(staff)

        response = self.client.post(
            reverse("admin_users_manager"),
            {
                "form_type": "manual_activation",
                "user": user.pk,
                "confirm_cash_received": "on",
            },
        )

        self.assertRedirects(response, reverse("admin_users_manager"))
        user.refresh_from_db()
        self.assertEqual(user.activation_status, User.ActivationStatus.ACTIVATED)
        self.assertEqual(user.status, User.AccountStatus.ACTIVE)
        transaction = MpesaTransaction.objects.get(
            user=user,
            transaction_kind=MpesaTransaction.TransactionKind.ACTIVATION,
        )
        self.assertEqual(transaction.amount, Decimal("185.00"))
        self.assertEqual(transaction.status, MpesaTransaction.Status.SUCCESS)
        self.assertTrue(transaction.mpesa_receipt_number.startswith("MANACT"))
        wallet = get_wallet(user)
        self.assertEqual(wallet.locked_balance, Decimal("185.00"))

    def test_staff_can_toggle_job_claiming(self):
        staff = User.objects.create_user(
            username="jobtogglestaff",
            email="jobtogglestaff@example.com",
            phone_number="254799999997",
            password="StrongPass123!",
            is_staff=True,
        )
        self.client.force_login(staff)

        response = self.client.post(reverse("admin_toggle_job_claims"), {"job_claims_enabled": "0"})

        self.assertRedirects(response, reverse("admin_dashboard"))
        settings_obj = get_finance_settings()
        self.assertFalse(settings_obj.job_claims_enabled)

        response = self.client.post(reverse("admin_toggle_job_claims"), {"job_claims_enabled": "1"})

        self.assertRedirects(response, reverse("admin_dashboard"))
        settings_obj.refresh_from_db()
        self.assertTrue(settings_obj.job_claims_enabled)

    def test_staff_can_toggle_chat_sessions(self):
        staff = User.objects.create_user(
            username="chattogglestaff",
            email="chattogglestaff@example.com",
            phone_number="254799999998",
            password="StrongPass123!",
            is_staff=True,
        )
        self.client.force_login(staff)

        response = self.client.post(reverse("admin_toggle_chat_sessions"), {"chat_sessions_enabled": "0"})

        self.assertRedirects(response, reverse("admin_dashboard"))
        settings_obj = get_finance_settings()
        self.assertFalse(settings_obj.chat_sessions_enabled)

        response = self.client.post(reverse("admin_toggle_chat_sessions"), {"chat_sessions_enabled": "1"})

        self.assertRedirects(response, reverse("admin_dashboard"))
        settings_obj.refresh_from_db()
        self.assertTrue(settings_obj.chat_sessions_enabled)

    @patch("reports.views.start_bulk_content_seed")
    def test_staff_can_start_bulk_content_seed(self, start_seed):
        start_seed.return_value = True
        staff = User.objects.create_user(
            username="seedstaff",
            email="seedstaff@example.com",
            phone_number="254799999989",
            password="StrongPass123!",
            is_staff=True,
        )
        self.client.force_login(staff)

        response = self.client.post(
            reverse("admin_seed_demo_content"),
            {"jobs": "12000", "surveys": "11000", "products": "10000"},
        )

        self.assertRedirects(response, reverse("admin_dashboard"))
        start_seed.assert_called_once_with(
            actor_id=staff.pk,
            jobs=12000,
            surveys=11000,
            products=10000,
        )
