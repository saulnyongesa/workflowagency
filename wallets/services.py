from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from core.models import AuditLog
from core.services import create_audit_log, get_finance_settings
from .models import LedgerTransaction, Wallet, WithdrawalRequest


EARNING_TRANSACTION_TYPES = {
    LedgerTransaction.TransactionType.REFERRAL_BONUS_AVAILABLE,
    LedgerTransaction.TransactionType.JOB_REWARD_APPROVED,
    LedgerTransaction.TransactionType.PRODUCT_COMMISSION,
}


def money(value):
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def get_wallet(user):
    wallet, _ = Wallet.objects.get_or_create(user=user)
    return wallet


def _bucket_field(bucket):
    fields = {
        LedgerTransaction.BalanceBucket.AVAILABLE: "available_balance",
        LedgerTransaction.BalanceBucket.PENDING: "pending_balance",
        LedgerTransaction.BalanceBucket.LOCKED: "locked_balance",
    }
    return fields[bucket]


@transaction.atomic
def post_ledger_transaction(
    *,
    user,
    amount,
    transaction_type,
    direction,
    balance_bucket,
    description,
    idempotency_key=None,
    source_app="",
    source_model="",
    source_id="",
    metadata=None,
    created_by=None,
):
    amount = money(amount)
    if amount <= 0:
        raise ValidationError("Ledger amount must be greater than zero.")

    if idempotency_key:
        existing = LedgerTransaction.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return existing, False

    wallet = get_wallet(user)
    wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
    bucket_field = _bucket_field(balance_bucket)
    current_balance = getattr(wallet, bucket_field)

    if direction == LedgerTransaction.Direction.CREDIT:
        setattr(wallet, bucket_field, current_balance + amount)
        if transaction_type in EARNING_TRANSACTION_TYPES:
            wallet.total_earned += amount
    elif direction == LedgerTransaction.Direction.DEBIT:
        if current_balance < amount:
            raise ValidationError("Wallet balance is not enough for this debit.")
        setattr(wallet, bucket_field, current_balance - amount)
        if transaction_type == LedgerTransaction.TransactionType.WITHDRAWAL_PAID:
            wallet.total_withdrawn += amount
    else:
        raise ValidationError("Invalid ledger direction.")

    wallet.save()
    ledger = LedgerTransaction.objects.create(
        wallet=wallet,
        user=user,
        transaction_type=transaction_type,
        direction=direction,
        balance_bucket=balance_bucket,
        amount=amount,
        description=description,
        idempotency_key=idempotency_key,
        source_app=source_app,
        source_model=source_model,
        source_id=source_id,
        metadata=metadata or {},
        created_by=created_by,
    )
    return ledger, True


def post_admin_adjustment(*, user, amount, direction, balance_bucket, reason, admin_user, request=None):
    ledger, created = post_ledger_transaction(
        user=user,
        amount=amount,
        transaction_type=LedgerTransaction.TransactionType.ADMIN_ADJUSTMENT,
        direction=direction,
        balance_bucket=balance_bucket,
        description=reason,
        idempotency_key=None,
        source_app="wallets",
        source_model="admin_adjustment",
        source_id=str(user.pk),
        created_by=admin_user,
    )
    if created:
        create_audit_log(
            action=AuditLog.Action.WALLET_ADJUSTED,
            actor=admin_user,
            instance=ledger,
            changes={
                "user": str(user),
                "amount": str(ledger.amount),
                "direction": ledger.direction,
                "bucket": ledger.balance_bucket,
                "reason": reason,
            },
            request=request,
        )
    return ledger


def wallet_liability_summary():
    totals = Wallet.objects.aggregate(
        available=Sum("available_balance"),
        pending=Sum("pending_balance"),
        locked=Sum("locked_balance"),
    )
    available = totals["available"] or Decimal("0.00")
    pending = totals["pending"] or Decimal("0.00")
    locked = totals["locked"] or Decimal("0.00")
    return {
        "available": available,
        "pending": pending,
        "locked": locked,
        "total": available + pending + locked,
    }


def confirmed_cash_total():
    from payments.models import MpesaTransaction

    total = MpesaTransaction.objects.filter(status=MpesaTransaction.Status.SUCCESS).aggregate(total=Sum("amount"))[
        "total"
    ]
    return total or Decimal("0.00")


def calculate_withdrawal_fee(amount, settings_obj=None):
    settings_obj = settings_obj or get_finance_settings()
    amount = money(amount)
    percent_fee = (amount * settings_obj.withdrawal_fee_percent / Decimal("100")).quantize(Decimal("0.01"))
    return money(settings_obj.withdrawal_fee_fixed + percent_fee)


