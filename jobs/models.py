from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class JobCategory(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    icon = models.CharField(max_length=60, blank=True)
    color = models.CharField(max_length=20, default="#0b5fff")
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "job categories"

    def __str__(self):
        return self.name


class Job(models.Model):
    class JobType(models.TextChoices):
        SURVEY = "survey", "Survey"
        WATCH_AD = "watch_ad", "Watch and earn"
        TRIVIA = "trivia", "Trivia"
        BLOGGING = "blogging", "Blogging/social proof"
        APP_TESTING = "app_testing", "App/game testing"
        WEBSITE_FEEDBACK = "website_feedback", "Website feedback"
        DATA_ENTRY = "data_entry", "Data entry/tagging"
        TRANSCRIPTION = "transcription", "Transcription"
        TRANSLATION = "translation", "Translation"
        PRODUCT_REVIEW = "product_review", "Product review"
        CHAT_SESSION = "chat_session", "Paid chat session"
        PRODUCT_AFFILIATE = "product_affiliate", "Product affiliate"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        FULL = "full", "Full"
        PAUSED = "paused", "Paused"
        EXPIRED = "expired", "Expired"
        ARCHIVED = "archived", "Archived"

    class ReviewMode(models.TextChoices):
        MANUAL = "manual", "Manual review"
        AUTO = "auto", "Auto approve"

    class ProofType(models.TextChoices):
        NONE = "none", "No proof"
        TEXT = "text", "Text answer"
        URL = "url", "URL"
        FILE = "file", "File upload"
        TEXT_URL = "text_url", "Text and URL"

    category = models.ForeignKey(JobCategory, on_delete=models.PROTECT, related_name="jobs")
    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True)
    job_type = models.CharField(max_length=40, choices=JobType.choices, default=JobType.OTHER)
    description = models.TextField()
    instructions = models.TextField()
    reward_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    worker_limit = models.PositiveIntegerField(default=1)
    claims_count = models.PositiveIntegerField(default=0)
    approved_count = models.PositiveIntegerField(default=0)
    pending_count = models.PositiveIntegerField(default=0)
    rejected_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    review_mode = models.CharField(max_length=20, choices=ReviewMode.choices, default=ReviewMode.MANUAL)
    proof_type = models.CharField(max_length=20, choices=ProofType.choices, default=ProofType.TEXT)
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(null=True, blank=True)
    claim_expires_after_minutes = models.PositiveIntegerField(default=1440)
    max_claims_per_user = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_jobs",
    )
    cloned_from = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clones",
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "job_type"]),
            models.Index(fields=["category", "status"]),
            models.Index(fields=["starts_at", "ends_at"]),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(worker_limit__gte=1), name="job_worker_limit_positive"),
            models.CheckConstraint(condition=Q(reward_amount__gt=0), name="job_reward_positive"),
        ]

    def __str__(self):
        return self.title

    @property
    def available_slots(self):
        return max(self.worker_limit - self.claims_count, 0)

    @property
    def is_open(self):
        now = timezone.now()
        return (
            self.status == self.Status.PUBLISHED
            and self.starts_at <= now
            and (self.ends_at is None or self.ends_at >= now)
            and self.claims_count < self.worker_limit
        )


class JobClaim(models.Model):
    class Status(models.TextChoices):
        CLAIMED = "claimed", "Claimed"
        EXPIRED = "expired", "Expired"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    job = models.ForeignKey(Job, on_delete=models.PROTECT, related_name="claims")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="job_claims")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CLAIMED)
    claimed_at = models.DateTimeField(default=timezone.now, editable=False)
    expires_at = models.DateTimeField()
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-claimed_at"]
        constraints = [
            models.UniqueConstraint(fields=["job", "user"], name="one_claim_per_user_per_job"),
        ]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["job", "status"]),
        ]

    def __str__(self):
        return f"{self.user} claim for {self.job}"


class JobSubmission(models.Model):
    claim = models.OneToOneField(JobClaim, on_delete=models.PROTECT, related_name="submission")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="job_submissions")
    text_answer = models.TextField(blank=True)
    proof_url = models.URLField(blank=True)
    proof_file = models.FileField(upload_to="job-proof/%Y/%m/", blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=JobClaim.Status.choices, default=JobClaim.Status.SUBMITTED)
    ledger_transaction = models.OneToOneField(
        "wallets.LedgerTransaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="job_submission",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_job_submissions",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self):
        return f"Submission for {self.claim.job}"
