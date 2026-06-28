import uuid

from django.contrib.auth.models import AbstractUser
from django.db import IntegrityError
from django.db import models
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    class AccountStatus(models.TextChoices):
        LOCKED = "locked", _("Locked")
        ACTIVE = "active", _("Active")
        FLAGGED = "flagged", _("Flagged")
        SUSPENDED = "suspended", _("Suspended")

    class ActivationStatus(models.TextChoices):
        NOT_ACTIVATED = "not_activated", _("Not activated")
        PAYMENT_PENDING = "payment_pending", _("Payment pending")
        ACTIVATED = "activated", _("Activated")
        ACTIVATION_REVERSED = "activation_reversed", _("Activation reversed")

    class KycStatus(models.TextChoices):
        NOT_REQUIRED = "not_required", _("Not required")
        PENDING = "pending", _("Pending")
        VERIFIED = "verified", _("Verified")
        REJECTED = "rejected", _("Rejected")

    email = models.EmailField(_("email address"), unique=True)
    phone_number = models.CharField(max_length=20, unique=True, blank=True, null=True)
    country = models.CharField(max_length=80, default="Kenya")
    referral_code = models.CharField(max_length=20, unique=True, blank=True)
    referred_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="direct_referrals",
    )
    status = models.CharField(
        max_length=20,
        choices=AccountStatus.choices,
        default=AccountStatus.LOCKED,
    )
    activation_status = models.CharField(
        max_length=30,
        choices=ActivationStatus.choices,
        default=ActivationStatus.NOT_ACTIVATED,
    )
    kyc_status = models.CharField(
        max_length=20,
        choices=KycStatus.choices,
        default=KycStatus.NOT_REQUIRED,
    )
    phone_verified_at = models.DateTimeField(null=True, blank=True)

    REQUIRED_FIELDS = ["email"]

    class Meta:
        indexes = [
            models.Index(fields=["phone_number"]),
            models.Index(fields=["referral_code"]),
            models.Index(fields=["status", "activation_status"]),
        ]

    def save(self, *args, **kwargs):
        if self.phone_number:
            self.phone_number = self.normalize_phone_number(self.phone_number)
        if not self.referral_code:
            self.referral_code = self.build_unique_referral_code()
        super().save(*args, **kwargs)

    @staticmethod
    def normalize_phone_number(phone_number):
        cleaned = "".join(char for char in phone_number if char.isdigit())
        if cleaned.startswith("0") and len(cleaned) == 10:
            return f"254{cleaned[1:]}"
        if cleaned.startswith("7") and len(cleaned) == 9:
            return f"254{cleaned}"
        return cleaned

    def build_referral_code(self):
        base = (self.username or self.email or "user").upper()
        base = "".join(char for char in base if char.isalnum())[:6] or "USER"
        suffix = uuid.uuid4().hex[:6].upper()
        return f"{base}{suffix}"[:20]

    def build_unique_referral_code(self):
        for _ in range(10):
            code = self.build_referral_code()
            exists = User.objects.filter(referral_code=code)
            if self.pk:
                exists = exists.exclude(pk=self.pk)
            if not exists.exists():
                return code
        raise IntegrityError("Could not generate a unique referral code.")

# Create your models here.
