import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class MpesaTransaction(models.Model):
    class TransactionKind(models.TextChoices):
        ACTIVATION = "activation", "Activation"
        DEPOSIT = "deposit", "Deposit"

    class PaymentMethod(models.TextChoices):
        STK_PUSH = "stk_push", "STK Push"
        C2B = "c2b", "C2B PayBill"

    class Status(models.TextChoices):
        INITIATED = "initiated", "Initiated"
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        UNMATCHED = "unmatched", "Unmatched"

    public_reference = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mpesa_transactions",
    )
    transaction_kind = models.CharField(max_length=20, choices=TransactionKind.choices)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.INITIATED)
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("1.00"))],
    )
    phone_number = models.CharField(max_length=20)
    account_reference = models.CharField(max_length=40, db_index=True)
    merchant_request_id = models.CharField(max_length=80, unique=True, null=True, blank=True)
    checkout_request_id = models.CharField(max_length=80, unique=True, null=True, blank=True)
    mpesa_receipt_number = models.CharField(max_length=40, unique=True, null=True, blank=True)
    result_code = models.CharField(max_length=20, blank=True)
    result_description = models.CharField(max_length=255, blank=True)
    raw_request = models.JSONField(default=dict, blank=True)
    raw_callback = models.JSONField(default=dict, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["transaction_kind", "status"]),
            models.Index(fields=["account_reference", "status"]),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gte=1), name="mpesa_transaction_amount_minimum"),
        ]

    def __str__(self):
        return f"{self.get_transaction_kind_display()} {self.amount} ({self.status})"

    @property
    def is_successful(self):
        return self.status == self.Status.SUCCESS
