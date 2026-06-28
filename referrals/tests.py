from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.services import get_finance_settings
from payments.models import MpesaTransaction
from referrals.models import ReferralBonus
from referrals.services import create_referral_bonus_for_activation, release_due_referral_bonuses
from wallets.services import get_wallet


User = get_user_model()


class ReferralFlowTests(TestCase):
    def setUp(self):
        self.referrer = User.objects.create_user(
            username="referralowner",
            email="referralowner@example.com",
            phone_number="254701111111",
            password="StrongPass123!",
        )
        self.referred = User.objects.create_user(
            username="referredmember",
            email="referredmember@example.com",
            phone_number="254702222222",
            password="StrongPass123!",
            referred_by=self.referrer,
        )
        settings_obj = get_finance_settings()
        settings_obj.referral_bonus_amount = Decimal("60.00")
        settings_obj.referral_bonus_release_delay_hours = 24
        settings_obj.save()
        self.transaction = MpesaTransaction.objects.create(
            user=self.referred,
            transaction_kind=MpesaTransaction.TransactionKind.ACTIVATION,
            payment_method=MpesaTransaction.PaymentMethod.STK_PUSH,
            status=MpesaTransaction.Status.SUCCESS,
            amount="185.00",
            phone_number="254702222222",
            account_reference=f"ACT{self.referred.pk:06d}",
            mpesa_receipt_number="REFRCP1",
        )

    def test_referral_bonus_starts_pending(self):
        bonus = create_referral_bonus_for_activation(self.referred, self.transaction)

        self.assertEqual(bonus.status, ReferralBonus.Status.PENDING)
        self.assertEqual(bonus.amount, Decimal("60.00"))

    def test_release_due_referral_bonus_credits_referrer_wallet(self):
        bonus = create_referral_bonus_for_activation(self.referred, self.transaction)
        bonus.release_at = timezone.now() - timezone.timedelta(minutes=1)
        bonus.save(update_fields=["release_at"])

        released = release_due_referral_bonuses()

        wallet = get_wallet(self.referrer)
        bonus.refresh_from_db()
        self.assertEqual(released, 1)
        self.assertEqual(wallet.available_balance, Decimal("60.00"))
        self.assertEqual(bonus.status, ReferralBonus.Status.CREDITED)

    def test_referral_dashboard_renders(self):
        self.client.force_login(self.referrer)

        response = self.client.get(reverse("referral_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your referral code")