def withdrawal_solvency_snapshot(amount, fee=None, settings_obj=None):
    settings_obj = settings_obj or get_finance_settings()
    amount = money(amount)
    fee = calculate_withdrawal_fee(amount, settings_obj) if fee is None else money(fee)
    liabilities = wallet_liability_summary()
    confirmed_cash = confirmed_cash_total()
    cash_after_payout = confirmed_cash - amount - fee
    liability_after_payout = liabilities["total"] - amount
    required_cash_after_payout = (
        liability_after_payout * settings_obj.reserve_ratio_target
    ) + settings_obj.minimum_platform_cash_buffer
    return {
        "confirmed_cash": confirmed_cash,
        "liability_total": liabilities["total"],
        "cash_after_payout": cash_after_payout,
        "liability_after_payout": liability_after_payout,
        "required_cash_after_payout": required_cash_after_payout,
        "is_safe": cash_after_payout >= required_cash_after_payout,
    }


@transaction.atomic
def request_withdrawal(*, user, amount, phone_number):
    settings_obj = get_finance_settings()
    if not settings_obj.payout_enabled:
        raise ValidationError("Withdrawals are currently disabled.")
    if user.status != user.AccountStatus.ACTIVE:
        raise ValidationError("Your account must be active to request withdrawal.")
    amount = money(amount)
    if amount < settings_obj.minimum_withdrawal_amount:
        raise ValidationError("Amount is below the minimum withdrawal limit.")

    today_total = (
        WithdrawalRequest.objects.filter(user=user, created_at__date=timezone.localdate())
        .exclude(status__in=[WithdrawalRequest.Status.REJECTED, WithdrawalRequest.Status.CANCELLED])
        .aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )
    if today_total + amount > settings_obj.maximum_daily_withdrawal_per_user:
        raise ValidationError("This request exceeds your daily withdrawal limit.")

    wallet = get_wallet(user)
    wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
    if wallet.available_balance < amount:
        raise ValidationError("Available balance is not enough for this withdrawal.")

    fee = calculate_withdrawal_fee(amount, settings_obj)
    if fee >= amount:
        raise ValidationError("Withdrawal fee must be lower than the requested amount.")
    solvency = withdrawal_solvency_snapshot(amount, fee, settings_obj)
    if not solvency["is_safe"]:
        raise ValidationError("Withdrawal is temporarily unavailable because platform reserves are too low.")

    withdrawal = WithdrawalRequest.objects.create(
        user=user,
        amount=amount,
        fee=fee,
        net_amount=amount - fee,
        phone_number=phone_number,
    )
    debit, _ = post_ledger_transaction(
        user=user,
        amount=amount,
        transaction_type=LedgerTransaction.TransactionType.WITHDRAWAL_REQUESTED,
        direction=LedgerTransaction.Direction.DEBIT,
        balance_bucket=LedgerTransaction.BalanceBucket.AVAILABLE,
        description=f"Withdrawal request #{withdrawal.pk}",
        idempotency_key=f"withdrawal-request-debit-{withdrawal.pk}",
        source_app="wallets",
        source_model="WithdrawalRequest",
        source_id=str(withdrawal.pk),
    )
    lock, _ = post_ledger_transaction(
        user=user,
        amount=amount,
        transaction_type=LedgerTransaction.TransactionType.WITHDRAWAL_REQUESTED,
        direction=LedgerTransaction.Direction.CREDIT,
        balance_bucket=LedgerTransaction.BalanceBucket.LOCKED,
        description=f"Withdrawal funds locked #{withdrawal.pk}",
        idempotency_key=f"withdrawal-request-lock-{withdrawal.pk}",
        source_app="wallets",
        source_model="WithdrawalRequest",
        source_id=str(withdrawal.pk),
    )
    withdrawal.request_debit_ledger = debit
    withdrawal.lock_credit_ledger = lock
    withdrawal.save(update_fields=["request_debit_ledger", "lock_credit_ledger", "updated_at"])
    return withdrawal


def assert_withdrawal_safe(withdrawal):
    snapshot = withdrawal_solvency_snapshot(withdrawal.amount, withdrawal.fee)
    if not snapshot["is_safe"]:
        raise ValidationError("Withdrawal cannot be approved because platform reserves are too low.")
    return snapshot


@transaction.atomic
def approve_withdrawal(*, withdrawal, reviewer, request=None):
    withdrawal = WithdrawalRequest.objects.select_for_update().get(pk=withdrawal.pk)
    if withdrawal.status != WithdrawalRequest.Status.REQUESTED:
        raise ValidationError("Only requested withdrawals can be approved.")
    assert_withdrawal_safe(withdrawal)
    withdrawal.status = WithdrawalRequest.Status.APPROVED
    withdrawal.reviewed_by = reviewer
    withdrawal.reviewed_at = timezone.now()
    withdrawal.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])
    create_audit_log(
        action=AuditLog.Action.WITHDRAWAL_REVIEWED,
        actor=reviewer,
        instance=withdrawal,
        changes={"status": {"old": WithdrawalRequest.Status.REQUESTED, "new": WithdrawalRequest.Status.APPROVED}},
        request=request,
    )
    return withdrawal


