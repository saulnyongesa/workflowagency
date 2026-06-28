from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class ReferralBonus(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CREDITED = "credited", "Credited"
        REVERSED = "reversed", "Reversed"
        FLAGGED = "flagged", "Flagged"

    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="referral_bonuses",
    )
    referred_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="earned_referral_bonuses",
    )
    activation_transaction = models.OneToOneField(
        "payments.MpesaTransaction",
        on_delete=models.PROTECT,
        related_name="referral_bonus",
    )
    ledger_transaction = models.OneToOneField(
        "wallets.LedgerTransaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="referral_bonus",
    )
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    release_at = models.DateTimeField()
    credited_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["referrer", "status"]),
            models.Index(fields=["referred_user"]),
            models.Index(fields=["status", "release_at"]),
        ]

    def __str__(self):
        return f"{self.referrer} bonus for {self.referred_user}"
