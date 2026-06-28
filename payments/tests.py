import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import FinanceSettings
from core.services import get_finance_settings
from referrals.models import ReferralBonus
from wallets.models import LedgerTransaction
from wallets.services import get_wallet
from .models import MpesaTransaction
from .services import create_mpesa_transaction, process_successful_mpesa_transaction


User = get_user_model()


class MpesaActivationTests(TestCase):
    def setUp(self):
        self.referrer = User.objects.create_user(
            username="referrer",
            email="referrer@example.com",
            phone_number="254700000001",
            password="StrongPass123!",
        )
        self.user = User.objects.create_user(
            username="activateduser",
            email="activateduser@example.com",
            phone_number="254700000002",
            password="StrongPass123!",
            referred_by=self.referrer,
        )
        settings_obj = get_finance_settings()
        settings_obj.activation_fee = Decimal("185.00")
        settings_obj.activation_credit_mode = FinanceSettings.ActivationCreditMode.MIXED
        settings_obj.activation_withdrawable_amount = Decimal("50.00")
        settings_obj.referral_bonus_amount = Decimal("75.00")
        settings_obj.referral_bonus_release_delay_hours = 0
        settings_obj.save()

    def test_successful_activation_credits_wallet_and_referral_bonus(self):
        transaction = create_mpesa_transaction(
            user=self.user,
            amount="185.00",
            phone_number="0700000002",
            transaction_kind=MpesaTransaction.TransactionKind.ACTIVATION,
            payment_method=MpesaTransaction.PaymentMethod.STK_PUSH,
        )

        process_successful_mpesa_transaction(
            transaction=transaction,
            mpesa_receipt_number="RCP12345",
            paid_amount="185.00",
            phone_number="254700000002",
            raw_callback={"ok": True},
        )

        self.user.refresh_from_db()
        wallet = get_wallet(self.user)
        referrer_wallet = get_wallet(self.referrer)
        self.assertEqual(self.user.status, User.AccountStatus.ACTIVE)
        self.assertEqual(self.user.activation_status, User.ActivationStatus.ACTIVATED)
        self.assertEqual(wallet.available_balance, Decimal("50.00"))
        self.assertEqual(wallet.locked_balance, Decimal("135.00"))
        self.assertEqual(referrer_wallet.available_balance, Decimal("75.00"))
        self.assertEqual(ReferralBonus.objects.get().status, ReferralBonus.Status.CREDITED)

    def test_stk_callback_processes_success_payload_once(self):
        transaction = create_mpesa_transaction(
            user=self.user,
            amount="185.00",
            phone_number="0700000002",
            transaction_kind=MpesaTransaction.TransactionKind.ACTIVATION,
            payment_method=MpesaTransaction.PaymentMethod.STK_PUSH,
        )
        transaction.checkout_request_id = "checkout-123"
        transaction.status = MpesaTransaction.Status.PENDING
        transaction.save()
        payload = {
            "Body": {
                "stkCallback": {
                    "ResultCode": 0,
                    "ResultDesc": "Success",
                    "CheckoutRequestID": "checkout-123",
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "Amount", "Value": 185},
                            {"Name": "MpesaReceiptNumber", "Value": "RCPSTK1"},
                            {"Name": "PhoneNumber", "Value": 254700000002},
                        ]
                    },
                }
            }
        }

        response = self.client.post(
            reverse("mpesa_stk_callback"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        second_response = self.client.post(
            reverse("mpesa_stk_callback"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        transaction.refresh_from_db()
        self.assertEqual(transaction.status, MpesaTransaction.Status.SUCCESS)
        self.assertEqual(
            LedgerTransaction.objects.filter(transaction_type=LedgerTransaction.TransactionType.ACTIVATION_CREDIT).count(),
            2,
        )

    @patch("payments.views.initiate_transaction_stk_push")
    def test_activation_page_creates_transaction(self, mocked_stk):
        self.client.force_login(self.user)

        response = self.client.post(reverse("activation_page"), {"phone_number": "0700000002"})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(MpesaTransaction.objects.filter(transaction_kind=MpesaTransaction.TransactionKind.ACTIVATION).count(), 1)
        mocked_stk.assert_called_once()

    def test_activation_page_renders(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("activation_page"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pay activation fee")


class MpesaDepositTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="deposituser",
            email="deposituser@example.com",
            phone_number="254700000003",
            password="StrongPass123!",
        )

    def test_successful_deposit_credits_available_wallet(self):
        transaction = create_mpesa_transaction(
            user=self.user,
            amount="500.00",
            phone_number="0700000003",
            transaction_kind=MpesaTransaction.TransactionKind.DEPOSIT,
            payment_method=MpesaTransaction.PaymentMethod.C2B,
        )

        process_successful_mpesa_transaction(
            transaction=transaction,
            mpesa_receipt_number="RCPDEP1",
            paid_amount="500.00",
            phone_number="254700000003",
            raw_callback={"ok": True},
        )

        wallet = get_wallet(self.user)
        self.assertEqual(wallet.available_balance, Decimal("500.00"))

    def test_c2b_confirmation_can_create_deposit_from_account_reference(self):
        payload = {
            "TransID": "C2B001",
            "TransAmount": "300.00",
            "BillRefNumber": f"DEP{self.user.pk:06d}",
            "MSISDN": "254700000003",
        }

        response = self.client.post(
            reverse("mpesa_c2b_confirmation"),
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        wallet = get_wallet(self.user)
        self.assertEqual(wallet.available_balance, Decimal("300.00"))

    def test_deposit_page_renders(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("deposit_page"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Add money to your wallet")
