from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from core.models import FinanceSettings
from core.models import AuditLog
from payments.models import MpesaTransaction
from .models import LedgerTransaction, WithdrawalRequest
from .services import (
    approve_withdrawal,
    get_wallet,
    mark_withdrawal_paid,
    post_admin_adjustment,
    post_ledger_transaction,
    reject_withdrawal,
    request_withdrawal,
)


User = get_user_model()


class WalletLedgerTests(TestCase):
    def setUp(self):
        self.referrer = User.objects.create_user(
            username="walletreferrer",
            email="walletreferrer@example.com",
            phone_number="254766666665",
            password="StrongPass123!",
        )
        self.user = User.objects.create_user(
            username="walletuser",
            email="walletuser@example.com",
            phone_number="254766666666",
            password="StrongPass123!",
            referred_by=self.referrer,
        )

    def test_get_wallet_creates_wallet_once(self):
        first = get_wallet(self.user)
        second = get_wallet(self.user)

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(self.user.wallet.pk, first.pk)

    def test_credit_available_balance_posts_ledger(self):
        ledger, created = post_ledger_transaction(
            user=self.user,
            amount="250.00",
            transaction_type=LedgerTransaction.TransactionType.DEPOSIT_CONFIRMED,
            direction=LedgerTransaction.Direction.CREDIT,
            balance_bucket=LedgerTransaction.BalanceBucket.AVAILABLE,
            description="Test deposit",
            idempotency_key="deposit-1",
        )

        self.assertTrue(created)
        self.assertEqual(ledger.amount, Decimal("250.00"))
        wallet = get_wallet(self.user)
        self.assertEqual(wallet.available_balance, Decimal("250.00"))

    def test_idempotency_key_prevents_double_credit(self):
        first, first_created = post_ledger_transaction(
            user=self.user,
            amount="250.00",
            transaction_type=LedgerTransaction.TransactionType.DEPOSIT_CONFIRMED,
            direction=LedgerTransaction.Direction.CREDIT,
            balance_bucket=LedgerTransaction.BalanceBucket.AVAILABLE,
            description="Test deposit",
            idempotency_key="deposit-2",
        )
        second, second_created = post_ledger_transaction(
            user=self.user,
            amount="250.00",
            transaction_type=LedgerTransaction.TransactionType.DEPOSIT_CONFIRMED,
            direction=LedgerTransaction.Direction.CREDIT,
            balance_bucket=LedgerTransaction.BalanceBucket.AVAILABLE,
            description="Duplicate deposit",
            idempotency_key="deposit-2",
        )

        wallet = get_wallet(self.user)
        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(wallet.available_balance, Decimal("250.00"))

    def test_debit_requires_enough_balance(self):
        with self.assertRaises(ValidationError):
            post_ledger_transaction(
                user=self.user,
                amount="10.00",
                transaction_type=LedgerTransaction.TransactionType.WITHDRAWAL_PAID,
                direction=LedgerTransaction.Direction.DEBIT,
                balance_bucket=LedgerTransaction.BalanceBucket.AVAILABLE,
                description="Withdrawal without funds",
            )

    def test_admin_adjustment_posts_audit_log(self):
        admin = User.objects.create_user(
            username="financeadmin",
            email="financeadmin@example.com",
            phone_number="254777777777",
            password="StrongPass123!",
            is_staff=True,
        )

        ledger = post_admin_adjustment(
            user=self.user,
            amount="100.00",
            direction=LedgerTransaction.Direction.CREDIT,
            balance_bucket=LedgerTransaction.BalanceBucket.AVAILABLE,
            reason="Opening test balance",
            admin_user=admin,
        )

        wallet = get_wallet(self.user)
        self.assertEqual(ledger.transaction_type, LedgerTransaction.TransactionType.ADMIN_ADJUSTMENT)
        self.assertEqual(wallet.available_balance, Decimal("100.00"))
        self.assertEqual(AuditLog.objects.filter(action=AuditLog.Action.WALLET_ADJUSTED).count(), 1)

    def test_wallet_dashboard_requires_login(self):
        response = self.client.get(reverse("wallet_dashboard"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_wallet_dashboard_renders_for_user(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("wallet_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recent wallet activity")

    def test_admin_wallet_adjustment_view_posts_adjustment(self):
        admin = User.objects.create_user(
            username="viewadmin",
            email="viewadmin@example.com",
            phone_number="254788888888",
            password="StrongPass123!",
            is_staff=True,
        )
        self.client.force_login(admin)

        response = self.client.post(
            reverse("admin_wallet_adjustment"),
            {
                "user": self.user.pk,
                "direction": LedgerTransaction.Direction.CREDIT,
                "balance_bucket": LedgerTransaction.BalanceBucket.AVAILABLE,
                "amount": "50.00",
                "reason": "View test adjustment",
            },
        )

        self.assertRedirects(response, reverse("admin_wallet_adjustment"))
        wallet = get_wallet(self.user)
        self.assertEqual(wallet.available_balance, Decimal("50.00"))


class WithdrawalWorkflowTests(TestCase):
    def setUp(self):
        self.referrer = User.objects.create_user(
            username="withdrawreferrer",
            email="withdrawreferrer@example.com",
            phone_number="254700000000",
            password="StrongPass123!",
        )
        self.user = User.objects.create_user(
            username="withdrawuser",
            email="withdrawuser@example.com",
            phone_number="254700000001",
            password="StrongPass123!",
            referred_by=self.referrer,
            status=User.AccountStatus.ACTIVE,
            activation_status=User.ActivationStatus.ACTIVATED,
        )
        self.admin = User.objects.create_user(
            username="withdrawadmin",
            email="withdrawadmin@example.com",
            phone_number="254700000002",
            password="StrongPass123!",
            is_staff=True,
            status=User.AccountStatus.ACTIVE,
            activation_status=User.ActivationStatus.ACTIVATED,
        )
        self.finance_settings = FinanceSettings.load()
        self.finance_settings.payout_enabled = True
        self.finance_settings.minimum_withdrawal_amount = Decimal("100.00")
        self.finance_settings.maximum_daily_withdrawal_per_user = Decimal("10000.00")
        self.finance_settings.withdrawal_fee_fixed = Decimal("0.00")
        self.finance_settings.withdrawal_fee_percent = Decimal("0.00")
        self.finance_settings.reserve_ratio_target = Decimal("1.00")
        self.finance_settings.minimum_platform_cash_buffer = Decimal("0.00")
        self.finance_settings.save()

    def fund_user_with_confirmed_cash(self, amount="1000.00"):
        MpesaTransaction.objects.create(
            user=self.user,
            transaction_kind=MpesaTransaction.TransactionKind.DEPOSIT,
            payment_method=MpesaTransaction.PaymentMethod.C2B,
            status=MpesaTransaction.Status.SUCCESS,
            amount=Decimal(amount),
            phone_number=self.user.phone_number,
            account_reference="WFLOW",
        )
        post_ledger_transaction(
            user=self.user,
            amount=amount,
            transaction_type=LedgerTransaction.TransactionType.DEPOSIT_CONFIRMED,
            direction=LedgerTransaction.Direction.CREDIT,
            balance_bucket=LedgerTransaction.BalanceBucket.AVAILABLE,
            description="Confirmed test deposit",
        )

    def test_withdrawal_below_minimum_is_blocked(self):
        self.fund_user_with_confirmed_cash()

        with self.assertRaises(ValidationError):
            request_withdrawal(user=self.user, amount="50.00", phone_number=self.user.phone_number)

    def test_withdrawal_request_locks_available_funds(self):
        self.fund_user_with_confirmed_cash()

        withdrawal = request_withdrawal(user=self.user, amount="300.00", phone_number=self.user.phone_number)

        wallet = get_wallet(self.user)
        self.assertEqual(withdrawal.status, WithdrawalRequest.Status.REQUESTED)
        self.assertEqual(wallet.available_balance, Decimal("700.00"))
        self.assertEqual(wallet.locked_balance, Decimal("300.00"))
        self.assertIsNotNone(withdrawal.request_debit_ledger)
        self.assertIsNotNone(withdrawal.lock_credit_ledger)

    def test_reject_withdrawal_returns_locked_funds(self):
        self.fund_user_with_confirmed_cash()
        withdrawal = request_withdrawal(user=self.user, amount="300.00", phone_number=self.user.phone_number)

        reject_withdrawal(withdrawal=withdrawal, reviewer=self.admin, reason="KYC mismatch")

        withdrawal.refresh_from_db()
        wallet = get_wallet(self.user)
        self.assertEqual(withdrawal.status, WithdrawalRequest.Status.REJECTED)
        self.assertEqual(wallet.available_balance, Decimal("1000.00"))
        self.assertEqual(wallet.locked_balance, Decimal("0.00"))
        self.assertEqual(withdrawal.rejection_reason, "KYC mismatch")

    def test_approve_and_mark_paid_reduces_locked_balance(self):
        self.fund_user_with_confirmed_cash()
        withdrawal = request_withdrawal(user=self.user, amount="300.00", phone_number=self.user.phone_number)

        approve_withdrawal(withdrawal=withdrawal, reviewer=self.admin)
        withdrawal.refresh_from_db()
        mark_withdrawal_paid(withdrawal=withdrawal, reviewer=self.admin, payout_reference="QWE123")

        withdrawal.refresh_from_db()
        wallet = get_wallet(self.user)
        self.assertEqual(withdrawal.status, WithdrawalRequest.Status.PAID)
        self.assertEqual(withdrawal.payout_reference, "QWE123")
        self.assertEqual(wallet.available_balance, Decimal("700.00"))
        self.assertEqual(wallet.locked_balance, Decimal("0.00"))
        self.assertEqual(wallet.total_withdrawn, Decimal("300.00"))

    def test_solvency_blocks_withdrawal_without_confirmed_cash(self):
        post_ledger_transaction(
            user=self.user,
            amount="1000.00",
            transaction_type=LedgerTransaction.TransactionType.ADMIN_ADJUSTMENT,
            direction=LedgerTransaction.Direction.CREDIT,
            balance_bucket=LedgerTransaction.BalanceBucket.AVAILABLE,
            description="Unsafe test credit",
        )

        with self.assertRaises(ValidationError):
            request_withdrawal(user=self.user, amount="300.00", phone_number=self.user.phone_number)

    def test_withdrawal_request_view_creates_request(self):
        self.fund_user_with_confirmed_cash()
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("withdrawal_request"),
            {"amount": "300.00", "phone_number": self.user.phone_number},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(WithdrawalRequest.objects.filter(user=self.user).count(), 1)

    def test_withdrawal_queue_renders_for_staff(self):
        self.fund_user_with_confirmed_cash()
        request_withdrawal(user=self.user, amount="300.00", phone_number=self.user.phone_number)
        self.client.force_login(self.admin)

        response = self.client.get(reverse("withdrawal_queue"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "withdrawuser")
