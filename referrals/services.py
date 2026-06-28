from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from core.services import get_finance_settings
from wallets.models import LedgerTransaction
from wallets.services import post_ledger_transaction
from .models import ReferralBonus


def referral_bonus_amount(settings_obj):
    if settings_obj.referral_bonus_type == settings_obj.ReferralBonusType.PERCENT:
        return (settings_obj.activation_fee * settings_obj.referral_bonus_percent / Decimal("100")).quantize(
            Decimal("0.01")
        )
    return settings_obj.referral_bonus_amount


@transaction.atomic
def create_referral_bonus_for_activation(referred_user, activation_transaction):
    referrer = referred_user.referred_by
    if not referrer or referrer == referred_user:
        return None

    existing = ReferralBonus.objects.filter(activation_transaction=activation_transaction).first()
    if existing:
        return existing

    settings_obj = get_finance_settings()
    amount = referral_bonus_amount(settings_obj)
    if amount <= 0:
        return None

    release_at = timezone.now() + timezone.timedelta(hours=settings_obj.referral_bonus_release_delay_hours)
    bonus = ReferralBonus.objects.create(
        referrer=referrer,
        referred_user=referred_user,
        activation_transaction=activation_transaction,
        amount=amount,
        release_at=release_at,
    )
    if bonus.release_at <= timezone.now():
        release_referral_bonus(bonus)
        bonus.refresh_from_db()
    return bonus


@transaction.atomic
def release_referral_bonus(bonus):
    bonus = ReferralBonus.objects.select_for_update().get(pk=bonus.pk)
    if bonus.status != ReferralBonus.Status.PENDING:
        return bonus, False
    if bonus.release_at > timezone.now():
        return bonus, False

    ledger, _ = post_ledger_transaction(
        user=bonus.referrer,
        amount=bonus.amount,
        transaction_type=LedgerTransaction.TransactionType.REFERRAL_BONUS_AVAILABLE,
        direction=LedgerTransaction.Direction.CREDIT,
        balance_bucket=LedgerTransaction.BalanceBucket.AVAILABLE,
        description=f"Referral bonus for {bonus.referred_user.username} activation",
        idempotency_key=f"referral-bonus-{bonus.pk}",
        source_app="referrals",
        source_model="ReferralBonus",
        source_id=str(bonus.pk),
    )
    bonus.ledger_transaction = ledger
    bonus.status = ReferralBonus.Status.CREDITED
    bonus.credited_at = timezone.now()
    bonus.save(update_fields=["ledger_transaction", "status", "credited_at", "updated_at"])
    return bonus, True


def release_due_referral_bonuses():
    released = 0
    due_bonuses = ReferralBonus.objects.filter(status=ReferralBonus.Status.PENDING, release_at__lte=timezone.now())
    for bonus in due_bonuses:
        _, did_release = release_referral_bonus(bonus)
        if did_release:
            released += 1
    return released
