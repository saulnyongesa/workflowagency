import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Wallet(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wallet")
    available_balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    pending_balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    locked_balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    total_earned = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    total_withdrawn = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(available_balance__gte=0)
                & Q(pending_balance__gte=0)
                & Q(locked_balance__gte=0)
                & Q(total_earned__gte=0)
                & Q(total_withdrawn__gte=0),
                name="wallet_balances_non_negative",
            )
        ]

    def __str__(self):
        return f"{self.user} wallet"

    @property
    def total_liability(self):
        return self.available_balance + self.pending_balance + self.locked_balance


class LedgerTransaction(models.Model):
    class TransactionType(models.TextChoices):
        DEPOSIT_CONFIRMED = "deposit_confirmed", "Deposit confirmed"
        ACTIVATION_CREDIT = "activation_credit", "Activation credit"
        REFERRAL_BONUS_PENDING = "referral_bonus_pending", "Referral bonus pending"
        REFERRAL_BONUS_AVAILABLE = "referral_bonus_available", "Referral bonus available"
        JOB_REWARD_PENDING = "job_reward_pending", "Job reward pending"
        JOB_REWARD_APPROVED = "job_reward_approved", "Job reward approved"
        PRODUCT_PURCHASE = "product_purchase", "Product purchase"
        PRODUCT_COMMISSION = "product_commission", "Product commission"
        WITHDRAWAL_REQUESTED = "withdrawal_requested", "Withdrawal requested"
        WITHDRAWAL_PAID = "withdrawal_paid", "Withdrawal paid"
        WITHDRAWAL_FAILED = "withdrawal_failed", "Withdrawal failed"
        ADMIN_ADJUSTMENT = "admin_adjustment", "Admin adjustment"
        FRAUD_HOLD = "fraud_hold", "Fraud hold"
        SYSTEM_REVERSAL = "system_reversal", "System reversal"

    class Direction(models.TextChoices):
        CREDIT = "credit", "Credit"
        DEBIT = "debit", "Debit"

    class BalanceBucket(models.TextChoices):
        AVAILABLE = "available", "Available"
        PENDING = "pending", "Pending"
        LOCKED = "locked", "Locked"

    class Status(models.TextChoices):
        POSTED = "posted", "Posted"
        REVERSED = "reversed", "Reversed"
        VOID = "void", "Void"

    public_reference = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name="ledger_transactions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ledger_transactions")
    transaction_type = models.CharField(max_length=40, choices=TransactionType.choices)
    direction = models.CharField(max_length=10, choices=Direction.choices)
    balance_bucket = models.CharField(max_length=20, choices=BalanceBucket.choices)
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.POSTED)
    description = models.CharField(max_length=255)
    idempotency_key = models.CharField(max_length=160, unique=True, null=True, blank=True)
    source_app = models.CharField(max_length=80, blank=True)
    source_model = models.CharField(max_length=120, blank=True)
    source_id = models.CharField(max_length=80, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_ledger_transactions",
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["transaction_type", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["source_app", "source_model", "source_id"]),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="ledger_amount_positive"),
        ]

    def __str__(self):
        return f"{self.get_transaction_type_display()} {self.amount} for {self.user}"


class WithdrawalRequest(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        APPROVED = "approved", "Approved"
        PROCESSING = "processing", "Processing"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="withdrawal_requests")
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    fee = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    net_amount = models.DecimalField(max_digits=14, decimal_places=2)
    phone_number = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED)
    request_debit_ledger = models.OneToOneField(
        LedgerTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="withdrawal_request_debit",
    )
    lock_credit_ledger = models.OneToOneField(
        LedgerTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="withdrawal_lock_credit",
    )
    paid_ledger = models.OneToOneField(
        LedgerTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="withdrawal_paid",
    )
    release_locked_ledger = models.OneToOneField(
        LedgerTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="withdrawal_release_locked",
    )
    release_available_ledger = models.OneToOneField(
        LedgerTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="withdrawal_release_available",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_withdrawals",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=255, blank=True)
    payout_reference = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["status", "-created_at"]),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="withdrawal_amount_positive"),
            models.CheckConstraint(condition=Q(fee__gte=0), name="withdrawal_fee_non_negative"),
            models.CheckConstraint(condition=Q(net_amount__gte=0), name="withdrawal_net_amount_non_negative"),
        ]

    def __str__(self):
        return f"{self.user} withdrawal {self.amount} ({self.status})"