@transaction.atomic
def mark_withdrawal_paid(*, withdrawal, reviewer, payout_reference="", request=None):
    withdrawal = WithdrawalRequest.objects.select_for_update().get(pk=withdrawal.pk)
    if withdrawal.status not in {WithdrawalRequest.Status.APPROVED, WithdrawalRequest.Status.PROCESSING}:
        raise ValidationError("Only approved withdrawals can be marked paid.")
    paid_ledger, _ = post_ledger_transaction(
        user=withdrawal.user,
        amount=withdrawal.amount,
        transaction_type=LedgerTransaction.TransactionType.WITHDRAWAL_PAID,
        direction=LedgerTransaction.Direction.DEBIT,
        balance_bucket=LedgerTransaction.BalanceBucket.LOCKED,
        description=f"Withdrawal paid #{withdrawal.pk}",
        idempotency_key=f"withdrawal-paid-{withdrawal.pk}",
        source_app="wallets",
        source_model="WithdrawalRequest",
        source_id=str(withdrawal.pk),
        created_by=reviewer,
    )
    old_status = withdrawal.status
    withdrawal.status = WithdrawalRequest.Status.PAID
    withdrawal.paid_ledger = paid_ledger
    withdrawal.reviewed_by = reviewer
    withdrawal.reviewed_at = withdrawal.reviewed_at or timezone.now()
    withdrawal.paid_at = timezone.now()
    withdrawal.payout_reference = payout_reference
    withdrawal.save(
        update_fields=[
            "status",
            "paid_ledger",
            "reviewed_by",
            "reviewed_at",
            "paid_at",
            "payout_reference",
            "updated_at",
        ]
    )
    create_audit_log(
        action=AuditLog.Action.WITHDRAWAL_REVIEWED,
        actor=reviewer,
        instance=withdrawal,
        changes={"status": {"old": old_status, "new": WithdrawalRequest.Status.PAID}},
        request=request,
    )
    return withdrawal


@transaction.atomic
def reject_withdrawal(*, withdrawal, reviewer, reason, request=None):
    withdrawal = WithdrawalRequest.objects.select_for_update().get(pk=withdrawal.pk)
    if withdrawal.status not in {WithdrawalRequest.Status.REQUESTED, WithdrawalRequest.Status.APPROVED}:
        raise ValidationError("This withdrawal cannot be rejected.")
    if not reason.strip():
        raise ValidationError("Rejection reason is required.")
    old_status = withdrawal.status
    locked_debit, _ = post_ledger_transaction(
        user=withdrawal.user,
        amount=withdrawal.amount,
        transaction_type=LedgerTransaction.TransactionType.WITHDRAWAL_FAILED,
        direction=LedgerTransaction.Direction.DEBIT,
        balance_bucket=LedgerTransaction.BalanceBucket.LOCKED,
        description=f"Withdrawal released #{withdrawal.pk}",
        idempotency_key=f"withdrawal-release-locked-{withdrawal.pk}",
        source_app="wallets",
        source_model="WithdrawalRequest",
        source_id=str(withdrawal.pk),
        created_by=reviewer,
    )
    available_credit, _ = post_ledger_transaction(
        user=withdrawal.user,
        amount=withdrawal.amount,
        transaction_type=LedgerTransaction.TransactionType.WITHDRAWAL_FAILED,
        direction=LedgerTransaction.Direction.CREDIT,
        balance_bucket=LedgerTransaction.BalanceBucket.AVAILABLE,
        description=f"Withdrawal returned #{withdrawal.pk}",
        idempotency_key=f"withdrawal-release-available-{withdrawal.pk}",
        source_app="wallets",
        source_model="WithdrawalRequest",
        source_id=str(withdrawal.pk),
        created_by=reviewer,
    )
    withdrawal.status = WithdrawalRequest.Status.REJECTED
    withdrawal.release_locked_ledger = locked_debit
    withdrawal.release_available_ledger = available_credit
    withdrawal.reviewed_by = reviewer
    withdrawal.reviewed_at = timezone.now()
    withdrawal.rejection_reason = reason.strip()
    withdrawal.save(
        update_fields=[
            "status",
            "release_locked_ledger",
            "release_available_ledger",
            "reviewed_by",
            "reviewed_at",
            "rejection_reason",
            "updated_at",
        ]
    )
    create_audit_log(
        action=AuditLog.Action.WITHDRAWAL_REVIEWED,
        actor=reviewer,
        instance=withdrawal,
        changes={"status": {"old": old_status, "new": WithdrawalRequest.Status.REJECTED}, "reason": reason},
        request=request,
    )
    return withdrawal
