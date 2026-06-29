from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class FinanceSettings(TimeStampedModel):
    class ActivationCreditMode(models.TextChoices):
        PLATFORM_CREDIT = "platform_credit", "Platform credit"
        WITHDRAWABLE_BALANCE = "withdrawable_balance", "Withdrawable balance"
        MIXED = "mixed", "Mixed"

    class ReferralBonusType(models.TextChoices):
        FIXED = "fixed", "Fixed amount"
        PERCENT = "percent", "Percentage"

    singleton_id = models.PositiveSmallIntegerField(default=1, unique=True, editable=False)
    activation_fee = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("185.00"))
    activation_credit_mode = models.CharField(
        max_length=30,
        choices=ActivationCreditMode.choices,
        default=ActivationCreditMode.MIXED,
    )
    activation_withdrawable_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    referral_bonus_type = models.CharField(
        max_length=20,
        choices=ReferralBonusType.choices,
        default=ReferralBonusType.FIXED,
    )
    referral_bonus_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("75.00"))
    referral_bonus_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    referral_bonus_release_delay_hours = models.PositiveIntegerField(default=24)
    minimum_withdrawal_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("300.00"))
    maximum_daily_withdrawal_per_user = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("10000.00"))
    withdrawal_fee_fixed = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    withdrawal_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    reserve_ratio_target = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("1.10"))
    minimum_platform_cash_buffer = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    job_reward_release_delay_hours = models.PositiveIntegerField(default=0)
    job_claims_enabled = models.BooleanField(default=True)
    auto_approve_small_jobs = models.BooleanField(default=False)
    auto_approve_job_reward_limit = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    max_claims_per_user_per_day = models.PositiveIntegerField(default=10)
    max_ad_watch_rewards_per_day = models.PositiveIntegerField(default=20)
    deposit_enabled = models.BooleanField(default=True)
    payout_enabled = models.BooleanField(default=False)
    maintenance_mode = models.BooleanField(default=False)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_finance_settings",
    )

    class Meta:
        verbose_name = "finance settings"
        verbose_name_plural = "finance settings"

    def __str__(self):
        return "Finance settings"

    def clean(self):
        money_fields = [
            "activation_fee",
            "activation_withdrawable_amount",
            "referral_bonus_amount",
            "minimum_withdrawal_amount",
            "maximum_daily_withdrawal_per_user",
            "withdrawal_fee_fixed",
            "minimum_platform_cash_buffer",
            "auto_approve_job_reward_limit",
        ]
        for field_name in money_fields:
            if getattr(self, field_name) < 0:
                raise ValidationError({field_name: "Amount cannot be negative."})

        if self.activation_withdrawable_amount > self.activation_fee:
            raise ValidationError(
                {
                    "activation_withdrawable_amount": (
                        "Withdrawable activation credit cannot exceed the activation fee."
                    )
                }
            )
        if self.referral_bonus_percent < 0 or self.referral_bonus_percent > 100:
            raise ValidationError({"referral_bonus_percent": "Percent must be between 0 and 100."})
        if self.withdrawal_fee_percent < 0 or self.withdrawal_fee_percent > 100:
            raise ValidationError({"withdrawal_fee_percent": "Percent must be between 0 and 100."})
        if self.reserve_ratio_target < Decimal("1.00"):
            raise ValidationError({"reserve_ratio_target": "Reserve ratio should be at least 1.00."})

    def save(self, *args, **kwargs):
        self.singleton_id = 1
        self.full_clean()
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        settings_obj, _ = cls.objects.get_or_create(singleton_id=1)
        return settings_obj


class SiteSetting(TimeStampedModel):
    class ValueType(models.TextChoices):
        STRING = "string", "String"
        DECIMAL = "decimal", "Decimal"
        INTEGER = "integer", "Integer"
        BOOLEAN = "boolean", "Boolean"
        JSON = "json", "JSON"

    key = models.SlugField(max_length=120, unique=True)
    label = models.CharField(max_length=160)
    group = models.CharField(max_length=80, default="general")
    value_type = models.CharField(max_length=20, choices=ValueType.choices, default=ValueType.STRING)
    value = models.TextField(blank=True)
    description = models.TextField(blank=True)
    is_sensitive = models.BooleanField(default=False)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_site_settings",
    )

    class Meta:
        ordering = ["group", "key"]
        indexes = [
            models.Index(fields=["group", "key"]),
        ]

    def __str__(self):
        return self.label


class AuditLog(models.Model):
    class Action(models.TextChoices):
        CREATED = "created", "Created"
        UPDATED = "updated", "Updated"
        DELETED = "deleted", "Deleted"
        FINANCE_SETTING_CHANGED = "finance_setting_changed", "Finance setting changed"
        WALLET_ADJUSTED = "wallet_adjusted", "Wallet adjusted"
        WITHDRAWAL_REVIEWED = "withdrawal_reviewed", "Withdrawal reviewed"
        SYSTEM = "system", "System"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=40, choices=Action.choices)
    model_label = models.CharField(max_length=120, blank=True)
    object_id = models.CharField(max_length=80, blank=True)
    object_repr = models.CharField(max_length=240, blank=True)
    changes = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action", "-created_at"]),
            models.Index(fields=["model_label", "object_id"]),
        ]

    def __str__(self):
        return f"{self.get_action_display()} - {self.object_repr or self.model_label}"
